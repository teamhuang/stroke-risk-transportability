"""Print manuscript Table 4 rows: adaptation strategy x local sample size, from the published
horizon-recalibration table (cif_mid estimand, four panels).

The pre-audit Table 4 fitted every correction inside the interval composition and evaluated at the
horizon, which is now known to be the wrong scale for a horizon-deployed rule; this table shows both
scales side by side, which is the finding rather than a footnote.

    python analysis/output/make_table4_rows.py
"""
import pandas as pd

T = "H:/脑出血国际队列/results/tables/incident_horizon_recal_2026-11-03.csv"
CTRY = {"US": "United States", "CN": "China", "KR": "Korea", "MX": "Mexico"}
r = pd.read_csv(T)
d = r[(r.model == "logistic") & (r.frac > 0)]
piv = d.groupby(["held", "strategy", "frac"]).mean(numeric_only=True).reset_index()

for model in ["logistic", "xgboost"]:
    dm = r[(r.model == model) & (r.frac > 0)]
    w = dm.groupby(["held", "strategy", "frac"]).agg(
        nb=("nb_at_05", "mean"), sd=("nb_at_05", "std"), au=("auroc", "mean"),
        oe=("pred_over_obs", "mean"), loc=("local_persons", "max"),
        fl=("flagged_at_05", "mean"), ta=("nb_all_at_05", "mean")).reset_index()
    print(f"\n#### {model}: horizon AUROC | NB frozen (SD) | NB offset_interval | NB offset_horizon (SD)"
          f" | NB recalibrate_horizon | NB retrain | NB treat-all | pred/obs f->oi/oh | AUROC retrain"
          f" | flagged% f->oh")
    for (held, frac), grp in w[w.strategy.isin(["frozen_sub", "offset_interval", "offset_horizon",
                                                "recalibrate_horizon", "retrain_local"])] \
            .set_index(["held", "frac", "strategy"]).groupby(level=[0, 1]):
        g = grp.droplevel([0, 1])
        fr, oi, oh, rh, rl = (g.loc[s] for s in ["frozen_sub", "offset_interval", "offset_horizon",
                                                 "recalibrate_horizon", "retrain_local"])
        print(f"| {CTRY[held]} | {int(fr.loc['loc']):,} ({frac:.0%}) | {fr.au:.4f} | "
              f"{fr.nb:+.5f} ({fr.sd:.5f}) | {oi.nb:+.5f} | {oh.nb:+.5f} ({oh.sd:.5f}) | "
              f"{rh.nb:+.5f} | {rl.nb:+.5f} | {fr.ta:+.5f} | "
              f"{fr.oe:.2f} -> {oi.oe:.2f} / {oh.oe:.2f} | {rl.au:.4f} | "
              f"{fr.fl:.3f} -> {oh.fl:.3f} |")
