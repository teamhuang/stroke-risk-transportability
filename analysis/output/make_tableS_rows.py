"""Print manuscript Supplementary tables S1 and S2 from the published cif_mid outputs.

S1 is the accounting the design rests on and the interval-level absolute risk behind every horizon
number; S2 is the sensitivity grid. Both were drafted against the three-panel pre-audit frame, which is
why they are generated rather than typed (docs/SELF_AUDIT.md defect 15).

    python analysis/output/make_tableS_rows.py
"""
import json
import numpy as np
import pandas as pd

T = "H:/脑出血国际队列/results/tables/"
CTRY = {"US": "United States", "CN": "China", "KR": "Korea", "MX": "Mexico"}
ORDER = ["CN", "KR", "MX", "US"]

P = pd.read_csv(T + "incident_loco_common_H4_2026-11-03.csv")
ACC = json.load(open(T + "incident_horizon_accounting_2026-11-03.json", encoding="utf-8"))
DIAG = json.load(open(T + "incident_personperiod_diagnostics_2026-11-03.json", encoding="utf-8"))
ASC = pd.read_csv(T + "incident_ascertainment_sensitivity_2026-11-03.csv")


def rows(f, level, model="logistic"):
    """One row per held-out country at one scale, with the interval rows' null horizon_rule respected."""
    d = f[(f.model == model) & (f.level == level)]
    d = d[(d.horizon_rule == "cif_mid") | d.horizon_rule.isna()]
    if not len(d):
        raise SystemExit(f"empty: level={level} in a table that should carry it")
    return d.set_index("held")


print("### S1a horizon accounting, keyed arms")
for k in ["H4_cif_mid_common_linear", "H4_exclusive_start_common_linear"]:
    a = ACC["keyed_accounting_by_arm"][k]
    print(f"  {k}: total {a['persons_total']:,} | events {a['event_within_horizon']:,} | "
          f"death as non-event {a['death_counted_as_non_event']:,} | death excluded "
          f"{a['death_excluded_from_frame']:,} | lost-before-H excluded "
          f"{a['lost_before_horizon_excluded']:,} | stroke-free through H "
          f"{a['stroke_free_through_horizon']:,} | evaluable {a['evaluable']:,} | prevalence "
          f"{a['observed_prevalence_unweighted']:.4f} unweighted / "
          f"{a['observed_prevalence_ipcw']:.4f} IPCW | median IPCW {a['median_ipcw_weight']}")

print("\n### S1b interval-level absolute risk (logistic, interval rows of the published LOCO table)")
iv = rows(P, "interval")
for h in ORDER:
    r = iv.loc[h]
    print(f"  {CTRY[h]}: predicted {r.mean_pred:.4f} vs observed {r.obs_prev:.4f} | Brier {r.brier:.4f}"
          f" | skill {r.skill_train:+.4f} | scaled Brier {r.scaled_brier:+.4f} | intercept "
          f"{r.cal_intercept:+.2f} | slope {r.cal_slope:.2f} | AUROC {r.auroc:.4f} "
          f"({r.auroc_lo:.4f}-{r.auroc_hi:.4f})")

print("\n### S1c composed four-year risk (logistic)")
hz = rows(P, "horizon_4y_composed")
for h in ORDER:
    r = hz.loc[h]
    print(f"  {CTRY[h]}: predicted {r.mean_pred:.4f} vs observed {r.obs_prev:.4f} (ratio "
          f"{r.pred_over_obs:.2f}, inverse {r.obs_over_pred:.2f}) | realised {r.realised_horizon_years} y"
          f" | median training interval {r.train_interval_years_median} y | share of training intervals "
          f"within a factor 2 of the horizon {100 * r.train_within_factor2_of_horizon_pct:.1f}% | "
          f"longest interval {r.train_interval_years_max} y")

print("\n### S1d mortality recovery and vital status, per cohort")
print("  (coverage keys are FRACTIONS of wave records; printed here as % - defect 17)")
rec = DIAG if isinstance(DIAG, list) else DIAG.get("per_cohort", [])
PCT = ("death_date_coverage_fraction", "iwstat_coverage_fraction", "date_coverage_of_wave_records",
       "weight_nonnull_pct_of_wave_records")
for v in (rec if isinstance(rec, list) else [rec]):
    if not isinstance(v, dict):
        continue
    c = v.get("cohort") or v.get("country") or "?"
    keys = [k for k in v if any(s in k for s in
            ("exit", "death", "vital", "mortality", "window", "alive", "interview", "coverage"))]
    parts = []
    for k in keys[:12]:
        x = v[k]
        parts.append(f"{k}={x}" if not isinstance(x, float) or k not in PCT
                     else f"{k}={x} ({100 * x:.1f}%)")
    print(f"  {c}: " + "; ".join(parts))

print("\n### S2 sensitivity arms (logistic): interval / composed AUROC and composed NB@5% per country")
ARMS = [("Primary: ten concepts, time-included, 4 y, unweighted", T + "incident_loco_common_H4_2026-11-03.csv", "interval", "horizon_4y_composed"),
        ("No time term in the hazard", T + "incident_loco_common_none_H4_2026-11-03.csv", "interval", "horizon_4y_composed"),
        ("Extended feature set (union, not intersection)", T + "incident_loco_extended_linear_H4_2026-11-03.csv", "interval", "horizon_4y_composed"),
        ("Survey design weights in the hazard", T + "incident_loco_common_linear_H4_weighted_2026-11-03.csv", "interval", "horizon_4y_composed"),
        ("Six-year horizon", T + "incident_loco_common_linear_H6_2026-11-03.csv", "interval", "horizon_6y_composed")]
print("| Arm | " + " | ".join(f"{CTRY[h]} AUROC (interval / horizon)" for h in ORDER) +
      " | " + " | ".join(f"{CTRY[h]} NB@5%" for h in ORDER) + " |")
print("|---|" + "---|" * 8)
for lab, f, lv1, lv2 in ARMS:
    d = pd.read_csv(f)
    a1, a2 = rows(d, lv1), rows(d, lv2)
    cells = [f"| {a1.loc[h].auroc:.4f} / {a2.loc[h].auroc:.4f} " for h in ORDER]
    nb = [f"| {a2.loc[h]['nb_at_0.05']:+.5f} " for h in ORDER]
    print(f"| {lab} " + "".join(cells) + " " + "".join(nb) + "|")
print("  NOTE the weighted arm's net benefit is computed on the design-weighted denominator, so its")
print("  NB column is not on the same scale as the other four rows; the AUROC columns are comparable.")

# the estimand arms, which are not in the LOCO files
print("\n### S2b estimand and coverage arms (logistic)")
pre = P[(P.model == "logistic") & (P.horizon_rule == "exclusive_start") &
        (P.level == "horizon_4y_composed")].set_index("held")
cur = hz
print("| Arm | " + " | ".join(CTRY[h] for h in ORDER) + " |")
print("|---|---|---|---|---|")
for lab, src, col in [("Composed horizon, midpoint dating (reported)", cur, "auroc"),
                      ("Composed horizon, interval-start dating (pre-audit frame)", pre, "auroc")]:
    print(f"| {lab} AUROC | " + " | ".join(f"{src.loc[h][col]:.4f}" for h in ORDER) + " |")
for lab, src, col in [("  same, predicted / observed", cur, "pred_over_obs"),
                      ("  same, predicted / observed", pre, "pred_over_obs")]:
    print(f"| {lab} | " + " | ".join(f"{src.loc[h][col]:.2f}" for h in ORDER) + " |")
a = ASC[ASC.model == "logistic"].set_index(["held", "coverage_rule"])
for cr, lab in [("published_t_cens", "primary coverage"), ("strict_t_ask", "strict coverage")]:
    r = a.loc[[(h, cr) for h in ORDER]]
    print(f"| {lab}: evaluable / events / NB@5% | " + " | ".join(
        f"{int(x.evaluable):,} / {int(x.events)} / {x.net_benefit_5pct:+.5f}" for _, x in r.iterrows()) + " |")
    print(f"| {lab}: predicted / observed | " + " | ".join(
        f"{x.pred_over_obs_ipcw:.2f}" for _, x in r.iterrows()) + " |")
