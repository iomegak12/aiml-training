# Contributing

Thanks for your interest in improving the IT Support Agent API. This guide explains how to set up the project, make a change and submit it.

By participating you agree to follow the [Code of Conduct](CODE_OF_CONDUCT.md).

## Getting set up

1. Install Python 3.12 and [uv](https://docs.astral.sh/uv/).
2. Clone the repository and install dependencies:

   ```bash
   uv sync
   cp .env.example .env
   ```

3. Run the tests. They need **no OpenAI key**:

   ```bash
   make test        # or: uv run pytest -q
   ```

4. To run the server against OpenAI, set `OPENAI_API_KEY` in `.env` and run `make run`.

## Project layout

| Path | What lives there |
|---|---|
| `src/it_tickets` | Ticket library (SQLite, SQLAlchemy ORM, Pydantic v2). No raw SQL. |
| `src/agent_tools` | LangChain tools. Ticket tools wrap `it_tickets` without changing it. |
| `src/ticket_agent` | Deep Agent construction, model settings, streaming events, plan approval |
| `src/api` | FastAPI app, middleware, errors, logging |
| `tests/` | pytest suite; `tests/api/` covers the REST API; `tests/helpers.py` has the scripted fake model |

## Making a change

1. Create a branch from `main`: `git checkout -b feature/short-description`.
2. Keep the change focused: one feature or fix per pull request.
3. Follow the existing style:
   - type hints on public functions, docstrings on public classes and endpoints
   - Pydantic models for request/response bodies
   - errors raised as `ApiError` (or mapped in `api/errors.py`) so clients always get Problem Details
   - no secrets in code, logs or test fixtures
4. Add or update tests. Use `ScriptedModel` from `tests/helpers.py` instead of calling OpenAI; tests must pass offline.
5. If behaviour visible to users changes, update `README.md` and add an entry under **Unreleased** in `CHANGELOG.md`.
6. Run `make test` and make sure everything passes.

## Commit messages

Use short, imperative subject lines, for example:

```
Add Retry-After header to rate-limited responses
Fix thread lock release when a stream is cancelled
```

## Pull requests

- Describe **what** changed and **why**, and how you tested it.
- Link related issues.
- Keep pull requests reviewable; split large changes.
- A maintainer reviews every pull request. Expect questions; they are part of the process.

## Reporting bugs and requesting features

Open a GitHub issue with:

- what you did (request, configuration with **secrets removed**)
- what you expected and what happened
- the `request_id` from the response or log, if relevant
- version (`GET /health`) and environment (local or Docker, OS)

Security issues must **not** be reported in public issues; see [SECURITY.md](SECURITY.md).
