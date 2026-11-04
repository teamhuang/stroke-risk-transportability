"""Figures for the REAL international arm (leave-one-country-out: US NHANES x China CHARLS
x Korea KLoSA x Mexico MHAS).

Reads loco_intl_models.csv from the arm's directory (default data/processed/intl, pass a path
to render e.g. the corrected pool at data/processed/intl/corrected) and emits one independent
panel per figure (5.5 x 5.5 cm), PNG (300 dpi) + vector PDF, Okabe-Ito colour-blind-safe
palette, Arial. Mirrors the main study's figure hygiene.

Panels
  intl_auroc        grouped AUROC by model x held-out country (+ internal marker)
  intl_decay        mean transportability decay by model (simple vs complex)
  intl_calslope     calibration slope by model x held-out country (ref = 1.0)
  intl_scatter      internal vs mean LOCO AUROC per model (y = x reference)

Usage: python make_figures_intl.py
"""
import os, sys, numpy as np, pandas as pd
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
D = os.path.abspath(os.path.join(HERE, "..", "..", "..", "data", "processed", "intl"))
FIG = os.path.join(D, "figures"); os.makedirs(FIG, exist_ok=True)

CM = 5.5 / 2.54
plt.rcParams.update({"font.family": "sans-serif", "font.sans-serif": ["Arial", "DejaVu Sans"],
                     "pdf.fonttype": 42, "ps.fonttype": 42, "font.size": 7,
                     "axes.spines.top": False, "axes.spines.right": False,
                     "axes.grid": True, "grid.alpha": .25, "grid.linestyle": "--",
                     "figure.dpi": 300})
# Okabe-Ito colour-blind-safe
OI = {"blue": "#0072B2", "orange": "#E69F00", "green": "#009E73", "verm": "#D55E00",
      "purple": "#CC79A7", "sky": "#56B4E9", "grey": "#999999", "yellow": "#F0E442"}
SHORT = {"logistic": "Logit", "elasticnet": "ElasticNet", "random_forest": "RF",
         "gradient_boosting": "GB", "xgboost": "XGB", "lightgbm": "LGBM"}
ORDER = ["logistic", "elasticnet", "random_forest", "xgboost", "gradient_boosting", "lightgbm"]
SIMPLE = {"logistic", "elasticnet"}


def save(fig, name):
    fig.savefig(os.path.join(FIG, name + ".png"), dpi=300, bbox_inches="tight")
    fig.savefig(os.path.join(FIG, name + ".pdf"), bbox_inches="tight")
    plt.close(fig)


def main():
    global D, FIG
    if len(sys.argv) > 1:
        D = os.path.abspath(sys.argv[1])
        FIG = os.path.join(D, "figures")
        os.makedirs(FIG, exist_ok=True)
    df = pd.read_csv(os.path.join(D, "loco_intl_models.csv"))
    df["model"] = pd.Categorical(df["model"], ORDER, ordered=True)
    df = df.sort_values("model")
    models = ORDER
    countries = sorted(df.held_country.unique())
    COUNTRY_LABEL = {"CN": "China", "KR": "Korea", "US": "United States", "MX": "Mexico",
                     "EN": "England", "EU": "Europe"}
    PAL = [OI["blue"], OI["orange"], OI["green"], OI["verm"], OI["purple"], OI["sky"]]
    per = {c: df[df.held_country == c].set_index("model").reindex(models) for c in countries}
    x = np.arange(len(models))

    # ---- Panel 1: grouped AUROC by model x country
    fig, ax = plt.subplots(figsize=(CM, CM))
    nc = len(countries)
    w = 0.8 / nc
    for k, c in enumerate(countries):
        d = per[c]
        off = (k - (nc - 1) / 2) * w
        ax.bar(x + off, d.auroc, w, color=PAL[k % len(PAL)],
               label=COUNTRY_LABEL.get(c, c), edgecolor="k", lw=.3)
        ax.errorbar(x + off, d.auroc,
                    yerr=[d.auroc - d.auroc_lo, d.auroc_hi - d.auroc],
                    fmt="none", ecolor="k", elinewidth=.5, capsize=1.2)
    ax.axhline(0.5, color=OI["grey"], lw=.6, ls=":")
    ax.set_xticks(x); ax.set_xticklabels([SHORT[m] for m in models], rotation=45, ha="right", fontsize=6)
    ax.set_ylabel("AUROC (95% CI)"); ax.set_ylim(0.45, 0.92); ax.set_title("LOCO discrimination", fontsize=8)
    ax.legend(fontsize=5, frameon=False, loc="upper center", ncol=nc)
    save(fig, "intl_auroc")

    # ---- Panel 2: mean transportability decay by model
    dec = df.groupby("model", observed=True)["decay"].mean().reindex(models)
    fig, ax = plt.subplots(figsize=(CM, CM))
    cols = [OI["green"] if m in SIMPLE else OI["verm"] for m in models]
    ax.bar(x, dec.values, 0.62, color=cols, edgecolor="k", lw=.3)
    ax.axhline(0, color="k", lw=.6)
    for xi, v in zip(x, dec.values):
        ax.text(xi, v + (0.001 if v >= 0 else -0.004), f"{v:+.3f}", ha="center", fontsize=5)
    ax.set_xticks(x); ax.set_xticklabels([SHORT[m] for m in models], rotation=45, ha="right", fontsize=6)
    ax.set_ylabel("AUROC decay (internal - LOCO)")
    ax.set_title("Transportability loss\n(green=simple, red=ensemble)", fontsize=8)
    ax.set_ylim(0, max(dec.values) * 1.25)
    save(fig, "intl_decay")

    # ---- Panel 3: calibration slope by model x country
    fig, ax = plt.subplots(figsize=(CM, CM))
    for k, c in enumerate(countries):
        d = per[c]
        off = (k - (nc - 1) / 2) * w
        ax.bar(x + off, d.cal_slope, w, color=PAL[k % len(PAL)],
               label=COUNTRY_LABEL.get(c, c), edgecolor="k", lw=.3)
    ax.axhline(1.0, color=OI["grey"], lw=.7, ls="--")
    ax.set_xticks(x); ax.set_xticklabels([SHORT[m] for m in models], rotation=45, ha="right", fontsize=6)
    ax.set_ylabel("Calibration slope (1.0 = ideal)")
    ax.set_title("LOCO calibration", fontsize=8); ax.set_ylim(0, 1.35)
    ax.legend(fontsize=5, frameon=False, loc="upper left", ncol=nc)
    save(fig, "intl_calslope")

    # ---- Panel 4: internal vs mean LOCO scatter
    internal = df.groupby("model", observed=True)["internal_auroc"].first().reindex(models)
    meand = df.groupby("model", observed=True)["auroc"].mean().reindex(models)
    fig, ax = plt.subplots(figsize=(CM, CM))
    lo = min(internal.min(), meand.min()) - 0.01
    hi = max(internal.max(), meand.max()) + 0.01
    lim = [lo, hi]
    ax.plot(lim, lim, color=OI["grey"], lw=.7, ls="--")
    for i, (m, xi, yi) in enumerate(zip(models, internal, meand)):
        col = OI["green"] if m in SIMPLE else OI["verm"]
        ax.scatter(xi, yi, s=22, color=col, edgecolor="k", lw=.4, zorder=3)
        dy = 4 if i % 2 == 0 else -7
        ax.annotate(SHORT[m], (xi, yi), textcoords="offset points", xytext=(4, dy), fontsize=5)
    ax.set_xlabel("Internal CV AUROC"); ax.set_ylabel("Mean LOCO AUROC")
    ax.set_xlim(lim); ax.set_ylim(lim); ax.set_aspect("equal")
    ax.set_title("Internal vs cross-country", fontsize=8)
    save(fig, "intl_scatter")

    print("wrote 4 panels ->", FIG)


if __name__ == "__main__":
    main()
