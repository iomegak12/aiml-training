"""
Synthetic raw loan-performance data for Northwind Finance (FICTIONAL lender, synthetic data).

One row per DISBURSED loan (Jan 2023 - Dec 2024), with what was known at application time
and the 12-month repayment outcome.

Target: defaulted_12m = the loan reached 90+ days past due within 12 months of disbursal.

Ground truth (hidden from participants): the log-odds of default are linear in credit score,
repayment burden (FOIR, with an extra jump above 65%), recent delinquencies, enquiries,
credit-card utilisation, thin credit file, employment, purpose, collateral, channel and youth.
Gender has NO effect. Raw-data problems are planted after the clean values (see PLANTED).
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

rng = np.random.default_rng(20261014)
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data"
OUT.mkdir(parents=True, exist_ok=True)
N_LOANS = 49_400      # unique loans; 600 duplicate rows are added -> 50,000 raw rows
N = N_LOANS + 10      # 10 extra applicants are held out as "new applications" (never in the training file)

# ------------------------------------------------------------------ applicants
CITIES = {  # city: (tier, weight)
    "Mumbai": (1, 9), "Delhi": (1, 9), "Bengaluru": (1, 9), "Hyderabad": (1, 6), "Chennai": (1, 6),
    "Pune": (1, 5), "Kolkata": (1, 5), "Gurugram": (1, 4), "Ahmedabad": (2, 4), "Jaipur": (2, 3),
    "Lucknow": (2, 3), "Kochi": (2, 3), "Indore": (2, 3), "Coimbatore": (2, 3), "Chandigarh": (2, 3),
    "Nagpur": (2, 2), "Bhopal": (3, 2), "Mysuru": (3, 2), "Vijayawada": (3, 2), "Dehradun": (3, 2),
    "Guwahati": (3, 2), "Raipur": (3, 2),
}
city_names = list(CITIES)
w = np.array([CITIES[c][1] for c in city_names], float)
city = rng.choice(city_names, N, p=w / w.sum())
tier = np.array([CITIES[c][0] for c in city])

age = np.clip(rng.normal(35, 9, N).round(), 21, 65).astype(int)
gender = rng.choice(["Male", "Female", "Other"], N, p=[0.60, 0.39, 0.01])
marital = np.where(age < 27, rng.choice(["Single", "Married"], N, p=[0.75, 0.25]),
                   rng.choice(["Single", "Married", "Divorced", "Widowed"], N, p=[0.2, 0.72, 0.06, 0.02]))
dependents = np.where(marital == "Single", rng.choice([0, 1], N, p=[0.85, 0.15]),
                      rng.choice([0, 1, 2, 3, 4], N, p=[0.15, 0.3, 0.35, 0.15, 0.05]))
education = rng.choice(["Graduate", "Postgraduate", "Diploma", "Higher Secondary"], N, p=[0.48, 0.25, 0.15, 0.12])
employment = rng.choice(["Salaried", "Self-Employed", "Business Owner"], N, p=[0.64, 0.22, 0.14])
max_exp = np.maximum(age - 21, 0)
years_employed = np.round(np.minimum(rng.gamma(2.2, 3.5, N), max_exp + 0.5) * (rng.random(N) < 0.98), 1)
p_own = np.clip(0.05 + 0.017 * (age - 21), 0.05, 0.75)
u = rng.random(N)
residence = np.where(u < p_own, "Owned",
                     np.where(u < p_own + (1 - p_own) * np.where(age < 28, 0.45, 0.15), "Family", "Rented"))

log_inc = (np.log(620_000) + 0.25 * (tier == 1) - 0.15 * (tier == 3)
           + 0.18 * (education == "Postgraduate") - 0.20 * (education == "Higher Secondary")
           + 0.025 * np.minimum(years_employed, 25)
           + np.select([employment == "Self-Employed", employment == "Business Owner"], [0.10, 0.35], 0)
           + rng.normal(0, 0.45 + 0.20 * (employment != "Salaried"), N))
annual_income = np.round(np.exp(log_inc), -3)
monthly_income = annual_income / 12

# ------------------------------------------------------------------ credit bureau
credit_history_months = np.round(np.maximum(0, (age - 21) * 12 * rng.uniform(0.15, 1.0, N)
                                             + rng.normal(6, 6, N))).astype(int)
credit_history_months = np.where(rng.random(N) < 0.07, rng.integers(0, 6, N), credit_history_months)
thin_file = credit_history_months < 6
credit_score = np.clip(rng.normal(718, 62, N) + 0.04 * np.minimum(credit_history_months, 240)
                       - 30 * (rng.random(N) < 0.08), 300, 900).round()
past_delinq = rng.poisson(np.exp(-2.2 + (700 - credit_score) / 55))
past_delinq = np.where(thin_file, 0, np.minimum(past_delinq, 9))
enquiries = rng.poisson(0.9 + 0.6 * (credit_score < 680) + 0.5 * (age < 30))
existing_loans = rng.choice([0, 1, 2, 3, 4], N, p=[0.40, 0.31, 0.17, 0.09, 0.03])
existing_loans = np.where(thin_file, 0, existing_loans)
existing_emi = np.where(existing_loans == 0, 0,
                        np.round(monthly_income * rng.uniform(0.04, 0.11, N) * existing_loans, -2))
has_card = (rng.random(N) < np.where(thin_file, 0.10, 0.62))
cc_util = np.where(has_card, np.clip(rng.beta(2.0, 3.2, N) + 0.25 * (credit_score < 680)
                                     + rng.normal(0, 0.05, N), 0.0, 1.15), np.nan)
cc_util = np.round(cc_util, 2)

# ------------------------------------------------------------------ the loan
PURPOSE = {  # purpose: (weight, tenure range months, base rate %, income multiple median, secured)
    "Home": (0.22, (120, 300), 8.7, 3.2, True),
    "Personal": (0.30, (12, 60), 13.0, 0.45, False),
    "Auto": (0.18, (36, 84), 9.4, 0.65, True),
    "Education": (0.08, (36, 120), 10.5, 0.8, False),
    "Business": (0.12, (12, 60), 14.0, 0.9, False),
    "Consumer Durable": (0.10, (6, 24), 15.5, 0.12, False),
}
purposes = list(PURPOSE)
purpose = rng.choice(purposes, N, p=[PURPOSE[p][0] for p in purposes])
tenure = np.array([rng.integers(PURPOSE[p][1][0] // 6, PURPOSE[p][1][1] // 6 + 1) * 6 for p in purpose])
mult = np.array([PURPOSE[p][3] for p in purpose])
loan_amount = np.round(annual_income * mult * np.exp(rng.normal(0, 0.35, N)), -3)
loan_amount = np.maximum(loan_amount, 15_000)
secured = np.array([PURPOSE[p][4] for p in purpose])
has_collateral = np.where(secured, True, (purpose == "Business") & (rng.random(N) < 0.30))
channel = np.where(purpose == "Consumer Durable",
                   rng.choice(["Partner Merchant", "Online"], N, p=[0.8, 0.2]),
                   rng.choice(["Branch", "Online", "DSA Agent", "Partner Merchant"], N, p=[0.38, 0.32, 0.27, 0.03]))
base_rate = np.array([PURPOSE[p][2] for p in purpose])
interest_rate = np.round(base_rate + np.clip((760 - credit_score) / 35, -1.0, 5.0) + 1.0 * thin_file
                         - 0.4 * has_collateral + rng.normal(0, 0.35, N), 2)
r = interest_rate / 100 / 12
emi = np.round(loan_amount * r / (1 - (1 + r) ** -tenure), 0)
foir = (existing_emi + emi) / monthly_income

start = pd.Timestamp("2023-01-01")
disb = start + pd.to_timedelta(rng.integers(0, 731, N), unit="D")

# ------------------------------------------------------------------ ground-truth default (90+ DPD within 12 months)
cs_eff = np.where(thin_file, 690, credit_score)
purpose_eff = pd.Series(purpose).map({"Home": -0.45, "Personal": 0.35, "Auto": -0.10, "Education": 0.10,
                                      "Business": 0.45, "Consumer Durable": 0.25}).to_numpy()
channel_eff = pd.Series(channel).map({"Branch": 0.0, "Online": 0.10, "DSA Agent": 0.35,
                                      "Partner Merchant": 0.15}).to_numpy()
logit = (-3.00
         - 0.0115 * (cs_eff - 720)
         + 0.55 * thin_file
         + 2.0 * (foir - 0.45) + 3.0 * np.maximum(foir - 0.65, 0)
         + 0.35 * past_delinq
         + 0.12 * enquiries
         + np.where(has_card, 1.1 * (np.nan_to_num(cc_util) - 0.35), 0)
         + 0.35 * (employment == "Self-Employed") + 0.25 * (employment == "Business Owner")
         - 0.03 * np.minimum(years_employed, 10)
         + purpose_eff - 0.35 * has_collateral + channel_eff
         + 0.25 * (age < 25) + 0.15 * (residence == "Rented")
         - 0.10 * (education == "Postgraduate") + 0.10 * (tier == 3))
p_default = 1 / (1 + np.exp(-logit))
defaulted = rng.random(N) < p_default

# post-outcome (leakage) columns
max_dpd = np.where(defaulted, rng.integers(90, 181, N),
                   np.where(rng.random(N) < 0.18, rng.choice([5, 10, 15, 30, 45, 60], N), 0))
in_collections = np.where(defaulted, rng.random(N) < 0.92, (max_dpd >= 30) & (rng.random(N) < 0.5))

df = pd.DataFrame({
    "loan_id": [f"NWL-{i:06d}" for i in range(1, N + 1)],
    "disbursal_date": disb.strftime("%Y-%m-%d"),
    "age": age.astype(float),
    "gender": gender,
    "marital_status": marital,
    "dependents": dependents.astype(float),
    "education": education,
    "city": city,
    "residence_type": residence,
    "employment_type": employment,
    "years_employed": years_employed,
    "annual_income": annual_income,
    "credit_score": np.where(thin_file & (rng.random(N) < 0.85), np.nan, credit_score),
    "credit_history_months": credit_history_months.astype(float),
    "existing_loans_count": existing_loans,
    "monthly_existing_emi": existing_emi,
    "past_delinquencies_24m": past_delinq,
    "enquiries_6m": enquiries.astype(float),
    "credit_card_utilization": cc_util,
    "loan_purpose": purpose,
    "loan_amount": loan_amount,
    "tenure_months": tenure,
    "interest_rate": interest_rate,
    "emi": emi,
    "has_collateral": has_collateral,
    "channel": channel,
    "max_dpd_12m": max_dpd,
    "in_collections": np.where(in_collections, "Yes", "No"),
    "defaulted_12m": np.where(defaulted, "Yes", "No"),
}).astype(object)

# hold out the last 10 as brand-new applications (clean, no outcome, no leakage columns)
holdout = df.iloc[N_LOANS:].copy()
df = df.iloc[:N_LOANS].copy()
N = N_LOANS
thin_file = thin_file[:N]

PLANTED = {"thin-file applicants with no credit score (meaningful missing)": int(df["credit_score"].isna().sum())}


def rows(share=None, k=None, mask=None):
    pool = np.arange(N) if mask is None else np.flatnonzero(mask)
    k = k if k is not None else int(len(pool) * share)
    return rng.choice(pool, k, replace=False)


# ---- random missing values
for col, share in [("credit_score", 0.015), ("years_employed", 0.025), ("dependents", 0.02),
                   ("marital_status", 0.015), ("education", 0.02), ("annual_income", 0.007),
                   ("residence_type", 0.015), ("city", 0.01), ("enquiries_6m", 0.01)]:
    i = rows(share, mask=df[col].notna().to_numpy())
    df.loc[i, col] = np.nan
    PLANTED[f"missing {col} (random)"] = len(i)
i = rows(0.003); df.loc[i, "defaulted_12m"] = np.nan; PLANTED["missing target (outcome not recorded)"] = len(i)


# ---- inconsistent categories
def vary(col, mapping, share):
    n_changed = 0
    for src, variants in mapping.items():
        m = (df[col] == src).to_numpy() & (rng.random(N) < share)
        df.loc[m, col] = rng.choice(variants, int(m.sum()))
        n_changed += int(m.sum())
    PLANTED[f"{col} spelling variants"] = n_changed


vary("gender", {"Male": ["M", "male", "MALE", " Male"], "Female": ["F", "female", "FEMALE", "Female "],
                "Other": ["O", "other"]}, 0.15)
vary("employment_type", {"Salaried": ["salaried", "SALARIED", "Salaried "],
                         "Self-Employed": ["Self Employed", "self-employed", "Self_Employed", "SE"],
                         "Business Owner": ["Business", "business owner", "Proprietor"]}, 0.12)
vary("loan_purpose", {"Home": ["home", "Housing", "HOME LOAN"], "Personal": ["personal", "PL", "Personal Loan"],
                      "Auto": ["Car", "auto", "Vehicle"], "Consumer Durable": ["Consumer durable", "CD", "Durables"],
                      "Business": ["business", "MSME"], "Education": ["education", "Edu"]}, 0.08)
vary("channel", {"DSA Agent": ["DSA", "dsa agent", "Agent"], "Online": ["online", "App", "Web"],
                 "Branch": ["branch", "BRANCH"], "Partner Merchant": ["Partner", "Merchant"]}, 0.08)
vary("defaulted_12m", {"Yes": ["Y", "1", "Default"], "No": ["N", "0", "Current"]}, 0.06)

# yes/no formats for collateral
hc = df["has_collateral"].astype(bool).to_numpy()
fmt = rng.choice(["Yes/No", "Y/N", "TRUE/FALSE", "1/0"], N, p=[0.70, 0.12, 0.10, 0.08])
df["has_collateral"] = [{"Yes/No": ("Yes", "No"), "Y/N": ("Y", "N"), "TRUE/FALSE": ("TRUE", "FALSE"),
                         "1/0": ("1", "0")}[f][0 if v else 1] for f, v in zip(fmt, hc)]
PLANTED["has_collateral formats (Yes/No, Y/N, TRUE/FALSE, 1/0)"] = 4

# ---- format problems
i = rows(0.08)
df.loc[i, "disbursal_date"] = pd.to_datetime(df.loc[i, "disbursal_date"]).dt.strftime("%d/%m/%Y").to_numpy()
PLANTED["dates in DD/MM/YYYY"] = len(i)


def inr(x):
    s = f"{int(x)}"
    if len(s) <= 3:
        return s
    head, tail = s[:-3], s[-3:]
    parts = []
    while len(head) > 2:
        parts.insert(0, head[-2:]); head = head[:-2]
    if head:
        parts.insert(0, head)
    return ",".join(parts) + "," + tail


i = rows(0.05, mask=df["annual_income"].notna().to_numpy())
df.loc[i, "annual_income"] = [inr(v) for v in df.loc[i, "annual_income"]]
PLANTED["income as text with Indian commas (e.g. 10,87,000)"] = len(i)
i = rows(k=150, mask=df["annual_income"].map(lambda v: isinstance(v, float) and not np.isnan(v)).to_numpy())
df.loc[i, "annual_income"] = [f"INR {int(v)}" for v in df.loc[i, "annual_income"]]
PLANTED["income with 'INR ' prefix"] = len(i)

# ---- invalid values
i = rows(k=25); df.loc[i, "age"] = rng.choice([0, -1, 150, 999], len(i)); PLANTED["impossible age"] = len(i)
i = rows(k=40, mask=df["credit_score"].notna().to_numpy())
df.loc[i, "credit_score"] = rng.choice([0, 999, 1200], len(i)); PLANTED["impossible credit score"] = len(i)
i = rows(0.005); df.loc[i, "interest_rate"] = (df.loc[i, "interest_rate"].astype(float) / 100).round(4)
PLANTED["interest rate as a fraction (0.125 instead of 12.5)"] = len(i)
i = rows(0.01, mask=df["credit_card_utilization"].notna().to_numpy())
df.loc[i, "credit_card_utilization"] = (df.loc[i, "credit_card_utilization"].astype(float) * 100).round(0)
PLANTED["card utilisation in percent (75 instead of 0.75)"] = len(i)
i = rows(k=12); df.loc[i, "loan_amount"] = -df.loc[i, "loan_amount"].astype(float); PLANTED["negative loan amount"] = len(i)

# ---- duplicates
dup_exact = df.iloc[rows(k=450)].copy()
dup_rekey = df.iloc[rows(k=150)].copy()
dup_rekey["loan_id"] = [rng.choice([s.lower(), f" {s}", f"{s} "]) for s in dup_rekey["loan_id"]]
raw = pd.concat([df, dup_exact, dup_rekey], ignore_index=True)
raw = raw.sample(frac=1, random_state=7).reset_index(drop=True)
PLANTED["exact duplicate rows"] = 450
PLANTED["same loan with re-formatted ID (case / spaces)"] = 150
PLANTED["leakage columns (recorded after the outcome)"] = "max_dpd_12m, in_collections"

raw.to_csv(OUT / "loan_performance_raw.csv", index=False)
(ROOT / "tools" / "planted_issues.json").write_text(json.dumps(PLANTED, indent=2))

# ---- 10 new applications to score (2025, clean, no outcome and no leakage columns)
new = holdout.drop(columns=["max_dpd_12m", "in_collections", "defaulted_12m"]).copy()
new["has_collateral"] = np.where(new["has_collateral"].astype(bool), "Yes", "No")
new["loan_id"] = [f"NWL-APP-{i:04d}" for i in range(1, 11)]
new = new.rename(columns={"loan_id": "application_id", "disbursal_date": "application_date"})
new["application_date"] = pd.date_range("2025-03-03", periods=10, freq="3D").strftime("%Y-%m-%d")
for c in ["age", "dependents", "credit_score", "credit_history_months", "enquiries_6m", "annual_income",
          "monthly_existing_emi", "loan_amount", "emi"]:
    new[c] = pd.to_numeric(new[c]).astype("Int64")
new.to_csv(OUT / "new_applications_sample.csv", index=False)

print("raw rows:", len(raw), "| unique loans:", N, "| true default rate:", round(defaulted[:N].mean(), 4))
print(json.dumps(PLANTED, indent=2))
