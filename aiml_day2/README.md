# Corvana Day 2 Kit

Practice kit for Days 1-2: Python, the core data libraries (NumPy, pandas, Matplotlib, seaborn) and first machine-learning models with scikit-learn.

The exercises use a subscription-renewal dataset for a fictional company, Corvana Networks.

## Setup

Google Colab already includes every dependency. For a local setup:

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
jupyter lab
```

## Data

Everything lives in [data/](data/).

| File | Contents |
| --- | --- |
| `accounts.csv` | One row per customer account: industry, segment, region, size, sales channel. |
| `subscriptions.csv` | One row per subscription: product, tier, seats, pricing, term, usage summary, renewal outcome. |
| `monthly_usage.csv` | Monthly usage per subscription: active users, seat utilization, feature adoption, support tickets. |
| `pricing_rules.json` | List price per seat per year for each product, plus pricing rules. |
| `renewals_raw_extract.csv` | Raw renewals extract joining account and subscription fields. Deliberately messy (mixed date formats, missing values) for cleaning practice. |
| `usage_raw_monthly.csv` | Raw monthly usage with gaps in `active_users`. |
| `renewal_pipeline_extract.txt` | Pipe-delimited CRM export of the renewal pipeline, with a comment line above the header. |

Tables join on `account_id` and `subscription_id`.

## License

[MIT](LICENSE)
