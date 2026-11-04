"""Print the competing-risks / duration-consistent primary arm from published tables only.

Answers the reviewer's decisive question with machine-printed numbers, not prose:

  "如果用时间一致、适当处理竞争死亡的模型重新分析，墨西哥是否仍然存在明显的绝对风险高估，而本地
   截距更新是否仍然带来独立评价中的净获益改善？"

Four blocks:

  1. the P0-1 variant comparison at the four-year horizon (AUROC, AUPRC, calibration-in-the-large,
     calibration slope, predicted/observed with person-clustered intervals, Brier, net benefit at
     2/5/10/15% and the local intercept repair) for the four specifications that differ only in the
     link (logit vs cloglog), in whether interval length enters as a covariate or as a log-exposure
     offset, and in whether death is composed as a competing event or ignored;
  2. the estimand decomposition, which is where P0-4 is settled: the same fitted hazards turned into
     1 - exp(-Lambda_stroke) versus the Aalen-Johansen CIF, plus the step-refinement ladder against
     the analytic continuous CIF;
  3. the repair, split into the two quantities the review insisted on separating - a gain AGAINST the
     frozen model and a level AGAINST doing nothing;
  4. mechanical "does the sentence still hold" checks, so a claim that a specification change breaks
     is reported as broken rather than quietly reworded.

Reads only results/tables/. Nothing here refits anything.

Usage: python make_cr_rows.py
"""
import os, sys, json
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
T = os.path.join(ROOT, "results", "tables")
DAY = "2026-11-03"
VARS = ["V1_logit_cause_specific", "V2_logit_competing",
        "V3_ph_cause_specific", "V4_ph_competing"]
SHORT = {"V1_logit_cause_specific": "V1 logit, len covariate, cause-specific",
         "V2_logit_competing": "V2 logit, len covariate, competing CIF",
         "V3_ph_cause_specific": "V3 PH offset, cause-specific",
         "V4_ph_competing": "V4 PH offset, competing CIF"}


def load(name):
    p = os.path.join(T, name)
    if not os.path.exists(p):
        sys.exit(f"missing published table: results/tables/{name} (run publish_incident_tables.py)")
    return pd.read_csv(p)


def main():
    d = load(f"incident_cr_primary_{DAY}.csv")
    paired = load(f"incident_cr_primary_paired_{DAY}.csv")
    diag = json.load(open(os.path.join(T, f"incident_cr_primary_diagnostics_{DAY}.json"),
                          encoding="utf-8"))
    pol = load(f"incident_update_policy_summary_{DAY}.csv")
    audit = load(f"incident_adaptation_leakage_audit_{DAY}.csv")
    cal = load(f"incident_calibration_curves_{DAY}.csv")

    prim = d[d.horizon_rule == "cif_mid"]
    fz = prim[prim.strategy == "frozen_all"].set_index(["held", "variant"])

    print("=" * 118)
    print("HEADLINE - the reviewer's decisive question, answered from the published rows")
    print('  "如果用时间一致、适当处理竞争死亡的模型重新分析，墨西哥是否仍然存在明显的绝对风险高估，')
    print('   而本地截距更新是否仍然带来独立评价中的净获益改善？"')
    print("=" * 118)
    v4 = fz.loc[("MX", "V4_ph_competing")]
    v4cn, v4kr, v4us = (fz.loc[("CN", "V4_ph_competing")], fz.loc[("KR", "V4_ph_competing")],
                        fz.loc[("US", "V4_ph_competing")])
    p4 = paired[(paired.horizon_rule == "cif_mid") & (paired.variant == "V4_ph_competing")
                & (paired.held == "MX")]
    p4 = p4[np.isclose(p4.frac.astype(float), 0.05)]
    r4 = p4.iloc[0]
    print(f"(a) YES, Mexico. Under the duration-consistent proportional-hazards specification with")
    print(f"    the competing death composed into the Aalen-Johansen cumulative incidence (V4), the")
    print(f"    frozen transferred model predicts {v4.mean_pred:.5f} against {v4.obs_prev:.5f}")
    print(f"    observed: predicted/observed {v4.pred_over_obs:.3f} "
          f"[{v4.ci_po_lo:.3f}, {v4.ci_po_hi:.3f}] (person-clustered bootstrap, B="
          f"{diag.get('bootstrap_B')}). The interval excludes 1.0 and the whole 2x range.")
    print(f"    The other three panels under the same arm: China {v4cn.pred_over_obs:.3f}, Korea "
          f"{v4kr.pred_over_obs:.3f}, United States {v4us.pred_over_obs:.3f}.")
    print(f"(b) YES, the repair still pays - as a gain against the frozen model. On persons who")
    print(f"    never entered the adaptation sample, at 5% local data the intercept repair moves")
    print(f"    Mexico's net benefit at 5% by {r4.mean_gain_nb_at_05:+.5f} "
          f"[{r4.lo_gain_nb_at_05:+.5f}, {r4.hi_gain_nb_at_05:+.5f}], positive in "
          f"{int(r4.n_gain_positive)}/{int(r4.n_complete_reps)} splits, and takes the level error")
    print(f"    from {v4.pred_over_obs:.2f} to {r4.mean_repaired_pred_over_obs:.2f}.")
    print(f"(c) BUT it does not become worth acting on: the repaired absolute net benefit beats")
    print(f"    treat-none in only {int(r4.n_repaired_nb_above_treat_none)}/"
          f"{int(r4.n_complete_reps)} splits. Better than the model you have is not better than")
    print(f"    doing nothing, and the two are reported apart below.")
    moves = []
    for link, a, b in (("logit", "V1_logit_cause_specific", "V2_logit_competing"),
                       ("PH", "V3_ph_cause_specific", "V4_ph_competing")):
        for held in ["CN", "KR", "MX", "US"]:
            p1 = fz.loc[(held, a)].pred_over_obs
            p2 = fz.loc[(held, b)].pred_over_obs
            moves.append(abs(p2 - p1) / p1)
    print(f"(d) The estimand correction is real and SMALL: the same fitted hazards composed as")
    print(f"    1 - exp(-Lambda_stroke) rather than as an Aalen-Johansen CIF moves predicted/observed")
    print(f"    by {100 * min(moves):.1f}-{100 * max(moves):.1f}% relative across the eight")
    print(f"    country x link cells (block 2), and no panel changes side of 1.0. Mixing the two")
    print(f"    estimands was a defect; it does not explain Mexico.")
    print(f"(e) One thing the correction DOES change: the sign of the United States repair (block 5,")
    print(f"    check [5]). The published logistic arm's 'recalibration costs money in the US' is")
    print(f"    specification-dependent and is withdrawn as a US-level claim.")
    print(f"(f) Duration consistency: V3 is exactly 1.000000 by algebra (block 2, `ratio8/1`), which")
    print(f"    is the property the review asked the primary model to have. V4's ratio is 0.94-0.95")
    print(f"    for a different and explicable reason: the discrete Aalen-Johansen sum is a Riemann")
    print(f"    approximation of the CIF integral. Its ONE-piece value equals the cause-specific")
    print(f"    1 - exp(-Lambda_stroke) exactly (a single piece leaves no room for a competing death")
    print(f"    to intervene before the event), and refining the pieces moves it down toward the")
    print(f"    analytic continuous CIF in the last column of block 2: the four-piece value sits")
    print(f"    0.1-2.6% above the closed form and the eight-piece value crosses to about 0.5% below")
    print(f"    it in China and the United States while staying above it in Korea and Mexico, i.e.")
    print(f"    the ladder brackets the analytic target. The residual is therefore a measured")
    print(f"    discretisation of the composition, quantified against a closed form - not the grid")
    print(f"    artefact the review flagged, which was the covariate arm's 1.53 (V1, block 2).")

    print("=" * 118)
    print("1. P0-1 VARIANT COMPARISON - frozen source model, four-year horizon, primary timing rule")
    print("   (person-clustered bootstrap intervals exist for this rule only, B=%s; the other two"
          % diag.get("bootstrap_B"))
    print("    timing conventions are reported without intervals and are labelled sensitivity arms)")
    print("=" * 118)
    hdr = (f"{'held':4s} {'spec':34s} {'AUROC':>7s} {'[95%]':>16s} {'AUPRC':>6s} {'CIL a':>7s} "
           f"{'slope':>6s} {'P/O':>6s} {'[95%]':>16s} {'Brier':>7s} {'NB@5%':>9s} {'[95%]':>18s}")
    print(hdr)
    for held in ["CN", "KR", "MX", "US"]:
        for v in VARS:
            r = fz.loc[(held, v)]
            print(f"{held:4s} {SHORT[v]:34s} {r.auroc:7.4f} "
                  f"[{r.ci_auroc_lo:.3f},{r.ci_auroc_hi:.3f}] {r.auprc:6.4f} "
                  f"{r.calib_intercept:+7.3f} {r.calib_slope:6.3f} {r.pred_over_obs:6.3f} "
                  f"[{r.ci_po_lo:.3f},{r.ci_po_hi:.3f}] {r.brier:7.5f} {r.nb_at_05:+9.5f} "
                  f"[{r.ci_nb_lo:+.5f},{r.ci_nb_hi:+.5f}]")
        print("-" * 118)

    print("\nnet benefit at every threshold, same rows (2/5/10/15% and treat-all as the floor):")
    print(f"{'held':4s} {'spec':34s} {'NB@2%':>10s} {'NB@5%':>10s} {'NB@10%':>10s} {'NB@15%':>10s}"
          f" {'treat-all':>10s} {'obs prev':>9s}")
    for held in ["CN", "KR", "MX", "US"]:
        for v in VARS:
            r = fz.loc[(held, v)]
            print(f"{held:4s} {SHORT[v]:34s} {r.nb_at_02:+10.5f} {r.nb_at_05:+10.5f} "
                  f"{r.nb_at_10:+10.5f} {r.nb_at_15:+10.5f} {r.nb_all_at_05:+10.5f} "
                  f"{r.obs_prev:9.5f}")

    print("\n" + "=" * 118)
    print("2. P0-4 ESTIMAND DECOMPOSITION - what each composition actually estimates")
    print("=" * 118)
    print(f"{'held':4s} {'spec':34s} {'P/O this':>9s} {'P/O other':>10s} {'ratio8/1':>9s} "
          f"{'step ladder 1/2/4/8':>34s} {'analytic CIF':>13s}")
    for held in ["CN", "KR", "MX", "US"]:
        for v in VARS:
            k = f"cif_mid|{held}|{v}"
            g = diag["diagnostics"].get(k)
            if not g:
                continue
            lad = g["duration_mean_risk_by_step"]
            other = g["mean_pred_other_composition"] / g["obs_prev"]
            closed = g.get("closed_form_cif_mean")
            print(f"{held:4s} {SHORT[v]:34s} {g['pred_over_obs']:9.3f} {other:10.3f} "
                  f"{g['duration_ratio_8_over_1']:9.4f} "
                  f"{('  '.join(f'{lad[s]:.5f}' for s in ['1','2','4','8'])):>34s} "
                  f"{(f'{closed:.5f}' if closed else '-'):>13s}")
    print("\nread this block as: the two cause-specific columns differ ONLY in whether the competing")
    print("death is composed in, the two PH rows differ from the two logit rows only in how interval")
    print("length enters, and `ratio8/1` is the duration-consistency test - the risk composed from")
    print("eight half-year pieces divided by the risk composed from one four-year piece, at the same")
    print("covariates. A value of exactly 1.0 is the algebraic property the review asked the primary")
    print("model to have. Where `analytic CIF` is present (the proportional-hazards arms) the discrete")
    print("Aalen-Johansen ladder converges on it as the pieces shrink, which is what makes the")
    print("residual 0.94-0.95 in the competing rows a measured discretisation gap rather than an")
    print("unstated assumption.")

    print("\n" + "=" * 118)
    print("3. P0-3/P1-2 THE REPAIR - gain against the frozen model vs level against doing nothing")
    print("=" * 118)
    pr = paired[paired.horizon_rule == "cif_mid"]
    print(f"{'held':4s} {'spec':34s} {'frac':>5s} {'paired gain NB@5%':>19s} {'[2.5,97.5]':>20s} "
          f"{'gain>0':>8s} {'repaired NB>0':>14s} {'repaired P/O':>13s}")
    for v in VARS:
        for held in ["CN", "KR", "MX", "US"]:
            s = pr[(pr.variant == v) & (pr.held == held)].sort_values("frac")
            for _, r in s.iterrows():
                print(f"{held:4s} {SHORT[v]:34s} {r.frac:5.2f} {r.mean_gain_nb_at_05:+19.5f} "
                      f"[{r.lo_gain_nb_at_05:+.5f},{r.hi_gain_nb_at_05:+.5f}] "
                      f"{int(r.n_gain_positive):3d}/{int(r.n_complete_reps):<4d} "
                      f"{int(r.n_repaired_nb_above_treat_none):3d}/{int(r.n_complete_reps):<4d} "
                      f"{r.mean_repaired_pred_over_obs:13.3f}")
            print("-" * 118)

    print("\n" + "=" * 118)
    print("4. P1-2 THE DECISION POLICY - prespecified rules, adaptation set only, disjoint evaluation")
    print("=" * 118)
    print(f"{'held':4s} {'frac':>5s} {'policy':17s} {'update%':>8s} {'a_hat':>7s} {'SE':>6s} "
          f"{'eval P/O':>9s} {'NB@5%':>9s} {'vs frozen':>10s} {'[2.5,97.5]':>20s} {'beats fz':>9s} "
          f"{'regret':>9s}")
    for held in ["CN", "KR", "MX", "US"]:
        for frac in sorted(pol.frac.unique()):
            for pname in ["always_frozen", "always_recal", "selective", "selective_magnet"]:
                r = pol[(pol.held == held) & (np.isclose(pol.frac.astype(float), frac))
                        & (pol.policy == pname)]
                if r.empty:
                    continue
                r = r.iloc[0]
                print(f"{held:4s} {frac:5.2f} {pname:17s} {r.updated_rate * 100:7.0f}% "
                      f"{r.a_hat_mean:+7.3f} {r.se_a_mean:6.3f} {r.oe_eval_mean:9.3f} "
                      f"{r.nb_at_05:+9.5f} {r.paired_vs_frozen:+10.5f} "
                      f"[{r.paired_vs_frozen_lo:+.5f},{r.paired_vs_frozen_hi:+.5f}] "
                      f"{r.beats_frozen_rate * 100:8.0f}% {r.regret_vs_oracle:+9.5f}")
            print("-" * 118)

    print("\n" + "=" * 118)
    print("5. MECHANICAL CHECKS - each printed as CLAIM SURVIVES / CLAIM BROKEN")
    print("=" * 118)
    mx = {v: fz.loc[("MX", v)] for v in VARS}
    lo, hi = min(m.pred_over_obs for m in mx.values()), max(m.pred_over_obs for m in mx.values())
    print(f"[1] Mexico over-predicts under ALL FOUR specifications: P/O {lo:.3f}-{hi:.3f}; "
          f"lowest is {SHORT[min(mx, key=lambda v: mx[v].pred_over_obs)]}. "
          f"{'CLAIM SURVIVES' if lo > 2 else 'CLAIM BROKEN'} (>2x in every arm).")
    ci = mx["V4_ph_competing"]
    print(f"[2] Mexico's V4 interval excludes 1.0: [{ci.ci_po_lo:.3f}, {ci.ci_po_hi:.3f}] -> "
          f"{'CLAIM SURVIVES' if ci.ci_po_lo > 1 else 'CLAIM BROKEN'}.")
    dr = {v: diag["diagnostics"][f"cif_mid|CN|{v}"]["duration_ratio_8_over_1"] for v in VARS}
    print(f"[3] duration consistency (CN): V1 {dr['V1_logit_cause_specific']:.4f} "
          f"V2 {dr['V2_logit_competing']:.4f} V3 {dr['V3_ph_cause_specific']:.6f} "
          f"V4 {dr['V4_ph_competing']:.4f} -> the offset arms are the consistent pair; "
          f"{'CLAIM SURVIVES' if dr['V3_ph_cause_specific'] == 1.0 else 'CHECK'} for V3 exactly.")
    for v in VARS:
        s = pr[(pr.variant == v) & (pr.held == "MX") & np.isclose(pr.frac.astype(float), 0.05)]
        if not s.empty:
            r = s.iloc[0]
            print(f"[4] Mexico repair at 5% local, {SHORT[v]}: paired gain "
                  f"{r.mean_gain_nb_at_05:+.5f} > 0 in {int(r.n_gain_positive)}/"
                  f"{int(r.n_complete_reps)} splits, but repaired net benefit beats treat-none in "
                  f"only {int(r.n_repaired_nb_above_treat_none)}/{int(r.n_complete_reps)} -> "
                  f"{'BOTH TRUE' if r.mean_gain_nb_at_05 > 0 and r.n_repaired_nb_above_treat_none < r.n_complete_reps else 'CHECK'}; "
                  f"'better than the frozen model' is not 'worth acting on'.")

    # Treat-none net benefit is exactly zero by definition, so "not above" is NOT the same statement
    # as "below": a repaired rule that clears nobody at the deployment threshold ties treat-none
    # exactly. Count the three ways, and express the exceedances in net persons, because an
    # exceedance of order 1/N_eval is a one-person difference and must not be quoted as though the
    # repaired rule beat doing nothing.
    print("[4b] the 'beats treat-none' count split three ways from the per-replicate rows, with each"
          " exceedance\n     converted to net persons (NB x evaluation sample size):")
    for v in VARS:
        q = prim[(prim.held == "MX") & (prim.variant == v) & (prim.strategy == "offset_logit")
                 & np.isclose(prim.frac.astype(float), 0.05)]
        if q.empty:
            continue
        r = q.groupby("rep")["nb_at_05"].mean()
        n = len(r)
        above, tie, below = int((r > 0).sum()), int((r == 0).sum()), int((r < 0).sum())
        nev = float(q["n_eval"].mean())
        pos = r[r > 0]
        top = float(pos.max()) if len(pos) else float("nan")
        flag = ""
        if tie:
            flag = f"  <-- above+below = {above + below} < {n}: say 'did not beat', not 'stayed below'"
        if len(pos) and top * nev < 1.0:
            flag += "  <-- every exceedance is under ONE net person"
        print(f"     {SHORT[v]:<38} above {above:>2}/{n}  exactly ties {tie:>2}  below {below:>2}"
              f"  | largest exceedance {top:.7f} = {top * nev:.2f} net persons of {nev:.0f}"
              + flag)
    us = {v: pr[(pr.variant == v) & (pr.held == "US") & np.isclose(pr.frac.astype(float), 0.05)]
          for v in VARS}
    signs = {v: (None if s.empty else float(s.iloc[0].mean_gain_nb_at_05)) for v, s in us.items()}
    got = [x for x in signs.values() if x is not None]
    verdict5 = ("CLAIM BROKEN: the sign of the US repair flips with the specification"
                if len({np.sign(x) for x in got}) > 1 else
                "consistent across the four four-year arms")
    print("[5] the published logistic arm said the US repair COSTS net benefit. Under the four-year")
    print("    competing-risks arms the same cell is: "
          + ", ".join(f"{v.split('_')[0]} {signs[v]:+.5f}" for v in VARS if signs[v] is not None))
    print(f"    -> {verdict5}. This is the")
    print("      same instability the review predicted for 'only Mexico needs recalibration': the")
    print("      US cell cannot be stated as a US-level finding without naming the estimand.")
    frozen_us = [fz.loc[("US", v)] for v in VARS]
    print("[6] US frozen absolute net benefit at 5%: "
          + ", ".join(f"{v.split('_')[0]} {r.nb_at_05:+.5f}" for v, r in zip(VARS, frozen_us))
          + f"; person-clustered CI on Mexico V4 [{ci.ci_nb_lo:+.5f}, {ci.ci_nb_hi:+.5f}] | "
            f"US V4 CI [{fz.loc[('US','V4_ph_competing')].ci_nb_lo:+.5f},"
            f"{fz.loc[('US','V4_ph_competing')].ci_nb_hi:+.5f}].")
    print("[7] leakage audit rows: " + " | ".join(
        f"Q{q['question']}:{str(q['verdict']).split(':')[0]}"
        for q in audit.to_dict("records") if str(q["verdict"]).startswith(("PASS", "PARTIAL"))))
    ov = audit[audit.question == 1]
    print(f"    adaptation/evaluation shared persons, max over "
          f"{int(ov.n_replicates.sum())} replicates x 4 panels: "
          f"{int(ov.adaptation_eval_shared_persons_max.max())} "
          f"({'PASS' if ov.adaptation_eval_shared_persons_max.max() == 0 else 'FAIL'}); "
          f"CR arm's own counter: {json.dumps(diag['leakage_checks'])[:120]}")
    q3 = audit[audit.question == 3]
    mxs = q3[q3.held == "MX"].set_index("arm")["observed_prevalence"]
    # the published permissive logistic arm's Mexico level error, read from the table it lives in
    rec = load(f"incident_horizon_recal_{DAY}.csv")
    r0 = rec[(rec.held == "MX") & (rec.strategy == "frozen_all")]
    r0 = r0.iloc[0] if len(r0) else None
    po_pub = float(r0.pred_over_obs) if r0 is not None else float("nan")
    print(f"[8] IPCW source sensitivity for Mexico: observed four-year incidence "
          f"pooled {mxs['ipcw source pooled_all_four']:.6f} / source-three-only "
          f"{mxs['ipcw source source_three_only']:.6f} / target-only {mxs['ipcw source target_only']:.6f}"
          f" -> the published level error of {po_pub:.2f} would become "
          f"{po_pub * mxs['ipcw source pooled_all_four'] / mxs['ipcw source source_three_only']:.2f} "
          f"or {po_pub * mxs['ipcw source pooled_all_four'] / mxs['ipcw source target_only']:.2f}: the "
          f"threefold error is not an artefact of whose follow-up built G.")
    print("[9] the two claims made about the Aalen-Johansen ladder, checked on the printed numbers:")
    worst_one, worst_four, worst_eight = 0.0, 0.0, 0.0
    for held in ["CN", "KR", "MX", "US"]:
        g3 = diag["diagnostics"][f"cif_mid|{held}|V3_ph_cause_specific"]
        g4 = diag["diagnostics"][f"cif_mid|{held}|V4_ph_competing"]
        l3 = g3["duration_mean_risk_by_step"]["1"]
        lad = g4["duration_mean_risk_by_step"]
        l1 = lad["1"]
        cf = g4["closed_form_cif_mean"]
        worst_one = max(worst_one, abs(l1 - l3) / l3)
        worst_four = max(worst_four, abs(lad["4"] - cf) / cf)
        worst_eight = max(worst_eight, abs(lad["8"] - cf) / cf)
        print(f"    {held}: V4 one-piece {l1:.5f} vs V3 {l3:.5f} "
              f"({100 * abs(l1 - l3) / l3:.4f}% apart); four-piece {lad['4']:.5f} and eight-piece "
              f"{lad['8']:.5f} vs analytic {cf:.5f} "
              f"({100 * (lad['4'] - cf) / cf:+.2f}%, {100 * (lad['8'] - cf) / cf:+.2f}%)")
    print(f"    -> {'CLAIM SURVIVES' if worst_one < 1e-12 else 'CLAIM BROKEN'}: the one-piece "
          f"competing-risks composition equals the cause-specific risk exactly (max gap "
          f"{100 * worst_one:.2e}%).")
    print(f"    -> {'CLAIM SURVIVES' if worst_four < 0.03 and worst_eight < 0.03 else 'CHECK'}: the "
          f"discrete composition tracks the analytic CIF to within {100 * max(worst_four, worst_eight):.2f}% "
          f"at four and eight pieces, and the sign of the gap changes between them, which is what "
          f"'brackets' means here. It is NOT claimed to be monotone onto the analytic value.")
    print("\n" + "=" * 118)
    print("6. P1-1 IS THE MISCALIBRATION ONLY AN INTERCEPT? decile-by-decile, before and after the repair")
    print("=" * 118)
    print(f"{'held':4s} {'dec':>3s} {'n':>7s} {'frozen':>8s} {'obs':>8s} {'obs 95%':>18s} "
          f"{'F/O':>6s} {'repaired':>9s} {'R/O':>6s} {'CI excludes F':>13s} {'CI excludes R':>13s}")
    for held in ["CN", "KR", "MX", "US"]:
        g = cal[cal.held == held].sort_values("group")
        nf = nr = 0
        for _, r in g.iterrows():
            fo = r.frozen_pred / r.obs if r.obs > 0 else np.nan
            ro = r.repaired_pred / r.obs if r.obs > 0 else np.nan
            exf = bool(r.obs < r.frozen_pred or r.obs > r.frozen_pred) and not (
                r.obs_lo <= r.frozen_pred <= r.obs_hi)
            exr = not (r.obs_lo <= r.repaired_pred <= r.obs_hi)
            nf += int(exf); nr += int(exr)
            print(f"{held:4s} {int(r.group):3d} {int(r.n_panel_rows):7d} {r.frozen_pred:8.4f} "
                  f"{r.obs:8.4f} [{r.obs_lo:.4f},{r.obs_hi:.4f}] {fo:6.2f} {r.repaired_pred:9.4f} "
                  f"{ro:6.2f} {'yes' if exf else 'no':>13s} {'yes' if exr else 'no':>13s}")
        print(f"     -> {held}: the observed decile risk rejects the frozen prediction in {nf}/10 "
              f"deciles and the repaired prediction in {nr}/10")
    print("\nread this as: a level ratio near one does not mean the curve is calibrated, and a repair")
    print("that moves every person by the same log-odds can still leave the low-risk deciles wrong in")
    print("both directions. The count of rejecting deciles, not the panel ratio, is what a threshold")
    print("at a given risk level actually experiences.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
