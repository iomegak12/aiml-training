# Multi-Agent RAG Architecture

This document explains how the multi-agent assistant answers a business question. It builds on the Pre-RAG
stores described in [pre_rag_architecture.md](pre_rag_architecture.md).

- A **LangGraph Coordinator** plans the work and dispatches **five specialist Deep Agents** in parallel.
- It reflects on their reports and writes the answer.
- A **judge LLM** gates the answer.
- Customer and ticket data come from a **FastMCP server** running in Docker.

## 1. System context

```mermaid
flowchart LR
    user([Business user<br/>notebook / app]) --> svc[CoordinatorService<br/>ask / resume]
    svc --> coord[Coordinator graph<br/>LangGraph StateGraph]

    subgraph team[Specialist Deep Agents]
        hr[HR Policy]
        prod[Product Manuals]
        cs[Customer Support]
        tm[Ticket Management]
        rs[Research]
    end

    coord -- Send, in parallel --> team
    hr --> hrdb[(Chroma<br/>hr_policies)]
    prod --> pdb[(Chroma<br/>product_manuals)]
    cs -- MCP read tools --> mcp
    tm -- MCP read tools --> mcp
    coord -- approved writes only --> mcp
    rs --> serper[[Serper web search]]

    subgraph docker[Docker - 127.0.0.1 only]
        mcp[CRM and Support<br/>FastMCP server] --> crmdb[(SQLite<br/>crm_support.db)]
    end

    coord --> judge{{Judge LLM<br/>JUDGE_OPENAI_MODEL}}
    coord <--> mem[(SQLite<br/>checkpoints + long-term store)]
    skills[/src/skills/] -. mounted read-only .-> team
    skills -. coordination skill .-> coord
```

| Component | Technology | Responsibility |
|---|---|---|
| Coordinator | LangGraph `StateGraph`, `OPENAI_MODEL` at `COORDINATOR_REASONING_EFFORT=high` | Plan, clarify, dispatch, reflect, approval, synthesis, judge loop, memory |
| Specialists | Deep Agents `create_deep_agent`, `SPECIALIST_REASONING_EFFORT=low` | Do one well-scoped task with their own tools and skills; return an `AgentReport` |
| RAG tools | `src/agentic_rag/rag` | Hybrid, advanced, multi-query and corrective pipelines over the two Chroma stores |
| CRM & Support | FastMCP 4 (streamable HTTP), SQLite, Docker | Customer profiles, tickets, resources, prompts and business rules |
| Judge | `JUDGE_OPENAI_MODEL` with its own key | Scores the final answer; below `JUDGE_PASS_SCORE` triggers a targeted retry |
| Memory | `AsyncSqliteSaver` and `AsyncSqliteStore` | Thread state (follow-ups, interrupts) and per-user facts |

## 2. The Coordinator graph

The diagram below is generated from the compiled graph by `make graph-diagram`
([coordinator_graph.mmd](../diagrams/coordinator_graph.mmd)). Dotted edges are conditional.

```mermaid
flowchart TD
    start([START]) --> start_turn --> load_memory --> plan
    plan -. needs a detail nobody can look up .-> clarify
    clarify -- interrupt, then resume --> plan
    plan -. "Send x N (ready steps)" .-> run_step
    plan -. no specialist work needed .-> synthesize
    plan -. proposals waiting .-> approve_actions
    run_step --> reflect
    reflect -. "more ready steps (Send)" .-> run_step
    reflect -. "gaps (max MAX_REPLANS)" .-> plan
    reflect -. "ticket writes proposed" .-> approve_actions
    reflect -. done .-> synthesize
    approve_actions -- interrupt, then resume --> execute_actions --> synthesize
    synthesize --> judge
    judge -. "score below JUDGE_PASS_SCORE<br/>and retries left" .-> plan
    judge -. "pass, or retries used up" .-> finalize
    finalize --> save_memory --> stop([END])
```

| Node | Model | What it does |
|---|---|---|
| `start_turn` | none | Reads the question from the last message and resets per-turn fields; keeps a short conversation window |
| `load_memory` | none | Recalls the user's long-term facts from the store |
| `plan` | coordinator (high) | Returns a structured `Plan` (steps with agent, goal, `depends_on`, success criteria) or a clarifying question; on replans and retries it targets only the gaps or the judge's critique |
| `clarify` | none | `interrupt()` with the question; the user's answer resumes the thread |
| `run_step` | specialist (low) | Runs one specialist; parallel branches append reports through an accumulate reducer |
| `reflect` | coordinator (high) | Continues with dependent steps, replans for important gaps, or moves on |
| `approve_actions` | none | `interrupt()` listing proposed ticket writes; approve, reject or edit each one |
| `execute_actions` | none | Calls the MCP `register_ticket` / `resolve_ticket` tools; results become evidence |
| `synthesize` | coordinator (high) | Writes the answer from reports and numbered evidence `[E#]` |
| `judge` | judge | Scores 4 criteria and the weighted overall; stores the critique and targets |
| `finalize` | none | Picks the passing (or best) attempt; adds a low-confidence notice if none passed |
| `save_memory` | fast | Extracts durable user facts and stores them under `("users", user_id, "facts")` |

**Budgets:**
- `MAX_AGENT_CALLS` caps specialist runs per question.
- `MAX_REPLANS` caps reflection replans per attempt.
- `JUDGE_MAX_RETRIES` caps judge-driven retries.
- Up to two clarifying questions per turn.

## 3. Plan, parallel dispatch, reflect and the judge loop

```mermaid
sequenceDiagram
    autonumber
    participant U as User
    participant C as Coordinator (graph)
    participant CS as Customer Support
    participant PM as Product Manuals
    participant TM as Ticket Management
    participant J as Judge LLM

    U->>C: "Ananya's TV shows E-715 - meaning, fix, existing ticket?"
    C->>C: plan (high effort): s1 customer, s2 manual and s3 tickets both depend on s1
    C->>CS: run_step s1
    CS-->>C: AgentReport (CUST-0001, Lumina 55 Pro)
    C->>C: reflect: s2 and s3 are ready
    par Send s2
        C->>PM: run_step s2 (model pinned: Lumina 55 Pro)
        PM-->>C: AgentReport (E-715 = HDMI 2.1 FRL link training failed)
    and Send s3
        C->>TM: run_step s3
        TM-->>C: AgentReport (TKT-000119 open, high)
    end
    C->>C: reflect: enough evidence, synthesize
    C->>C: synthesize with [E1..En] citations
    C->>J: question + answer + evidence
    alt overall below JUDGE_PASS_SCORE and retries left
        J-->>C: critique + targets (e.g. product_manuals, synthesis)
        C->>C: plan again for the weak parts only
    else pass, or retries used up
        J-->>C: scores
        C-->>U: answer (+ low-confidence notice if never passed)
    end
```

## 4. Ticket writes: propose, approve, execute

The Ticket Management agent has **only read tools**. Write tools stay in the graph, so no write happens without a
human decision, and an interrupt never fires inside a parallel specialist.

```mermaid
sequenceDiagram
    autonumber
    participant U as Support executive
    participant C as Coordinator (graph)
    participant TM as Ticket Management agent
    participant M as CRM and Support MCP server
    participant DB as SQLite

    C->>TM: "raise a ticket for Kavya's charging issue"
    TM->>M: get_tickets_by_customer(CUST-0003, open)
    M->>DB: SELECT ...
    M-->>TM: open tickets (duplicate check)
    TM-->>C: AgentReport + proposed_actions [register_ticket(...)]
    C-->>U: interrupt {type: approval, actions: [...]}
    Note over C: state saved in the checkpointer - the process may even restart
    U->>C: resume("approve") or {decisions: [{id, decision: edit, arguments}]}
    C->>M: register_ticket(customer_id, title, description, priority, product_model)
    M->>M: business rules: active customer, enums, duplicate guard
    M->>DB: INSERT ticket
    M-->>C: {created: true, ticket: TKT-000121}
    C->>C: evidence kind=action, then synthesize and judge
    C-->>U: answer citing TKT-000121
```

## 5. RAG pipelines (tools of the HR Policy and Product Manuals agents)

```mermaid
flowchart LR
    q[question] --> h1 & a1 & m1 & c1

    subgraph hybrid[hybrid_search]
        h1[infer filter<br/>model / doc_id / version] --> h2[vector + BM25] --> h3[RRF fusion]
    end

    subgraph advanced[advanced_search]
        a1[LLM rewrite<br/>+ filters] --> a2[current versions only<br/>unless asked] --> a3[hybrid, 20 candidates] --> a4[LLM rerank 0-10] --> a5[budgeted context<br/>reading order] --> a6[cited answer]
    end

    subgraph multi[multi_query_search]
        m1[decompose into<br/>sub-questions] --> m2[hybrid per sub-question<br/>in parallel] --> m3[RRF across lists<br/>top 2 each kept] --> m4[cited answer]
    end

    subgraph corrective[corrective_search]
        c1[advanced retrieval] --> c2{grade relevant?}
        c2 -- too few --> c3[broaden: no filters, MMR] --> c4{still nothing?}
        c4 -- yes --> c5[try the other store] --> c6{relevant?}
        c6 -- no --> idk[I don't know]
        c2 -- enough --> c7[answer]
        c4 -- no --> c7
        c6 -- yes --> c7
        c7 --> c8{grounded?} -- no --> c9[regenerate without<br/>unsupported statements]
    end
```

| Pipeline | LLM calls | Best for |
|---|---|---|
| `hybrid_search` | 0 (retrieval only) | Error codes, model numbers, policy IDs, fast lookups |
| `advanced_search` | rewrite, rerank, answer | Most questions; version-aware |
| `multi_query_search` | decompose, answer | Compound questions |
| `corrective_search` | rewrite, rerank, grade (1-3), answer, groundedness (1-2) | Unsure coverage; must not guess |

## 6. Skills: one source, three consumers

```mermaid
flowchart LR
    src[/src/skills - source of truth/] -- make sync-skills --> claude[/.claude/skills/]
    src -- make sync-skills --> agents[/.agents/skills/]
    claude --> cc[Claude Code]
    claude --> gh[GitHub Copilot]
    agents --> cx[OpenAI Codex]
    agents --> gh
    src -- "CompositeBackend route<br/>/skill-name/ (read-only)" --> da[Deep Agents specialists]
    src -- coordination skill body --> planner[Coordinator plan prompt]
    check[make check-skills] -. drift + frontmatter check .-> claude & agents
```

| Skill | Used by | Contents |
|---|---|---|
| `hr-policies` | HR Policy agent | Tool choice, version rules, policy catalogue; `scripts/search.py` |
| `product-support` | Product Manuals agent | Model pinning, model table, error-code handling; `scripts/search.py` |
| `rag-answering` | HR and Product agents | Search discipline, evidence quotes, "I don't know", confidence |
| `customer-support` | Customer Support agent | Identity resolution, what to report, inactive customers |
| `ticket-management` | Ticket Management agent | Server rules, duplicate guard, priority guide, proposing writes |
| `web-research` | Research agent | When to search, source quality, URL and date evidence |
| `coordination` | Coordinator (plan prompt) | Ownership table, planning, clarification and replanning rules |

## 7. Memory and state

| Kind | Where | Key | Lifetime | Used for |
|---|---|---|---|---|
| Short-term | `data/agent_state/checkpoints.sqlite` | `thread_id` | Per conversation | Follow-ups, clarification and approval interrupts, resuming after a restart |
| Long-term | `data/agent_state/long_term_memory.sqlite` | `("users", user_id, "facts")` | Across conversations | Customer ID, products owned, preferences, tickets raised |
| Specialist | in-memory Deep Agent state | per run | One step | Tool outputs and scratch files, isolated from the Coordinator |

`make clean-agent-state` deletes both SQLite files, and `service.forget(user_id)` deletes one user's facts.

## 8. Context engineering

- **Isolation:** each specialist reads raw tool output. The Coordinator sees only compact reports (findings,
  evidence quotes, confidence and gaps), usually a few hundred tokens instead of thousands.
- **Budgets:** `build_context` keeps the most relevant chunks within a token budget, then orders them for
  reading (document, page, position).
- **Compression:** Coordinator prompts use digests, the last six conversation messages (truncated) and one-line
  long-term facts. Deep Agents summarise long specialist histories automatically.

Notebook 11 measures all three.
