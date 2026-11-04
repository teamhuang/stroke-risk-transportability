"""Person-clustered internal reference for the four-country LOCO arm (supplementary).

Why this exists: run_loco_models.py takes the "internal" AUROC from modeling.internal_cv,
which splits at ROW level. China, Korea and Mexico contribute several respondent-waves per
person, so the same person appears in the training folds and in the held-out fold of that
internal CV. The LOCO fits themselves are unaffected - they respect the country boundary and
no person crosses countries - but the *reference* against which transportability decay is
computed is optimistic, and it gets more optimistic with every panel cohort added. MHAS puts
3.4 waves on each of 27,092 people, so the decay that carries the paper's central claim needs
a clustered companion number.

This script changes nothing in the primary arm. It re-fits the identical pipelines with
GroupKFold on `pid`, per country and pooled, and writes
  data/processed/intl/loco_intl_internal_clustered.csv
with internal AUROC under row-level and person-clustered splits side by side.

Usage: python run_loco_internal_clustered.py [std_dir]
"""
import os, sys, glob, numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))          # analysis/scripts
import modeling as M
from sklearn.model_selection import StratifiedGroupKFold

MODELS = ["logistic", "elasticnet", "random_forest", "gradient_boosting", "xgboost", "lightgbm"]
N_SPLITS = 5


def clustered_cv(X, y, groups, name, n_splits=N_SPLITS):
    """Out-of-fold predictions under a person-clustered split; same pipeline as primary."""
    oof = np.zeros(len(y))
    covered = np.zeros(len(y), bool)
    sgkf = StratifiedGroupKFold(n_splits=n_splits, shuffle=True, random_state=M.SEED)
    for tr, te in sgkf.split(X, y, groups):
        _, p = M.fit_predict(X.iloc[tr], y[tr], X.iloc[te], name)
        oof[te] = p
        covered[te] = True
    return oof, covered


def main():
    d = sys.argv[1] if len(sys.argv) > 1 else os.path.abspath(
        os.path.join(HERE, "..", "..", "..", "data", "processed", "intl"))
    from std_pool import std_files
    files = std_files(d)   # HRS is US too; see std_pool.py
    df = pd.concat([pd.read_csv(f) for f in files], ignore_index=True)
    df = df.reset_index(drop=True)
    X, y, _ = M.design(df)
    # a person is unique to one country, but pid strings are cohort-scoped -> cluster on cohort+pid
    groups = (df["cohort"].astype(str) + "|" + df["pid"].astype(str)).values
    print("clustered-internal | rows", len(df), "| persons", pd.Series(groups).nunique(),
          "| waves/person", round(len(df) / pd.Series(groups).nunique(), 2))

    # a person must not appear under two countries, otherwise the grouping would be wrong
    by_country = df.groupby("country")["pid"].nunique()
    print("persons per country:", by_country.to_dict())

    rows = []
    loco = pd.read_csv(os.path.join(d, "loco_intl_models.csv"))
    mean_loco = loco.groupby("model")["auroc"].mean()
    # row-level internal AUROC is taken from the primary run rather than recomputed:
    # it is the same frozen pipeline, so this costs nothing and cannot drift.
    rowlevel = loco.groupby("model")["internal_auroc"].first()
    for name in MODELS:
        row_auroc = float(rowlevel[name])
        oof, covered = clustered_cv(X, y, groups, name)
        m = M.compute_metrics(y[covered], oof[covered])
        lo, hi = M.bootstrap_ci(y[covered], oof[covered], "auroc")
        rows.append({"model": name, "internal_auroc_rowlevel": row_auroc,
                     "internal_auroc_clustered": m["auroc"], "clu_lo": lo, "clu_hi": hi,
                     "auprc_clustered": m["auprc"], "brier_clustered": m["brier"],
                     "cal_slope_clustered": m["cal_slope"], "rows_covered": int(covered.sum()),
                     "inflation_row_minus_clu": row_auroc - m["auroc"]})
        print(f"{name:18s} row-level {row_auroc:.4f} | clustered {m['auroc']:.4f} "
              f"[{lo:.4f}-{hi:.4f}] | inflation {row_auroc - m['auroc']:+.4f}", flush=True)
    out = pd.DataFrame(rows)

    # decay under each reference, joined to the primary LOCO table
    out["mean_loco_auroc"] = out["model"].map(mean_loco)
    out["decay_rowlevel"] = out["internal_auroc_rowlevel"] - out["mean_loco_auroc"]
    out["decay_clustered"] = out["internal_auroc_clustered"] - out["mean_loco_auroc"]
    out.to_csv(os.path.join(d, "loco_intl_internal_clustered.csv"), index=False)
    print("\n", out[["model", "internal_auroc_rowlevel", "internal_auroc_clustered",
                     "mean_loco_auroc", "decay_rowlevel", "decay_clustered"]].round(4).to_string(index=False))
    print("wrote", os.path.join(d, "loco_intl_internal_clustered.csv"))


if __name__ == "__main__":
    main()
