# Security Policy

## Supported versions

| Version | Supported |
|---------|-----------|
| 0.1.x   | Yes       |

## Handling secrets

This project reads API keys (`OPENAI_API_KEY`, `JUDGE_OPENAI_API_KEY`, `SERPER_API_KEY`) from a local `.env` file.

- **Never commit `.env`.** It is listed in `.gitignore`. Check before every commit with `git status`.
- If a key has ever been committed, pushed, pasted into a chat, or shared in a screen recording, **rotate it
  immediately** in the OpenAI dashboard. Deleting the file in a later commit does not remove it from history.
- To check whether `.env` was ever committed, run `git log --all --oneline -- .env`. The command should print nothing.
- When teaching, use a project-scoped key with a monthly spending limit, and revoke it after the session.
- The generator sends only synthetic, fictional content to the API. Do not add real personal data, real
  employee records or confidential company documents to the catalog.

The multi-agent system also reads `SERPER_API_KEY` and `JUDGE_OPENAI_API_KEY`; the same rules apply. The
Docker Compose file passes **no API keys** into the MCP server container - it only needs its own settings.

## CRM & Support MCP server (no authentication)

The FastMCP server in `src/mcp_servers/crm_support` is a **classroom demo without authentication**: any process
that can reach the port can read every customer profile and register or resolve tickets.

Mitigations in this project:
- `docker-compose.yml` publishes the port on the loopback interface only (`127.0.0.1:${MCP_PORT}:8765`), so the
  server is not reachable from the LAN. Do not change it to `0.0.0.0` or `"8765:8765"`.
- When run outside Docker, the server binds to `MCP_HOST=127.0.0.1` by default.
- FastMCP's host/origin validation is left at its default, which protects against DNS-rebinding from a browser.
- The container runs as a non-root user from a slim image; only `data/crm/` is mounted.
- The data is fictional (`.example` e-mail addresses, `+91 00000` phone numbers).
- Write tools are annotated as non-read-only, and the agents can only *propose* writes; the Coordinator executes
  them after a human approves.

Before using the pattern with real data, add at least:
- **Authentication**: FastMCP bearer-token/JWT verification or an OAuth provider, and per-tool authorisation
  (read-only clients must not see `register_ticket` / `resolve_ticket`).
- **TLS** in front of the server (reverse proxy) and network policies instead of a published port.
- **Audit logging** of every write (who, what, when) and rate limiting.
- **Data minimisation**: return only the fields a caller needs; mask contact details by default.

## Agent memory and logs

- `data/agent_state/` stores conversations (checkpoints) and long-term facts about users in plain SQLite files.
  Treat them as personal data: do not commit them (they are in `.gitignore`), and use `service.forget(user_id)` or
  `make clean-agent-state` to delete them.
- `data/eval/` reports contain questions and generated answers; review before sharing.
- The Research agent sends search queries to Serper; never put customer data into web queries.

## Generated content

- All brands, companies, products, people and contact details in the corpus are fictional. Phone numbers are
  placeholders, and every web address uses the reserved `.example` domain.
- Statutory references in the HR policies are illustrative teaching material, not legal advice.
- The LLM cache (`data/cache/llm/`) stores prompts and responses in plain text. It contains no secrets, but
  treat it like any generated artefact and do not publish it without review.

## Reporting a vulnerability

Please report security issues privately by email to **jd.ramkumar@gmail.com** with the subject line
`[SECURITY] aiml-day6`. Include steps to reproduce and the affected version. You can expect an acknowledgement
within 5 working days. Please do not open a public issue for security reports.
