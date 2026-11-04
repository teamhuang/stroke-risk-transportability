"""Apply a CONFIRMED mapping to a raw cohort file -> standardised 14-feature + stroke CSV.

The mapping is produced by a human after running discover_intl.py, so variable names are
never guessed. Concept that a cohort genuinely lacks -> NaN (reported, not fabricated).

Usage: python harmonize_intl.py raw_file.dta mapping.json cohort_name country > out.csv
mapping.json = {
  "stroke": {"var":"X","recode":"yes_no"},
  "age":    {"var":"X","recode":"cont"},
  ... one entry per canonical concept; "recode" in {cont, yes_no, cat, binary_01}
}
Canonical concepts: stroke,age,sex,education,marital,income_pir,bmi,ever_smoker,
current_smoker,alcohol,hypertension,high_cholesterol,diabetes,heart_attack
"""
import os, sys, json, numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from discover_intl import read_any
import config as C

CANON = ["stroke","age","sex","education","marital","income_pir","bmi","ever_smoker",
         "current_smoker","alcohol","hypertension","high_cholesterol","diabetes","heart_attack"]
MISS = [7,9,77,99,777,999,55,66,666,555,15]

def recode(x, kind):
    x = pd.Series(pd.to_numeric(pd.Series(x), errors="coerce")).copy()
    x[x.isin(MISS)] = np.nan
    if kind == "cont":      return x
    if kind == "yes_no":    return x.map({1:1, 2:0}).astype("float64")   # 1 yes,2 no
    if kind == "binary_01": return x.map({0:0, 1:1}).astype("float64")
    if kind == "cat":       return x
    raise ValueError(kind)

def main():
    if len(sys.argv) < 5:
        print(__doc__); sys.exit(0)
    raw, mpath, cohort, country = sys.argv[1:5]
    df, labels, _ = read_any(raw)
    mapping = json.load(open(mpath))
    out = pd.DataFrame({"cohort": [cohort]*len(df), "country": [country]*len(df)})
    report = {}
    for concept in CANON:
        spec = mapping.get(concept)
        if not spec or spec["var"] not in df.columns:
            out[concept] = np.nan; report[concept] = "ABSENT"; continue
        out[concept] = recode(df[spec["var"]].values, spec.get("recode","cont")).values
        report[concept] = f"{spec['var']} ({spec.get('recode','cont')})"
    # canonicalise sex to 1=male/0=female if stored 1/2
    if "sex" in out and out["sex"].dropna().max() and out["sex"].dropna().max() > 1:
        out["sex"] = out["sex"].map({1:1,2:0}).astype("float64")
    # require determinable stroke
    out = out[out["stroke"].isin([0,1])].copy()
    print("MAPPING REPORT", cohort, country, "rows:", len(out), file=sys.stderr)
    for k,v in report.items(): print(f"  {k:16s}: {v}", file=sys.stderr)
    dest_dir = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                            "..","..","..","data","processed","intl"))
    os.makedirs(dest_dir, exist_ok=True)
    dest = os.path.join(dest_dir, f"std_{cohort}.csv")
    out.to_csv(dest, index=False)
    print("wrote", dest, file=sys.stderr)

if __name__ == "__main__":
    main()
