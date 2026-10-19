# Step 14 — Traffic Simulator (plan & outcome)

## Context
The dashboard and alerts are live (Step 13). Ram wants realistic traffic to experiment with:
- normal behaviour
- an economic-downturn drift
- bad inputs
- a mix of all three

The next step (drift / health / fairness reports) relies on the traffic this produces.

Findings:
- The cleaned file is `data/processed/loan_applications_raw.parquet`; the spec's `applications_clean.parquet` doesn't exist.
- 53,954 of 55,000 rows have every required API field.
- Purpose shares: Home 30%, Personal 28%, Auto 20%, Business 12%, Education 10%.

## Decisions (agreed with Ram)
| Topic | Decision |
|---|---|
| Data | `--data` flag, default `PROCESSED_DATA / "loan_applications_raw.parquet"` |
| Seed | `--seed` defaults to `RANDOM_STATE` (51), not 42 |
| Drift purpose | Personal with p = 0.5; otherwise the other 4 purposes by training share (renormalised) |
| Payload | 5 required fields, plus `credit_score`, `years_employed`, `gender`, `age` when present, plus `application_id` |

## `scripts/simulate_traffic.py`
- **Building requests**:
  - `load_applicants`, `to_payload`, `purpose_weights`
  - `apply_drift`: income × 0.6, score −80 with a minimum of 300, purpose resampled
  - `make_invalid`: score 1200, negative income, `Holiday`, or no `employment_type`
  - `build_request`: mixed = 70 / 20 / 10; bad = 30% invalid
- **Sending**: `send` posts to `/predict` with a 5 s timeout, catches `RequestException`, and returns `(status | None, latency_ms)`.
- **Counting**: `Stats` tracks 2xx / 4xx / 5xx / errors, per-kind counts and average latency.
- **`run`**: a paced loop, so send `i` happens at `start + i / rps`; it prints progress every 10 s, then a summary.
- **Makefile**:
  - `simulate-normal` (120 s), `simulate-drift` (300 s), `simulate-bad` (120 s)
  - `reset-logs`: `open(PREDICTION_LOG, "w")`, which truncates to 0 bytes and never deletes the file

## Tests: `tests/test_simulate_traffic.py` (20 tests; full suite 138 passed)
- `to_payload` drops missing values and uses ints; `load_applicants` filters out invalid rows.
- Drift: income, score floor and a missing score; Personal ≈ 50% over 2,000 draws. Drifted payloads still pass `ApplicantIn`.
- All 12 seeded invalid variants are rejected by `ApplicantIn`.
- Mixed and bad shares hold; `Stats` classification is correct.
- `run` against an unreachable URL counts errors and doesn't crash.

## Outcome (2026-10-16)
`python scripts/simulate_traffic.py --mode normal --rps 5 --duration 30` against the compose stack:
```
[   10s] sent    51 | 2xx    51 | 4xx    0 | 5xx   0 | errors   0 | avg   71.9 ms
[   20s] sent   101 | 2xx   101 | 4xx    0 | 5xx   0 | errors   0 | avg   71.6 ms
=== Summary ===
[   30s] sent   150 | 2xx   150 | 4xx    0 | 5xx   0 | errors   0 | avg   71.6 ms
achieved 5.02 rps over 29.9 s | by kind: {'normal': 150}
```
- `logs/predictions.jsonl` grew by exactly 150 lines (132 → 282).
- The client-side latency includes the Docker Desktop port proxy; the server-side p95 is about 24 ms.

## Not in this step
Drift (PSI), health and fairness reports.
