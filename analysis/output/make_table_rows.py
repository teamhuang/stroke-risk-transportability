"""Print manuscript Table 2 and Table 3 rows from the published four-panel incident tables.

Kept as a script rather than a shell one-liner because markdown tables are the single most common
source of transcription error in this project's drafts: every number here is read from the published
CSV in the same expression that formats it.

    python analysis/output/make_table_rows.py
"""
import pandas as pd

T = "H:/脑出血国际队列/results/tables/incident_loco_common_H4_2026-11-03.csv"
NAME = {"logistic": "**Logistic**", "elasticnet": "Elastic net logistic",
        "spline_logistic": "Spline logistic", "agesex_logistic": "Age + sex only",
        "random_forest": "Random forest (unweighted)",
        "random_forest_balanced": "Random forest, balanced weights", "xgboost": "XGBoost",
        "gradient_boosting": "Gradient boosting", "lightgbm": "LightGBM"}
ORDER = ["elasticnet", "logistic", "spline_logistic", "random_forest", "random_forest_balanced",
         "xgboost", "gradient_boosting", "lightgbm", "agesex_logistic"]
CT = ["US", "CN", "KR", "MX"]

d = pd.read_csv(T)
iv = d[d.level == "interval"]
print("### TABLE 2 (interval scale, fitted on the other three panels)")
for m in ORDER:
    r = iv[iv.model == m].set_index("held").loc[CT]
    cells = [f"{a:.3f} ({lo:.3f}-{hi:.3f})" for a, lo, hi
             in zip(r.auroc, r.auroc_lo, r.auroc_hi)]
    print(f"| {NAME[m]} | " + " | ".join(cells)
          + f" | {r.auroc.mean():.3f} | {r.auroc.max() - r.auroc.min():.3f} |")

hz = d[(d.level == "horizon_4y_composed") & (d.horizon_rule == "cif_mid")]
print("\n### TABLE 3 (4-year composed horizon, cif_mid): auroc / mean_pred vs obs / pred-over-obs / NB@5%")
for m in ORDER:
    r = hz[hz.model == m].set_index("held").loc[CT]
    cells = [f"{x.horizon_auroc:.3f} ({x.auroc_lo:.3f}-{x.auroc_hi:.3f}) | {x.mean_pred:.4f} vs "
             f"{x.obs_prev:.4f} | {x.pred_over_obs:.2f} | {x['nb_at_0.05']:+.5f}"
             for _, x in r.iterrows()]
    print(f"| {NAME[m]} | " + " | ".join(cells) + " |")

print("\n### logistic detail per country")
r = hz[hz.model == "logistic"].set_index("held").loc[CT]
for c, x in r.iterrows():
    print(f"{c}: n={int(x.persons)} ev={int(x.events)} obs_unw={x.obs_prev_unweighted:.4f} "
          f"obs_ipcw={x.obs_prev:.4f} mean_pred={x.mean_pred:.4f} pred/obs={x.pred_over_obs:.3f} "
          f"auroc={x.horizon_auroc:.4f} [{x.auroc_lo:.4f},{x.auroc_hi:.4f}] auprc={x.auprc:.4f} "
          f"brier={x.brier:.4f} skill_train={x.skill_train:+.4f} scaled_brier={x.scaled_brier:+.4f} "
          f"slope={x.cal_slope:.3f} intercept={x.cal_intercept:+.2f} "
          f"nb5={x['nb_at_0.05']:+.5f} nb_all5={x['nb_all_at_0.05']:+.5f} "
          f"nb2={x['nb_at_0.02']:+.5f} nb_all2={x['nb_all_at_0.02']:+.5f} "
          f"nb10={x['nb_at_0.1']:+.5f} nb_all10={x['nb_all_at_0.1']:+.5f} "
          f"nb15={x['nb_at_0.15']:+.5f} nb_all15={x['nb_all_at_0.15']:+.5f} "
          f"train_support={x.train_within_factor2_of_horizon_pct:.3f} "
          f"realised={x.realised_horizon_years:.3f} n_feat={int(x.n_features)}")

print("\n### single-interval (non-composed) horizon, logistic  [the step=None arm]")
si = d[(d.level == "horizon_4y_single_interval") & (d.horizon_rule == "cif_mid")]
r = si[si.model == "logistic"].set_index("held").loc[CT]
for c, x in r.iterrows():
    print(f"{c}: auroc={x.horizon_auroc:.4f} mean_pred={x.mean_pred:.4f} obs={x.obs_prev:.4f} "
          f"pred/obs={x.pred_over_obs:.3f} skill={x.skill_train:+.4f}")

print("\n### exclusive_start arm, logistic (the pre-audit estimand, for the before/after sentence)")
ex = d[(d.level == "horizon_4y_composed") & (d.horizon_rule == "exclusive_start")]
r = ex[ex.model == "logistic"].set_index("held").loc[CT]
for c, x in r.iterrows():
    print(f"{c}: auroc={x.horizon_auroc:.4f} mean_pred={x.mean_pred:.4f} obs={x.obs_prev:.4f} "
          f"pred/obs={x.pred_over_obs:.3f} intercept={x.cal_intercept:+.2f} nb5={x['nb_at_0.05']:+.5f} "
          f"n={int(x.persons)}")
