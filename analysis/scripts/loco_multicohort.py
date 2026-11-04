"""Pluggable multi-cohort LEAVE-ONE-COHORT-OUT (LOCO) module.

This is the true international version of the study design. It runs on a single
harmonised CSV where each row is one participant and columns are:

    cohort, country, stroke,
    age, sex, race_ethnicity, education, marital, income_pir, bmi,
    ever_smoker, current_smoker, alcohol, hypertension, high_cholesterol,
    diabetes, heart_attack
    (optional) weight, psu, strata

To obtain the international cohorts (all free, registration-required — unlike NHANES):
  * CHARLS  https://charls.pku.edu.cn  (China)
  * ELSA    https://www.elsa-project.ac.uk  (England)
  * HRS     https://hrs.isr.umich.edu  (USA)
  * SHARE   https://share-eric.eu  (continental Europe)
Harmonise each to the columns above (same 14 features, same binary/categorical coding),
concatenate, then run:

    python loco_multicohort.py harmonized_intl.csv

The script performs country-level LOCO (train on all-but-one country, test on the held
country), reports AUROC / Brier / calibration slope per country with bootstrap CIs, and
the mean transportability decay — the analysis that would upgrade the manuscript from a
single-country + subgroup design to a genuine four-country LOCO study. It reuses the
exact, synthetic-validated pipeline in modeling.py, so no new code path is introduced.

A built-in synthetic demo (no file argument) proves the module runs end-to-end.
"""
import os, sys, numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(__file__))
import modeling as M, config as C

FEATURES = C.FEATURES  # the canonical 14

def loco(df):
    X, y, _ = M.design(df)
    countries = sorted(df["country"].dropna().unique())
    rows = []
    for c in countries:
        tr = df["country"].values != c
        te = df["country"].values == c
        if y[te].sum() < 5 or y[tr].sum() < 5:
            rows.append({"held_country": c, "n": int(te.sum()), "events": int(y[te].sum()),
                         "auroc": np.nan, "brier": np.nan, "cal_slope": np.nan,
                         "note": "insufficient events"}); continue
        _, p = M.fit_predict(X[tr], y[tr], X[te], "logistic")
        m = M.compute_metrics(y[te], p)
        lo, hi = M.bootstrap_ci(y[te], p, "auroc")
        rows.append({"held_country": c, "n": m["n"], "events": m["events"],
                     "prevalence": m["prevalence"], "auroc": m["auroc"],
                     "auroc_lo": lo, "auroc_hi": hi, "brier": m["brier"],
                     "cal_intercept": m["cal_intercept"], "cal_slope": m["cal_slope"],
                     "note": "ok"})
    out = pd.DataFrame(rows)
    ok = out[out.note == "ok"]
    # mean decay vs a pooled internal AUROC
    pooled = M.compute_metrics(y, M.internal_cv(df, "logistic")["_oof"])
    out.attrs["mean_loco_auroc"] = float(ok["auroc"].mean())
    out.attrs["internal_auroc"] = pooled["auroc"]
    out.attrs["mean_decay"] = pooled["auroc"] - float(ok["auroc"].mean())
    return out

def demo():
    rng = np.random.default_rng(C.SEED)
    frames = []
    for i, cn in enumerate(["US", "EN", "CN", "EU"]):
        n = 3000 + rng.integers(0, 1500)
        age = rng.normal(55 + i, 15, n).clip(20, 90)
        htn = rng.binomial(1, .3 + .05*i, n); dm = rng.binomial(1, .12, n)
        mi = rng.binomial(1, .06, n); es = rng.binomial(1, .4, n)
        cs = (es == 1) * rng.binomial(1, .3, n); al = rng.binomial(1, .5, n)
        bmi = rng.normal(28, 5, n); pir = rng.normal(2.5, 1.3, n).clip(.1, 6)
        lp = (-4 + .05*(age-55) + .6*htn + .5*dm + .5*mi + .3*es + .2*cs - .1*(pir-2.5) + .02*(bmi-28))
        if i == 3: lp *= 0.7   # induce real cross-country attenuation
        p = 1/(1+np.exp(-lp)); y = rng.binomial(1, p)
        d = pd.DataFrame({"cohort": f"demo_{cn}", "country": cn, "age": age,
            "sex": rng.binomial(1,.5,n)+1, "race_ethnicity": rng.integers(1,6,n),
            "education": rng.integers(1,6,n), "marital": rng.integers(1,7,n),
            "income_pir": pir, "bmi": bmi, "ever_smoker": es, "current_smoker": cs,
            "alcohol": al, "hypertension": htn, "high_cholesterol": rng.binomial(1,.4,n),
            "diabetes": dm, "heart_attack": mi, "stroke": y})
        frames.append(d)
    df = pd.concat(frames, ignore_index=True)
    return df

def main():
    if len(sys.argv) > 1:
        df = pd.read_csv(sys.argv[1]); src = sys.argv[1]
    else:
        df = demo(); src = "SYNTHETIC DEMO (replace with harmonized_intl.csv)"
    miss = [c for c in ["country","stroke"]+FEATURES if c not in df.columns]
    if miss: raise SystemExit(f"input missing columns: {miss}")
    print("LOCO on:", src, "| rows", len(df), "| countries", df.country.nunique())
    out = loco(df)
    print(out.round(4).to_string(index=False))
    print(f"\ninternal AUROC {out.attrs['internal_auroc']:.3f} | "
          f"mean LOCO AUROC {out.attrs['mean_loco_auroc']:.3f} | "
          f"mean decay {out.attrs['mean_decay']:+.3f}")
    out.to_csv(os.path.join(os.path.dirname(__file__), "..", "output", "loco_multicohort.csv"), index=False)

if __name__ == "__main__":
    main()
