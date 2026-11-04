"""Round-6 printer: emit every JOINT-PRIMARY manuscript object straight from the `_joint` disk files.

The sixth-round review made the joint multinomial competing-risks model the single PRIMARY absolute-risk
arm, so the manuscript's headline, age-band table (was V4 Table 12), age-aware table (was V4 Table 13),
the calibration/decile/smooth reads and the decision-curve statement must all cite joint numbers. This
script regenerates those cells as paste-ready markdown from the `_joint` outputs produced by
`incident_cr_joint_primary.py` and `incident_cr_joint.py`, so no joint number is hand-typed. Run with the
V4 files present (they are the labelled sensitivity arm; this script does not read them).

Usage: python make_joint_primary_rows.py
"""
import os, sys, json
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
D = os.path.join(ROOT, "data", "processed", "intl", "incident")
CTRY = {"CN": "China", "KR": "Korea", "MX": "Mexico", "US": "United States"}
ORDER = ["CN", "KR", "MX", "US"]


def headline():
    jn = pd.read_csv(os.path.join(D, "incident_cr_joint.csv"))
    f = jn[(jn.horizon_rule == "cif_mid") & (jn.composition_arm == "joint_multinomial")
           & (jn.strategy == "frozen_all") & (jn.frac == 0.0)].set_index("held")
    po = [f.loc[c].pred_over_obs for c in ORDER]
    print("### Joint primary headline (Table 3 / abstract)")
    for c in ORDER:
        r = f.loc[c]
        print(f"{CTRY[c]}: mean_pred {r.mean_pred:.4f} obs {r.obs_prev:.4f} P/O {r.pred_over_obs:.3f} "
              f"[{r.ci_po_lo:.3f}, {r.ci_po_hi:.3f}] AUROC {r.auroc:.4f} NB@5 {r.nb_at_05:+.6f} "
              f"[{r.ci_nb_lo:+.6f}, {r.ci_nb_hi:+.6f}] slope {r.calib_slope:.3f} n {int(r.n_eval)}")
    others = [p for c, p in zip(ORDER, po) if c != "MX"]
    print(f"non-Mexico P/O span: {min(others):.2f}-{max(others):.2f}")
    pr = pd.read_csv(os.path.join(D, "incident_cr_joint_paired.csv"))
    q = pr[(pr.horizon_rule == "cif_mid") & np.isclose(pr.frac, 0.05)
           & (pr.composition_arm == "joint_multinomial")].set_index("held")
    mx = q.loc["MX"]
    print(f"MX repair: gain {mx.mean_gain_nb_at_05:+.5f} [{mx.lo_gain_nb_at_05:+.5f}, "
          f"{mx.hi_gain_nb_at_05:+.5f}] pos {int(mx.n_gain_positive)}/{int(mx.n_complete_reps)} "
          f"above-none {int(mx.n_repaired_nb_above_treat_none)}/{int(mx.n_complete_reps)} "
          f"repaired P/O {mx.mean_repaired_pred_over_obs:.2f}")
    print(f"US repair above-none {int(q.loc['US'].n_repaired_nb_above_treat_none)}/40; "
          f"CN gain {q.loc['CN'].mean_gain_nb_at_05:+.5f}; KR {q.loc['KR'].mean_gain_nb_at_05:+.5f}")


def table12():
    s = pd.read_csv(os.path.join(D, "incident_cr_joint_subgroups.csv"))
    print("\n### Table 12 (joint): age-band frozen vs repaired P/O")
    print("| Panel | Age band | n | events | Frozen P/O | Repaired P/O | AUROC [95%] |")
    print("|---|---|---|---|---|---|---|")
    for c in ORDER:
        g = s[s.held == c]
        for _, r in g.iterrows():
            lvl = "all ages" if r.level == "ALL" else r.level
            ci = "" if not np.isfinite(r.auroc_lo) else f" [{r.auroc_lo:.3f}, {r.auroc_hi:.3f}]"
            print(f"| {CTRY[c]} | {lvl} | {int(r.n)} | {int(r.events)} | {r.pred_over_obs:.3f} "
                  f"| {r.pred_over_obs_offset:.3f} | {r.auroc:.3f}{ci} |")
    # the two sign-flip cells the prose cites
    for c, b in [("MX", "20-59"), ("MX", "80+"), ("CN", "80+"), ("US", "80+")]:
        r = s[(s.held == c) & (s.level == b)].iloc[0]
        print(f"  {CTRY[c]} {b}: frozen {r.pred_over_obs:.3f} -> repaired {r.pred_over_obs_offset:.3f}")


def table13():
    S = pd.read_csv(os.path.join(D, "incident_cr_joint_age_recalibration_summary.csv"))
    strat = ["A_frozen", "B_overall", "C_band", "D_age_linear", "E_band_shrunk"]
    label = {"A_frozen": "A frozen", "B_overall": "B overall intercept", "C_band": "C per-band (naive)",
             "D_age_linear": "D intercept + age", "E_band_shrunk": "E per-band shrunk"}
    print("\n### Table 13 (joint): Mexico five update strategies")
    print("| Local data | Strategy | Pooled P/O | Worst age band (x) | Mean |log band P/O| | NB at 5% | SD of NB |")
    print("|---|---|---|---|---|---|---|")
    for frac in (0.05, 0.25):
        g = S[(S.held == "MX") & np.isclose(S.frac, frac)].set_index("strategy")
        for st in strat:
            r = g.loc[st]
            print(f"| {int(round(frac*100))}% | {label[st]} | {r.pooled_pred_over_obs:.2f} "
                  f"| {np.exp(r.max_abs_band_log_po):.1f} | {r.mean_abs_band_log_po:.2f} "
                  f"| {r.mean_nb_at_05:.5f} | {r.sd_nb_at_05:.5f} |")


def threelevel():
    dca = pd.read_csv(os.path.join(D, "incident_cr_joint_dca.csv"))
    jn = pd.read_csv(os.path.join(D, "incident_cr_joint.csv"))
    f = jn[(jn.horizon_rule == "cif_mid") & (jn.composition_arm == "joint_multinomial")
           & (jn.strategy == "frozen_all") & (jn.frac == 0.0)].set_index("held")
    pr = pd.read_csv(os.path.join(D, "incident_cr_joint_paired.csv"))
    q = pr[(pr.horizon_rule == "cif_mid") & np.isclose(pr.frac, 0.05)
           & (pr.composition_arm == "joint_multinomial")].set_index("held")
    print("\n### Three-level deployability summary (joint): calibration / relative decision / clinical utility")
    print("| Panel | (1) level P/O | (2) repair gain vs frozen | (3) repaired beats treat-none? | "
          "frozen NB@5 [95%] |")
    print("|---|---|---|---|---|")
    for c in ORDER:
        r = f.loc[c]
        above = int(q.loc[c].n_repaired_nb_above_treat_none)
        nb = q.loc[c].n_complete_reps
        print(f"| {CTRY[c]} | {r.pred_over_obs:.2f} | {q.loc[c].mean_gain_nb_at_05:+.5f} "
              f"({int(q.loc[c].n_gain_positive)}/{nb} splits) | {above}/{nb} splits | "
              f"{r.nb_at_05:+.6f} [{r.ci_nb_lo:+.6f}, {r.ci_nb_hi:+.6f}] |")
    d5 = dca[np.isclose(dca.threshold, 0.05)].set_index("held")
    print("repaired NB@5:", {CTRY[c]: round(float(d5.loc[c].nb_repaired), 6) for c in ORDER})


def decile_tail():
    d = pd.read_csv(os.path.join(D, "incident_cr_joint_deciles.csv"))
    G = pd.read_csv(os.path.join(D, "incident_cr_joint_calibration_smooth.csv"))
    print("\n### Joint decile top + smooth tail (MX)")
    top = d[(d.held == "MX")].sort_values("group").iloc[-1]
    print(f"decile10: frozen_pred {top.frozen_pred:.4f} repaired {top.repaired_pred:.4f} "
          f"obs {top.obs:.4f} [{top.obs_lo:.4f}, {top.obs_hi:.4f}]")
    frz = G[(G.held == "MX") & (G.arm == "frozen") & (G.predicted_risk >= 0.10)]
    if len(frz):
        r = frz.iloc[(frz.predicted_risk - 0.107).abs().argsort()].iloc[0]
        print(f"smooth frozen tail ~{r.predicted_risk:.3f} -> obs {r.observed_smooth:.3f} "
              f"[{r.obs_lo:.3f}, {r.obs_hi:.3f}]")
    rep = G[(G.held == "MX") & (G.arm == "repaired") & (G.predicted_risk >= 0.04)]
    if len(rep):
        r = rep.iloc[(rep.predicted_risk - 0.06).abs().argsort()].iloc[0]
        print(f"smooth repaired tail ~{r.predicted_risk:.3f} -> obs {r.observed_smooth:.3f} "
              f"[{r.obs_lo:.3f}, {r.obs_hi:.3f}]")


if __name__ == "__main__":
    headline(); table12(); table13(); threelevel(); decile_tail()
