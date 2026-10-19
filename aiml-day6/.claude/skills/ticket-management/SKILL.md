---
name: ticket-management
description: Look up and analyse support tickets with the CRM MCP tools get_tickets_by_customer and search_tickets, and PROPOSE (never execute) new tickets or resolutions for human approval. Covers ticket status and priority rules, the duplicate guard and resolution requirements. Use for ticket history, open issues per product, raising a complaint or closing a ticket.
---

# Ticket management

Read tools (call them freely):
- `get_tickets_by_customer(customer_id, status)` - a customer's tickets, newest first.
- `search_tickets(text, status, priority, raised_by, product_model, resolved_by, created_from, created_to, limit)` -
  case-insensitive partial matching on title/description and other fields.

Write tools (`register_ticket`, `resolve_ticket`) are **not available to you**. When a write is needed, add a
`proposed_actions` entry to your report; the Coordinator asks a human to approve it and executes it afterwards.

## Rules enforced by the server (check them before proposing)
- Status: `open`, `in_progress`, `resolved`, `closed`. Priority: `low`, `medium`, `high`, `critical`.
- Only **active** customers can raise tickets.
- **Duplicate guard**: a similar open ticket from the same customer returns the existing ticket instead of a
  new one - search the customer's open tickets first and mention a likely duplicate.
- Only `open` or `in_progress` tickets can be resolved; `resolved_by` and `resolution_remarks` are required.

## Proposing a new ticket (`register_ticket`)
Arguments: `customer_id`, `title` (specific: model + symptom + error code), `description` (what happened, what was
tried, manual steps already suggested), `priority`, `product_model`.
Priority guide: `critical` - safety risk or device dead; `high` - core function broken (no picture, no network,
repeated error code); `medium` - degraded function or workaround exists; `low` - questions, cosmetic issues.

## Proposing a resolution (`resolve_ticket`)
Arguments: `ticket_id`, `resolved_by` (the agent or person named by the user), `resolution_remarks` (what fixed it,
citing the manual section if one was used).

## Reporting
Summarise counts by status/priority when listing many tickets; give ticket IDs for every claim. Cite with kind `crm`
and the ticket ID.
