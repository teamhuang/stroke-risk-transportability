"""Multi-model leave-one-country-out (LOCO) for the real international arm (US NHANES +
China CHARLS + Korea KLoSA). For every held-out country and every classifier we train on the
other countries' data and test on the held-out country, reporting AUROC / AUPRC / Brier /
calibration slope with cluster-free bootstrap CIs, plus the pooled internal-CV AUROC so
the transportability decay is comparable across model families.

Reuses the exact synthetic-validated pipeline in modeling.py (leakage-aware: imputer +
scaler fit on the TRAIN country only). No new estimator config is introduced.

Usage: python run_loco_models.py [std_dir]
"""
import os, sys, glob, json, numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))          # analysis/scripts
import modeling as M

MODELS = ["logistic", "elasticnet", "random_forest", "gradient_boosting", "xgboost", "lightgbm"]
BOOT = 1000
SEED = M.SEED


def main():
    d = sys.argv[1] if len(sys.argv) > 1 else os.path.abspath(
        os.path.join(HERE, "..", "..", "..", "data", "processed", "intl"))
    from std_pool import std_files
    files = std_files(d)   # HRS is US too; see std_pool.py
    df = pd.concat([pd.read_csv(f) for f in files], ignore_index=True)
    X, y, _ = M.design(df)
    countries = sorted(df["country"].dropna().unique())
    print("LOCO-models | rows", len(df), "| countries", countries, "| events", int(y.sum()))

    rows = []
    for model in MODELS:
        # pooled internal CV (pooled countries) as the reference discrimination
        try:
            oof = M.internal_cv(df, model)["_oof"]
            internal = M.compute_metrics(y, oof)["auroc"]
        except Exception as e:
            internal = np.nan
        for c in countries:
            tr = (df["country"].values != c)
            te = (df["country"].values == c)
            if y[te].sum() < 5 or y[tr].sum() < 5:
                continue
            _, p = M.fit_predict(X[tr], y[tr], X[te], model)
            m = M.compute_metrics(y[te], p)
            lo, hi = M.bootstrap_ci(y[te], p, "auroc")
            rows.append({"model": model, "held_country": c, "n": m["n"], "events": m["events"],
                         "prevalence": m["prevalence"], "auroc": m["auroc"],
                         "auroc_lo": lo, "auroc_hi": hi, "auprc": m["auprc"],
                         "brier": m["brier"], "cal_intercept": m["cal_intercept"],
                         "cal_slope": m["cal_slope"], "internal_auroc": internal,
                         "decay": internal - m["auroc"]})
    out = pd.DataFrame(rows)
    out.to_csv(os.path.join(d, "loco_intl_models.csv"), index=False)
    # console summary
    pv = out.pivot_table(index="model", columns="held_country", values="auroc")
    pv["mean_LOCO"] = out.groupby("model")["auroc"].mean()
    pv["internal"] = out.groupby("model")["internal_auroc"].first()
    pv["mean_decay"] = out.groupby("model")["decay"].mean()
    print("\n=== AUROC by model x held-out country ===")
    print(pv.round(3).to_string())
    print("\nwrote", os.path.join(d, "loco_intl_models.csv"))


if __name__ == "__main__":
    main()
