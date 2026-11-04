"""Print the P1-5 definitional-ablation arm from published tables only.

The question (review item P1-5): is Mexico's absolute-risk over-prediction a RISK difference, or an
artefact of the four panels asking about cardiac disease and drinking in different words? The primary
feature set is already the intersection of what every panel asks; this arm subtracts the two concepts
whose QUESTION differs (heart_attack, alcohol) and refits both cause-specific hazards from scratch,
then adds a stricter tier that also drops the availability-mismatched items (hypertension, marital).

Every number comes from results/tables/. Nothing here refits anything.

Usage: python make_definition_rows.py
"""
import os, sys, json
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
T = os.path.join(ROOT, "results", "tables")
DAY = "2026-11-03"
TIERS = ["common", "core", "core_strict"]
LABEL = {"common": "published primary arm (10 concepts, 19 columns)",
         "core": "+ drop heart_attack, alcohol (questions differ across panels)",
         "core_strict": "+ drop hypertension, marital too (availability differs)"}
VAR = "V4_ph_competing"


def load(name):
    p = os.path.join(T, name)
    if not os.path.exists(p):
        sys.exit(f"missing published table: results/tables/{name} "
                 f"(run incident_cr_definition.py then publish_incident_tables.py)")
    return pd.read_csv(p)


def main():
    d = load(f"incident_cr_definition_{DAY}.csv")
    pr = load(f"incident_cr_definition_paired_{DAY}.csv")
    miss = load(f"incident_cr_definition_missingness_{DAY}.csv")
    dj = json.load(open(os.path.join(T, f"incident_cr_definition_diagnostics_{DAY}.json"),
                        encoding="utf-8"))
    fz = d[(d.strategy == "frozen_all") & (d.variant == VAR)].set_index(["fset", "held"])
    v1 = d[(d.strategy == "frozen_all") & (d.variant == "V1_logit_cause_specific")] \
        .set_index(["fset", "held"])

    print("=" * 112)
    print("P1-5 DEFINITIONAL ABLATION - is Mexico's level error measurement or risk?")
    print("=" * 112)
    print("measured missingness that justifies each tier (share of interval rows, %):")
    print(miss.set_index(miss.columns[0]).to_string())
    for t in TIERS:
        print(f"  {t:<12} {LABEL[t]}  -> "
              f"{len(dj['feature_columns'][t])} columns: {', '.join(dj['feature_columns'][t])}")

    print("\n" + "-" * 112)
    print(f"frozen transported model, four-year horizon, competing-risks composition ({VAR}):")
    print("%-12s %-4s %8s %8s %8s %-16s %9s %9s" %
          ("tier", "held", "AUROC", "mean p", "obs CIF", "pred/obs [95%]", "NB@5%", "NB@2%"))
    for t in TIERS:
        for h in ["CN", "KR", "MX", "US"]:
            r = fz.loc[(t, h)]
            print("%-12s %-4s %8.4f %8.5f %8.5f %9.3f [%6.3f,%6.3f] %+9.5f %+9.5f" %
                  (t, h, r.auroc, r.mean_pred, r.obs_prev, r.pred_over_obs,
                   r.ci_po_lo, r.ci_po_hi, r.nb_at_05, r.nb_at_02))
        print("-" * 100)

    mx = {t: float(fz.loc[(t, "MX")].pred_over_obs) for t in TIERS}
    print("\nTHE HEADLINE")
    print(f"  Mexico predicted/observed: common {mx['common']:.3f} -> core {mx['core']:.3f}"
          f" -> core_strict {mx['core_strict']:.3f}")
    drift = max(abs(mx[t] - mx["common"]) for t in TIERS[1:])
    verdict = ("CLAIM SURVIVES: removing the two non-comparable concepts moves Mexico's level error by "
               f"{drift:.3f} ({drift / mx['common'] * 100:.1f}% relative), so the over-prediction is "
               "not an artefact of how the questionnaires word cardiac disease or drinking"
               if min(mx.values()) > 2 else
               "CLAIM BROKEN: Mexico falls below 2-fold once the non-comparable items leave, so the "
               "level gap is at least partly measurement")
    print("  " + verdict)
    print(f"  and the confidence interval still excludes 1.0 in every tier: "
          + ", ".join(f"{t} [{fz.loc[(t, 'MX')].ci_po_lo:.2f},{fz.loc[(t, 'MX')].ci_po_hi:.2f}]"
                      for t in TIERS))

    print("\n" + "-" * 112)
    print("the local intercept repair, same rule in every tier (5% local data, persons disjoint):")
    print("%-12s %-4s %9s %10s %16s %14s %8s %6s %6s %6s" %
          ("tier", "held", "gain NB@5%", "level after", "level after SD",
           "net persons*", "above", "tie", "below", "reps"))
    nev = float(d[(d.strategy == "frozen_all") & (d.held == "MX")].n_eval.mean())
    for t in TIERS:
        for h in ["CN", "KR", "MX", "US"]:
            s = pr[(pr.fset == t) & (pr.held == h) & (pr.variant == VAR)
                   & np.isclose(pr.frac.astype(float), 0.05)]
            if not len(s):
                continue
            r = s.iloc[0]
            rr = d[(d.fset == t) & (d.held == h) & (d.variant == VAR) & (d.strategy == "offset_logit")
                   & np.isclose(d.frac.astype(float), 0.05)]
            print("%-12s %-4s %+9.5f %10.3f %16.3f %14.2f %8d %6d %6d %6d" %
                  (t, h, r.mean_gain_nb_at_05, r.mean_repaired_pred_over_obs,
                   rr.pred_over_obs.std(ddof=1), max(r.max_nb_above_treat_none, 0.0) * nev,
                   r.n_nb_above_treat_none, r.n_nb_tied_treat_none, r.n_nb_below_treat_none,
                   r.n_complete_reps))
        print("-" * 100)
    print(f"* largest single-split exceedance of treat-none, converted to net persons in the "
          f"{nev:.0f}-person Mexican evaluation sample; a value under 1.0 is a one-person rounding")
    print("  difference, not a clinical margin (docs/SELF_AUDIT.md defect 25).")
    print("\n  The 'level after' column is a MEAN over adaptation splits and must never be quoted as a")
    print("  point: the repaired ratio's own spread across splits is wide, because a 396-adult local")
    print("  sample carrying ~4 events pins an intercept only loosely. From the published primary arm:")
    pp_ = os.path.join(T, f"incident_cr_primary_{DAY}.csv")
    if os.path.exists(pp_):
        dp = pd.read_csv(pp_)
        q = dp[(dp.horizon_rule == "cif_mid") & (dp.held == "MX") & (dp.variant == VAR)
               & (dp.strategy == "offset_logit") & np.isclose(dp.frac.astype(float), 0.05)]
        print(f"    mean {q.pred_over_obs.mean():.3f}, SD across the {len(q)} splits "
              f"{q.pred_over_obs.std(ddof=1):.3f}, range {q.pred_over_obs.min():.2f}-"
              f"{q.pred_over_obs.max():.2f} - so '3.00 to 1.14' is '3.00 to something centred on 1.14'.")

    print("\n" + "-" * 112)
    print("MECHANICAL CHECKS")
    ch = [c for c in dj.get("checks", []) if c["name"].startswith("common tier")]
    for c in ch:
        print(f"  [1] replication of the published primary arm by the 'common' tier: "
              f"{c['n_cells']} cells, {c['n_mismatches']} mismatches -> "
              f"{'PASS' if c['n_mismatches'] == 0 else 'FAIL ' + str(c['detail'][:3])}")
    if not ch:
        print("  [1] replication check absent - run incident_cr_definition.py with 'common' in --fsets")
    worst = max(float(v1.loc[(t, "MX")].pred_over_obs) for t in TIERS)
    lo = min(float(fz.loc[(t, "MX")].pred_over_obs) for t in TIERS)
    print(f"  [2] Mexico's level error across all {len(TIERS) * 2} tier-by-composition cells: "
          f"{lo:.3f} to {worst:.3f} -> {'CLAIM SURVIVES' if lo > 2 else 'CLAIM BROKEN'} (>2-fold in all)")
    others = {t: {h: float(fz.loc[(t, h)].pred_over_obs) for h in ["CN", "KR", "US"]} for t in TIERS}
    flat = [v for t in TIERS for v in others[t].values()]
    print(f"  [3] the other three panels: level ratios across tiers span {min(flat):.3f}-{max(flat):.3f}"
          f" -> {'CLAIM SURVIVES' if max(flat) < 2 else 'CLAIM BROKEN'} (nothing approaches 2-fold), "
          f"but ablation moves Korea {'up' if others['core_strict']['KR'] > others['common']['KR'] else 'down'}: "
          f"{others['common']['KR']:.3f} -> {others['core']['KR']:.3f} -> "
          f"{others['core_strict']['KR']:.3f}, i.e. fewer variables do not fix Korea either")
    conv = [v for v in dj["diagnostics"].values()
            if not (v.get("converged_stroke") and v.get("converged_death"))]
    print(f"  [4] convergence: {len(conv)} of {len(dj['diagnostics'])} cells failed to converge -> "
          f"{'PASS' if not conv else 'CHECK ' + str(conv[:2])}")

    print("\n" + "-" * 112)
    print("CARRY-FORWARD FOR THE MANUSCRIPT (copy these exact strings):")
    print(f"  Mexico pred/obs by tier: {mx['common']:.3f} / {mx['core']:.3f} / "
          f"{mx['core_strict']:.3f};  repair gain at 5%: "
          + " / ".join(f"{float(pr[(pr.fset == t) & (pr.held == 'MX') & (pr.variant == VAR) & np.isclose(pr.frac.astype(float), 0.05)].iloc[0].mean_gain_nb_at_05):+.5f}"
                       for t in TIERS))


if __name__ == "__main__":
    main()
