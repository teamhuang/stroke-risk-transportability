"""Print the manuscript's link-function / interval-grid rows from the published cloglog tables.

Two objections close here. (1) "你的模型本身仍然使用 logistic discrete-time hazard ... cloglog
敏感性分析应该在投稿前完成" - the same interval rows are now fitted with a logit link, a cloglog link
with exposure as a covariate, and the proportional-hazards formulation (cloglog with log-exposure as an
offset), and scored on identical persons with identical IPCW weights. (2) "不同国家随访间隔差异很大" -
all three are refitted on a common sub-year interval grid.

Everything below is read from results/tables/, never recomputed.

SUPERSEDED IN PART on 2026-11-03: this generator prints the WEIGHTED-ROW grid arms (fractional event
weight, midpoint piece, last piece). `--alloc uniform` matches the event COUNT inside an interview gap but
is not the interval-censored likelihood, so `make_ic_rows.py` now prints the arm that maximises the actual
likelihood - d*log(1-(1-p)^n) + (1-d)*n*log(1-p) - which is the column Table 8 quotes as definitive and
which moves China (1.018 -> 0.755) and the United States (1.170 -> 0.984) across the line of correct
level. Both generators are kept: the weighted-row numbers are honest about what they are, and reading them
beside the correct likelihood is what shows the size of the difference. "16 specifications" below means
4 arms x 4 weighted-row fits; with the interval-censored arm the honest total is 16 of 20. See
docs/SELF_AUDIT.md defects 19 and 20.

    python analysis/output/make_cloglog_rows.py
"""
import json
import numpy as np
import pandas as pd

T = "H:/脑出血国际队列/results/tables/"
CTRY = {"US": "United States", "CN": "China", "KR": "Korea", "MX": "Mexico"}
ORDER = ["CN", "KR", "MX", "US"]
ARMS = ["sklearn_logistic", "logit_glm", "cloglog_glm", "cloglog_ph"]
SHORT = {"sklearn_logistic": "logit (published)", "logit_glm": "logit GLM",
         "cloglog_glm": "cloglog, exposure covariate", "cloglog_ph": "cloglog, log-exposure offset"}

F = pd.read_csv(T + "incident_cloglog_2026-11-03.csv")
G = pd.read_csv(T + "incident_cloglog_grid1_last_2026-11-03.csv")
PF = pd.read_csv(T + "incident_cloglog_paired_2026-11-03.csv")
PG = pd.read_csv(T + "incident_cloglog_paired_grid1_last_2026-11-03.csv")
U = pd.read_csv(T + "incident_cloglog_grid1_uniform_2026-11-03.csv")
PU = pd.read_csv(T + "incident_cloglog_paired_grid1_uniform_2026-11-03.csv")
M = pd.read_csv(T + "incident_cloglog_grid1_midcell_2026-11-03.csv")
PM = pd.read_csv(T + "incident_cloglog_paired_grid1_midcell_2026-11-03.csv")
J = json.load(open(T + "incident_cloglog_diagnostics_2026-11-03.json", encoding="utf-8"))
JG = json.load(open(T + "incident_cloglog_grid1_last_diagnostics_2026-11-03.json",
                    encoding="utf-8"))
JU = json.load(open(T + "incident_cloglog_grid1_uniform_diagnostics_2026-11-03.json",
                    encoding="utf-8"))
JM = json.load(open(T + "incident_cloglog_grid1_midcell_diagnostics_2026-11-03.json",
                    encoding="utf-8"))
fz = lambda D: D[D.strategy == "frozen_all"].set_index(["held", "arm"])


def cell(D, h, a, col, nd=4):
    r = fz(D)
    return "n/a" if (h, a) not in r.index else f"{r.loc[(h, a), col]:.{nd}f}"


print("### Table 8: frozen four-year risk, `cif_mid` IPCW frame, realised horizon 4.0 yr")
print("### four hazard specifications x four ways of writing the same follow-up")
FITLAB = {"natural": "unsplit (primary)", "uniform": "1-yr grid, uniform event",
          "midcell": "1-yr grid, midpoint piece", "last": "1-yr grid, last piece"}
FITS = [("natural", F, PF), ("uniform", U, PU), ("midcell", M, PM), ("last", G, PG)]
for h in ORDER:
    print(f"| {CTRY[h]} | measure | " + " | ".join(FITLAB[k] for k, _, _ in FITS) + " |")
    if h == ORDER[0]:
        print("|---|---|" + "---|" * len(FITS))
    for col, lbl, nd in [("pred_over_obs", "predicted ÷ observed", 3),
                         ("mean_pred", "mean predicted", 5),
                         ("nb_at_05", "net benefit at 5%", 5),
                         ("auroc", "AUROC", 4)]:
        cells = []
        for k, D, _ in FITS:
            v = [fz(D).loc[(h, a), col] for a in ARMS]
            cells.append(f"{min(v):.{nd}f}-{max(v):.{nd}f}" if nd < 5
                         else f"{np.mean(v):.{nd}f}")
        print(f"|  | {lbl} | " + " | ".join(cells) + " |")
    print()
print("  (pred ÷ observed and AUROC shown as the range over the four arms; mean predicted and net")
print("   benefit as the mean over arms, because the arms agree to <0.001 on both)")

print("\n### per-arm detail on the primary (unsplit) fit and the honest grid fits")
print("| Panel | arm | pred ÷ obs unsplit | uniform | midcell | last | AUROC unsplit | uniform | "
      "midcell | last |")
print("|---|---|---|---|---|---|---|---|---|---|")
for h in ORDER:
    for a in ARMS:
        lv = [fz(D).loc[(h, a), "pred_over_obs"] for _, D, _ in FITS]
        av = [fz(D).loc[(h, a), "auroc"] for _, D, _ in FITS]
        print(f"| {CTRY[h]} | {SHORT[a]} | " + " | ".join(f"{x:.3f}" for x in lv) + " | " +
              " | ".join(f"{x:.4f}" for x in av) + " |")

print("\n### the one-intercept repair, in the arm's own link space, 20 replications of the same "
      "local samples the published arm used")
SPACE = {"sklearn_logistic": "logit", "logit_glm": "logit",
         "cloglog_glm": "cloglog", "cloglog_ph": "cloglog"}
print("| Panel | arm | frac | local adults (median events) | paired NB gain (SD) | beats frozen | "
      "repaired NB@5% | repaired pred ÷ obs |")
print("|---|---|---|---|---|---|---|---|")
for h in ORDER:
    for a in ARMS:
        strat = f"offset_{SPACE[a]}"
        s = PF[(PF.held == h) & (PF.arm == a) & (PF.strategy == strat)]
        for frac in [0.02, 0.25, 0.50]:
            r = s[s.frac == frac]
            if not len(r):
                continue
            rep = F[(F.held == h) & (F.arm == a) & (F.frac == frac) & (F.strategy == strat)]
            print(f"| {CTRY[h]} | {SHORT[a]} | {frac:.0%} | "
                  f"{int(F[(F.held == h) & (F.arm == a) & (F.frac == frac)].local_persons.max()):,} "
                  f"(median {int(np.median(rep.local_events))}) | {r.mean_gain_nb_at_05.iloc[0]:+.6f} "
                  f"({r.sd_gain_nb_at_05.iloc[0]:.6f}) | {int(r.n_gain_positive.iloc[0])}/"
                  f"{int(r.n_complete_reps.iloc[0])} | {rep.nb_at_05.mean():+.5f} | "
                  f"{rep.mean_pred.mean() / rep.obs_prev.mean():.3f} |")

print("\n### the repair gain at 2% local data under every fit (means over the 20 replicates)")
print("| Panel | arm | unsplit | uniform | midcell | last |")
print("|---|---|---|---|---|---|")
for h in ORDER:
    for a in ARMS:
        strat = f"offset_{SPACE[a]}"
        cells = []
        for _, D, P in FITS:
            r = P[(P.held == h) & (P.arm == a) & (P.strategy == strat) & (P.frac == 0.02)]
            rep = D[(D.held == h) & (D.arm == a) & (D.frac == 0.02) & (D.strategy == strat)]
            cells.append("n/a" if not len(r) else
                         f"{r.mean_gain_nb_at_05.iloc[0]:+.5f} "
                         f"({int(r.n_gain_positive.iloc[0])}/{int(r.n_complete_reps.iloc[0])}, "
                         f"NB {rep.nb_at_05.mean():+.5f})")
        print(f"| {CTRY[h]} | {SHORT[a]} | " + " | ".join(cells) + " |")

print("\n### does it matter which link space the intercept is fitted in?")
for h in ORDER:
    for a in ["cloglog_glm", "cloglog_ph"]:
        m = PF[(PF.held == h) & (PF.arm == a) &
               PF.strategy.isin(["offset_cloglog", "offset_logit"])] \
            .pivot_table(index="frac", columns="strategy", values="mean_gain_nb_at_05")
        d = (m["offset_cloglog"] - m["offset_logit"]).abs().max()
        print(f"  {CTRY[h]} {SHORT[a]}: max |gain(cloglog space) - gain(logit space)| = {d:.6f}")

print("\n### duration consistency: same person, same covariates, H composed from 8 pieces vs 1 piece")
DIAG = {"unsplit (primary)": J, "1-yr grid, uniform": JU, "1-yr grid, midcell": JM,
        "1-yr grid, last piece": JG}
print("| fit | " + " | ".join(SHORT[a] for a in ARMS) + " |")
print("|---|" + "---|" * len(ARMS))
for k, DJ in DIAG.items():
    row = []
    for a in ARMS:
        v = [DJ["fit_and_linkage_diagnostics"].get(f"{h}|{a}", {})
             .get("ratio_pieces8_over_1", float("nan")) for h in ORDER]
        row.append(f"{min(v):.3f}-{max(v):.3f}")
    print(f"| {k} | " + " | ".join(row) + " |")
print("  (ratio of the 8-piece composed risk to the single-interval risk; 1.000 = duration-consistent)")

print("\n### convergence and the exposure effect, from the fit records")
for a in ["logit_glm", "cloglog_glm", "cloglog_ph"]:
    for h in ORDER:
        v = J["fit_and_linkage_diagnostics"].get(f"{h}|{a}")
        if not v or "params" not in v:
            continue
        ix = v["terms"].index("b[exposure_years]") if "b[exposure_years]" in v["terms"] else None
        print(f"  {CTRY[h]} {SHORT[a]}: converged={v['converged']}"
              + (f", exposure_years coefficient {v['params'][ix]:+.4f}" if ix is not None else
                 ", exposure enters as offset only"))

print("\n### do the conclusions survive? mechanical checks over 4 arms x 4 fits = 16 specifications")
HONEST = [("natural", F, PF), ("uniform", U, PU), ("midcell", M, PM)]
for h in ORDER:
    lv = {k: [fz(D).loc[(h, a), "pred_over_obs"] for a in ARMS] for k, D, _ in FITS}
    au = [fz(D).loc[(h, a), "auroc"] for _, D, _ in FITS for a in ARMS]
    hv = [x for k, D, _ in HONEST for x in lv[k]]
    print(f"  {CTRY[h]}: pred÷obs {min(hv):.3f}-{max(hv):.3f} over the 12 honest specifications "
          f"(last-piece fit {min(lv['last']):.3f}-{max(lv['last']):.3f}); "
          f"AUROC spread over all 16 {max(au) - min(au):.4f}")
mx_h = [fz(D).xs("MX", level="held")["pred_over_obs"][a] for _, D, _ in HONEST for a in ARMS]
mx_all = [fz(D).xs("MX", level="held")["pred_over_obs"][a] for _, D, _ in FITS for a in ARMS]
oth_h = [fz(D).xs(h, level="held")["pred_over_obs"][a] for _, D, _ in HONEST
         for h in ("CN", "KR", "US") for a in ARMS]
print(f"  Mexico over-predicts by more than 2x in {sum(v > 2 for v in mx_all)} of {len(mx_all)} "
      f"specifications (honest range {min(mx_h):.2f}-{max(mx_h):.2f}; other panels "
      f"{min(oth_h):.2f}-{max(oth_h):.2f})")
for h in ORDER:
    rng = []
    for k, D, P in FITS:
        c = P[(P.held == h) & (P.frac == 0.02) & (P.strategy.str.startswith("offset_"))]
        rng.append((k, c.mean_gain_nb_at_05.min(), c.mean_gain_nb_at_05.max(),
                    int((c.mean_gain_nb_at_05 > 0).sum()), len(c)))
    print(f"  {CTRY[h]} repair gain at 2%: " + "; ".join(
        f"{k} {lo:+.5f}..{hi:+.5f} ({pos}/{n} cells positive)" for k, lo, hi, pos, n in rng))
print(f"  anchor reproduction check (sklearn arm vs the published frozen row): "
      f"{J['anchor_reproduction'].get('reproduces_published')} "
      f"({J['anchor_reproduction'].get('published_file')})")
GR = json.load(open(T + "incident_grid_reframe_last_2026-11-03.json", encoding="utf-8"))
GU = json.load(open(T + "incident_grid_reframe_uniform_2026-11-03.json", encoding="utf-8"))
GM = json.load(open(T + "incident_grid_reframe_midcell_2026-11-03.json", encoding="utf-8"))
print(f"  grid reframe: {GR['after']['rows']:,} rows from {GR['before']['rows']:,} at delta="
      f"{GR['delta_years']:g} yr; persons {GR['after']['persons']:,}, events "
      f"{GR['after']['event_weight']:,}, person-years {GR['after']['person_years']:,} "
      f"(before {GR['before']['person_years']:,}), max interval "
      f"{GR['after']['max_interval_years']} yr; checks {GR['checks']}")
for nm, D in (("uniform", GU), ("midcell", GM)):
    print(f"  {nm} allocation: {D['after']['rows']:,} rows, event weight "
          f"{D['after']['event_weight']:,}, person-years {D['after']['person_years']:,} "
          f"(drop after the event cell {D['person_years_dropped_after_the_event_cell']:,})")

print("\n### the exact figures the manuscript sentences quote")
cov_unsplit = [J["fit_and_linkage_diagnostics"][f"{h}|{a}"]["ratio_pieces8_over_1"]
               for h in ORDER for a in ARMS if a != "cloglog_ph"]
cov_all = [DJ["fit_and_linkage_diagnostics"][f"{h}|{a}"]["ratio_pieces8_over_1"]
           for DJ in DIAG.values() for h in ORDER for a in ARMS if a != "cloglog_ph"]
off_all = [DJ["fit_and_linkage_diagnostics"][f"{h}|{a}"]["ratio_pieces8_over_1"]
           for DJ in DIAG.values() for h in ORDER for a in ["cloglog_ph"]]
print(f"  duration ratio, covariate arms: unsplit fit {min(cov_unsplit):.2f}-{max(cov_unsplit):.2f}; "
      f"all four fits {min(cov_all):.3f}-{max(cov_all):.3f}")
print(f"  duration ratio, offset arm over all four fits: "
      f"{sorted(set(round(v, 6) for v in off_all))}")
print(f"  max |ratio(logit GLM) - ratio(cloglog covariate)| = "
      f"{max(abs(J['fit_and_linkage_diagnostics'][f'{h}|logit_glm']['ratio_pieces8_over_1'] - J['fit_and_linkage_diagnostics'][f'{h}|cloglog_glm']['ratio_pieces8_over_1']) for h in ORDER):.4f}")
print(f"  China: step-composed {J['fit_and_linkage_diagnostics']['CN|sklearn_logistic']['frozen_mean_pred_step']:.4f}"
      f" vs single 4-year interval "
      f"{J['fit_and_linkage_diagnostics']['CN|sklearn_logistic']['frozen_mean_pred_single_interval']:.4f}")
for k, D, _ in FITS:
    v = fz(D).xs("MX", level="held")["pred_over_obs"][ARMS]
    print(f"  Mexico under {FITLAB[k]}: pred ÷ obs {v.min():.3f}-{v.max():.3f}")
print(f"  honest fits only (unsplit + uniform + midcell): Mexico {min(mx_h):.3f}-{max(mx_h):.3f}, "
      f"the other three panels {min(oth_h):.3f}-{max(oth_h):.3f}")
for h in ORDER:
    hv = [fz(D).xs(h, level="held")["pred_over_obs"][a] for _, D, _ in HONEST for a in ARMS]
    last_v = [fz(G).xs(h, level="held")["pred_over_obs"][a] for a in ARMS]
    print(f"  {CTRY[h]}: honest fits {min(hv):.3f}-{max(hv):.3f}, last-piece fit "
          f"{min(last_v):.3f}-{max(last_v):.3f}; above 1 in "
          f"{sum(v > 1 for v in hv)} of {len(hv)} honest cells")
print(f"  offset arm (duration-consistent) levels, honest fits: " +
      ", ".join(f"{CTRY[h]} "
                f"{min(fz(D).xs(h, level='held')['pred_over_obs']['cloglog_ph'] for _, D, _ in HONEST):.2f}-"
                f"{max(fz(D).xs(h, level='held')['pred_over_obs']['cloglog_ph'] for _, D, _ in HONEST):.2f}"
                for h in ORDER))
