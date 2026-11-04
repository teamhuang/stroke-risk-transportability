"""Print Table 5 (internal vs transferred discrimination) from published tables only.

Two reasons this exists as a printer rather than as typed markdown.

1. The manuscript claims nothing is transcribed by hand, and Table 5 was the one main table that had
   no printer behind it. Every cell here is read out of
   `results/tables/incident_internal_clustered_2026-11-03.csv`, and the held-out range is recomputed
   from that file's own per-country columns instead of being quoted.
2. The column the CSV calls `decay_clustered` is a descriptive difference, not a measure of
   generalisation capacity: it is confounded by case-mix, outcome definition, predictor distributions,
   follow-up length and event rate, and four countries cannot support a statement about a
   between-country random effect. The header it is printed under says so. The CSV column name is
   unchanged, because renaming it would desynchronise the producer from every published table that
   already carries it; this file is the translation point.

Usage: python make_table5_rows.py
"""
import os, sys
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
T = os.path.join(ROOT, "results", "tables")
DAY = "2026-11-03"
ORDER = [("elasticnet", "Elastic net logistic"), ("logistic", "**Logistic**"),
         ("spline_logistic", "Spline logistic"),
         ("random_forest", "Random forest (unweighted)"),
         ("random_forest_balanced", "Random forest, balanced"),
         ("xgboost", "XGBoost"), ("gradient_boosting", "Gradient boosting"),
         ("lightgbm", "LightGBM"), ("agesex_logistic", "Age + sex only")]
LABEL = dict(ORDER)


def main():
    ic = pd.read_csv(os.path.join(T, f"incident_internal_clustered_{DAY}.csv"))
    ic = ic[(ic.feature_set == "common") & (ic.time == "linear") & (ic.level == "interval")]
    if ic.empty:
        sys.exit("no common/linear/interval rows in the published internal table")
    print("### Table 5. Internal performance, transferred performance and the "
          "internal-to-external discrimination difference (interval scale, person-clustered reference)")
    print()
    print("| Model | Internal AUROC (person-clustered CV, pooled four panels) | "
          "Internal AUROC (row-level CV) | Mean held-out AUROC | "
          "Internal-to-external difference (clustered − mean held-out) | Held-out range |")
    print("|---|---|---|---|---|---|")
    missing = []
    for key, label in ORDER:
        r = ic[ic.model == key]
        if r.empty:
            missing.append(key)
            continue
        r = r.iloc[0]
        per = r[[c for c in ic.columns if c.startswith("auroc_held_")]].astype(float)
        print(f"| {label} | {r.auroc_clustered:.4f} | {r.auroc_rowlevel:.4f} | "
              f"{r.mean_loco:.4f} | {r.decay_clustered:+.4f} | "
              f"{per.max() - per.min():.3f} |")
    if missing:
        sys.exit(f"models absent from the published table (do not type them in): {missing}")

    print("\nPer-country held-out AUROC behind the range, same file:")
    print()
    print("| Model | " + " | ".join(LABEL[k] for k, _ in ORDER if (ic.model == k).any()) + " |")
    hdr = [k for k, _ in ORDER if (ic.model == k).any()]
    print("|---|" + "---|" * len(hdr))
    for c in sorted([x for x in ic.columns if x.startswith("auroc_held_")]):
        held = c.replace("auroc_held_", "")
        vals = []
        for k in hdr:
            r = ic[ic.model == k]
            vals.append(f"{r.iloc[0][c]:.4f}")
        print(f"| {held} | " + " | ".join(vals) + " |")

    # the spread statistic the Results text quotes: max minus min over the four holdouts, per model
    sp = []
    for k, label in ORDER:
        r = ic[ic.model == k]
        if r.empty:
            continue
        per = r.iloc[0][[c for c in ic.columns if c.startswith("auroc_held_")]].astype(float)
        sp.append((label, float(r.iloc[0].decay_clustered), float(per.max() - per.min())))
    lin = [s for s in sp if "logistic" in s[0].lower().replace("**", "").replace(" ", "_")]
    ens = [s for s in sp if s[0].split()[0] in ("Random", "XGBoost", "Gradient", "LightGBM")]
    if lin and ens:
        ratio = (np.mean([e[1] for e in ens]) / np.mean([l[1] for l in lin]))
        print(f"\nmean internal-to-external difference: linear family "
              f"{np.mean([l[1] for l in lin]):+.4f}, ensemble family {np.mean([e[1] for e in ens]):+.4f} "
              f"-> ratio {ratio:.2f}")
        print("mean held-out range: linear "
              f"{np.mean([l[2] for l in lin]):.3f}, ensemble {np.mean([e[2] for e in ens]):.3f}")
    # the per-panel sign flip the manuscript quotes, checked rather than asserted
    lin_keys = ["elasticnet", "logistic", "spline_logistic"]
    ens_keys = ["random_forest", "random_forest_balanced", "xgboost",
                "gradient_boosting", "lightgbm"]
    for c in sorted([x for x in ic.columns if x.startswith("auroc_held_")]):
        per = ic.set_index("model")[c]
        have_lin = [k for k in lin_keys if k in per.index]
        have_ens = [k for k in ens_keys if k in per.index]
        if not have_lin or not have_ens:
            continue
        base = per[have_lin].max()
        gain = [per[k] - base for k in have_ens]
        eight = per[[k for k in have_lin + have_ens]]
        print(f"  {c.replace('auroc_held_', '')}: ensembles vs best linear "
              f"{min(gain):+.4f} to {max(gain):+.4f}; eight-learner spread "
              f"{eight.max() - eight.min():.4f}")

    print("\nThis difference is descriptive. It mixes case-mix, outcome definition, predictor "
          "distributions, follow-up length and event rate, and four countries cannot identify a "
          "between-country variance component; it is reported because the *ordering* of models by "
          "internal fit is not the ordering by transferred fit, not because the size of the drop is a "
          "property of the learner.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
