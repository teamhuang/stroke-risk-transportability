"""Build a harmonised, respondent-wave standardised table for KLoSA (Korea) directly
from the original KLoSA wave Excel files (w01..w09), replicating the concept mapping of
the Gateway creation code for the variables we could CONFIRM against the real files.

No Stata is available, so the Gateway .do is used only as a REFERENCE for which question
code = which concept and the value coding; each mapping below was checked against the
actual wave-1 (and spot-checked later-wave) distributions. Where a concept cannot be
confidently mapped it is set to NaN and reported (never fabricated).

CONFIRMED mapping (KLoSA codes 1=yes / 5=no for the diagnosis block):
  stroke        = w{v}C038   (1->1, 5->0; code 3 'transient/other' -> NaN)
  hypertension  = w{v}C006   (1->1, 5->0)
  diabetes      = w{v}C011   (1->1, 5->0)
  heart_attack  = w{v}C033   (1->1, 5->0)   [ever told heart disease]
  ever_smoker   = w{v}C116   (1->1, 5->0)
  current_smoker= w{v}C117   (1->1, 5->0; NaN where not asked)
  alcohol       = w{v}C119   (1-7 ->1 drinks at least occasionally, 8 ->0 never, else NaN)
  education     = w{v}A003   -> shared 3-level via Gateway raeducl {1-4->1, 5->2, 6-9->3}
  sex           = w{v}gender1 (1 male->1, 5 female->2)
  age           = w{v}A001_age (w1) / w{v}A002_age (w2-9) / w{v}age2 fallback
  marital       = w{v}marital (w2-9; 1 married->1 partnered, 2-5 ->2 not; w1 absent->NaN)
GAPS (set NaN, reported): bmi, income_pir, high_cholesterol  (no clean harmonised source
  in the KLoSA core waves; w01wgt_c is a survey weight, not body weight).

Unit = respondent x wave. Usage: python klosa_reshape.py [out_csv]
"""
import os, sys, numpy as np, pandas as pd, warnings
warnings.filterwarnings("ignore")

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.abspath(os.path.join(HERE, "..", "..", "..", "data", "raw", "intl", "KLoSA"))
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.abspath(
    os.path.join(HERE, "..", "..", "..", "data", "processed", "intl", "std_KLoSA.csv"))
COHORT, COUNTRY = "KLoSA", "KR"
WAVES = list(range(1, 10))


def yesno(s):
    s = pd.to_numeric(pd.Series(s), errors="coerce")
    return s.where(s.isin([1, 5])).map({1: 1.0, 5: 0.0})


def edu(s):
    s = pd.to_numeric(pd.Series(s), errors="coerce")
    return s.where(s.between(1, 9)).map(lambda v: 1 if v <= 4 else (2 if v == 5 else 3))


def sex(s):
    s = pd.to_numeric(pd.Series(s), errors="coerce")
    return s.where(s.isin([1, 5])).map({1: 1.0, 5: 2.0})


def alcohol(s):
    s = pd.to_numeric(pd.Series(s), errors="coerce")
    return s.where(s.between(1, 8)).map(lambda v: 0.0 if v == 8 else 1.0)


def marital(s):
    s = pd.to_numeric(pd.Series(s), errors="coerce")
    return s.where(s.between(1, 5)).map(lambda v: 1.0 if v == 1 else 2.0)


def getcol(df, name):
    return df[name] if name in df.columns else pd.Series(np.nan, index=df.index)


def main():
    frames = []
    for wv in WAVES:
        fn = os.path.join(BASE, f"w{wv:02d}_e.xlsx")
        if not os.path.exists(fn):
            print(f"  !! missing {fn}", file=sys.stderr); continue
        p = f"w{wv:02d}"
        df = pd.read_excel(fn, engine="calamine")
        agecol = f"{p}A001_age" if f"{p}A001_age" in df.columns else (
            f"{p}A002_age" if f"{p}A002_age" in df.columns else f"{p}age2")
        row = {
            "cohort": [COHORT] * len(df), "country": [COUNTRY] * len(df),
            "wave": [wv] * len(df), "pid": pd.to_numeric(getcol(df, "pid"), errors="coerce").values,
            "stroke": yesno(getcol(df, f"{p}C038")).values,
            "age": pd.to_numeric(getcol(df, agecol), errors="coerce").values,
            "sex": sex(getcol(df, f"{p}gender1")).values,
            "education": edu(getcol(df, f"{p}A003")).values,
            "marital": marital(getcol(df, f"{p}marital")).values,
            "income_pir": np.full(len(df), np.nan),
            "bmi": np.full(len(df), np.nan),
            "ever_smoker": yesno(getcol(df, f"{p}C116")).values,
            "current_smoker": yesno(getcol(df, f"{p}C117")).values,
            "alcohol": alcohol(getcol(df, f"{p}C119")).values,
            "hypertension": yesno(getcol(df, f"{p}C006")).values,
            "high_cholesterol": np.full(len(df), np.nan),
            "diabetes": yesno(getcol(df, f"{p}C011")).values,
            "heart_attack": yesno(getcol(df, f"{p}C033")).values,
        }
        frames.append(pd.DataFrame(row))
    long = pd.concat(frames, ignore_index=True)
    long = long[long["pid"].notna() & long["stroke"].isin([0, 1])].copy()
    FEATS = ["stroke", "age", "sex", "education", "marital", "income_pir", "bmi",
             "ever_smoker", "current_smoker", "alcohol", "hypertension",
             "high_cholesterol", "diabetes", "heart_attack"]
    std = long[["cohort", "country", "wave", "pid"] + FEATS].copy()
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    std.to_csv(OUT, index=False)
    print(f"KLoSA reshape -> {OUT}", file=sys.stderr)
    print(f"  respondent-wave rows {len(std)} | persons {std['pid'].nunique()} | "
          f"stroke {int(std.stroke.sum())} (prev {std.stroke.mean():.3f})", file=sys.stderr)
    print((std[FEATS].notna().mean() * 100).round(1).to_string(), file=sys.stderr)
    print("  GAPS: bmi / income_pir / high_cholesterol = NaN (no clean KLoSA core source)", file=sys.stderr)


if __name__ == "__main__":
    main()
