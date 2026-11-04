"""Joint competing-risks model as the primary figures, in Nature / npj DM house style.

Three joint-model figures, each reading the joint CSVs so a figure and its table cannot disagree, drawn on the
shared `nature_style` canvas (5 cm tall; 6.5 cm wide for the 2 x 2 facets, 5 cm for the single-panel bar plot;
Arial; Okabe-Ito; bold a/b/c/d facet letters; NO explanatory note text on the canvas - that lives in the
manuscript caption):

  Fig 1  incident_joint_fig1_calibration   - per held country (facets a-d), observed 4-y risk (IPCW, cif_mid)
         against predicted risk in deciles of the FROZEN joint model, before (frozen, blue circles) and after
         (vermilion squares) the 5% local intercept, with person-clustered observed-risk intervals. The dotted
         line is correct calibration; over-prediction therefore sits BELOW it.
  Fig 2  incident_joint_fig2_update        - per held country (facets a-d), four-year net benefit at the
         illustrative 5% threshold against local sample size for the three prespecified joint-model policies.
  Fig 3  incident_joint_fig3_observed_risk - the transported joint prediction over observed risk. The first
         three bars are estimand-matched EVENT-TIME ALLOCATIONS on one estimand (midpoint, uniform-within-
         interval, model-based) and are drawn as one cluster; the fourth bar, separated by a gap and hatched,
         is the pooled-hazard interval-censored MLE, a hazard/censoring RE-SPECIFICATION, not an allocation -
         the visual grouping encodes the distinction the caption states.

Usage: python incident_figures_joint.py
"""
import os, sys, warnings
import numpy as np, pandas as pd
warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nature_style as NS

NS.configure()
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
D = os.path.join(ROOT, "data", "processed", "intl", "incident")
FIGDIR = os.path.join(ROOT, "deliverables", "figures", "incident")
os.makedirs(FIGDIR, exist_ok=True)
ORDER = ["CN", "KR", "MX", "US"]
NAME = {"CN": "China", "KR": "Korea", "MX": "Mexico", "US": "United States"}


def fig1_calibration():
    dec = pd.read_csv(os.path.join(D, "incident_cr_joint_deciles.csv"))
    fig, axes = NS.grid(2, 2)
    for j, (ax, h) in enumerate(zip(axes.ravel(), ORDER)):
        s = dec[(dec.held == h) & (dec.arm.notna())]
        hi = max(s.frozen_pred.max(), s.repaired_pred.max(), s.obs.max()) * 1.05
        ax.plot([0, hi], [0, hi], ls=":", lw=0.8, color="#777777", zorder=1)
        ax.errorbar(s.frozen_pred, s.obs, yerr=[s.obs - s.obs_lo, s.obs_hi - s.obs],
                    fmt="o", ms=3.0, lw=0.7, color=NS.BLUE, capsize=1.3)
        ax.scatter(s.repaired_pred, s.obs, marker="s", s=14, color=NS.VERM, zorder=3)
        ax.set_title(NAME[h], fontsize=8)
        ax.set_xlabel("predicted 4-y risk")
        if j % 2 == 0:
            ax.set_ylabel("observed risk")
        else:
            ax.tick_params(axis="y", labelleft=False)
        ax.set_xlim(0, hi); ax.set_ylim(0, hi)
    from matplotlib.lines import Line2D
    handles = [Line2D([], [], marker="o", ls="", color=NS.BLUE, label="frozen deciles"),
               Line2D([], [], marker="s", ls="", color=NS.VERM, label="after 5% repair")]
    fig.legend(handles=handles, loc="lower center", ncol=2, fontsize=6.5, frameon=False,
               bbox_to_anchor=(0.5, 0.005))
    NS.letters(fig, axes)
    fig.tight_layout(pad=0.6, w_pad=1.6, rect=(0, 0.05, 1, 1))
    NS.finalise(fig, "incident_joint_fig1_calibration", FIGDIR)


def fig2_update():
    pol = pd.read_csv(os.path.join(D, "incident_update_policy_joint_summary_cif_mid.csv"))
    style = {"always_frozen": (NS.GREY, "-", "o", "frozen"),
             "always_recal": (NS.VERM, "-", "s", "recalibrate"),
             "selective": (NS.BLUE, "-", "^", "selective")}
    fig, axes = NS.grid(2, 2)
    for j, (ax, h) in enumerate(zip(axes.ravel(), ORDER)):
        s = pol[pol.held == h]
        for p, (c, ls, mk, lab) in style.items():
            ss = s[s.policy == p].sort_values("frac")
            if ss.empty:
                continue
            ax.plot(ss.frac * 100, ss.nb_at_05, ls + mk, ms=3, lw=1.1, color=c, mec="none")
        ax.axhline(0.0, ls="--", lw=0.7, color="#555555")
        ax.set_xscale("log"); ax.set_xticks([2, 5, 10, 25, 50])
        ax.set_xticklabels(["2", "5", "10", "25", "50"])
        ax.set_title(NAME[h], fontsize=8)
        ax.set_xlabel("local sample %")
        if j % 2 == 0:
            ax.set_ylabel("NB at 5%")
        else:
            ax.tick_params(axis="y", labelleft=False)
    from matplotlib.lines import Line2D
    handles = [Line2D([], [], color=c, marker=mk, ls=ls, ms=3, label=lab)
               for (c, ls, mk, lab) in style.values()]
    fig.legend(handles=handles, loc="lower center", ncol=3, fontsize=5.8, frameon=False,
               columnspacing=1.0, handlelength=1.6, bbox_to_anchor=(0.5, 0.0))
    NS.letters(fig, axes)
    fig.tight_layout(pad=0.6, w_pad=1.6, rect=(0, 0.09, 1, 1))
    NS.finalise(fig, "incident_joint_fig2_update", FIGDIR)


def fig3_observed_risk():
    av = pd.read_csv(os.path.join(D, "incident_cr_alloc_variants_cif_mid.csv")).set_index("held")
    fx = pd.read_csv(os.path.join(D, "incident_cr_interval_flexhaz_cif_mid.csv")).set_index("held")
    # three estimand-matched allocations (tight cluster) + re-specified hazard (separated by a gap, hatched)
    alloc = [("PO_mid", "midpoint", NS.BLUE), ("PO_uniform", "uniform", NS.GRN),
             ("PO_model", "model-based", NS.AMB)]
    w, gap = 0.17, 0.30
    centers = np.arange(len(ORDER)) * 1.0
    fig, ax = NS.grid(1, 1)
    for i, (r, lb, c) in enumerate(alloc):
        vals = [av.at[h, r] for h in ORDER]
        ax.bar(centers + (i - 1) * w, vals, w, color=c, label=lb)
    pvals = [fx.at[h, "PO_frozen_over_pw"] for h in ORDER]
    ax.bar(centers + w + gap, pvals, w, color=NS.VERM, label="pooled-hazard MLE",
           hatch="///", edgecolor="white", linewidth=0)
    ax.axhline(1.0, ls="--", lw=0.8, color="#444444")
    ax.set_yscale("log")
    ax.set_xticks(centers + gap / 2)
    ax.set_xticklabels([NAME[h] for h in ORDER], fontsize=7, rotation=25, ha="right")
    ax.set_xlabel("held-out country"); ax.set_ylabel("predicted / observed")
    ax.legend(ncol=2, loc="upper left", fontsize=5.8, frameon=False)
    fig.tight_layout(pad=0.5)
    NS.finalise(fig, "incident_joint_fig3_observed_risk", FIGDIR, multi=True)


def fig4_smooth():
    """Redraw the smooth joint calibration (frozen vs 5% repair) from the model's own output CSV - no refit.
    x-axis is the predicted four-year PROBABILITY (the linear predictor mapped through the logistic link), so
    the log-log presentation is on the (0,1) scale and valid; the spline was fitted on the linear predictor."""
    g = pd.read_csv(os.path.join(D, "incident_cr_joint_calibration_smooth.csv"))
    fig, axes = NS.grid(2, 2)
    for j, (ax, h) in enumerate(zip(axes.ravel(), ORDER)):
        for arm, col in (("frozen", NS.BLUE), ("repaired", NS.VERM)):
            s = g[(g.held == h) & (g.arm == arm)].sort_values("predicted_risk")
            ax.fill_between(s.predicted_risk, s.obs_lo, s.obs_hi, color=col, alpha=0.18, lw=0)
            ax.plot(s.predicted_risk, s.observed_smooth, color=col, lw=1.3)
        ax.plot([0.002, 0.4], [0.002, 0.4], ls=":", lw=0.8, color="#777777")
        ax.axvline(0.05, lw=0.6, color="#333333", alpha=0.6)
        ax.set_xscale("log"); ax.set_yscale("log"); ax.set_xlim(0.002, 0.4); ax.set_ylim(0.002, 0.4)
        ax.set_xlabel("predicted 4-y risk")
        if j % 2 == 0:                       # ylabel only on the left column
            ax.set_ylabel("observed (smoothed)")
        else:
            ax.tick_params(axis="y", labelleft=False)
        ax.set_title(NAME[h], fontsize=8)
    from matplotlib.lines import Line2D
    handles = [Line2D([], [], color=NS.BLUE, lw=1.3, label="frozen"),
               Line2D([], [], color=NS.VERM, lw=1.3, label="after 5% repair")]
    fig.legend(handles=handles, loc="lower center", ncol=2, fontsize=6.5, frameon=False,
               bbox_to_anchor=(0.5, 0.005))
    NS.letters(fig, axes)
    fig.tight_layout(pad=0.6, w_pad=1.6, rect=(0, 0.05, 1, 1))
    NS.finalise(fig, "incident_cr_joint_calibration_smooth", FIGDIR)


if __name__ == "__main__":
    for f in [fig1_calibration, fig2_update, fig3_observed_risk, fig4_smooth]:
        try:
            f()
        except Exception as e:
            print("ERROR", f.__name__, repr(e)[:240])
    for base in ["incident_joint_fig1_calibration", "incident_joint_fig2_update",
                 "incident_joint_fig3_observed_risk", "incident_cr_joint_calibration_smooth"]:
        p = os.path.join(FIGDIR, base + ".png")
        print(base, "png bytes", os.path.getsize(p) if os.path.exists(p) else "MISSING")
