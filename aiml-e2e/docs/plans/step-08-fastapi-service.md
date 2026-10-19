# Step 8 — FastAPI Service (plan & outcome)

## Context
Step 7's `LoanOfferPredictor` turns applications into offers. Step 8 exposes it as a REST API:
- Pydantic v2 validation, so bad input gets 422, never 500.
- The pickle loads once, in a lifespan handler.
- Liveness and readiness endpoints.
- The "synthetic data, never for real credit decisions" disclaimer in the API description.

## Decisions (agreed with Ram)
| Topic | Decision |
|---|---|
| Invalid item in a batch | Whole batch → 422; `loc` names the item index |
| Model load failure | App still starts: `/health` 200, `/ready` and `/predict*` → 503 with the reason |
| Unknown fields | `extra="forbid"` → 422 (a typo can't become "missing credit score") |
| Serve | `python -m northwind_loans.api` (`uvicorn.run`), `make serve` |
| 422 body | FastAPI default |
| `/model-info` | Compact: name, version, created_at, sklearn_version, model_sha256, metrics, columns, excluded_features, credit_policy |
| Host/port | `API_HOST` default 0.0.0.0, `API_PORT` 8000 (config.py, from .env) |

## Files
- **`api/schemas.py`**:
  - `ApplicantIn` has 5 required fields and 8 optional ones. Score, tenure and age limits come from `VALID_RANGES`; the income limit is `INCOME_PAISE_THRESHOLD`.
  - `gender` and `age` descriptions say "fairness monitoring only".
  - It carries an OpenAPI example from NWF-035344.
  - Also `OfferOut`, `BatchIn` (1..1000) and `BatchOut`.
- **`api/main.py`**:
  - `create_app(model_dir)`: the title and `version=str(metadata["version"])` come from `registry.load_metadata` (JSON only, at import).
  - `lifespan` creates ONE `LoanOfferPredictor` in `app.state.predictor`; `get_predictor` returns 503 if there isn't one.
  - Endpoints are plain `def`, so FastAPI runs them in its threadpool.
  - Module level: `app = create_app()`.
- **`api/__main__.py`**: `uvicorn.run(..., host=API_HOST, port=API_PORT)`.
- **Other source changes**:
  - `registry.load_metadata` + `_resolve_version`
  - `predict.LoanOfferPredictor.predict_records`
  - `API_HOST`/`API_PORT` in config and `.env*`
  - `make serve`
- **Tests**:
  - `tests/conftest.py`: a session fixture `trained_model_dir`.
  - `tests/test_api.py` (17 tests), checking:
    - health/ready; app version and disclaimer
    - the example → 200
    - a thin file is flagged
    - credit 950 → 422; Holiday → 422
    - zero income, paise income, tenure 400 and a typo field → 422; a missing field → 422
    - batch 200 / bad item 422 / empty 422
    - compact model-info; OpenAPI example + fairness note
    - no model → 503

## Notable fix
`fastapi.testclient` raised a third-party `DeprecationWarning`: starlette 0.41.3 (pinned via fastapi) uses an alias deprecated in the unpinned anyio 4.15.1.
- Pinning anyio would mean adding a dependency, which needs Ram's approval.
- Instead, `pyproject.toml` sets `filterwarnings = ["error", "ignore:<that exact message>"]`.
- So `make test` is now strict about every other warning.

## Outcome (2026-10-15, live server, model v4)
| Call | Result |
|---|---|
| `GET /health` | 200 `{"status":"ok"}` |
| `GET /ready` | 200 `{"status":"ready","model_version":4}` |
| `GET /model-info` | 200, 10 keys, test R² 0.9785 |
| `POST /predict` (example NWF-035344) | 200, offered 4,583,000 (raw 4,583,776, `round_down_1000`) |
| `POST /predict` credit_score 950 | 422 `less_than_equal`: "Input should be less than or equal to 900" |
| `POST /predict` loan_purpose Holiday | 422 `literal_error`: "Input should be 'Home', 'Personal', 'Auto', 'Education' or 'Business'" |
| `POST /predict/batch` (9 cleaned sample rows) | 200, same offers as Step 7's CLI; NWF-039077 flagged `credit_score_missing` |
| `POST /predict/batch` (10 rows incl. NWF-013391) | 422 `missing` at `["body","applicants",8,"requested_tenure_months"]` |
| `GET /docs` | 200 |

- The server was stopped (PID 18924). Port 8000 was free afterwards and `/health` refused connections.
- Full suite: 95 passed.

## Not in this step
Docker, Prometheus metrics, Grafana, and the traffic simulators.
