"""Concatenate standardised cohort files -> run country-level LOCO -> figures + summary.

Usage: python assemble_loco.py [dir_with_std_*.csv]
Defaults to ../../../data/processed/intl. Reuses the synthetic-validated modeling pipeline.
"""
import os, sys, glob, json, numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))            # analysis/scripts (config, modeling)
sys.path.insert(0, HERE)                              # intl (loco_multicohort)
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
import config as C, modeling as M
from loco_multicohort import loco

CM = 5.5/2.54
plt.rcParams.update({"font.family":"sans-serif","font.sans-serif":["Arial","DejaVu Sans"],
    "pdf.fonttype":42,"font.size":7,"axes.spines.top":False,"axes.spines.right":False,
    "axes.grid":True,"grid.alpha":.25,"grid.linestyle":"--","figure.dpi":300})
OI={"blue":"#0072B2","orange":"#E69F00","green":"#009E73","verm":"#D55E00","purple":"#CC79A7","grey":"#999999"}

def main():
    d = sys.argv[1] if len(sys.argv)>1 else os.path.abspath(os.path.join(HERE,"..","..","..","data","processed","intl"))
    from std_pool import std_files
    files = std_files(d)   # HRS is US too; see std_pool.py
    if not files:
        print("no std_*.csv found in", d); sys.exit(1)
    df = pd.concat([pd.read_csv(f) for f in files], ignore_index=True)
    print("concatenated:", len(df), "rows | countries:", sorted(df.country.unique()),
          "| events:", int(df.stroke.sum()))
    out = loco(df)
    out = out.sort_values("auroc")
    out.to_csv(os.path.join(d,"loco_intl_results.csv"), index=False)
    summary = {"countries": out.held_country.tolist(),
               "internal_auroc": out.attrs["internal_auroc"],
               "mean_loco_auroc": out.attrs["mean_loco_auroc"],
               "mean_decay": out.attrs["mean_decay"],
               "per_country": out.to_dict("records")}
    json.dump(summary, open(os.path.join(d,"loco_intl_summary.json"),"w"), indent=2, default=float)
    print(out.round(4).to_string(index=False))
    print(f"\ninternal {out.attrs['internal_auroc']:.3f} | mean LOCO {out.attrs['mean_loco_auroc']:.3f} | decay {out.attrs['mean_decay']:+.3f}")

    figdir = os.path.join(d,"figures"); os.makedirs(figdir, exist_ok=True)
    def bar(vals, ylab, title, fname, ref=None, refcol=None):
        fig,ax=plt.subplots(figsize=(CM,CM)); x=np.arange(len(vals))
        ax.bar(x, vals, color=OI["blue"], edgecolor="black", lw=.4)
        if ref is not None: ax.axhline(ref, color=refcol or OI["grey"], lw=.8, ls="--")
        ax.set_xticks(x); ax.set_xticklabels(out.held_country, fontsize=6)
        ax.set_ylabel(ylab); ax.set_title(title); fig.savefig(os.path.join(figdir,fname+".png"),dpi=300,bbox_inches="tight")
        fig.savefig(os.path.join(figdir,fname+".pdf"),bbox_inches="tight"); plt.close(fig)
    bar(out.auroc.values, "AUROC (held-out country)", "Country LOCO discrimination",
        "loco_auroc", ref=out.attrs["internal_auroc"], refcol=OI["verm"])
    bar(out.brier.values, "Brier", "Country LOCO calibration (Brier)", "loco_brier")
    bar(out.cal_slope.values, "Calibration slope", "Country LOCO calibration slope",
        "loco_calslope", ref=1.0, refcol=OI["grey"])
    print("figures ->", figdir)

if __name__=="__main__":
    main()
