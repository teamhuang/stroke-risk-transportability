"""Re-encode the existing NHANES harmonised table onto the SAME shared cross-cohort
scheme used by charls_reshape.py, so NHANES(US) and CHARLS(CN) are directly comparable
under leave-one-country-out validation.

This is an ADDITIONAL international arm only; it does NOT touch the NHANES single-country
study (that keeps its native 5-level education / 6-level marital / PIR / race encoding).

Shared scheme (identical on both sides):
  * sex        : NHANES source 1=male/0=female -> shared 1=male/2=female (matches CHARLS)
  * education  : 3-level {1 low, 2 upper-sec, 3 tertiary}
                 NHANES DMDEDUC2 1->1, 2->1, 3->2, 4->3, 5->3
                 CDC's five categories are 1 Less than 9th grade, 2 9th-11th grade,
                 3 High-school diploma or GED, 4 Some college or AA degree,
                 5 College graduate or above - there is no "postgrad" category, and codes 1-2 are
                 both BELOW upper secondary, so both map to low. The previous bridge put code 2
                 (9th-11th, no diploma) into upper-secondary, inflating US education relative to
                 the panels, which code low as "did not complete upper secondary".
  * marital    : 2-level {1 partnered, 2 not}
                 NHANES DMDMARTL 1,6->1 ; 2,3,4,5->2
  * income_pir : within-cohort z of log1p(PIR)  (CHARLS uses within-cohort z of log1p wealth)
  * bmi        : continuous (unchanged)
  * binary conditions / smoking / alcohol / stroke : 0/1 (unchanged)
  * race_ethnicity : DROPPED (CHARLS has no US-race variable; both cohorts must share an
                     identical feature set for a fair LOCO).

Usage: python build_nhanes_std.py [in_csv] [out_csv]
"""
import os, sys, numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
IN = os.path.abspath(os.path.join(HERE, "..", "..", "..", "data", "processed",
                                  "nhanes_stroke_harmonized.csv"))
OUT = os.path.abspath(os.path.join(HERE, "..", "..", "..", "data", "processed", "intl",
                                   "std_NHANES.csv"))
EDU = {1: 1, 2: 1, 3: 2, 4: 3, 5: 3}
MARR = {1: 1, 2: 2, 3: 2, 4: 2, 5: 2, 6: 1}
FEATS = ["stroke", "age", "sex", "education", "marital", "income_pir", "bmi",
         "ever_smoker", "current_smoker", "alcohol", "hypertension",
         "high_cholesterol", "diabetes", "heart_attack"]


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else IN
    out = sys.argv[2] if len(sys.argv) > 2 else OUT
    df = pd.read_csv(src)
    o = pd.DataFrame({"cohort": ["NHANES"] * len(df), "country": ["US"] * len(df),
                      "wave": df["cycle"].astype(str).values,
                      "pid": df["seqn"].values})
    o["stroke"] = pd.to_numeric(df["stroke"], errors="coerce").where(lambda s: s.isin([0, 1]))
    o["age"] = pd.to_numeric(df["age"], errors="coerce")
    o["sex"] = pd.to_numeric(df["sex"], errors="coerce").map({1: 1, 0: 2})  # NHANES 1=male/0=female -> shared 1=male/2=female
    o["education"] = pd.to_numeric(df["education"], errors="coerce").map(EDU)
    o["marital"] = pd.to_numeric(df["marital"], errors="coerce").map(MARR)
    o["bmi"] = pd.to_numeric(df["bmi"], errors="coerce")
    for c in ["ever_smoker", "current_smoker", "alcohol", "hypertension",
              "high_cholesterol", "diabetes", "heart_attack"]:
        o[c] = pd.to_numeric(df[c], errors="coerce").where(lambda s: s.isin([0, 1]))
    # income: within-cohort z of log1p(PIR)
    pir = pd.to_numeric(df["income_pir"], errors="coerce")
    lg = np.log1p(pir.where(pir >= 0))
    o["income_pir"] = (lg - lg.mean()) / (lg.std(ddof=0) if lg.std(ddof=0) else np.nan)
    o = o[o["stroke"].isin([0, 1])].copy()
    os.makedirs(os.path.dirname(out), exist_ok=True)
    o.to_csv(out, index=False)
    print(f"NHANES std -> {out}", file=sys.stderr)
    print(f"  rows {len(o)} | events {int(o.stroke.sum())} | prevalence {o.stroke.mean():.3f}", file=sys.stderr)
    print("  feature non-null %:", file=sys.stderr)
    print((o[FEATS].notna().mean() * 100).round(1).to_string(), file=sys.stderr)
    print("  education dist:", o.education.value_counts(dropna=False).sort_index().to_dict(), file=sys.stderr)
    print("  marital dist:", o.marital.value_counts(dropna=False).sort_index().to_dict(), file=sys.stderr)


if __name__ == "__main__":
    main()
