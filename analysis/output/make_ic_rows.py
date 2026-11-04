"""Print every Table 8 / interval-censored-likelihood number the manuscript quotes, from published
tables only.

Reads `results/tables/` and nothing else (docs/SELF_AUDIT.md defect 9: two generations of the same
filename pattern live in the working directory, and a default glob finds the superseded one).

The question this answers is the reviewer's second-round one: the `uniform` event-time allocation in
Table 8 matches the event COUNT across an interval's pieces but is not the interval-censored
likelihood, so does the grid conclusion change when the actual likelihood
  d*log(1-(1-p)^n) + (1-d)*n*log(1-p)
is maximised instead? Everything below is printed side by side with the weighted-row arms for exactly
that comparison, and the two anchor gates of the new arm are printed rather than assumed:
  * its unsplit fit must reproduce the published GLM arms (it is the same likelihood at n = 1);
  * its offset arm must be IDENTICAL at every grid size (the aggregation collapses analytically).
"""
import json, os, sys
import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
T = os.path.join(ROOT, "results", "tables")
D = "2026-11-03"
CTRY = {"CN": "China", "KR": "Korea", "MX": "Mexico", "US": "United States"}
ORDER = ["CN", "KR", "MX", "US"]
ARMS = ["ic_logit_len_l2", "ic_logit_len", "ic_cloglog_len", "ic_cloglog_off"]
SHORT = {"ic_logit_len_l2": "logit, published penalty (L2)",
         "ic_logit_len": "logit, GLM", "ic_cloglog_len": "cloglog, length as covariate",
         "ic_cloglog_off": "cloglog, log-length offset"}
# the weighted-row arms of Table 8, for the "did the moment-matched device mislead us?" comparison
GLM_FITS = {"unsplit": "incident_cloglog_2026-11-03.csv",
            "uniform": "incident_cloglog_grid1_uniform_2026-11-03.csv",
            "midcell": "incident_cloglog_grid1_midcell_2026-11-03.csv",
            "last": "incident_cloglog_grid1_last_2026-11-03.csv"}
GLM_ARMS = {"sklearn_logistic": "logit (published)", "logit_glm": "logit GLM",
            "cloglog_glm": "cloglog, exposure covariate", "cloglog_ph": "cloglog, log-exposure offset"}


def rd(name):
    p = os.path.join(T, name)
    if not os.path.exists(p):
        sys.exit(f"missing {name} - run intl/incident_ic_grid.py then intl/publish_incident_tables.py")
    return pd.read_csv(p)


def frozen(d):
    return d[d.strategy == "frozen_all"].set_index(["held", "arm"])


IC = rd(f"incident_ic_likelihood_{D}.csv")
ICP = rd(f"incident_ic_likelihood_paired_{D}.csv")
DIAG = json.load(open(os.path.join(T, f"incident_ic_likelihood_diagnostics_{D}.json"), encoding="utf-8"))
FZ = {k: frozen(rd(v)) for k, v in GLM_FITS.items()}
IC0 = frozen(IC[IC.delta_years == 0.0])
IC1 = frozen(IC[IC.delta_years > 0.0])
d1 = sorted(set(IC[IC.delta_years > 0.0].delta_years))
GRID_LABEL = f"1-yr pieces" if d1 == [1.0] else f"{d1}-yr pieces"

print(f"### the interval-censored likelihood: P(stroke inside a gap) = 1 - prod_pieces (1 - h), "
      f"maximised directly")
print(f"### rows = parent intervals; pieces per gap = ceil(L/delta); scored on the cif_mid IPCW frame\n")
print("| Panel | specification | parent intervals as one piece | " + GRID_LABEL +
      " (correct IC likelihood) |")
print("|---|---|---|---|")
for h in ORDER:
    for a in ARMS:
        x, y = IC0.loc[(h, a)], IC1.loc[(h, a)]
        print(f"| {CTRY[h]} | {SHORT[a]} | {x.pred_over_obs:.3f} ({x.auroc:.4f}) | "
              f"{y.pred_over_obs:.3f} ({y.auroc:.4f}) |")
print("\n  (predicted / observed, held-out AUROC in brackets)\n")

print("### does the moment-matched `uniform` arm agree with the correct likelihood?")
print("| Panel | arm | unsplit GLM | unsplit IC | 1-yr uniform-weighted | 1-yr IC | 1-yr midcell | diff(IC,uniform) |")
print("|---|---|---|---|---|---|---|---|")
PAIR = {"ic_logit_len_l2": "sklearn_logistic", "ic_logit_len": "logit_glm",
        "ic_cloglog_len": "cloglog_glm", "ic_cloglog_off": "cloglog_ph"}
for h in ORDER:
    for a in ARMS:
        g = PAIR[a]
        u0, u1, um = (FZ["unsplit"].loc[(h, g)].pred_over_obs, FZ["uniform"].loc[(h, g)].pred_over_obs,
                      FZ["midcell"].loc[(h, g)].pred_over_obs)
        i0, i1 = IC0.loc[(h, a)].pred_over_obs, IC1.loc[(h, a)].pred_over_obs
        print(f"| {CTRY[h]} | {SHORT[a]} | {u0:.3f} | {i0:.3f} | {u1:.3f} | {i1:.3f} | {um:.3f} | "
              f"{i1 - u1:+.3f} |")

print("\n### the two anchor gates, printed not assumed")
for k, v in DIAG["anchor_checks"].items():
    mx = max(v.values()) if isinstance(v, dict) else v
    tag = "NOT A GATE" if k == "published_row_tolerance_gap" else "gate"
    print(f"  [{tag}] {k}: max abs diff {mx:.3e}")
    if isinstance(v, dict):
        print(f"        " + ", ".join(f"{a}={b:.3e}" for a, b in v.items()))
print("  gate failures: " + (", ".join(DIAG["anchor_gate_failures"]) or "none"))

print("\n### duration consistency under the correct likelihood (8 pieces vs 1, fixed covariates)")
print("| fit | " + " | ".join(SHORT[a] for a in ARMS) + " |")
print("|---|---|---|---|---|")
for lab, dd in (("parent intervals", 0.0), (GRID_LABEL, d1[0])):
    cells = []
    for a in ARMS:
        r = [DIAG["fit_and_linkage_diagnostics"][f"{h}|{a}|d{dd:g}"]["ratio_pieces8_over_1"]
             for h in ORDER]
        cells.append(f"{min(r):.3f}-{max(r):.3f}")
    print(f"| {lab} | " + " | ".join(cells) + " |")
print("  (1.000 = duration-consistent; the offset arm is invariant because the aggregation collapses "
      "to exp(-lambda*L) at every piece count)")

print("\n### convergence of the new fits")
for h in ORDER:
    for a in ARMS:
        for dd in (0.0, d1[0]):
            g = DIAG["fit_and_linkage_diagnostics"][f"{h}|{a}|d{dd:g}"]
            print(f"  {CTRY[h]} {SHORT[a]} d={dd:g}: converged={g['converged']} iters={g['n_iter']} "
                  f"nll={g['nll']:.1f}")

print("\n### the one-intercept repair under the correct likelihood, at 2% of the local panel")
print("| Panel | specification | grid | paired gain vs frozen (SD) | cells positive | "
      "repaired NB@5% | frozen NB@5% |")
print("|---|---|---|---|---|---|---|")
for h in ORDER:
    for a in ARMS:
        for dd in (0.0, d1[0]):
            s = ICP[(ICP.held == h) & (ICP.arm == a) & (ICP.delta_years == dd)
                    & (ICP.frac == 0.02) & (ICP.strategy == f"offset_{IC[IC.arm == a].link.iloc[0]}")]
            if not len(s):
                continue
            r = s.iloc[0]
            fz = IC[(IC.held == h) & (IC.arm == a) & (IC.delta_years == dd)
                    & (IC.strategy == "frozen_sub") & (IC.frac == 0.02)]
            rp = IC[(IC.held == h) & (IC.arm == a) & (IC.delta_years == dd)
                    & (IC.strategy == f"offset_{IC[IC.arm == a].link.iloc[0]}") & (IC.frac == 0.02)]
            print(f"| {CTRY[h]} | {SHORT[a]} | {'unsplit' if dd == 0 else GRID_LABEL} | "
                  f"{r.mean_gain_nb_at_05:+.5f} ({r.sd_gain_nb_at_05:.5f}) | "
                  f"{r.n_gain_positive}/{r.n_complete_reps} | {rp.nb_at_05.mean():+.5f} | "
                  f"{fz.nb_at_05.mean():+.5f} |")

print("\n### do the three claims survive the correct likelihood? mechanical checks")
for h in ORDER:
    v = [IC1.loc[(h, a)].pred_over_obs for a in ARMS] + [IC0.loc[(h, a)].pred_over_obs for a in ARMS]
    au = [IC1.loc[(h, a)].auroc for a in ARMS] + [IC0.loc[(h, a)].auroc for a in ARMS]
    w = [FZ["uniform"].loc[(h, PAIR[a])].pred_over_obs for a in ARMS] + \
        [FZ["midcell"].loc[(h, PAIR[a])].pred_over_obs for a in ARMS]
    print(f"  {CTRY[h]}: IC likelihood pred/obs {min(v):.3f}-{max(v):.3f} over 8 fits "
          f"(weighted-row honest fits {min(w):.3f}-{max(w):.3f}); AUROC spread {max(au)-min(au):.4f}")
mx = [IC1.loc[("MX", a)].pred_over_obs for a in ARMS] + [IC0.loc[("MX", a)].pred_over_obs for a in ARMS]
print(f"  Mexico over-predicts >2x in {sum(1 for x in mx if x > 2)} of 8 IC fits; "
      f"range {min(mx):.3f}-{max(mx):.3f}")
for h in ORDER:
    for dd, lab in ((0.0, "unsplit"), (d1[0], "grid")):
        s = ICP[(ICP.held == h) & (ICP.frac == 0.02) & (ICP.delta_years == dd)
                & ICP.strategy.str.startswith("offset_")]
        print(f"  {CTRY[h]} {lab}: repair positive in {int((s.mean_gain_nb_at_05 > 0).sum())}/"
              f"{len(s)} cells, gain {s.mean_gain_nb_at_05.min():+.5f} to {s.mean_gain_nb_at_05.max():+.5f}; "
              f"repaired absolute NB@5% {IC[(IC.held == h) & (IC.frac == 0.02) & (IC.delta_years == dd) & IC.strategy.str.startswith('offset_')].nb_at_05.mean():+.5f} (treat-none = 0)")
print(f"  grid invariance of the offset arm: "
      f"{DIAG['anchor_checks']['ic_cloglog_off_grid_invariance']['oe_ratio']:.3e} in pred/obs")
print(f"  likelihood note: {DIAG['not_the_thing_this_replaces'][:120]}...")
