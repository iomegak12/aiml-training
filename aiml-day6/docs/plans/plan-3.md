# Plan: Multi-Agent RAG with LangGraph, Specialist Deep Agents, a CRM/Ticket MCP Server, Judge Gate and Memory (aiml-day6)

## Context
The corpus (30 PDFs) and two Chroma stores (`hr_policies`, `product_manuals`) exist. The next teaching module answers business questions with a **team of specialised agents coordinated by a LangGraph workflow** instead of one all-in-one agent:
- **Coordinator:** plans, dispatches, reflects and synthesises at **high reasoning effort**.
- **HR Policy agent.**
- **Product Manuals agent.**
- **Customer Support agent:** customer profiles.
- **Ticket Management agent:** support tickets.
- **Research agent:** Serper web search.

The module demonstrates:
- **RAG patterns:** hybrid, advanced, multi-query, corrective, and agentic (the graph itself).
- **Skills:** domain skills that are reusable in Claude Code, Codex and Copilot.
- **A CRM and ticket MCP server:** FastMCP, Docker, SQLite.
- **A judge gate:** retries driven by the judge's critique.
- **Interrupts:** human approval and clarification.
- **Memory:** short-term and long-term.

### Decisions agreed in the MCQ rounds
- **Topology:** a custom LangGraph **plan → parallel dispatch (Send) → specialists → reflect (replan up to MAX_REPLANS) → synthesize → judge (retries back to plan with the critique)**.
- **Specialists:** each is a **Deep Agent** (`create_deep_agent`) with only its own tools and skills, invoked from a graph node.
- **Responsibilities:**
  - Customer Support covers profiles (read-only).
  - Ticket Management covers ticket history, search, register and resolve (writes need approval).
  - A separate **Research agent** owns web search.
- **Planning:** the Coordinator uses `OPENAI_MODEL` at `COORDINATOR_REASONING_EFFORT=high` with a structured plan, bounded by `MAX_REPLANS` and `MAX_AGENT_CALLS`. Specialists run at low effort.
- **RAG patterns:** pipelines are **tools of the HR and Product agents**, and skills guide which one to use.
- **Judge:** it scores the **final answer only**. Below `JUDGE_PASS_SCORE`, its critique goes back to planning, which targets only the weak parts. Retries are capped at `JUDGE_MAX_RETRIES`, after which the best attempt is returned with a low-confidence warning.
- **Contract:** specialists return a structured **AgentReport**.
- **Memory:** one SQLite checkpointer on the parent graph (short-term, `thread_id`). **Long-term memory is owned by the Coordinator** in a SQLite store, per `user_id`.
- **Skills:** per-agent skill sets, 7 in total. `make sync-skills` mirrors them to `.claude/skills` and `.agents/skills`, with a drift check.
- **Clarification:** the Coordinator may **interrupt to ask a clarifying question**.
- **Notebooks:** **scenario-based**, delivered without outputs.
- **MCP server:**
  - FastMCP in `src/mcp_servers/crm_support/`.
  - **No authentication**; the port is published on localhost only.
  - Streamable HTTP; SQLite (configurable).
  - Resources, prompts, business rules and a rich seed.
  - A coloured banner.
  - Docker Compose through `make mcp-server-up` and `make mcp-server-down`, with a slim multi-stage `python:3.12-slim` + uv image and no HEALTHCHECK.
- **Out of scope:** no CLI chat or API, and no LangSmith. Batch evaluation is sampled.

## Requirements traceability (original request in `docs/prompts/prompt-3.txt`, plus later changes)
| Requirement | Where it is delivered |
|---|---|
| Hybrid search: similarity, semantic, keyword and metadata filters | `retrieval/vector.py` (similarity and MMR), `retrieval/keyword.py` (BM25), `retrieval/hybrid.py` (RRF), `retrieval/filters.py` |
| Advanced search: rephrase, rerank, best order, prepare context | `rag/advanced.py` with `rag/steps.py` (rewrite, rerank) and `rag/context.py` |
| Multi-query RAG: sub-questions, searched separately, then combined | `rag/multi_query.py`, and Coordinator plans that fan out in parallel with `Send` |
| Corrective RAG: relevance check, rephrase or another source, admit unknown, statement-level support check | `rag/corrective.py` (grade, re-route, groundedness self-check, "I don't know") |
| Agentic RAG: decides whether, where and when to search again (policy library → CRM → support history) | The Coordinator graph (plan, dispatch, reflect and replan) over the HR, Product, Customer Support, Ticket and Research agents |
| Domain skills that pick the vector store(s) | `src/skills/hr-policies`, `product-support` (+5 more), assigned per specialist |
| Current trends through Serper (`SERPER_API_KEY`) | `web/serper.py` and the Research agent with the `web-research` skill |
| Judge LLM (`JUDGE_OPENAI_MODEL` and `JUDGE_OPENAI_API_KEY`) gates the answer, retrying below 80% up to 3 times (`.env`) | `evaluation/judge.py` and the graph `judge` node, using `JUDGE_PASS_SCORE` and `JUDGE_MAX_RETRIES` |
| Short-term and long-term memory | SQLite checkpointer (`thread_id`) and Coordinator-owned SQLite store (`user_id`) |
| Context engineering: compression and summarisation | Deep Agents summarisation and offloading in the specialists, `rag/context.py` token budgets, isolated specialist contexts, compact AgentReports, notebook 11 |
| Modular code in `src/` | `src/agentic_rag/…`, `src/mcp_servers/crm_support/…`, `src/skills/` |
| Notebooks with use cases and runs only | `notebooks/01…12` (scenario-based, no outputs) |
| README, TROUBLESHOOTING and related files updated | See "Other changes" |
| Skills kept in `src/skills` and reusable in Claude Code, Codex and Copilot | `src/skills` is the source of truth; `make sync-skills` mirrors to `.claude/skills` and `.agents/skills`, and `make check-skills` detects drift |
| CRM and ticket MCP server (FastMCP, SQLite, Docker, colourful console, no auth) | Part A |
| Specialised agents plus a Coordinator, orchestrated by LangGraph with deliberate planning | Parts C and D |

## Part A: CRM and Support MCP server (`src/mcp_servers/crm_support/`)
This part is unchanged from the previous review. The package is `mcp_servers.crm_support`; it never imports LangChain or the agent code, so the image stays slim.

| Module | Responsibility |
|---|---|
| `config.py` | `CRM_DB_PATH` (default `data/crm/crm_support.db`), `MCP_HOST`, `MCP_PORT` (8765), `MCP_PATH` (`/mcp`), `CRM_SEED_ON_START`, `MCP_LOG_LEVEL`. |
| `models.py` | **Customer:** `customer_id` (`CUST-0001`), `full_name`, `communication_address`, `email`, `phone_number`, `credit_limit`, `active_status`, `remarks`, `created_at`, `updated_at`. **Ticket:** `ticket_id` (`TKT-000001`), `title`, `description`, `raised_by`, `product_model` (optional), `status` (`open`, `in_progress`, `resolved` or `closed`), `priority` (`low`, `medium`, `high` or `critical`), `resolved_by`, `resolution_date`, `resolution_remarks`, `created_at`, `updated_at`. |
| `db.py` | `sqlite3` repository: foreign key and indexes, parameterised `LIKE … COLLATE NOCASE` partial matching (wildcards escaped), paging (default 20, maximum 100). |
| `rules.py` | Inactive customers can't raise tickets; only open or in-progress tickets can be resolved (requires `resolved_by` and remarks, sets `resolution_date`); enum validation lists the allowed values; the duplicate guard (similar open title from the same customer) returns the existing ID. |
| `tools.py` | `get_customer_profile`, `search_customer_profiles`, `get_tickets_by_customer`, `register_ticket`, `search_tickets` and `resolve_ticket`, with docstrings and read-only / destructive annotations. No customer create, update or delete. |
| `resources.py` | `crm://customers/{customer_id}`, `crm://customers/{customer_id}/tickets`, `tickets://{ticket_id}`, `crm://schema` and `tickets://stats`, all JSON and read-only. |
| `prompts.py` | `triage_ticket(ticket_id)` and `customer_360_summary(customer_id)`. |
| `seed.py` and `seed/seed_data.json` | About 40 fictional customers and 120 tickets referencing the corpus models and error codes. `scripts/build_crm_seed.py` builds the JSON from `data_generation.catalog`. The database is seeded on first start when empty. |
| `banner.py` | A coloured `rich` startup panel: endpoint, transport, database path and counts, the tools, resources and prompts, seed status, and "Auth: DISABLED (localhost only)". |
| `server.py` and `__main__.py` | `FastMCP("crm-support")` over HTTP at `/mcp`, plus a `/health` route used by `make mcp-server-status`. |

**Packaging:**
- **`Dockerfile`:** builder `ghcr.io/astral-sh/uv` runs `uv sync --frozen --only-group crm-mcp --no-install-project`; runtime `python:3.12-slim` contains the venv and `src/mcp_servers` only, runs as non-root, and has no HEALTHCHECK.
- **`docker-compose.yml`:** service `crm-mcp` with `127.0.0.1:${MCP_PORT}:8765`, `./data/crm:/app/data`, `tty: true` and `FORCE_COLOR=1`.
- **`.dockerignore`.**
- **uv group:** `crm-mcp = ["fastmcp>=4.1"]`.
- **Make targets:** `mcp-server-up`, `mcp-server-down`, `mcp-server-logs`, `mcp-server-status`, `mcp-seed-reset` and `crm-seed`.

## Part B: shared building blocks (`src/agentic_rag/`)
| Module | Responsibility |
|---|---|
| `config.py` | `AgentSettings.load(root)`: all models and efforts, keys, judge thresholds, retrieval knobs, Serper settings, state paths, MCP URL, graph budgets. Reuses `data_ingestion.config.IngestionSettings`. |
| `llm.py` | `coordinator_llm()` (high effort), `specialist_llm()`, `fast_llm()` and `judge_llm()` (own key), plus a structured-output helper. |
| `retrieval/` | `RetrievedChunk`, `MetadataFilter`; stores (reuses `data_ingestion.vectorstore.open_store` and `data_ingestion.embeddings.make_embeddings`); filters to Chroma `where`; vector (similarity and MMR); `BM25Index`; `hybrid_search` with RRF. |
| `web/serper.py` | Serper Google search over httpx, returning `WebResult`. |
| `rag/` | `steps.py` (rewrite, decompose, grade, rerank on the fast model), `context.py`, `answer.py`, `result.py`, and the pipelines `hybrid_rag`, `advanced`, `multi_query` and `corrective`. |
| `evaluation/judge.py` | `JudgeScores` (context relevance, groundedness, answer relevance and completeness, each 0-100; weighted overall; critique; `targets` naming which agent or step was weak). |
| `evaluation/batch.py` | Golden-Q&A sample: hit@k per RAG pipeline, plus judge pass rate for the pipelines and the full multi-agent graph. |
| `memory.py` | SQLite checkpointer and SQLite store factories in `data/agent_state/`. |
| `mcp_client.py` | Loads the MCP tools from `config/mcp_servers.json` (`${CRM_MCP_URL}`) with the LangChain MCP adapter and splits them into **customer** and **ticket** groups. If the server is unreachable, it warns and the CRM agents are marked unavailable for planning. |
| `skills_sync.py` | Syncs and checks the skill mirrors. |

## Part C: specialist agents (`src/agentic_rag/agents/`)
`base.py` provides `build_specialist(spec)`, which calls `create_deep_agent` with the agent's tools, skills (`/skills/` routed to only its skill folders), system prompt and specialist model. It also provides `run_specialist(agent, step) -> AgentReport`, which pulls a structured report from the final message with `response_format` or a structured extraction. `reports.py` defines the contract:
- **`AgentReport`:** `agent`, `step_id`, `findings`, `evidence[]`, `confidence` (0-1), `gaps[]`, `proposed_actions[]`.
- **`Evidence`:** one of three kinds. A `doc` has `doc_id`, `page`, `chunk_id` and a quote. A `crm` has a `customer_id` or `ticket_id`. A `web` has a `url`, `title` and `date`.
- **`ProposedAction`:** a tool and its arguments.

| Agent | Tools | Skills | Notes |
|---|---|---|---|
| HR Policy | `hybrid_search`, `advanced_search`, `multi_query_search` and `corrective_search` on the `hr` store | `hr-policies`, `rag-answering` | Current versions by default, with superseded values flagged. |
| Product Manuals | Same pipelines on the `products` store | `product-support`, `rag-answering` | Always pins brand and model; hybrid search for error codes. |
| Customer Support | MCP `get_customer_profile` and `search_customer_profiles` (read-only) | `customer-support` | Identity resolution and the profile and 360 view. |
| Ticket Management | MCP `get_tickets_by_customer` and `search_tickets` (read); `register_ticket` and `resolve_ticket` are **never called directly** | `ticket-management` | Writes are returned as `proposed_actions`, which the graph approves and then executes. |
| Research | `web_search` (Serper) | `web-research` | Current and external information only, with URLs. |

## Part D: the Coordinator graph (`src/agentic_rag/graph/`)
- **`state.py`:** `CoordinatorState` holds `messages`, `question`, `user_id`, `memories`, `plan`, `reports` (reducer `operator.add`), `completed_steps`, `replans`, `agent_calls`, `draft_answer`, `attempts` (judge history), `pending_actions`, `approved_actions` and `final`.
- **Nodes:**
  - `load_memory`: reads the user's long-term facts from the store.
  - `plan`: high effort, structured `Plan` (steps with `agent`, `goal`, `rationale`, `depends_on` and `success_criteria`). It can **interrupt with a clarifying question**. It loads the `coordination` skill body and the agent registry (descriptions and availability). On a retry or replan, it receives the critique and gaps and replans only the weak parts.
  - `dispatch`: a conditional edge that sends every ready step (dependencies satisfied) through `Send("run_step", …)` **in parallel**, within `MAX_AGENT_CALLS`.
  - `run_step`: runs the specialist and appends its `AgentReport`.
  - `reflect`: high effort. It decides whether more steps are ready, a replan is needed (bounded by `MAX_REPLANS`), or it's time to synthesise.
  - `approve_actions`: an **interrupt** showing proposed ticket writes; the user approves, edits or rejects.
  - `execute_actions`: calls the MCP write tool for approved actions and records the outcome as evidence.
  - `synthesize`: high effort. Writes the final answer with citations from the evidence.
  - `judge`: scores the answer. On a pass, it continues to saving memory. Below the threshold, it goes back to `plan` with the critique (up to `JUDGE_MAX_RETRIES`). At the limit, it returns the best attempt with `low_confidence`.
  - `save_memory`: the fast model extracts durable user facts and writes them to the store.
- **`builder.py`:** `build_graph(settings)` compiles the `StateGraph` with the SQLite checkpointer and store, and also exports Mermaid (`get_graph().draw_mermaid()`).
- **`service.py`:** `ask(question, thread_id, user_id)` returns `GraphResult` (answer, scores, evidence, plan trace, attempts) or a pending interrupt. `resume(thread_id, value)` handles clarification and approval.

## Skills (`src/skills/`, Agent Skills spec; 7 in total)
- `hr-policies`
- `product-support`
- `customer-support`
- `ticket-management` (priorities, duplicate guard, approval etiquette)
- `web-research`
- `rag-answering`
- `coordination` (agent ownership, planning heuristics, when to ask for clarification)

`hr-policies` and `product-support` include `scripts/search.py`, so coding assistants can run retrieval through the shell. `make sync-skills` mirrors them to `.claude/skills` (Claude Code and Copilot) and `.agents/skills` (Codex and Copilot), and `make check-skills` detects drift.

## Configuration additions (`.env` and `.env.example`)
```dotenv
OPENAI_FAST_MODEL=gpt-5.1
OPENAI_FAST_REASONING_EFFORT=low
COORDINATOR_REASONING_EFFORT=high
SPECIALIST_REASONING_EFFORT=low
MAX_REPLANS=2
MAX_AGENT_CALLS=8
JUDGE_REASONING_EFFORT=low          # JUDGE_OPENAI_MODEL / JUDGE_OPENAI_API_KEY already present
JUDGE_PASS_SCORE=80
JUDGE_MAX_RETRIES=3
RAG_TOP_K=6
RAG_CANDIDATE_K=20
RRF_K=60
SERPER_RESULTS=5                    # SERPER_API_KEY already present
AGENT_STATE_DIR=data/agent_state
MCP_CONFIG_PATH=config/mcp_servers.json
CRM_MCP_URL=http://localhost:8765/mcp
EVAL_SAMPLE_SIZE=20
CRM_DB_PATH=data/crm/crm_support.db
MCP_PORT=8765
CRM_SEED_ON_START=true
```

## Notebooks (`notebooks/`, scenario-based, use cases only, no outputs)
1. `01_hr_policy_question`: hybrid and advanced RAG, the version trap, the judge.
2. `02_product_troubleshooting`: near-duplicates with model filters, error-code BM25, corrective RAG.
3. `03_customer_complaint_end_to_end`: customer lookup → tickets → manual → proposed ticket → **approval** → registered.
4. `04_ticket_resolution_workflow`: find open tickets for a model → draft resolution from the manual → approve → resolve.
5. `05_mixed_multi_domain_question`: one question needing HR, Product and CRM, with the multi-query plan and **parallel dispatch**.
6. `06_current_trends_question`: Research agent plus corpus.
7. `07_ambiguous_question_clarification`: clarifying interrupt, then resume.
8. `08_follow_ups_and_memory`: short-term follow-ups, and long-term facts recalled on a new thread.
9. `09_judge_retry_and_low_confidence`: an unanswerable question and a forced high threshold, showing the attempt history.
10. `10_support_dashboard_mcp`: raw FastMCP client, the 5 resources (stats, schema …), the 2 prompts, and business-rule errors.
11. `11_context_engineering`: token budgets, specialist context isolation, compaction.
12. `12_rag_patterns_evaluation`: batch evaluation comparing pipelines and the full graph.

## Other changes
- **Dependencies:** `uv add deepagents langgraph "langchain[mcp]" rank-bm25 langgraph-checkpoint-sqlite`, the `crm-mcp` group (`fastmcp`), and dev `ipykernel nbformat nbclient`. Hatch packages gain `src/agentic_rag` and `src/mcp_servers`.
- **Makefile:** the MCP targets, `sync-skills`, `check-skills`, `evaluate` and `graph-diagram` (exports the Mermaid diagram of the compiled graph to the docs).
- **`.gitignore`:** `data/agent_state/`, `data/eval/` and `data/crm/`.
- **Docs:** README (multi-agent architecture with Mermaid, agent roster, skills reuse recommendation, MCP and Docker, `.env`); `docs/architecture/multi_agent_architecture.md` (generated graph Mermaid, plan-dispatch-reflect and judge sequence diagrams, MCP and approval flow, all validated with the Mermaid parser); TROUBLESHOOTING; SECURITY (MCP without authentication; production guidance); CHANGELOG; project memory.

## Verification
1. **MCP server:** up and down, the banner, the health route, all tools with case-insensitive partial search, every business-rule error, the 5 resources and 2 prompts, localhost-only binding, a multi-stage non-root image with no HEALTHCHECK (size reported), and data persisting across restarts.
2. **Building blocks:** BM25 finds E-715; hybrid search with a model filter ranks the Lumina 55 Pro first; each RAG pipeline handles its target case; Serper returns results.
3. **Specialists:** each agent alone returns a valid `AgentReport` with evidence. Ticket Management **proposes** writes and never executes them.
4. **Graph:**
   - The plan shows sensible agent assignment.
   - Independent steps run in parallel (timestamps).
   - Reflect replans at most `MAX_REPLANS` times.
   - Clarify and approve interrupts resume correctly.
   - Judge pass and fail paths work, including retry targeting and the low-confidence fallback.
   - Memory works across threads and processes.
   - With the MCP server down, planning excludes the CRM agents.
5. **Notebooks:** every scenario notebook executes in a scratch copy with nbclient; the committed copies stay output-free.
6. **Skills:** sync and check pass, drift fails, and the frontmatter is valid for all 7.
7. **Batch evaluation:** `scripts/evaluate_rag.py --sample 10` runs on the pipelines and the graph.
8. **Regression:** `make verify` and `make validate-stores-offline` pass.
