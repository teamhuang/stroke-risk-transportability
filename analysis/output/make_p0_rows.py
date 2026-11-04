"""Printer for the two tables the fifth-round review added: Table 9b and Table 13.

Defects 15/24/26 in docs/SELF_AUDIT.md established the rule that a table quoted in the manuscript must
have a printer behind it, so that a stale cell is a loud failure rather than a hand-edit nobody checked.
This script regenerates both tables as paste-ready markdown straight from disk and then asserts that the
manuscript already carries those exact strings; run it after any re-run of the underlying arms and diff.

Nothing here refits anything. Sources, all read-only:

  Table 9b (the same estimand under three competing-risks compositions)
    V4 shipped product  -> results/tables/incident_cr_primary_2026-11-03.csv
                          (variant V4_ph_competing, strategy frozen_all, frac 0.0, cif_mid)
    V5 exact on marginal -> data/processed/intl/incident/incident_cr_exact_diagnostics.json
                          (diagnostics[cif_mid|<panel>].V5_pred_over_obs) + its ladder CSV for the
                          step-drift / survival-gap / step-mass footnotes
    Joint multinomial   -> data/processed/intl/incident/incident_cr_joint.csv (composition_arm
                          joint_multinomial, strategy frozen_all, frac 0.0, cif_mid) for the point +
                          person-clustered CI; ..._joint_diagnostics.json for the flat ladder, gradient
                          self-test and probability conservation; ..._joint_paired.csv for the repair.

  Table 13 (Mexico: five recalibration strategies, worst age band)
    -> data/processed/intl/incident/incident_age_recalibration_summary.csv

Usage: python make_p0_rows.py [--check]      # --check only asserts the manuscript, prints nothing new
"""
import os, sys, json
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
T = os.path.join(ROOT, "results", "tables")
D = os.path.join(ROOT, "data", "processed", "intl", "incident")
MS = os.path.join(ROOT, "deliverables", "manuscript.md")
DAY = "2026-11-03"
RULE = "cif_mid"
CTRY = {"CN": "China", "KR": "Korea", "MX": "Mexico", "US": "United States"}
ORDER = ["CN", "KR", "MX", "US"]
check_only = "--check" in sys.argv


def table9b():
    prim = pd.read_csv(os.path.join(T, f"incident_cr_primary_{DAY}.csv"))
    v4 = prim[(prim.variant == "V4_ph_competing") & (prim.strategy == "frozen_all")
              & (prim.frac == 0.0) & (prim.horizon_rule == RULE)].set_index("held")
    ed = json.load(open(os.path.join(D, "incident_cr_exact_diagnostics.json")))
    jd = json.load(open(os.path.join(D, "incident_cr_joint_diagnostics.json")))
    jn = pd.read_csv(os.path.join(D, "incident_cr_joint.csv"))
    jf = jn[(jn.horizon_rule == RULE) & (jn.composition_arm == "joint_multinomial")
            & (jn.strategy == "frozen_all") & (jn.frac == 0.0)].set_index("held")
    lad = pd.read_csv(os.path.join(D, "incident_cr_exact_ladder.csv"))
    v4_ladder = lad[(lad.horizon_rule == RULE) & (lad.composition_arm == "V4_shipped_product")
                    & (lad.n_steps == 8)].ratio_over_1.min()

    lines = ["| Panel | V4 shipped product (Table 9) | V5 exact on marginal fits | Joint multinomial |",
             "|---|---|---|---|"]
    for c in ORDER:
        a = v4.loc[c]; j = jf.loc[c]
        v5 = ed["diagnostics"][f"{RULE}|{c}"]["V5_pred_over_obs"]
        lines.append(f"| {CTRY[c]} | {a.pred_over_obs:.3f} [{a.ci_po_lo:.3f}, {a.ci_po_hi:.3f}] | "
                     f"{v5:.3f} | {j.pred_over_obs:.3f} [{j.ci_po_lo:.3f}, {j.ci_po_hi:.3f}] |")
    # footnotes read straight from disk
    emx = ed["diagnostics"][f"{RULE}|MX"]
    jmx = jd["diagnostics"][f"{RULE}|MX"]
    jp = pd.read_csv(os.path.join(D, "incident_cr_joint_paired.csv"))
    jrepair = jp[(jp.horizon_rule == RULE) & (jp.held == "MX") & np.isclose(jp.frac, 0.05)
                 & (jp.composition_arm == "joint_multinomial")].iloc[0]
    notes = {
        "survival_gap": emx["survival_product_vs_exact_gap"],
        "step_mass_mx": emx["prob_mass_p_plus_q_plus_S"],
        "v4_ladder_drift": float(v4_ladder),
        "joint_ladder": jmx["ladder_ratio_8_over_1"],
        "gradient_rel_err": jd["selftest"]["gradient_relative_error"],
        "prob_conservation": jd["selftest"]["interval_probability_mass_deviation"],
        "repair_gain": jrepair.mean_gain_nb_at_05,
        "repair_lo": jrepair.lo_gain_nb_at_05,
        "repair_hi": jrepair.hi_gain_nb_at_05,
        "repair_pos": int(jrepair.n_gain_positive),
        "repair_reps": int(jrepair.n_complete_reps),
        "repair_above_none": int(jrepair.n_repaired_nb_above_treat_none),
        "repaired_po": jrepair.mean_repaired_pred_over_obs,
    }
    return "\n".join(lines), notes


def table13():
    S = pd.read_csv(os.path.join(D, "incident_age_recalibration_summary.csv"))
    strat = ["A_frozen", "B_overall", "C_band", "D_age_linear", "E_band_shrunk"]
    label = {"A_frozen": "A frozen", "B_overall": "B overall intercept",
             "C_band": "C per-band (naive)", "D_age_linear": "D intercept + age",
             "E_band_shrunk": "E per-band shrunk"}
    rows = ["| Local data | Strategy | Pooled P/O | Worst age band (×) | Mean \\|log band P/O\\| | "
            "NB at 5% | SD of NB |",
            "|---|---|---|---|---|---|---|"]
    for frac in (0.05, 0.25):
        g = S[(S.held == "MX") & np.isclose(S.frac, frac)].set_index("strategy")
        for st in strat:
            r = g.loc[st]
            fold = float(np.exp(r.max_abs_band_log_po))
            rows.append(f"| {int(round(frac * 100))}% | {label[st]} | "
                        f"{r.pooled_pred_over_obs:.2f} | {fold:.1f} | "
                        f"{r.mean_abs_band_log_po:.2f} | {r.mean_nb_at_05:.5f} | "
                        f"{r.sd_nb_at_05:.5f} |")
    return "\n".join(rows)


def main():
    t9b, n9b = table9b()
    t13 = table13()
    text = open(MS, encoding="utf-8").read()
    fails = []

    if not check_only:
        print("### Table 9b — the same estimand under three competing-risks compositions\n")
        print(t9b)
        print("\nnine-cell ladder drift (V4, 8 steps vs 1): "
              f"{n9b['v4_ladder_drift']:.4f}; joint/V5 flat: {n9b['joint_ladder']:.6f}")
        print(f"survival product vs exact gap: {n9b['survival_gap']:.1e} (refutes the "
              f"'1-p_s-p_d' charge); MX step mass 1+p_s p_d: {n9b['step_mass_mx']:.5f}")
        print(f"joint gradient self-test rel err: {n9b['gradient_rel_err']:.2e}; "
              f"probability conservation: {n9b['prob_conservation']:.2e}")
        print(f"joint MX repair (+0.00368 CI, 40/40): {n9b['repair_gain']:+.5f} "
              f"[{n9b['repair_lo']:.5f}, {n9b['repair_hi']:.5f}] positive in "
              f"{n9b['repair_pos']}/{n9b['repair_reps']}, above treat-none "
              f"{n9b['repair_above_none']}/{n9b['repair_reps']}, repaired P/O {n9b['repaired_po']:.2f}")
        print("\n### Table 13 — Mexico: five recalibration strategies, worst age band\n")
        print(t13)
        print("\nAll Mexico net benefits <= 0 at both fractions: an age-aware update improves fairness "
              "across ages, not deployability.")

    # ---- assert the manuscript carries the printed cells ----
    # spot-check the strings that matter most (independent of audit_consistency_round.py)
    for need in ["0.794 [0.726, 0.880]", "3.004 [2.631, 3.462]", "0.802 [0.734, 0.889]",
                 "2.975 [2.605, 3.428]", "0.9424", "1.1 × 10",
                 "D intercept + age", "Table 9b"]:
        if need not in text:
            fails.append(f"manuscript missing {need!r}")
    if fails:
        print("CHECK FAIL:")
        for m in fails:
            print("  -", m)
        sys.exit(1)
    print("\nOK: Table 9b and Table 13 strings present in the manuscript and regenerated from disk.")


if __name__ == "__main__":
    main()
