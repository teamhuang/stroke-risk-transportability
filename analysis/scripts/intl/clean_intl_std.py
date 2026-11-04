"""Build the CORRECTED international tables: data/processed/intl/corrected/std_*.csv

Takes the three cohorts whose mappings are right but whose value ranges are not
(NHANES, CHARLS, MHAS) and applies one shared plausibility rule, then reports exactly what
changed. KLoSA v2 arrives by a different route (klosa_reshape_v2.py rebuilds its mappings from
the wave files) and writes into the same directory.

Why this is needed: std_CHARLS.csv carries measured BMI values up to 52,734 kg/m^2
(59 rows outside 12-70, 12 above 500). Those are source keying errors, not bodies, and
logistic/elastic-net fit a StandardScaler on the training rows - so a handful of impossible
numbers rescale the BMI axis for every cohort and every held-out country.

Rules, applied identically to all four cohorts:
  1. adults only: age >= 20, matching the main NHANES study's inclusion criterion.
  2. bmi kept only inside 12-70 kg/m^2, else NaN (missing, then median-imputed from the
     training countries like any other genuine gap). Not zero-filled: an impossible value is
     an unobserved value.
  3. current_smoker forced to 0 where ever_smoker == 0 - the same structural-denominator rule
     the NHANES arm already applies ("never-smokers set 0 (structural)").
  4. any binary feature holding a value other than 0/1 stays NaN by construction.
Everything dropped is counted and printed; no row is silently altered.

Usage: python clean_intl_std.py
"""
import os, glob, numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.abspath(os.path.join(HERE, "..", "..", "..", "data", "processed", "intl"))
DST = os.path.join(SRC, "corrected")
COHORTS = ["NHANES", "CHARLS", "MHAS"]
ALLOWED = {"stroke": [0, 1], "sex": [1, 2], "education": [1, 2, 3], "marital": [1, 2],
           "ever_smoker": [0, 1], "current_smoker": [0, 1], "alcohol": [0, 1],
           "hypertension": [0, 1], "high_cholesterol": [0, 1], "diabetes": [0, 1],
           "heart_attack": [0, 1]}
BMI_RANGE = (12, 70)
MIN_AGE = 20


def clean(df):
    log = {}
    n0 = len(df)
    df = df[pd.to_numeric(df["age"], errors="coerce") >= MIN_AGE].copy()
    log["rows_dropped_under_age_20"] = n0 - len(df)

    b = pd.to_numeric(df["bmi"], errors="coerce")
    bad = b.notna() & ~b.between(*BMI_RANGE)
    log["bmi_impossible_to_nan"] = int(bad.sum())
    log["bmi_max_before"] = float(b.max()) if b.notna().any() else np.nan
    df.loc[bad, "bmi"] = np.nan
    log["bmi_mean_sd_after"] = f"{df['bmi'].mean():.2f} ({df['bmi'].std():.2f})"

    mis = (df["ever_smoker"] == 0) & (df["current_smoker"] == 1)
    log["current_smoker_structural_zero"] = int(mis.sum())
    df.loc[mis, "current_smoker"] = 0.0
    return df, log


def main():
    os.makedirs(DST, exist_ok=True)
    for c in COHORTS:
        src = os.path.join(SRC, f"std_{c}.csv")
        if not os.path.exists(src):
            print(f"  !! {src} missing, skipped"); continue
        df = pd.read_csv(src)
        out, log = clean(df)
        out.to_csv(os.path.join(DST, f"std_{c}.csv"), index=False)
        print(f"\n=== {c}: {len(df)} -> {len(out)} rows")
        for k, v in log.items():
            print(f"    {k:32s} {v}")
        violations = {}
        for col, lv in ALLOWED.items():
            if col in out:
                s = pd.to_numeric(out[col], errors="coerce").dropna()
                n = int((~s.isin(lv)).sum())
                if n:
                    violations[col] = n
        print("    codes outside the shared scheme:", violations or "none")
    print("\ncorrected dir ->", DST)
    print("files:", sorted(os.path.basename(f) for f in glob.glob(os.path.join(DST, "*.csv"))))


if __name__ == "__main__":
    main()
