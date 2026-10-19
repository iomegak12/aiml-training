# Troubleshooting

## Setup

**`uv: command not found`**
Install uv from <https://docs.astral.sh/uv/getting-started/installation/>.
- Windows PowerShell: `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"`
- macOS or Linux: `curl -LsSf https://astral.sh/uv/install.sh | sh`

Open a new terminal afterwards.

**`ModuleNotFoundError: No module named 'data_generation'`**
The helper package is installed into `.venv` by `uv sync`. Run `uv sync` once, and always start the script with
`uv run scripts/corpus_data_generator.py ...`, not `python scripts/...`, so that the project environment is used.

**Wrong Python version**
The project needs Python 3.12 or later (pinned in `.python-version`). If you don't have it, run
`uv python install 3.12`, then `uv sync`.

## `make` on Windows

`make` is not installed on Windows by default. You can:
- Install it with `winget install GnuWin32.Make` or `choco install make`, then reopen the terminal.
- Use Git Bash, which some Git installs include `make` with.
- Run the commands directly, without `make`:

| Make target | Direct command |
|---|---|
| `make setup` | `uv sync` |
| `make generate` | `uv run scripts/corpus_data_generator.py generate` |
| `make generate-template` | `uv run scripts/corpus_data_generator.py generate --mode template` |
| `make generate-hr` | `uv run scripts/corpus_data_generator.py generate --mode hybrid --only hr` |
| `make verify` | `uv run scripts/corpus_data_generator.py verify` |

## OpenAI and hybrid mode

**`ERROR: hybrid mode needs OPENAI_API_KEY`**
Add `OPENAI_API_KEY=...` to `.env` in the project root, or run with `--mode template`.

**`AuthenticationError` (401)**
The key is invalid or revoked. Create a new key and update `.env`. Check that there are no quotes or trailing
spaces around the value.

**`NotFoundError` or "model does not exist" (404)**
Your account does not have access to the model in `OPENAI_MODEL`. Change it in `.env` to a model available to
you.

**`BadRequestError` mentioning `reasoning` or `effort`**
The chosen model does not support that reasoning effort. Try `--effort low` or `--effort medium`, or change
`OPENAI_REASONING_EFFORT` in `.env`.

**A hybrid run is slow**
Reasoning effort is the main factor. In our measurements, `high` takes about 27 s per request (about 18 min for
the full corpus), and `low` takes about 3.4 s (about 3 min). Use `make generate-fast`, or
`make generate EFFORT=low WORKERS=10`, or set `OPENAI_REASONING_EFFORT=low` in `.env`. See the speed table in
the README.

**Changed `--effort` but nothing was regenerated**
That is by design. The cache ignores the effort level, so cached sections are reused. Add `--refresh`
(`make refresh EFFORT=low`) to request them again at the new effort.

**Rate limits (429)**
Requests are retried automatically with backoff. To reduce pressure, lower concurrency with `--workers 2`
(`make generate WORKERS=2`), or generate one category at a time (`--only hr`, then `--only products`).
Completed sections are cached, so an interrupted run resumes where it stopped.

**Some sections show "rejected" in the summary**
That is the guard working. The LLM added a number or mentioned another model, so the template text was kept.
The reasons are listed under `enrichment.rejections` in `data/corpus/generation_report.json`. A few rejections
are normal. To retry them, run `generate --refresh`. Note that this re-requests every section.

**`errors` is above zero after a hybrid run**
Those sections hit an API error after all retries and fell back to the template text. Run `generate` again;
cached sections are not requested a second time.

## Output and verification

**`PermissionError` when generating on Windows**
A PDF from the previous run is open in a viewer or in VS Code. Close it, then run `generate` again; the
generator deletes and rebuilds `data/corpus`.

**`page counts within range` fails**
Rich LLM prose made a document longer than its range, even at the tightest layout. Options:
- Use `--effort low`, which usually produces shorter text.
- Lower `max_words` for the category in `PROFILES` in `src/data_generation/llm/enricher.py`, then run
  `generate --refresh`.
- Remove some of the `enrich=True` flags in the builders for that document type.

**`golden Q&A evidence found on cited pages` fails**
Evidence strings must appear verbatim in the PDF text. This happens after editing the catalog wording without
updating the matching `qa` evidence (HR policies) or spec row labels (manuals). The failure message shows the
question ID and the missing evidence.

**`manifest matches files on disk` fails**
Files were added to or removed from `data/corpus` by hand. Run `generate` again to rebuild a clean corpus.

**Start completely fresh**
Run `make clean`, plus `make clean-cache` to also discard the LLM prose. Then run `generate` again.

## Vector stores (ingestion and validation)

**`Store not found` in the validation script**
Run `uv run scripts/ingest_vector_stores.py` (`make ingest`) first. The databases live in `data/vectorstores/`.

**I changed the chunk size, but nothing seems different**
Re-run ingestion. Changed chunks are detected automatically, and the affected documents are re-embedded and
replaced. `validate_vector_stores.py` shows the `chunk_size` recorded on the collection. Use `--reset` for a
completely clean rebuild.

**I changed the metadata logic in `src/data_ingestion`, but the old metadata is still there**
Change detection compares chunk text, not metadata. Run with `--reset` (`make ingest-reset`) to rebuild the
store with the new metadata.

**`PermissionError` or "database is locked" on Windows**
Another process has the Chroma database open: a notebook, a second script, or a file viewer. Close it and
re-run. To start from scratch, run `make clean-stores` while nothing else is using the folder.

**Metadata type errors from Chroma**
Chroma accepts only scalar values (str, int, float, bool). New metadata must go through
`metadata.sanitize_for_chroma`, which drops `None` and joins lists.

**Embedding rate limits (429) or timeouts**
Lower `INGEST_BATCH_SIZE` (fewer documents embedded in parallel) or `EMBEDDING_BATCH_SIZE` (smaller requests)
in `.env`. Requests are retried automatically, and finished documents are not re-embedded on the next run.

**Validation without API calls**
Use `--skip-queries` (`make validate-stores-offline`). Only the sample queries need the embeddings API.

## Text extraction differences

The golden Q&A is verified with `pypdf`. Other loaders (PyMuPDF, pdfplumber, Unstructured) may order table
cells or join wrapped lines differently. This is a useful classroom discussion point, not a corpus bug. Normalise
whitespace before comparing text.

## Multi-agent RAG (src/agentic_rag)

**The CRM agents are "UNAVAILABLE" in `service.roster()`**
The CRM & Support MCP server is not reachable at `CRM_MCP_URL`. Start it with `make mcp-server-up` and check
`make mcp-server-status`. The graph still works without it: the Coordinator plans only with the other agents and
says that customer/ticket data is unavailable.

**The Research agent is unavailable**
`SERPER_API_KEY` is missing from `.env`.

**`RuntimeError: This event loop is already running` / `await` outside a function**
Use `await service.ask(...)` directly in a notebook cell (Jupyter supports top-level `await`). In a script, wrap
the code in `async def main()` and call `asyncio.run(main())`.

**A run "hangs" for 30-90 seconds**
That is normal for multi-step questions: the Coordinator plans, reflects and writes at `high` reasoning effort and
the judge reviews the answer. Pass `on_event=print` to `ask`/`resume` to watch progress. To speed up a class demo,
set `COORDINATOR_REASONING_EFFORT=medium` or lower `MAX_AGENT_CALLS` / `JUDGE_MAX_RETRIES`.

**The answer starts with "Low confidence"**
The judge never scored an attempt at or above `JUDGE_PASS_SCORE` within `JUDGE_MAX_RETRIES` retries. Inspect
`result.attempts` (scores, critique, targets). Very high pass marks (above about 95) are rarely reachable.

**`status == "needs_approval"` or `"needs_clarification"` and no answer**
The graph is paused at an interrupt. Answer it with `await service.resume(result.thread_id, value)`: the
clarification text, or `"approve"` / `"reject"` / `{"decisions": [{"id": 0, "decision": "edit", "arguments": {...}}]}`.

**"database is locked" from `data/agent_state`**
Two processes write to the same SQLite checkpoint file at the same time (for example two notebooks). Run one at a
time, or point one of them to another `AGENT_STATE_DIR`.

**Stale memory makes answers odd (e.g. the wrong phone model is assumed)**
Long-term facts are per `user_id`. Use `await service.forget("user-id")`, a new `user_id`, or
`make clean-agent-state` to delete all memory.

**`make check-skills` fails**
A file under `.claude/skills` or `.agents/skills` was edited directly, or `src/skills` changed without a sync.
Edit only `src/skills/`, then run `make sync-skills`. Frontmatter errors (`name` must match the folder,
`description` at most 1024 characters) are reported with the skill name.

## CRM & Support MCP server (Docker)

**`make mcp-server-up` fails with "port is already allocated"**
Another process uses port 8765. Set `MCP_PORT=8766` in `.env` (the URL `CRM_MCP_URL` must match) and retry.

**`make mcp-server-status` says the server is not reachable**
Check `docker compose ps` and `make mcp-server-logs`. The container prints a coloured banner with the endpoint,
database path and record counts when it is ready.

**The banner has no colours or wraps badly**
Docker logs are coloured because the service has `tty: true` and `FORCE_COLOR=1`; some terminals strip ANSI
codes. Use Windows Terminal or VS Code's terminal.

**Tickets created in class are still there after a restart**
That is intended: `./data/crm` is a bind mount. Run `make mcp-seed-reset` to restore the demo data.

**`permission denied` on `data/crm` (Linux/macOS)**
The container runs as a non-root user. Make the folder writable: `mkdir -p data/crm && chmod 777 data/crm`, or
run the container with your UID.

**Running the server without Docker**
`uv sync --group crm-mcp` and `uv run python -m mcp_servers.crm_support` (add `--reset-seed` to reload the seed).
It listens on `127.0.0.1:8765` by default.
