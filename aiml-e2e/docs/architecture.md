# Architecture — Northwind loan offer system

> Educational demonstration on synthetic data. Never use it for real credit decisions.

```
 data/raw/*.csv ──► profiling.py ──► reports/data_profile.*
        │
        ▼
   cleaning.py ──► data/processed/*.parquet ──► features.py (PolicyFeatures)
                                                   │
                                                   ▼
                                       train.py (impute → policy features →
                                       scale/one-hot → LinearRegression)
                                                   │
                                                   ▼
                     registry.py ──► models/loan_offer_model_vN.pkl
                                     models/loan_offer_model_vN.json  (signed metadata
                                                   │                  + reference profile)
                                                   ▼
  client / simulate_traffic.py ──HTTP──► FastAPI (Docker, :8000)
                                         predict.py → business_rules.py
                                           │            │
                              /metrics ◄───┘            └──► logs/predictions.jsonl
                                 │                           (audit log, no age/gender)
                                 ▼                                │
                         Prometheus (:9090) ──► Grafana (:3000)   ▼
                         alerts.yml             live dashboard   monitoring.py
                                                                  (PSI drift + fairness
                                                                   → reports/monitoring_report.*)
```

| Component | Role |
|---|---|
| `config.py` | paths, credit policy, valid ranges, settings from `.env` |
| `profiling.py` | describes the raw data without changing it |
| `cleaning.py` | money/date/category parsing, impossible values set to missing, de-duplication; `standardize_frame` is reused at prediction time |
| `features.py` | stateless credit-policy features (FOIR, EMI capacity, caps, haircut) and the model column lists |
| `train.py` | engineered vs baseline pipeline, 5-fold CV + test split, training report |
| `reference_profile.py` | training decile bins, category shares and fairness baseline, stored with the model |
| `registry.py` | versioned pickle, SHA-256 hash and HMAC-signed metadata |
| `business_rules.py` | raw estimate → offer (floor, 5× income cap, round down) plus manual-review reasons |
| `predict.py` | `LoanOfferPredictor`: clean → model → rules → review |
| `api/` | FastAPI app, Pydantic schemas, JSON logs, Prometheus metrics, audit log |
| `monitoring/` | Prometheus scrape config and alerts; Grafana datasource and dashboard provisioning |
| `scripts/simulate_traffic.py` | normal / drift / bad / mixed traffic generator |
| `monitoring.py` | offline drift (PSI) and fairness screening report; exit code 1 on "investigate" |

There are two monitoring paths:
- **Live (Prometheus/Grafana)**: request health, latency, offers and mean-based drift alerts, every 5 s.
- **Offline (`make monitor`)**: distribution drift (PSI) and fairness by group, for a
  scheduled job. Gender and age are joined by `application_id` from a separate store, so the
  audit log stays free of them.
