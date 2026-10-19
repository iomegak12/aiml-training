# Step 1 — Project Scaffold (Northwind Finance, aiml-e2e)

## Context
Live training demo. Step 1 creates the skeleton only: folders, packaging, config, Makefile, docs, .venv.
No ML code, no API code, no Docker files. `data/raw` and `data/sample` are never touched.
Existing data: `data/raw/loan_applications_raw.csv`, `data/sample/sample_applicants.csv`.
Tools available: make (chocolatey), uv 0.9.16, CPython 3.12.12.

## Decisions agreed with Ram
- Dist name `northwind-loans`, import name `northwind_loans`, `requires-python = ">=3.11,<3.13"`.
- `.env` loaded with **python-dotenv==1.0.1** (added to the agreed list).
- Deps in `pyproject.toml`: runtime in `[project.dependencies]`, `pytest` + `httpx` in `[dev]` extra.
- `__init__.py` re-exports settings → `from northwind_loans import TARGET` and `from northwind_loans import config` both work.
- `.env` controls: PROJECT_ROOT + dir overrides, LOG_LEVEL=INFO, RANDOM_STATE=51. Business rules (TARGET, CREDIT_POLICY, VALID_RANGES, INCOME_PAISE_THRESHOLD) stay in code.
- Makefile auto-detects OS for `.venv/Scripts/python.exe` vs `.venv/bin/python`.
- Only `setup` and `test` are real now; all other targets are placeholder `echo "... (Step N)"`.
- Target `loads` → **`logs`** (in `.PHONY`, because a `logs/` folder exists).
- Community docs short & practical; CODE_OF_CONDUCT adopts Contributor Covenant 2.1 by reference.

## Files / folders to create
```
src/northwind_loans/__init__.py      # __version__ + re-export of config names (__all__)
src/northwind_loans/config.py        # all settings
src/northwind_loans/api/__init__.py  # empty
data/processed/.gitkeep  models/.gitkeep  logs/.gitkeep  reports/.gitkeep  scripts/.gitkeep
monitoring/prometheus/.gitkeep
monitoring/grafana/provisioning/dashboards/.gitkeep
monitoring/grafana/provisioning/datasources/.gitkeep
tests/__init__.py  tests/test_config.py   # light smoke test
pyproject.toml  Makefile  .gitignore  .env.example  .env (git-ignored)
README.md  CHANGELOG.md  TROUBLESHOOTING.md  CONTRIBUTING.md  SECURITY.md  CODE_OF_CONDUCT.md  LICENSE (MIT, © 2026 Ramkumar)
```

### pyproject.toml
- `[build-system] requires = ["setuptools>=68"]`, backend `setuptools.build_meta`.
- `[tool.setuptools.packages.find] where = ["src"]`.
- Runtime pins: pandas 2.2.3, numpy 2.1.3, pyarrow 18.1.0, scikit-learn 1.5.2, scipy 1.14.1, fastapi 0.115.6, uvicorn[standard] 0.32.1, pydantic 2.10.4, prometheus-client 0.21.1, python-json-logger 3.2.1, requests 2.32.3, python-dotenv 1.0.1.
- `[project.optional-dependencies] dev = ["pytest==8.3.4", "httpx==0.28.1"]`.
- `[tool.pytest.ini_options] testpaths = ["tests"]`.

### config.py (plain module constants, type hints, short docstring)
- `PROJECT_ROOT` = env override, else `Path(__file__).resolve().parents[2]`; `load_dotenv(PROJECT_ROOT / ".env")`.
- `RAW_DATA` = data/raw/loan_applications_raw.csv, `SAMPLE_DATA` = data/sample/sample_applicants.csv,
  `PROCESSED_DATA` = data/processed, `REPORTS_DIR`, `MODEL_DIR`, `LOG_DIR` (each overridable via env).
- `TARGET = "max_loan_offered"`, `RANDOM_STATE` (default 51), `LOG_LEVEL` (default INFO).
- `CREDIT_POLICY` dict exactly as given; `credit_haircut` lists all 5 bands explicitly (others = 1.0) for clarity.
- `VALID_RANGES`, `INCOME_PAISE_THRESHOLD = 20_000_000`.
- No directory creation on import (later steps create what they write).

### .gitignore
`.venv/`, `.env`, `__pycache__/`, `*.egg-info/`, `.pytest_cache/`, `build/`, `dist/`,
contents of `data/processed/`, `models/`, `logs/`, `reports/` (keeping `.gitkeep`). Raw/sample data stays tracked.

### Makefile
- `setup`: `uv venv --python 3.12 .venv` + `uv pip install --python $(PY) -e ".[dev]"`.
- `test`: `$(PY) -m pytest -q`.
- Placeholders: profile, clean-data, train, predict-sample, serve, docker-build, up, down, logs, simulate-normal, simulate-drift, simulate-bad, monitor.
- `help` default target listing everything.

### README.md
Goal, synthetic-data / **not for real credit decisions** disclaimer, folder tree, quickstart (`make setup`, `make test`), roadmap of steps.

## Verification (show real output)
1. `make setup`: creates .venv on 3.12 and installs the editable package.
2. Acceptance: `.venv/Scripts/python -c "from northwind_loans import ...; print(...)"` prints every setting (paths, TARGET, RANDOM_STATE, LOG_LEVEL, CREDIT_POLICY, VALID_RANGES, INCOME_PAISE_THRESHOLD).
3. `make test`: test_config.py passes (paths exist, TARGET, random state 51, policy keys).
4. `uv pip list --python .venv` shows the exact pinned versions.
5. `git check-ignore .env` shows it is ignored; `git status data/` is unchanged from the start.
6. `make train` prints its placeholder; `make logs` runs, not "up to date".
No git commit unless Ram asks.
