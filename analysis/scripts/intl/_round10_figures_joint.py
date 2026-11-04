"""Round-10 P0-4: renumber the figures so the JOINT primary estimator owns the main figures, demote the
old logistic / XGBoost / class-ablation / specification-grid / logistic-calibration figures to Supplementary
figures, fix the Figure 9 caption's stale logistic P/O (1.02 / 3.22 / 1.16), and remap the six in-text
Figure references. Every main figure now names the model, the horizon rule and the evaluation frame.

Marker-based rewrite of the whole '## Figures' block + targeted reference remaps; atomic write."""
import io, os

MD = "H:/脑出血国际队列/deliverables/manuscript.md"
with io.open(MD, "r", encoding="utf-8") as f:
    text = f.read()
orig = text

# ---------- 1. remap in-text Figure references (do this BEFORE replacing the Figures block) ----------
fig_ref_fixes = [
 ("weights (Figure 8).", "weights (Figure S6)."),
 ("fixed, observed risk with person-clustered bootstrap intervals, `intl/incident_cr_joint_primary.py`;\nFigure 9)",
  "fixed, observed risk with person-clustered bootstrap intervals, `intl/incident_cr_joint_primary.py`;\nFigure 1)"),
 ("person-clustered bootstrap band (Figure 9b, `incident_cr_joint_calibration_smooth`)",
  "person-clustered bootstrap band (Figure 4, `incident_cr_joint_calibration_smooth`)"),
 ("the four panels disagree (Table S8, Figure 1). Deployed frozen",
  "the four panels disagree (Table S8, Figure S1). Deployed frozen"),
 ("the per-panel cascade behind Figure 10, computed", "the per-panel cascade behind Figure 6, computed"),
 ("person-clustered bootstrap band, Figure 9b),", "person-clustered bootstrap band, Figure 4),"),
]
for old, new in fig_ref_fixes:
    assert text.count(old) >= 1, "fig ref anchor missing: " + old[:55]
    text = text.replace(old, new)
    print("remapped x%d: %s" % (text.count(new), old[:50]))

# ---------- 2. replace the whole Figures block ----------
START = "## Figures"
i0 = text.find(START)
assert i0 != -1
old_figs = text[i0:]

new_figs = (
"## Figures\n\n"
"Six main figures, all drawn from the dated CSVs in `results/tables/` and "
"`data/processed/intl/incident/` that the tables are transcribed from, so a figure and a table cannot "
"disagree. The four joint-model figures (1-4) are the primary estimator's own output; the estimand and "
"sample-flow figures (5-6) are model-agnostic. Every main figure names the model, the horizon rule and the "
"evaluation frame in its title. The earlier logistic / XGBoost adaptation, fitting-scale, ranking-vs-level, "
"complexity, class-weight, specification-grid and logistic-calibration figures are retained as Supplementary "
"Figures S1-S8; they are labelled as the model they actually plot and are no longer the headline panels.\n\n"
"- **Figure 1. Cross-country calibration of the joint competing-risks model (primary estimator).** "
"`incident_joint_fig1_calibration` - observed four-year risk (IPCW, `cif_mid`) against predicted risk in "
"deciles of the *frozen joint model*, one facet per held-out country, with person-clustered observed-risk "
"intervals; the filled circles are the frozen deciles and the vermilion squares are the same deciles after "
"the one-parameter intercept repair fitted on 5% of the held-out adults. The dotted line is correct "
"calibration. Mexico's ten frozen deciles sit far above the diagonal (the level error is a level error), the "
"repair pulls them onto it, and the United States' middle deciles move *past* the diagonal - the shape "
"problem the decile count makes visible. Model: joint multinomial competing-risks; rule: `cif_mid`; frame: "
"leave-one-country-out evaluable persons, never in any local adaptation sample.\n"
"- **Figure 2. Joint-model local update: net benefit against local sample size.** "
"`incident_joint_fig2_update` - four-year net benefit at the illustrative 5% threshold against the size of "
"the local sample (2-50%, log axis) for the three prespecified policies (*always frozen*, *always "
"recalibrate*, *selective*), one facet per held-out country, every arm scored on identical evaluation "
"persons; the dashed line is treat-none. In Mexico the selective and always-recalibrate arms lift the net "
"benefit from about -0.0037 to near zero by 5% local data, while in China and Korea they track the frozen "
"line (nothing to repair). Model: joint competing-risks; rule: `cif_mid`; frame: 40 person-disjoint "
"adaptation/evaluation splits.\n"
"- **Figure 3. Joint-model predicted \u00f7 observed under four observed-risk estimators.** "
"`incident_joint_fig3_observed_risk` - the transported joint prediction divided by the observed four-year "
"risk under the hard-midpoint, uniform-within-interval and model-based conditional allocations "
"(`incident_cr_alloc_variants_cif_mid.csv`) and under the pooled-hazard interval-censored MLE "
"(`incident_cr_interval_flexhaz_cif_mid.csv`), log axis, one group per country. Only Mexico stays above two "
"under every allocation; the pooled-hazard MLE's China dip (0.80 \u2192 0.40) is an estimand/censoring "
"re-specification, not an allocation effect, and China is unmoved (0.80) under the three estimand-matched "
"allocations. Model: joint competing-risks; frame: the same `cif_mid` evaluable set with IPCW.\n"
"- **Figure 4. Smooth joint-model calibration with a person-clustered bootstrap band, before and after the "
"local repair.** `incident_cr_joint_calibration_smooth` - observed four-year risk as a spline function of the "
"frozen joint model's linear predictor (log-log axes, dotted line of correct calibration, vertical line at "
"the 5% threshold), frozen (blue) versus after the 5% local intercept (vermilion). In Mexico a predicted "
"risk near 0.11 corresponds to a smoothed observed risk of 0.047 (band 0.019-0.108): the top of the risk "
"range is over-predicted roughly twofold even though the panel average is over-predicted threefold, and the "
"intercept moves the whole curve without bending the tail back onto the diagonal - a level repair is not a "
"shape repair, and the tail is where a 5% threshold acts. Model: joint competing-risks; rule: `cif_mid`.\n"
"- **Figure 5. The estimand, drawn.** `incident_estimand_cif` - Aalen\u2013Johansen cumulative incidence of "
"first stroke against years from entry under three interval-dating rules, per country, with the naive "
"1 \u2212 Kaplan\u2013Meier complement that treats death as censoring overlaid; `incident_ascertainment` - "
"observed four-year incidence, predicted \u00f7 observed and the value of a level repair under the primary "
"(permissive) and partial-strict coverage rules, per country. These are observed-risk / estimand figures and "
"do not depend on the classifier.\n"
"- **Figure 6. Sample flow per panel, from interviews to the four-year evaluation frame.** "
"`incident_sample_flow` - four stages per country (adults ever interviewed, at risk after excluding prevalent "
"stroke, contributing at least one analysable interval, evaluable at the four-year horizon), with the terminal "
"composition of the last stage printed beside each row: events, deaths inside the window counted as "
"determined non-events, and adults stroke-free through the horizon. Drawn from `intl/incident_sample_flow.py`, "
"which reads the same horizon frame as every four-year table, so the bars and Table 1 cannot disagree. "
"Korea's zero deaths inside the window are a property of the released wave files, not of Korean mortality.\n\n"
"### Supplementary figures\n\n"
"- **Figure S1. The logistic / XGBoost adaptation experiment (superseded by Figure 2).** "
"`incident_adapt_nb_logistic`, `incident_adapt_nb_xgboost` - a 2 \u00d7 2 facet per held-out country, four-year "
"net benefit at a 5% threshold against local sample size (2-50%, log axis) for all five arms on identical "
"evaluation persons, SD bars across 20 draws; the yellow band is treat-all and the black line treat-none. "
"Model: logistic / XGBoost (sensitivity to the joint Figure 2).\n"
"- **Figure S2. What the fitting scale is worth, and what retraining is worth (logistic).** "
"`incident_adapt_scale` - the paired net-benefit gain over frozen for one intercept fitted on the interval "
"scale and on the horizon scale at 2% local data, every replicate shown; China's interval-fit column is "
"entirely below zero. `incident_adapt_auroc` - horizon AUROC against local sample size, frozen versus "
"retrained. Model: logistic.\n"
"- **Figure S3. Ranking versus level (logistic).** `incident_level_interval`, `incident_level_composed` - "
"mean predicted risk per model per country against the observed rate (dashed), on the interval grid and on "
"the composed four-year horizon, log axis; `incident_composition` - the same logistic model scored as one "
"four-year interval against the composed hazard. Model: logistic.\n"
"- **Figure S4. Transportability by model complexity.** `incident_internal_vs_loco` - internal "
"(person-clustered CV) against mean held-out AUROC; `incident_spread` - best-minus-worst held-out AUROC "
"across the four countries by model; `incident_vs_prevalent` - the same three classifiers on the prevalent "
"and the incident outcome. These compare classifiers on the shared estimand (Table S7), not the joint "
"primary estimator.\n"
"- **Figure S5. Class-weight ablation (cross-sectional arm).** `incident_ablation_skill` - Brier skill "
"against the train-prevalence constant for logistic, plain / Platt / isotonic / balanced forest and gradient "
"boosting, four countries.\n"
"- **Figure S6. The same estimand under four hazard specifications and five ways of writing the follow-up "
"(Table 8).** `incident_link_grid` - predicted \u00f7 observed four-year risk for the published L2 logistic, an "
"unpenalised logistic GLM, a cloglog hazard with interval length as a covariate and the proportional-hazards "
"formulation with log-length as an offset, one facet per country, five bars per specification; the vermilion "
"bar is the interval-censored likelihood maximised directly, and the grey hatched column (\u2020) places the "
"stroke in the last sub-interval (drawn for transparency, excluded from every conclusion). This is the "
"separately-fitted sensitivity arm; the joint primary composition is Figure 3.\n"
"- **Figure S7. Logistic calibration by risk decile and smooth curve, before and after the local repair "
"(superseded by Figures 1 and 4).** `incident_calibration_curves` - observed four-year risk (IPCW, `cif_mid`) "
"against predicted risk in deciles of the *frozen logistic model*, open vermilion squares after the 5% "
"intercept repair, person-clustered bootstrap intervals; `incident_calibration_smooth` - the logistic spline "
"equivalent. The logistic panel ratios here (China 1.02, Mexico 3.22, United States 1.16) belong to the "
"logistic sensitivity arm; the joint primary estimator's frozen ratios are 0.80 / 1.15 / 2.98 / 0.90 "
"(Table 3, Figures 1 and 4), and it is the joint figures that carry the headline.\n"
"- **Figure S8. Age-band transportability (logistic arm).** `incident_subgroup_age` - AUROC by age band with "
"person-clustered 95% CIs, and net benefit by age band with treat-all marked, four countries. The joint "
"primary estimator's within-population age analysis is Table 12; this figure plots the logistic arm.\n\n"
"`intl/make_figures_incident.py` and `intl/incident_figures_joint.py` generate these panels; the "
"three-cohort panels drafted before the estimand audit are kept in "
"`deliverables/figures/incident/superseded/` and are not cited.\n"
)

text = text[:i0] + new_figs
tmp = MD + ".tmp"
with io.open(tmp, "w", encoding="utf-8") as f:
    f.write(text); f.flush(); os.fsync(f.fileno())
os.replace(tmp, MD)
print("rewrote Figures block; delta bytes", len(text) - len(orig))
