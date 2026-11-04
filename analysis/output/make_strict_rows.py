"""Print manuscript Table 7 (strict-coverage refit) and the local-intercept stability table from the
published strict-refit CSV.

Table 7 is the arm the coverage objection requires: the models are refitted leave-one-panel-out on a
risk set that stops where outcome ascertainment stops, so the label and the training target agree. The
stability table answers the companion question - how well is that one parameter estimated when the local
sample contains four events - because a repair whose intercept has SD 0.44 on the log-odds scale is not a
verified minimum sample size.

    python analysis/output/make_strict_rows.py
"""
import numpy as np
import pandas as pd

T = "H:/脑出血国际队列/results/tables/"
CTRY = {"US": "United States", "CN": "China", "KR": "Korea", "MX": "Mexico"}
ORDER = ["CN", "KR", "MX", "US"]
d = pd.read_csv(T + "incident_strict_refit_2026-11-03.csv")

print("### Table 7: partial-strict refit, logistic, four-year horizon, NB at 5%")
print("| Panel | Local adults (median local events) | Frozen AUROC | Frozen NB | Offset NB | "
      "Paired gain (SD) | Beats frozen | predicted ÷ observed: frozen → repaired |")
print("|---|---|---|---|---|---|---|")
lg = d[d.model == "logistic"]
for h in ORDER:
    s = lg[lg.held == h]
    f = s[s.strategy == "frozen"].iloc[0]
    oe_f = f.mean_pred / f.obs_prev
    print(f"| {CTRY[h]} | refit on {int(f.n_eval) + 0:,} scored adults, frozen AUROC {f.auroc:.4f} "
          f"| {f.auroc:.4f} | {f.nb_at_05:+.5f} | — | — | {oe_f:.2f} |")
    for frac in sorted(s[s.strategy == "offset_horizon"].frac.unique()):
        g = s[(s.strategy == "offset_horizon") & (s.frac == frac)]
        gain = g.nb_gain.to_numpy()
        print(f"|  | {int(g.local_persons.max()):,} ({frac:.0%}; median "
              f"{int(np.median(g.local_events))} events) |  | {g.nb_frozen_same_rows.mean():+.5f} | "
              f"{g.nb_at_05.mean():+.5f} | {gain.mean():+.6f} ({gain.std():.6f}) | "
              f"{int((gain > 0).sum())}/{len(gain)} | {g.mean_pred.mean() / g.obs_prev.mean():.2f} |")

print("\n### local-intercept stability: the one parameter's own sampling error")
print("| Panel | local adults | median local events | mean fitted intercept | SD | "
      "|1/√events| (binomial expectation) | repaired pred ÷ obs, IQR |")
print("|---|---|---|---|---|---|---|")
for h in ORDER:
    off = lg[(lg.held == h) & (lg.strategy == "offset_horizon")]
    for frac in sorted(off.frac.unique()):
        g = off[off.frac == frac]
        oe = g.mean_pred / g.obs_prev
        ev = int(np.median(g.local_events))
        print(f"| {CTRY[h]} | {int(g.local_persons.max()):,} ({frac:.0%}) | {ev} | "
              f"{g.fitted_intercept.mean():+.3f} | {g.fitted_intercept.std():.3f} | "
              f"{1 / np.sqrt(max(ev, 1)):.3f} | [{oe.quantile(.25):.2f}, {oe.quantile(.75):.2f}] |")

print("\n### the three coverage conventions, side by side (logistic, frozen, whole panel)")
P = pd.read_csv(T + "incident_loco_common_H4_2026-11-03.csv")
per = P[(P.level == "horizon_4y_composed") & (P.horizon_rule == "cif_mid")]
A = pd.read_csv(T + "incident_ascertainment_sensitivity_2026-11-03.csv")
a = A[(A.model == "logistic")].set_index(["held", "coverage_rule"])
print("| Panel | permissive: evaluable / pred ÷ obs / NB / AUROC | partial-strict (label only): "
      "same four fields | partial-strict (REFIT): same four fields |")
print("|---|---|---|---|")
for h in ORDER:
    r = per[(per.model == "logistic") & (per.held == h)].iloc[0]
    s = a.loc[(h, "strict_t_ask")]
    f = lg[(lg.held == h) & (lg.strategy == "frozen")].iloc[0]
    print(f"| {CTRY[h]} | {int(r.n):,} / {r.pred_over_obs:.2f} / {r['nb_at_0.05']:+.5f} / {r.auroc:.4f} "
          f"| {int(s.evaluable):,} / {s.pred_over_obs_ipcw:.2f} / {s.net_benefit_5pct:+.5f} / "
          f"{s.horizon_auroc:.4f} | {int(f.n_eval):,} / {f.mean_pred / f.obs_prev:.2f} / "
          f"{f.nb_at_05:+.5f} / {f.auroc:.4f} |")

print("\n### does the model's own ranking change? AUROC per model, permissive vs strict refit")
for m in sorted(d.model.unique()):
    pm = per[per.model == m] if m in set(per.model) else None
    sr = d[(d.model == m) & (d.strategy == "frozen")]
    if pm is None or not len(sr):
        continue
    print(f"  {m}: " + "  ".join(
        f"{CTRY[h]} {float(pm[pm.held == h].auroc.iloc[0]):.4f} -> "
        f"{float(sr[sr.held == h].auroc.iloc[0]):.4f}" for h in ORDER))
