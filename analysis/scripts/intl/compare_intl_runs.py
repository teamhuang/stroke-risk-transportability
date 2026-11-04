"""Compare international-arm LOCO runs side by side (3-country / 4-country / corrected).

Reads any number of loco_intl_models.csv files given as NAME=path and writes one tidy
comparison per metric to results/tables/intl_run_comparison.csv, so a change in the reported
Korea decay can be attributed to a specific data decision instead of argued about.

Usage: python compare_intl_runs.py old3=path new4=path corrected=path [metric:auroc|decay|cal_slope|brier]
"""
import os, sys, numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results", "tables"))


def main():
    runs, metric = {}, "auroc"
    for a in sys.argv[1:]:
        if a.startswith("metric:"):
            metric = a.split(":", 1)[1]; continue
        name, path = a.split("=", 1)
        runs[name] = pd.read_csv(path)
    if not runs:
        print(__doc__); return
    base = None
    for name, df in runs.items():
        w = df.pivot_table(index="model", columns="held_country", values=metric).round(4)
        w["MEAN"] = df.groupby("model")[metric].mean().round(4)
        w["internal"] = df.groupby("model")["internal_auroc"].first().round(4)
        long = w.reset_index().melt(id_vars="model", var_name="held", value_name=metric)
        long.insert(0, "run", name)
        base = long if base is None else pd.concat([base, long], ignore_index=True)
    wide = base.pivot_table(index=["model", "held"], columns="run", values=metric)
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, f"intl_run_comparison_{metric}.csv")
    wide.to_csv(path)
    print(f"metric = {metric}")
    print(wide.to_string())
    print("\nwrote", path)


if __name__ == "__main__":
    main()
