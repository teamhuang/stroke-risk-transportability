"""Descriptive table for the four-country international arm (rows = respondent-waves).

Reads std_*.csv from data/processed/intl (or a directory given as argv[1], e.g. the corrected
pool) and writes results/tables/intl_arm_characteristics.csv - or
intl_arm_characteristics_<name>.csv for a named subdirectory - one column per country plus a
pooled column. Everything is unweighted and row-level unless stated; the missingness block is
printed because three features are imputed from the training countries during LOCO, so a reader
must see which cells were never observed.

Usage: python make_intl_table1.py [std_dir]
"""
import os, sys, glob, numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
D = os.path.abspath(os.path.join(HERE, "..", "..", "..", "data", "processed", "intl"))
OUT = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results", "tables"))

FEATS = ["age", "sex", "education", "marital", "income_pir", "bmi", "ever_smoker",
         "current_smoker", "alcohol", "hypertension", "high_cholesterol", "diabetes",
         "heart_attack"]
BINARY = ["ever_smoker", "current_smoker", "alcohol", "hypertension", "high_cholesterol",
          "diabetes", "heart_attack"]
MEAN = ["age", "income_pir", "bmi"]
NAME = {"US": "United States (NHANES)", "CN": "China (CHARLS)",
        "KR": "Korea (KLoSA)", "MX": "Mexico (MHAS)"}


def describe(df):
    # every percentage uses the OBSERVED denominator, so a cohort that never asked the item
    # cannot masquerade as a cohort where the answer was no
    def pct(mask, s):
        den = int(s.notna().sum())
        return round(100 * float((mask & s.notna()).sum()) / den, 1) if den else None
    r = {}
    r["rows (respondent-waves)"] = len(df)
    # person identity is cohort-scoped: bare pid strings collide across cohorts, so pooling
    # nunique() on pid alone undercounts people
    r["adults"] = (df["cohort"].astype(str) + "|" + df["pid"].astype(str)).nunique()
    r["waves per adult"] = round(len(df) / max(r["adults"], 1), 2)
    r["prevalent strokes"] = int(df["stroke"].sum())
    r["stroke prevalence, %"] = round(100 * df["stroke"].mean(), 2)
    for c in MEAN:
        r[f"{c}, mean (sd)"] = (f"{df[c].mean():.2f} ({df[c].std():.2f})"
                                if df[c].notna().any() else "not observed")
    r["female, % of observed"] = pct(df["sex"] == 2, df["sex"])
    for v, lab in [(1, "low"), (2, "upper-secondary"), (3, "tertiary")]:
        r[f"education {lab}, % of observed"] = pct(df["education"] == v, df["education"])
    r["partnered, % of observed"] = pct(df["marital"] == 1, df["marital"])
    for c in BINARY:
        r[f"{c}, % of observed"] = pct(df[c] == 1, df[c])
    for c in ["bmi", "income_pir", "high_cholesterol", "education", "marital"]:
        r[f"{c} missing, %"] = round(100 * df[c].isna().mean(), 1)
    return r


def main():
    global D
    tag = ""
    if len(sys.argv) > 1:
        D = os.path.abspath(sys.argv[1])
        tag = "_" + os.path.basename(D.rstrip("\\/"))
    os.makedirs(OUT, exist_ok=True)
    cols = {}
    from std_pool import std_files
    for f in std_files(D):
        df = pd.read_csv(f)
        cols[NAME.get(df["country"].iloc[0], df["country"].iloc[0])] = describe(df)
    pooled = pd.concat([pd.read_csv(f) for f in std_files(D)],
                       ignore_index=True)
    cols["Pooled (all countries)"] = describe(pooled)
    out = pd.DataFrame(cols)
    out.insert(0, "Characteristic", out.index)
    path = os.path.join(OUT, f"intl_arm_characteristics{tag}.csv")
    out.to_csv(path, index=False)
    print(out.to_string(index=False))
    print("\nwrote", path)


if __name__ == "__main__":
    main()
