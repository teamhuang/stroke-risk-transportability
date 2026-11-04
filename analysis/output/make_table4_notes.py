"""Print the manuscript's adaptation block (Table 4, Table 4 continued and the paired-gain sentences)
straight from the published cif_mid tables, so nothing in that section is quoted from memory.

Two scale arms are printed side by side because the scale a repair is fitted on is a finding, not a
footnote: the same intercept fitted inside the interval composition degrades China, fitted on the
composed four-year risk it does not.

    python analysis/output/make_table4_notes.py
"""
import numpy as np
import pandas as pd

T = "H:/脑出血国际队列/results/tables/"
CTRY = {"US": "United States", "CN": "China", "KR": "Korea", "MX": "Mexico"}
ORDER = ["CN", "KR", "MX", "US"]

R = pd.read_csv(T + "incident_horizon_recal_2026-11-03.csv")
U = pd.read_csv(T + "incident_update_strategies_paired_2026-11-03.csv")
U = U[U.horizon_rule == "cif_mid"]


def pct_ci(s, q=(2.5, 97.5)):
    return np.percentile(s, q)


print("### A. paired repair gains over frozen, NB@5%, 2% local, per model")
for mdl in ["logistic", "elasticnet", "xgboost"]:
    dm = R[R.model == mdl]
    for strat in ["offset_horizon", "offset_interval", "recalibrate_horizon"]:
        p = dm[dm.frac == 0.02].pivot_table(index=["held", "rep"], columns="strategy",
                                            values="nb_at_05", observed=True, dropna=False)
        g = (p[strat] - p["frozen_sub"]).to_frame("gain").dropna().reset_index()
        cells = []
        for h in ORDER:
            s = g[g.held == h]["gain"]
            if not len(s):
                continue
            lo, hi = pct_ci(s)
            cells.append(f"{CTRY[h]} {s.mean():+.6f} (SD {s.std():.6f}, [{lo:+.5f},{hi:+.5f}], "
                         f"beats frozen {int((s > 0).sum())}/{len(s)})")
        print(f"  {mdl:10s} {strat:20s} " + "; ".join(cells))

print("\n### B. level ratio after the horizon-scale repair: mean vs median vs IQR (Monte-Carlo spread)")
for h in ORDER:
    r = R[(R.model == "logistic") & (R.frac == 0.02) & (R.strategy == "offset_horizon") & (R.held == h)]
    q = r["pred_over_obs"]
    f = R[(R.model == "logistic") & (R.frac == 0.02) & (R.strategy == "frozen_sub") & (R.held == h)]
    print(f"  {CTRY[h]:14s} frozen {f['pred_over_obs'].mean():.2f} -> repaired mean {q.mean():.3f} "
          f"median {q.median():.3f} IQR [{q.quantile(.25):.3f}, {q.quantile(.75):.3f}] over "
          f"{len(q)} draws of {int(r['local_persons'].max()):,} local adults")

print("\n### C. paired retrain - frozen horizon AUROC, all 4 panels x 3 models")
piv = R[R.frac > 0].pivot_table(index=["held", "model", "frac", "rep"], columns="strategy",
                                 values="auroc", observed=True, dropna=False)
diff = (piv["retrain_local"] - piv["frozen_sub"]).to_frame("d").dropna().reset_index()
for f, g in diff.groupby("frac"):
    v = g["d"]
    print(f"  frac={f:.2f}: mean {v.mean():+.4f} (SD {v.std():.4f}); worse in {int((v < 0).sum())}/{len(v)}")
print("  per panel, logistic:")
dl = diff[diff.model == "logistic"]
for f, g in dl.groupby("frac"):
    print(f"    frac={f:.2f} " + "  ".join(f"{CTRY[h]} {s['d'].mean():+.4f}"
                                           for h, s in g.groupby("held")))

print("\n### D. Table 4 continued - update spectrum, logistic, 2% local (mean over replications)")
strat_order = ["offset_horizon", "recalibrate_horizon", "time_only", "pooled",
               "revise_lam0.003", "revise_lam0.3", "revise_lam3", "refit_local"]
lbl = {"offset_horizon": "intercept only (horizon scale)",
       "recalibrate_horizon": "intercept + slope (horizon scale)",
       "time_only": "time coefficients only",
       "pooled": "pooled updating (Riley)",
       "revise_lam0.003": "penalised revision, lambda 0.003",
       "revise_lam0.3": "penalised revision, lambda 0.3",
       "revise_lam3": "penalised revision, lambda 3",
       "refit_local": "de novo local refit"}
u2 = U[(U.model == "logistic") & (U.frac == 0.02)]
print("| Strategy | " + " | ".join(f"{CTRY[h]} AUROC / NB" for h in ORDER) + " |")
print("|---|---|---|---|---|")
for s in strat_order:
    g = u2[u2.strategy == s]
    cells = []
    for h in ORDER:
        gh = g[g.held == h]
        if not len(gh):
            cells.append("| —")
            continue
        cells.append(f"| {gh.auroc.mean():.4f} / {gh.nb_at_05.mean():+.5f}")
    print(f"| {lbl[s]} " + "".join(cells) + " |")
print("\n  frozen reference (same rows): " + "  ".join(
    f"{CTRY[h]} {u2[u2.held == h].auroc_frozen.mean():.4f} / {u2[u2.held == h].nb_frozen.mean():+.5f}"
    for h in ORDER))
print("  flagged at 5% after each arm: " + "  ".join(
    f"{s}: " + "/".join(f"{u2[(u2.strategy == s) & (u2.held == h)].flagged_at_05.mean():.3f}" for h in ORDER)
    for s in ["offset_horizon", "refit_local", "pooled"]))

print("\n### E. learning curve (logistic): AUROC gain over frozen, [CN/KR/MX/US]")
for s in ["pooled", "revise_lam0.3", "revise_lam3", "refit_local", "time_only"]:
    g = U[(U.model == "logistic") & (U.strategy == s)].assign(g=lambda x: x.auroc - x.auroc_frozen)
    print(f"  {s:14s} " + "  ".join(
        f"{f:.0%}[" + "/".join(f"{g[(g.frac == f) & (g.held == h)].g.mean():+.4f}" for h in ORDER) + "]"
        for f in sorted(g.frac.unique())))
print("  NB@5% gain over frozen, same arms:")
for s in ["pooled", "revise_lam3", "refit_local", "time_only", "offset_horizon"]:
    g = U[(U.model == "logistic") & (U.strategy == s)]
    print(f"  {s:14s} " + "  ".join(
        f"{f:.0%}[" + "/".join(f"{g[(g.frac == f) & (g.held == h)].nb_gain.mean():+.5f}" for h in ORDER) + "]"
        for f in sorted(g.frac.unique())))
