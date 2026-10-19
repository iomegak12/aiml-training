# Corvana Day 3 Kit: Feature Engineering & Linear Regression

Datasets and environment setup for **Day 3** of the 6-day AI/ML & Generative AI program, built around the **Corvana Networks Renewal Intelligence Program** case study.

On Day 3 participants build a **Renewal Value Forecast**: a reusable scikit-learn regression pipeline that predicts what each renewing subscription will be worth, then apply it to the open renewal pipeline.

> **Fictional data.** Corvana Networks, its products, customers, people and every number in this repository are invented for training. All datasets are synthetic and generated with a fixed random seed, so every participant sees the same numbers. Nothing here describes any real company's data, products or processes.

---

## The scenario

Corvana Networks sells networking, security, observability and collaboration software as annual subscriptions. Participants play **Ravi Iyer**, a Revenue Operations Analyst, working for **Meera Krishnan**, VP Customer Success.

Finance's FY27 plan assumes every renewing customer comes back at **today's contract value + 3%**. Meera wants to know:

1. How do we prepare the data properly (encoding, scaling, new features, no leakage) in a form we can rerun next month?
2. How much better than "today's ACV + 3%" can we forecast renewal value?
3. What moves renewal value up or down, and by how much?
4. How far off will we typically be, in dollars and in percent?
5. What does that mean for the **412 renewals** still open?

| Lab | Focus |
|---|---|
| **Lab 1**: Feature preparation | Split first, categorical encoding, scaling, feature engineering, feature selection, preprocessing leakage, `ColumnTransformer` + `Pipeline` |
| **Lab 2**: Regression modelling | Business baselines, simple and multiple linear regression, gradient descent, log target, residual analysis, polynomial features, Ridge / Lasso / ElasticNet, cross-validation, final model and forecast |
| **Wrap-up** | A short Renewal Value Forecast memo |

---

## Repository layout

```
.
├── data/
│   ├── renewals_day3.csv            # Day 3 training data
│   ├── open_renewals.csv            # Day 3 forecasting data
│   ├── accounts.csv                 # Days 1–2 (kept for reference)
│   ├── subscriptions.csv
│   ├── monthly_usage.csv
│   ├── renewal_pipeline_extract.txt
│   ├── pricing_rules.json
│   ├── renewals_raw_extract.csv
│   └── usage_raw_monthly.csv
├── requirements.txt
├── CHANGELOG.md
├── CODE_OF_CONDUCT.md
├── CONTRIBUTING.md
├── SECURITY.md
└── LICENSE
```

## Datasets

### Used on Day 3

| File | Rows | Grain | Notes |
|---|---|---|---|
| `renewals_day3.csv` | 795 (615 renewed) | One row per closed FY26 renewal | Output of Day 2's rule-based cleaning, with **missing values left in** so imputation happens inside the pipeline. Adds `customer_since`. |
| `open_renewals.csv` | 412 | One row per subscription still to renew | Same feature columns, no outcome. |

**Target:** `renewal_acv`, the new annual contract value in USD. Only the 615 renewed subscriptions are modelled, since renewal value exists only for customers who renewed. A derived target, `change_pct = renewal_acv / annual_contract_value - 1`, captures upsell or downsell.

### From Days 1–2

| File | Rows | Grain |
|---|---|---|
| `accounts.csv` | 600 | One row per customer account |
| `subscriptions.csv` | 1,207 | One row per subscription (account × product) |
| `monthly_usage.csv` | 14,484 | One row per subscription per month (Oct 2025 – Sep 2026) |
| `renewal_pipeline_extract.txt` | 120 records | Raw pipe-delimited CRM export with deliberate defects |
| `pricing_rules.json` | — | Price list, tier multipliers and discount bands |
| `renewals_raw_extract.csv` | 813 | Raw closed FY26 renewals with planted data-quality defects (incl. 18 duplicates) |
| `usage_raw_monthly.csv` | 9,540 | Monthly telemetry with gaps |

The Day 2 raw files contain **intentional** defects (mixed date formats, inconsistent labels, duplicates, gaps). Please don't "fix" them; they are part of the exercises.

---

## Getting started

### Option A: Google Colab

Colab already includes every library in `requirements.txt`. Upload the `data/` folder (or mount Google Drive) and start a new notebook.

### Option B: Local setup

Requires Python 3.10 or later.

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
jupyter lab
```

Then load the data from a notebook in the repository root:

```python
import pandas as pd

renewals = pd.read_csv("data/renewals_day3.csv", parse_dates=["renewal_date", "customer_since"])
renewed = renewals[renewals["renewal_status"] == "Renewed"]
open_renewals = pd.read_csv("data/open_renewals.csv", parse_dates=["renewal_date", "customer_since"])

print(renewed.shape, open_renewals.shape)  # (615, 31) (412, 25)
```

Use `random_state=42` for every split and model so your numbers match the reference results.

### Library versions

| Library | Minimum | Why |
|---|---|---|
| scikit-learn | 1.4 | `TargetEncoder` (1.3+), `OneHotEncoder(sparse_output=...)` (1.2+), pandas output |
| pandas | 2.2 | |
| numpy | 1.26 | |
| matplotlib / seaborn | 3.8 / 0.13 | Charts and residual plots |
| scipy | 1.11 | Spearman correlation in pandas |

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `ImportError: cannot import name 'TargetEncoder'` | `pip install -U scikit-learn` |
| `TypeError: ... unexpected keyword 'sparse_output'` | Upgrade scikit-learn |
| `ValueError: Pandas output does not support sparse data` | Pass `sparse_output=False` to `OneHotEncoder` |
| `ValueError: Input X contains NaN` | Fit the whole pipeline (with its imputer), not the model alone |
| `ConvergenceWarning` from Lasso / ElasticNet | Raise `max_iter` (e.g. 50,000) |
| Numbers differ slightly from a reference result | Check `random_state=42` everywhere; small differences across library versions are normal |

---

## Contributing

Issues and pull requests are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) and the [Code of Conduct](CODE_OF_CONDUCT.md). For security concerns, see [SECURITY.md](SECURITY.md).

## License

Released under the [MIT License](LICENSE).
