---
name: coordination
description: Planning rules for the Coordinator of the multi-agent assistant - which specialist owns which data (HR policies, product manuals, customer profiles, support tickets, web research), how to split a business question into parallel steps with dependencies, when to ask a clarifying question, how to replan after gaps or a failed judge review, and how to propose ticket actions for approval.
---

# Coordinating the specialist agents

## Ownership (one owner per data source)
| Agent | Owns | Never ask it for |
|---|---|---|
| `hr_policy` | HR policy documents (`hr` store) | product, customer or web facts |
| `product_manuals` | TV and phone manuals (`products` store) | policies, customer data |
| `customer_support` | CRM customer profiles (read-only) | ticket history, writes |
| `ticket_management` | support tickets; proposes ticket writes | profile details, manual content |
| `research` | public web (current trends, news, prices) | anything internal |

Unavailable agents (e.g. CRM server down, no Serper key) must not be planned; mention the limitation instead.

## Building a plan
- Use the fewest steps that fully answer the question. A single-domain question is usually one step.
- Give each step a precise `goal` (what to find, for which model/customer/policy) and `success_criteria`.
- Steps without dependencies run **in parallel**. Add `depends_on` only when a step needs another step's output,
  e.g. look up the customer (to learn their product model) **before** searching that model's manual.
- Put identifiers into goals: customer IDs, ticket IDs, exact product models, policy names.
- Ticket writes: ask `ticket_management` to *propose* `register_ticket` / `resolve_ticket`; the graph will ask a
  human to approve. Only propose a write when the user asked for it or clearly needs it (an unresolved complaint).

## Clarify instead of guessing
Ask one short clarifying question when the answer depends on information you cannot look up:
- **Product troubleshooting with an unknown model** ("my phone isn't charging", "my TV shows an error"): if no
  model, model number, customer ID or customer name appears in the question, the conversation or the user's
  long-term facts, ask for the exact model (and the error message or code) BEFORE planning - fixes, limits and
  error codes differ between models, so a generic answer is not acceptable.
- "the policy" or "that ticket" with several plausible candidates and nothing to disambiguate them.

Do not ask when an agent can find the answer (e.g. the customer's model from their CRM profile, or a policy that
is uniquely named).

## Replanning
- After reflection: add steps only for concrete `gaps` that matter for the question; do not repeat a step with
  the same goal.
- After a failed judge review: read the critique and `targets`; redo only the weak parts (a better-targeted step
  or better synthesis). Evidence already gathered is kept.

## Synthesis
Lead with the direct answer, then details per domain, then actions taken or awaiting approval. Cite evidence
IDs `[E1]`, `[E2]` from the reports. Say clearly what could not be found.
