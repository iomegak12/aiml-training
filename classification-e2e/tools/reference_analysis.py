"""Reference analysis for the Northwind Finance loan-default use case.

Cleans the raw file, engineers features, and runs every classification step the use case describes.
Its printed output is the source of every number in docs/use_case.md ("Expected results").
"""
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from imblearn.over_sampling import SMOTE
from imblearn.pipeline import Pipeline as ImbPipeline
from imblearn.under_sampling import RandomUnderSampler
from sklearn.calibration import CalibratedClassifierCV
from sklearn.cluster import KMeans
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (average_precision_score, brier_score_loss, confusion_matrix, roc_auc_score,
                             silhouette_score)
from sklearn.model_selection import StratifiedKFold, cross_val_predict, cross_val_score
from sklearn.neighbors import KNeighborsClassifier
from sklearn.pipeline import Pipeline, make_pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parent.parent
pd.set_option("display.width", 160)
pd.set_option("display.max_columns", 30)

# ------------------------------------------------------------------ 1. profile
raw = pd.read_csv(ROOT / "data" / "loan_performance_raw.csv", dtype=str)
print("=== 1. raw profile ===")
print("rows", len(raw), "| columns", raw.shape[1], "| exact duplicate rows", int(raw.duplicated().sum()))
print("target values:", raw["defaulted_12m"].value_counts(dropna=False).to_dict())

# ------------------------------------------------------------------ 2. clean
df = raw.drop_duplicates().copy()
df["loan_id"] = df["loan_id"].str.strip().str.upper()
df = df.drop_duplicates(subset="loan_id", keep="last")
print("\n=== 2. cleaning ===")
print("after de-duplication:", len(df))

iso = pd.to_datetime(df["disbursal_date"], format="%Y-%m-%d", errors="coerce")
dmy = pd.to_datetime(df["disbursal_date"], format="%d/%m/%Y", errors="coerce")
df["disbursal_date"] = iso.fillna(dmy)


def money(s):
    return pd.to_numeric(s.str.replace("INR", "", regex=False).str.replace(",", "", regex=False).str.strip(),
                         errors="coerce")


df["annual_income"] = money(df["annual_income"])
num = ["age", "dependents", "years_employed", "credit_score", "credit_history_months", "existing_loans_count",
       "monthly_existing_emi", "past_delinquencies_24m", "enquiries_6m", "credit_card_utilization", "loan_amount",
       "tenure_months", "interest_rate", "emi", "max_dpd_12m"]
for c in num:
    df[c] = pd.to_numeric(df[c], errors="coerce")

maps = {
    "gender": {"m": "Male", "male": "Male", "f": "Female", "female": "Female", "o": "Other", "other": "Other"},
    "employment_type": {"salaried": "Salaried", "self-employed": "Self-Employed", "self employed": "Self-Employed",
                        "self_employed": "Self-Employed", "se": "Self-Employed", "business owner": "Business Owner",
                        "business": "Business Owner", "proprietor": "Business Owner"},
    "loan_purpose": {"home": "Home", "housing": "Home", "home loan": "Home", "personal": "Personal", "pl": "Personal",
                     "personal loan": "Personal", "auto": "Auto", "car": "Auto", "vehicle": "Auto",
                     "consumer durable": "Consumer Durable", "cd": "Consumer Durable", "durables": "Consumer Durable",
                     "business": "Business", "msme": "Business", "education": "Education", "edu": "Education"},
    "channel": {"dsa agent": "DSA Agent", "dsa": "DSA Agent", "agent": "DSA Agent", "online": "Online", "app": "Online",
                "web": "Online", "branch": "Branch", "partner merchant": "Partner Merchant", "partner": "Partner Merchant",
                "merchant": "Partner Merchant"},
}
for c, m in maps.items():
    df[c] = df[c].str.strip().str.lower().map(m)
df["has_collateral"] = df["has_collateral"].str.strip().str.lower().map(
    {"yes": 1, "y": 1, "true": 1, "1": 1, "no": 0, "n": 0, "false": 0, "0": 0})
df["defaulted"] = df["defaulted_12m"].str.strip().str.lower().map(
    {"yes": 1, "y": 1, "1": 1, "default": 1, "no": 0, "n": 0, "0": 0, "current": 0})

fixes = {
    "age out of 21-70 -> missing": df["age"].between(21, 70).eq(False) & df["age"].notna(),
    "credit score out of 300-900 -> missing": df["credit_score"].between(300, 900).eq(False) & df["credit_score"].notna(),
    "interest rate < 1 -> x100": df["interest_rate"] < 1,
    "card utilisation > 2 -> /100": df["credit_card_utilization"] > 2,
    "negative loan amount -> sign fixed": df["loan_amount"] < 0,
}
for k, m in fixes.items():
    print(f"  {k}: {int(m.sum())}")
df.loc[fixes["age out of 21-70 -> missing"], "age"] = np.nan
df.loc[fixes["credit score out of 300-900 -> missing"], "credit_score"] = np.nan
df.loc[fixes["interest rate < 1 -> x100"], "interest_rate"] *= 100
df.loc[fixes["card utilisation > 2 -> /100"], "credit_card_utilization"] /= 100
df["loan_amount"] = df["loan_amount"].abs()
print("unmapped categories left:", {c: int(df[c].isna().sum()) for c in maps})
print("rows without an outcome (dropped):", int(df["defaulted"].isna().sum()))
df = df[df["defaulted"].notna()].copy()
df["defaulted"] = df["defaulted"].astype(int)
print("modelling rows:", len(df), "| defaults:", int(df["defaulted"].sum()), "| default rate:", round(df["defaulted"].mean(), 4))


# ------------------------------------------------------------------ 3. features
def add_features(d):
    d = d.copy()
    monthly = d["annual_income"] / 12
    d["foir"] = (d["monthly_existing_emi"].fillna(0) + d["emi"]) / monthly
    d["loan_to_income"] = d["loan_amount"] / d["annual_income"]
    d["thin_file"] = (d["credit_history_months"] < 6).astype(int)
    d["has_credit_card"] = d["credit_card_utilization"].notna().astype(int)
    d["card_util_filled"] = d["credit_card_utilization"].fillna(0)
    d["log_income"] = np.log(d["annual_income"])
    return d


df = add_features(df)
print("\n=== 3. what moves default (univariate) ===")
print("thin file: default", round(df.loc[df.thin_file == 1, "defaulted"].mean(), 3), "vs", round(df.loc[df.thin_file == 0, "defaulted"].mean(), 3))
df["foir_band"] = pd.cut(df["foir"], [0, 0.3, 0.45, 0.6, 0.75, 10], labels=["<30%", "30-45%", "45-60%", "60-75%", "75%+"])
print(df.groupby("foir_band", observed=True)["defaulted"].agg(["count", "mean"]).round(3).T)
df["cs_band"] = pd.cut(df["credit_score"], [299, 650, 700, 750, 800, 900], labels=["<650", "650-699", "700-749", "750-799", "800+"])
print(df.groupby("cs_band", observed=True)["defaulted"].agg(["count", "mean"]).round(3).T)
print(df.groupby("loan_purpose")["defaulted"].mean().round(3).sort_values().to_dict())
print(df.groupby("channel")["defaulted"].mean().round(3).sort_values().to_dict())
print("employment:", df.groupby("employment_type")["defaulted"].mean().round(3).to_dict())
print("residence:", df.groupby("residence_type")["defaulted"].mean().round(3).to_dict())
print("past delinquencies 0 / 1 / 2+:", [float(round(df.loc[m, "defaulted"].mean(), 3)) for m in
      [df.past_delinquencies_24m == 0, df.past_delinquencies_24m == 1, df.past_delinquencies_24m >= 2]])
print("enquiries 0-1 / 2-3 / 4+:", [float(round(df.loc[m, "defaulted"].mean(), 3)) for m in
      [df.enquiries_6m <= 1, df.enquiries_6m.between(2, 3), df.enquiries_6m >= 4]])
TIER3 = ["Bhopal", "Mysuru", "Vijayawada", "Dehradun", "Guwahati", "Raipur"]
print("tier-3 cities vs others:", float(round(df.loc[df.city.isin(TIER3), "defaulted"].mean(), 3)),
      float(round(df.loc[df.city.notna() & ~df.city.isin(TIER3), "defaulted"].mean(), 3)))
print("by gender (actual default rate):", df.groupby("gender")["defaulted"].mean().round(3).to_dict())

NUM = ["age", "years_employed", "log_income", "credit_score", "credit_history_months", "thin_file",
       "existing_loans_count", "past_delinquencies_24m", "enquiries_6m", "has_credit_card", "card_util_filled",
       "foir", "loan_to_income", "tenure_months", "has_collateral", "dependents"]
CAT = ["employment_type", "loan_purpose", "channel", "residence_type", "education"]
FEATURES = NUM + CAT
EXCLUDED = {"gender, marital_status": "protected / sensitive: kept only for fairness checks",
            "max_dpd_12m, in_collections": "leakage: recorded after the outcome",
            "interest_rate": "set from the risk decision itself (circular for an approval model)",
            "loan_id, disbursal_date, city": "identifiers / time / high-cardinality location"}


def prep():
    return ColumnTransformer([
        ("num", make_pipeline(SimpleImputer(strategy="median", add_indicator=True), StandardScaler()), NUM),
        ("cat", make_pipeline(SimpleImputer(strategy="most_frequent"), OneHotEncoder(handle_unknown="ignore")), CAT),
    ])


def lr(**kw):
    return Pipeline([("prep", prep()), ("model", LogisticRegression(max_iter=2000, **kw))])


# ------------------------------------------------------------------ 4. out-of-time split
cut = pd.Timestamp("2024-07-01")
train, test = df[df["disbursal_date"] < cut], df[df["disbursal_date"] >= cut]
Xtr, ytr, Xte, yte = train[FEATURES], train["defaulted"], test[FEATURES], test["defaulted"]
print("\n=== 4. out-of-time split ===")
print("train (Jan 2023 - Jun 2024):", len(train), "default", round(ytr.mean(), 4), "| test (Jul - Dec 2024):", len(test), "default", round(yte.mean(), 4))
cv = StratifiedKFold(5, shuffle=True, random_state=42)

# ------------------------------------------------------------------ 5. models
print("\n=== 5. models (5-fold CV on train) ===")
res = {}
p_lr = cross_val_predict(lr(), Xtr, ytr, cv=cv, method="predict_proba")[:, 1]
res["logistic regression"] = p_lr
for C in [0.01, 0.1, 1, 10]:
    print(f"  logistic C={C}: CV AUC {cross_val_score(lr(C=C), Xtr, ytr, cv=cv, scoring='roc_auc').mean():.3f}")
l1 = lr(penalty="l1", C=0.01, solver="liblinear", random_state=42).fit(Xtr, ytr)
names = l1[0].get_feature_names_out()
kept = pd.Series(l1[-1].coef_[0], index=names)
print("  L1 (C=0.01) keeps", int((kept != 0).sum()), "of", len(kept), "| CV AUC",
      round(cross_val_score(lr(penalty="l1", C=0.01, solver="liblinear", random_state=42), Xtr, ytr, cv=cv, scoring="roc_auc").mean(), 3))

sub = train.sample(12000, random_state=1)
for k in [5, 25, 51, 101, 151]:
    knn = Pipeline([("prep", prep()), ("model", KNeighborsClassifier(n_neighbors=k))])
    print(f"  KNN k={k}: CV AUC {cross_val_score(knn, sub[FEATURES], sub['defaulted'], cv=cv, scoring='roc_auc').mean():.3f} (12,000-row sample)")
knn_best = Pipeline([("prep", prep()), ("model", KNeighborsClassifier(n_neighbors=101))])
p_knn = cross_val_predict(knn_best, Xtr, ytr, cv=cv, method="predict_proba")[:, 1]
res["KNN k=101"] = p_knn
raw_prep = ColumnTransformer([("num", SimpleImputer(strategy="median"), NUM)])
knn_raw = Pipeline([("prep", raw_prep), ("model", KNeighborsClassifier(n_neighbors=101))])
print(f"  KNN k=101 unscaled: CV AUC {cross_val_score(knn_raw, sub[FEATURES], sub['defaulted'], cv=cv, scoring='roc_auc').mean():.3f} (sample)")
for name, p in res.items():
    print(f"{name:<20} ROC AUC {roc_auc_score(ytr, p):.3f} | PR AUC {average_precision_score(ytr, p):.3f}")
print("random PR AUC = default rate", round(ytr.mean(), 3))

m = lr().fit(Xtr, ytr)
coef = pd.Series(m[-1].coef_[0], index=m[0].get_feature_names_out())
top = coef.reindex(coef.abs().sort_values(ascending=False).index).head(12)
print("\nTop logistic coefficients (per SD for numeric):")
print(pd.DataFrame({"coef": top, "odds_ratio": np.exp(top)}).round(3))

# leakage demo
leak = Pipeline([("prep", ColumnTransformer([("n", SimpleImputer(), ["max_dpd_12m"])])), ("m", LogisticRegression())])
print("\nLEAKAGE: model on max_dpd_12m alone, CV AUC", round(cross_val_score(leak, train, ytr, cv=cv, scoring="roc_auc").mean(), 3))
with_rate = Pipeline([("prep", ColumnTransformer([
    ("num", make_pipeline(SimpleImputer(strategy="median", add_indicator=True), StandardScaler()), NUM + ["interest_rate"]),
    ("cat", make_pipeline(SimpleImputer(strategy="most_frequent"), OneHotEncoder(handle_unknown="ignore")), CAT)])),
    ("model", LogisticRegression(max_iter=2000))])
print("with interest_rate added: CV AUC", round(cross_val_score(with_rate, train, ytr, cv=cv, scoring="roc_auc").mean(), 3))

# ------------------------------------------------------------------ 6. thresholds and money
print("\n=== 6. threshold economics (CV probabilities on train) ===")
MARGIN, LGD = 0.07, 0.45
print(f"assumptions: a good loan earns {MARGIN:.0%} of the amount; a default loses {LGD:.0%} of it -> break-even PD {MARGIN / (MARGIN + LGD):.3f}")
amt = train["loan_amount"].to_numpy()
rows = []
for t in [0.05, 0.08, 0.10, 0.12, 0.135, 0.15, 0.20, 0.25, 0.30, 0.50, 1.01]:
    approve = p_lr < t
    good, bad = approve & (ytr.to_numpy() == 0), approve & (ytr.to_numpy() == 1)
    profit = (MARGIN * amt[good].sum() - LGD * amt[bad].sum()) / 1e7      # crore
    rows.append({"reject_if_PD>=": t, "approval_rate": approve.mean(), "bad_rate_approved": ytr[approve].mean(),
                 "defaulters_rejected": 1 - bad.sum() / ytr.sum(), "goods_rejected": ((~approve) & (ytr == 0)).sum() / (ytr == 0).sum(),
                 "profit_crore": profit})
tt = pd.DataFrame(rows)
print(tt.round(3).to_string(index=False))
t_best = tt.loc[tt["profit_crore"].idxmax(), "reject_if_PD>="]
print("profit-maximising cut-off:", t_best)

# confusion at 0.5 vs chosen, on TEST (final check)
final = lr().fit(Xtr, ytr)
pte = final.predict_proba(Xte)[:, 1]
print("\n=== 7. final check on out-of-time test ===")
print(f"test ROC AUC {roc_auc_score(yte, pte):.3f} | PR AUC {average_precision_score(yte, pte):.3f} | Brier {brier_score_loss(yte, pte):.4f}")
for t in [0.5, t_best]:
    pred = (pte >= t).astype(int)
    tn, fp, fn, tp = confusion_matrix(yte, pred).ravel()
    print(f"cut-off {t}: TN {tn} FP {fp} FN {fn} TP {tp} | accuracy {(tp + tn) / len(yte):.3f} precision {tp / max(tp + fp, 1):.3f} "
          f"recall {tp / (tp + fn):.3f} | approval rate {(pred == 0).mean():.3f} | bad rate in approved {yte[pred == 0].mean():.3f}")
amt_te = test["loan_amount"].to_numpy()
for t in [1.01, t_best]:
    a = pte < t
    pr = (MARGIN * amt_te[a & (yte == 0)].sum() - LGD * amt_te[a & (yte == 1)].sum()) / 1e7
    print(f"  test profit, cut-off {t}: Rs {pr:.1f} crore (approve-everyone = 1.01)")
print("always 'no default' accuracy:", round(1 - yte.mean(), 3))

# ------------------------------------------------------------------ 8. calibration and imbalance
print("\n=== 8. calibration and imbalance (CV on train) ===")
p_bal = cross_val_predict(lr(class_weight="balanced"), Xtr, ytr, cv=cv, method="predict_proba")[:, 1]
cal = CalibratedClassifierCV(lr(class_weight="balanced"), method="sigmoid", cv=5)
p_cal = cross_val_predict(cal, Xtr, ytr, cv=cv, method="predict_proba")[:, 1]
for name, p in [("plain", p_lr), ("balanced", p_bal), ("balanced + calibrated", p_cal)]:
    q = pd.qcut(p, 5, labels=False)
    print(f"{name:<22} AUC {roc_auc_score(ytr, p):.3f} Brier {brier_score_loss(ytr, p):.4f} mean PD {p.mean():.3f} (actual {ytr.mean():.3f}) "
          f"| top-fifth predicted {p[q == 4].mean():.3f} vs actual {ytr[q == 4].mean():.3f}")
for name, sampler in [("SMOTE", SMOTE(random_state=42)), ("under-sampling", RandomUnderSampler(random_state=42))]:
    pipe = ImbPipeline([("prep", prep()), ("s", sampler), ("model", LogisticRegression(max_iter=2000))])
    p = cross_val_predict(pipe, Xtr, ytr, cv=cv, method="predict_proba")[:, 1]
    print(f"{name:<22} AUC {roc_auc_score(ytr, p):.3f} Brier {brier_score_loss(ytr, p):.4f} mean PD {p.mean():.3f}")
print("expected loss on test book (PD x LGD x amount), Rs crore: plain",
      round((pte * LGD * amt_te).sum() / 1e7, 1), "| actual loss", round((yte * LGD * amt_te).sum() / 1e7, 1))
fb = lr(class_weight="balanced").fit(Xtr, ytr).predict_proba(Xte)[:, 1]
print("  balanced model would forecast", round((fb * LGD * amt_te).sum() / 1e7, 1))

# ------------------------------------------------------------------ 9. fairness
print("\n=== 9. fairness check on test at the chosen cut-off ===")
tg = test.assign(approved=(pte < t_best).astype(int), pd_hat=pte)
print(tg.groupby("gender")[["defaulted", "pd_hat", "approved"]].mean().round(3))
print(tg.groupby(pd.cut(tg["age"], [20, 25, 35, 50, 70]), observed=True)[["defaulted", "pd_hat", "approved"]].mean().round(3))

# ------------------------------------------------------------------ 10. segments
print("\n=== 10. K-Means borrower segments ===")
SEG = ["log_income", "credit_score", "foir", "card_util_filled", "age", "credit_history_months"]
S = df[SEG].copy(); S = S.fillna(S.median())
Z = StandardScaler().fit_transform(S)
zs = Z[np.random.default_rng(0).choice(len(Z), 8000, replace=False)]
for k in range(2, 8):
    km = KMeans(k, n_init=10, random_state=42).fit(Z)
    print(f"  k={k} inertia {km.inertia_:.0f} silhouette {silhouette_score(zs, km.predict(zs)):.3f}")
K = 4
km = KMeans(K, n_init=10, random_state=42).fit(Z)
df["segment"] = km.labels_
prof = df.groupby("segment").agg(borrowers=("loan_id", "count"), income_median=("annual_income", "median"),
                                 credit_score=("credit_score", "mean"), foir=("foir", "median"),
                                 card_util=("card_util_filled", "mean"), age=("age", "mean"),
                                 history_m=("credit_history_months", "mean"), thin_file=("thin_file", "mean"),
                                 default_rate=("defaulted", "mean"))
print(prof.round(3))

# ------------------------------------------------------------------ 11. score new applications
print("\n=== 11. new applications ===")
final_all = lr().fit(df[FEATURES], df["defaulted"])
new = add_features(pd.read_csv(ROOT / "data" / "new_applications_sample.csv"))
new["has_collateral"] = new["has_collateral"].map({"Yes": 1, "No": 0})
new["pd"] = final_all.predict_proba(new[FEATURES])[:, 1]
new["decision"] = np.where(new["pd"] < t_best, "Approve", "Refer / decline")
new["expected_loss"] = new["pd"] * LGD * new["loan_amount"]
print(new[["application_id", "loan_purpose", "loan_amount", "credit_score", "foir", "pd", "decision", "expected_loss"]]
      .round({"foir": 2, "pd": 3, "expected_loss": 0}).to_string(index=False))

# ------------------------------------------------------------------ 12. sensitivity: drop age
NUM_NOAGE = [c for c in NUM if c != "age"]
p_noage = ColumnTransformer([
    ("num", make_pipeline(SimpleImputer(strategy="median", add_indicator=True), StandardScaler()), NUM_NOAGE),
    ("cat", make_pipeline(SimpleImputer(strategy="most_frequent"), OneHotEncoder(handle_unknown="ignore")), CAT)])
m_noage = Pipeline([("prep", p_noage), ("model", LogisticRegression(max_iter=2000))])
print("\n=== 12. sensitivity ===")
print("CV AUC without age:", round(cross_val_score(m_noage, Xtr, ytr, cv=cv, scoring="roc_auc").mean(), 3))
