# Troubleshooting

### `uv: command not found`
Install uv: `pip install uv` or see <https://docs.astral.sh/uv/getting-started/installation/>.

### `make: command not found` (Windows)
Install GNU make, e.g. `choco install make` (Chocolatey) or `winget install GnuWin32.Make`.
Or run the commands from the Makefile by hand.

### uv cannot find Python 3.12
Run `uv python install 3.12`, then `make setup` again.

### `ModuleNotFoundError: No module named 'northwind_loans'`
The package is not installed in the active environment. Run `make setup`, or
`uv pip install -e ".[dev]"`, and make sure you use `.venv`'s Python.

### Activating the virtual environment
- Windows PowerShell: `.venv\Scripts\Activate.ps1`
  (if blocked: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`)
- Windows Git Bash: `source .venv/Scripts/activate`
- macOS / Linux: `source .venv/bin/activate`

### `make logs` says "logs is up to date"
A folder called `logs/` exists. The target must be listed in `.PHONY` (it is in this Makefile).

### `UnicodeEncodeError: 'charmap' codec can't encode character '₹'` (Windows)
The console cannot print `₹`. Set UTF-8 output: `$env:PYTHONIOENCODING="utf-8"` (PowerShell)
or `export PYTHONIOENCODING=utf-8` (Git Bash). The data itself is fine.

### `metadata signature mismatch` / `model file hash mismatch` when loading a model
The JSON or the `.pkl` changed after saving, or `MODEL_SIGNING_KEY` is different from the
key used when the model was saved. Restore the key, or retrain with `make train`.

### `make serve`: port 8000 already in use
Find and stop the process (PowerShell):
`Get-NetTCPConnection -LocalPort 8000 -State Listen | % { Stop-Process -Id $_.OwningProcess }`
or set another `API_PORT` in `.env`.

### Windows Firewall prompt when starting the API
`API_HOST=0.0.0.0` listens on all network interfaces. Allow it for private networks, or set
`API_HOST=127.0.0.1` in `.env` for local-only access.

### `/ready` returns 503
No model was loaded (none in `models/`, or the signature/hash check failed). The reason is
in the response; run `make train` and restart the server.

### Metrics look different on each scrape / counters reset
The API must run with a **single** uvicorn worker (prometheus_client keeps counters per
process), and counters reset when the server restarts — Prometheus `rate()` handles that.

### `logs/predictions.jsonl` grows forever
It is append-only by design (audit). Delete or rotate it between demos; it is git-ignored.

### `failed to connect to the docker API ... dockerDesktopLinuxEngine`
Docker Desktop is not running. Start it and wait until `docker info` answers.

### Container: `/ready` returns 503 "metadata signature mismatch"
The container has no (or a different) `MODEL_SIGNING_KEY`. Run with `--env-file .env`
(compose already uses `env_file: .env`) using the same key that signed the model.

### `curl: (52) Empty reply from server` right after `docker run`
Docker's port proxy accepts connections before uvicorn is listening. Wait a second and
retry (or poll `/ready`).

### Git Bash mangles container paths (`C:/Program Files/Git/app/...`)
Prefix the command with `MSYS_NO_PATHCONV=1`, e.g.
`MSYS_NO_PATHCONV=1 docker exec loan-api ls /app/models`.

### `curl -X POST localhost:9090/-/reload` is refused
Prometheus needs `--web.enable-lifecycle` (set in docker-compose.yml). After changing the
compose `command`, run `docker compose up -d prometheus` (a reload is not enough).

### Grafana rejects the password from `.env`
`GRAFANA_ADMIN_PASSWORD` is applied only when Grafana creates its database. For an existing
`grafana-data` volume: `docker compose exec grafana grafana cli admin reset-admin-password <new>`.

### Dashboard panel says "No data" right after traffic
`rate(...[1m])` needs at least two scrapes of a series (scrape interval is 5 s) — wait
~15 s. Counters with labels that never occurred (e.g. no 5xx yet) have no series; the error
panels use `or vector(0)` for that reason.

### Rates show 0 for the first errors after a restart
A labelled counter that first appears at 5 looks like "no change" to `rate()`. The API
creates its known label combinations at 0 on start-up; brand-new label values (an unknown
field name) only count from their second occurrence.

### `PermissionError ... pytest-of-<user>\pytest-current` on Windows
pytest could not replace its temp link. The project uses `--basetemp=.pytest_tmp`
(pyproject.toml) to avoid it; delete the stale folder in `%TEMP%` manually if you like.

### Settings in `.env` are ignored
`.env` must be in the project root (next to `pyproject.toml`). Variables already set
in your shell take precedence over `.env`.

### `make monitor` ends with `make: *** [Makefile] Error 1`
Expected when at least one feature has PSI > 0.25 ("investigate") - the exit code is meant to
fail a scheduled job. Read the verdict in `reports/monitoring_report.md`.

### `make monitor` reports NO DATA
No predictions in the last 30 minutes of `logs/predictions.jsonl`. Run a simulator first, or
call `python -m northwind_loans.monitoring` without `--since-minutes` for the whole log.

### Fairness tables say "skipped (< 30)" / "not enough data"
Groups with fewer than 30 records are left out (too noisy). Run the simulator longer.
