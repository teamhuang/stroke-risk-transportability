# Pre-delivery self-audit (AGENTS 7-dimension checklist + verdict)

Study (as of 2026-11-03): **incident (first reported) stroke** prediction in four nationally
representative ageing cohorts — United States RAND HRS 1992-2022 (16 waves), China CHARLS release D,
Korea KLoSA waves 1-9, Mexico MHAS release D — as discrete-time hazards on **430,521 person-intervals
from 94,005 at-risk adults, 1,062,341 person-years, 6,979 incident events**; nine classifiers including
an age+sex and a spline baseline; leave-one-country-out at two scales (per-interval and composed
4-year horizon); calibration with two naive Brier references; decision-curve net benefit; and a
frozen / intercept-only / recalibrate / retrain adaptation experiment. The reported four-year
estimand is the **cumulative incidence** of a first stroke with competing deaths kept in as
non-events and loss to follow-up carried by IPCW (see defect 8 - this replaced an earlier frame that
mixed two dating conventions, and it materially changes which country needs repair).
The earlier cross-sectional work (NHANES 14-variable prevalent arm, temporal external, race/ethnicity
LOSO, PHQ association, permutation importance; plus the four-country prevalent LOCO, **247,088
respondent-waves from 80,856 adults, 8,181 prevalent strokes**) survives only as the comparison arm and
Supplementary material; nothing in the main text's claims rests on it.

Every number below is transcribed from software output
(`results/tables/incident_loco_common_H4_2026-11-03.csv`,
`incident_adaptation_2026-11-03.csv`, `incident_internal_clustered_2026-11-03.csv`,
`incident_personperiod_diagnostics_2026-11-03.json`, `rf_probability_ablation_common_2026-11-03.csv`,
and for the comparison arm `data/processed/intl/corrected/loco_intl_models.csv`,
`results/tables/loco_intl_internal_clustered.csv`, `results/tables/intl_arm_characteristics_corrected.csv`),
not memory. Figures are generated FROM those files by `make_figures_incident.py` /
`make_figures_intl.py` (figure newer than, and derived from, the numbers — traceability check passed).

## What changed since the previous audit of this file

### Round 9 (honest allocation relabel + cross-check + structural trim) — 2026-11-04

- **Defect 33 — Table 19's midpoint-free estimator was mis-described as a general interval-censored
  conditional.** The clip((H-t_start)/(t_end-t_start)) allocation is a UNIFORM-within-interval assumption, not
  the interval-censored conditional event-time probability; the reviewer was right. Relabelled as
  "uniform-within-interval allocation" with the assumption stated. Added a joint-model-based conditional
  allocation (truncated-exponential in the fitted total hazard, `incident_cr_alloc_variants.py`) that drops the
  uniform assumption; result unchanged: China P/O 0.80 under midpoint/uniform/model-based, Mexico the only move
  2.98->2.18->2.14 (model-based pulls observed risk up ~1.9%, exactly as decreasing within-interval survival implies).
  audit_consistency_round9 checks the third arm's numbers against the CSV and forbids the unqualified
  "interval-censored expectation" label.
- **Wording tightened (no claim change).** abstract "China barely moved" now scoped to the estimand-matched
  allocation check (distinct from Table 15/18's parametric 0.40-0.47); "the rule flagged Mexico alone" ->
  "Mexico was the only country regularly selected" (others fire 2-24%); clinical value explicitly
  "re-evaluate-before-deployment" with the 8/40-splits / <1-net-person caveat.
- **Structure (reviewer's second length flag).** Physically moved the cross-sectional (prevalent) arm and the
  exact-Shapley attributions out of the main article into `deliverables/Supplementary_technical.md` (Notes S-C/S-D),
  leaving concise main stubs with the headline number + scope caveat; recast residual software-development-history
  ("a first version", "rebuilt a second time", "as it should have been from the start", "in the earlier version was")
  as method+result. Kept the grid/likelihood and composition subsections in main because they define primary-model
  tables (Table 8, joint-primary) the reviewer said must remain to understand the primary model.
- **Front matter.** Added author / affiliation / corresponding-author skeleton as [AUTHOR-SPECIFIC] placeholders
  (the file previously carried only a title); enumerated all 36 author-only items in SUBMISSION_BLOCKERS section Z.
- **Gates.** audit_consistency_round9.py 64 PASS; round-8 patched for Table 19's new columns (123 PASS);
  round-7 86 PASS; round-6 53 PASS. manuscript.docx, cover_letter.docx and the new Supplementary_technical.docx
  rebuilt from audited md and validate PASS.


### Round 8 (post-review reconciliation) — 2026-11-04

- **Defect 31 — competing-risk double-count identity was wrong (Finding B, reviewer-correct).** The text and
  scripts asserted `p_s - alpha_s = p_s * p_d`. Numerically false: with lambda_s=0.03, lambda_d=0.02, D=2 the
  gap p_s - alpha_s = 0.001138 and p_d - alpha_d = 0.001148, while p_s * p_d = 0.002283. Correct identity:
  the gap p_s - alpha_s = P(death also falls in the step before the stroke), and the *total* probability-mass
  double-count obeys p_s*p_d = (p_s-alpha_s) + (p_d-alpha_d). Fixed at four sites (manuscript Results + Methods,
  incident_cr_joint.py, incident_cr_exact.py); incident_cr_simulation.py's "bias is the p_s*p_d term" retained
  because it correctly names the total double-count. audit_consistency_round8 checks the identity numerically.
- **Defect 32 — the interval-censored observed risk was mislabelled and its estimand conflated (Findings A + C).**
  Round 7 called the intercept-only MLE "the fully nonparametric limit" and let China's P/O 0.43 stand beside a
  main line of "only Mexico is miscalibrated." Renamed to a constant-hazard parametric model (overclaim
  "fully nonparametric limit" removed). New analyses show the China figure is a *pooled-hazard re-specification*,
  not a time-allocation effect: flexible hazards keep it ~0.40-0.47 (Table 18, so not a flat-hazard artefact), but
  an estimand-matched allocation-only check (identical evaluable frame + IPCW) leaves China at 0.80 (ratio 1.00)
  while Mexico alone moves (2.98->2.18, ratio 1.37; Table 19). The update rule re-run on the interval-censored
  outcome still flags only Mexico (fires 98% and pays in MX, 24% and net-loss in CN). Conclusion rewritten into a
  stable / conditional two-tier.
- **Round-8 additions (not defects, robustness the reviewer required):** five-variable transparent clinical
  baseline (Table 20) - matches discrimination (AUROC within 0.009) and fails to transport in the same places;
  2-D unreported-pre-fatal-stroke sensitivity with parameters explicitly labelled hypothetical (Table S6) -
  uniform under-ascertainment never erases the Mexican over-prediction, only an extreme differential does;
  age gate unified to MIN_AGE=20.
- **Structure:** Results reordered/retitled to the reviewer's six named subsections (population, transportability,
  sensitivity to timing/ascertainment, local recalibration & utility, selective updating, age & robustness);
  Methods converted to ### subheadings (19); the software-development-history defect list and the reference
  verification/selection note were removed from the manuscript; Ethics/CRediT/Data/Code availability rewritten with
  honest [AUTHOR-SPECIFIC] placeholders (never invented). Data availability no longer routes via the retired
  g2aging.org mirror.


The earlier version of this audit certified a **three-country** arm. That arm has been
superseded, for two reasons, and the earlier certification should not be quoted:

1. **Mexico (MHAS) was added**, turning the cross-national test into a four-country one across a
   Western, two East-Asian and one Latin-American health system.
2. **Two data defects in the already-reported arm were found and fixed.** They were surfaced by
   building a per-cohort descriptive table for the new country — the corrected cohort's column
   made the existing cohorts' columns look wrong, which is the value of adding a cohort. Full
   evidence in `results/reports/intl_arm_data_defects_2026-11-02.md`; headline below.
3. **The outcome was rebuilt as incident stroke and the manuscript's identity moved with it.** On
   2026-11-02 the reviewer objection that a cross-sectional "ever reported stroke" item cannot support
   a prospective claim was accepted, and on 2026-11-03 the three panels were expanded into
   person-intervals with mortality-aware censoring (`intl/incident_personperiod.py`) and re-modelled
   leave-one-country-out. This is a design change, not a new table: the headline discrimination drops
   0.06–0.12 AUROC in every country (O16), the paper's central experiment becomes the
   freeze/recalibrate/retrain comparison (O18), and the four-country prevalent arm is demoted to
   Supplementary material. The earlier certification of the prevalent arm as the study's main result
   must not be quoted.

4. **The United States is now in the incident arm, as RAND HRS.** NHANES still cannot be: its
   cycles resample different people, so it has no within-person follow-up and contributes zero
   intervals. RAND HRS 1992-2022 v1 does, and it is the only panel here carrying day-precision
   interview dates (`R{w}IWMID`), a vital-status item that separates "non-response but alive" from
   "died this wave"/"died previous wave"/"dropped from sample" (`R{w}IWSTAT`), and a death date from
   the Tracker file (`RADDATE`, populated for 19,144 of 45,234 respondents). That is what lets the US
   arm censor on death at day precision instead of at a wave's fieldwork window: 14,724 of its
   death-terminated intervals are date-known and only 153 rest on status alone. Harmonisation and
   every value code are recorded in `intl/hrs_reshape.py` and
   `results/reports/hrs_reshape_diagnostics.json`; the coding check that the SAS header could not
   provide is in `results/reports/hrs_metadata_probe.json` (see the note under defect 8's fix list).
   The US panel is now the largest source of events (4,350 of 6,979) and the best-behaved: median
   interval 2.0 years, 95th percentile 3.8 years, so a four-year horizon is interpolation rather
   than extrapolation.
5. **A P0 estimand audit overturned the manuscript's headline, and this audit file says so before
   a reviewer finds it.** Defect 8 is the largest error in this project and it changed the
   direction of the central result on the corrected definition. The adaptation experiment, the
   scale audit (`incident_horizon_recalibration.py`) and the competing-risk audit
   (`incident_competing_risks.py`) are all now reported against a named estimand with the pre-audit
   frame retained as a sensitivity arm, so the reader can see which part of the story was the
   convention and which part survives it.
6. **A fifth convention was audited twice, and both audits found a problem with our own tool.**
   The reviewer's second structural question was whether the composed four-year risks are an artefact of
   a logistic discrete-time hazard that takes interval length as a covariate, fitted on panels that do
   not share a follow-up clock. The arm that answers it (`incident_cloglog.py` +
   `incident_grid_reframe.py`, Table 8) was first run with the stroke forced into the last sub-interval
   of each parent gap, which is an event-time assumption and not a neutral re-cut; two conclusions
   drawn from it are withdrawn (defect 19). The rebuilt arm reported three event-time allocations side by
   side, and the reviewer's second reading was that the replacement was still not the interval-censored
   likelihood — fractional event weight matches the number of events in a gap, not the probability that the
   event lies in it. `intl/incident_ic_grid.py` now maximises the actual likelihood, and under it China and
   the United States cross the line of correct level (1.02 → 0.76, 1.17 → 0.98) where the weighted-row arms
   stopped short, so a third sentence was withdrawn (defect 20). What survives both rebuilds is the paper's
   structure: duration consistency belongs to the exposure specification (offset arm exactly 1.000 at every
   grid and every allocation, and provably so), Mexico over-predicts >2-fold in 16 of 16 honest
   specifications, and the one-intercept repair is worth fitting only in Mexico. Building that arm's anchor
   also exposed the published model's optimiser tolerance (defect 21). The submission is on hold pending
   this being read back by the reviewer; the licence attestations (O7/O8, O22) remain the blocking items.
7. **The third-round review moved the primary analysis, and one of this paper's own claims with it.**
   The reviewer's decisive question was whether Mexico's threefold over-prediction and the repair's gain
   survive a model that is simultaneously duration-consistent and correct about competing death. They do
   (`intl/incident_cr_primary.py`: two cause-specific interval-censored hazards composed into a discrete
   Aalen–Johansen CIF, four specifications, three event-time conventions, 40 splits, 500 person-clustered
   bootstraps): Mexico 3.00 [2.63, 3.46] under the corrected arm against 3.20 under the cause-specific
   one, repair +0.00366 in 40/40 splits, repaired level 1.14. The estimand mixing was real and the
   correction is small — 0.5-3.2% relative across the eight panel-by-link cells — which is a measured
   answer rather than a reassurance. Three things came out of doing it properly that were not known
   beforehand. (i) Defect 23: the sign of the United States repair is a property of the composition, not
   of the country, and the manuscript's heading said the country. (ii) The discrete Aalen–Johansen sum is
   *not* exactly step-invariant even when each cause-specific hazard is: its one-piece value equals the
   cause-specific risk and it converges on the analytic continuous CIF as pieces shrink (0.1-2.6% above at
   four pieces, crossing to ~0.5% below at eight in two panels). That gap is now printed against the
   closed form instead of being described as consistency. (iii) Korea cannot have a competing-risk
   estimand at all from these files — 0 observed deaths, so its CIF equals 1 − KM by construction and its
   death hazard is transported; the arm was written to say so in its own output
   (`klosa_death_ascertainment`) rather than in a footnote. Separately, the adaptation experiment's
   independence is now machine-checked (`intl/incident_adaptation_leakage_audit.py`: 0 shared persons over
   100 replicate × panel splits, the calibration target shown to be the adaptation sample's own event
   fraction, and the IPCW-source question quantified — Mexico's level error would read 3.07 or 3.73 if G
   came only from the source panels or only from the target), and the retrospective "which country should
   update" is replaced by a prespecified policy arm (`intl/incident_update_policy.py`, 200 splits) whose
   failure mode — Korea, where three local events cannot resolve a −0.53 log-odd offset — is the result
   most worth publishing. Defect 22 is the last-writer-wins label trap recurring in a new diagnostics
   file. Submission remains on hold.
8. **The two remaining open review items were closed in the same pass, and both strengthened the central
   claim rather than qualifying it.** P1-5 asked whether Mexico's over-prediction is a risk difference or
   an artefact of four questionnaires that do not ask the same questions. `intl/incident_cr_definition.py`
   answers it by refitting everything - both cause-specific hazards, both compositions, the local repair -
   on three nested feature tiers (19 columns, then 17 with the cardiac and alcohol items removed because
   their *wording* differs, then 11 with the availability-mismatched items removed), and the ratio moves
   3.004 -> 3.171 -> 3.106: 5.5% relative and away from correct, with every interval starting above 2.7 and
   the repair gain holding at +0.00365/+0.00454/+0.00430. The tier that should reproduce the published arm
   does so in all eight frozen cells to within 1e-6 because the script refits through the same code path it
   is being compared against, and the missingness table that justifies each tier is published rather than
   asserted (the hypertension item is 29.1% missing in Korea and 0.0-1.0% elsewhere; the alcohol item is
   near-complete everywhere, so its exclusion is definitional and not a missingness convenience). Published
   as Table 11 with `analysis/output/make_definition_rows.py`. P1-6 asked for the age strata to reach the
   main text; they are Table 12, printed by `analysis/output/make_subgroup_rows.py`, and doing the printer
   properly is what exposed defect 26 - eight hand-quoted cells, two of them unresolvable at the published
   precision, and a column (`pred_over_obs_offset`) that had been published unread and quantifies what one
   intercept does inside a country: Mexico 20-59 goes 2.383 -> 0.728. Defect 25 in the same pass reworded
   the treat-none comparison into a three-way above/tied/below count after finding that all three of
   Mexico's nominal "wins" over doing nothing are under one net person in an 18,818-row evaluation sample.
   What is still open after this round is not analysis: the licence and ethics attestations (A1, A2), the
   convergence decision (B1), the external threshold opinion (P1-4), the literature positioning (P1-7) and
   the journal's live rules (C).

9. **The fifth-round review asked whether the composed CIF is a probability at all, and whether the
   calibration repair can be made age-aware; the first question turned into a genuine correction that the
   headline survives, the second into a result with an honest negative.** Three analyses were run from data
   already on disk, plus two manuscript-hygiene edits, and none of it changed the paper's central number.
   (i) **P0-1, competing-risks composition.** The reviewer charged that the shipped Aalen-Johansen survival
   factor was wrong and should read `1 - p_s - p_d`. That specific charge is *false*: under independent latent
   times the factor `(1 - p_s)(1 - p_d) = exp(-(lambda_s + lambda_d) D)` is exactly right, and the audit now
   says so. But writing it up forced the composition open and exposed a *different*, real error - the shipped
   ladder multiplies marginal step probabilities, whereas an exclusive first-event composition needs
   `alpha_s = lambda_s/(lambda_s + lambda_d) * (1 - exp(-(lambda_s + lambda_d) D))`, so each step's mass was
   `1 + p_s * p_d > 1`. Two independent fixes are reported beside each other: **V5**, the same estimate
   computed exactly on the marginals, and a **joint multinomial competing-risks likelihood** on the three
   mutually-exclusive interval outcomes (stroke-first / death-first / neither) with an analytic gradient
   self-tested to 1.46e-09 and a probability-conservation assert at 1.1e-16 (defects 27-29 were its own build
   bugs, all fixed). A known-truth simulation (independent latent times + frailty + long-gap) confirms the
   direction of the bias. The message the reader needs is invariance: **Mexico's over-prediction is 3.00
   shipped, 2.93 under V5, 2.98 [2.61, 3.43] under the joint model - a 0.96% relative shift - and the one-
   intercept repair still pays (+0.00368 [0.00342, 0.00387], 40/40 splits, repaired level 1.14).** Published
   as Table 9b; the ladder that was drifting to 0.9424 under the shipped composition is flat at 1.000000
   under both fixes. (ii) **P1-2, age-aware recalibration** (`incident_age_recalibration.py`, 120 splits):
   five update strategies compared on persons disjoint from the adaptation sample, judged not only on the
   panel average but on the worst age band. The population intercept that "fixes" Mexico's average leaves a
   2.2x sign error somewhere in the age spectrum and can invert the 20-59 band (2.383 -> 0.728, defect 26);
   adding a linear centred-age term (strategy D) cuts the worst band to 1.2x at 5% and 1.1x at 25% *and* has
   the lowest net-benefit variance (SD 0.00006 at 5%, lower than doing nothing) - the reviewer's "important
   new finding," delivered as a measured result. The honest negative sits with it: **no age-aware update
   lifts Mexico's net benefit above treat-none; all remain <= 0** - ranking is not the problem, the level is.
   Published as Table 13. (iii) **P1-1, smooth calibration curves** (`incident_calibration_smooth.py`, 200
   person-clustered bootstraps, spline `cr(lp, df=4)`): draws observed-vs-predicted risk as a curve rather
   than ten deciles, so the residual *shape* is visible - the intercept repair moves Mexico's whole curve down
   but the top of the range still misses (predicted 0.13 against observed 0.065 [0.014, 0.178] before, 0.066
   after), which is the level-vs-shape distinction the decile plot only hinted at. Published as Figure 9b.
   (iv) **Manuscript hygiene from the SHAP note**: the main-text SHAP subsection is demoted to one paragraph
   pointing at Table S5 (an exact-Shapley attribution on a frozen model is not a new claim, and the reviewer
   was right that it belongs in the supplement), and the abstract was trimmed to exactly 150 words by removing
   an internal word-count meta-note. A three-use IPCW disclosure table was added to Methods so the reader can
   see which weight source produces which level error (3.22 frozen / 3.07 source-only / 3.73 target-only). The
   open items are unchanged and none is analytical: licence and ethics (A1, A2), convergence (B1), the external
   threshold opinion (P1-4) and the journal's live rules (C).

10. **The sixth-round review did not ask for a new statistic; it asked the paper to stop hedging.** Its central
   P0 was that the joint multinomial competing-risks model - already fitted, already shown to reproduce the
   headline - was still being described as "a robustness arm" while V4 remained the reported primary, which is
   exactly the old-V4/new-joint mixing a reviewer calls a submission risk. This round resolves it: the joint
   estimator is now declared the primary absolute-risk model wherever a single headline number is quoted
   (abstract, the primary-analysis subsection, the composition subsection, Table 9b with Joint first as the
   primary column), and Table 9 and the shipped Aalen-Johansen ladder are relabelled the
   *separately-fitted marginal-hazard sensitivity arm*. Because "primary" must then be primary for the age
   subgroups, calibration and decision curves too, `intl/incident_cr_joint_primary.py` regenerates every joint
   sub-analysis from the shared per-person joint CIF (`incident_cr_joint_subgroups.csv`,
   `_deciles.csv`, `_calibration_smooth.{csv,png,pdf}`, `_age_recalibration.csv`/`_summary.csv`, `_dca.csv`),
   and `analysis/output/make_joint_primary_rows.py` prints Table 12, Table 13 and the new three-level
   deployability Table 14 straight from those files - all cross-consistent (joint panel P/O 2.975 = Table 9b =
   subgroup ALL row = age-recal frozen). The joint arm reproduces the same honest story (age-aware strategy D
   cuts the worst band 6.3x to 1.2x/1.1x with the lowest net-benefit variance; no strategy lifts Mexico above
   treat-none; US is the one panel clearing all three levels). The other sixth-round items are editorial and
   were landed in the same pass: Results condensed from fifteen `###` subsections to six by demoting the
   detail blocks to `####` in place (no body moved, so every table/figure cross-reference survives - the
   alternative, a physical reorder with table renumbering, was judged a bigger integrity risk than its gain),
   the "how this section is ordered" meta-paragraph and the round-by-round audit narration ("a reviewer asked",
   "the reviewer warned", "an earlier version described", "this converts the reviewer's finding") removed or
   restated as neutral sensitivity language, the composition *derivation* marked for Supplementary Methods, the
   Table 7 "positive at 5% or more" claim corrected (the repaired net benefit dips negative again at 10%, so it
   is now "close to zero, small-positive at some larger samples", with the replicate SD stated), a seven-element
   primary-estimand definition added at the top of Methods, the outcome relabelled *survey-ascertained*
   throughout, a SHAP scope note added (the attributions explain the ranking classifier arm on log-odds, not
   the joint four-year CIF), and the abstract re-tuned to 131 words under the joint headline. `analysis/output/
   audit_consistency_round6.py` (53 assertions, all PASS) is now the gate: it re-derives every joint-primary
   number from the released `_joint` files and fails the build on any desync or any retired phrase. No new
   code defect surfaced this round (the joint machinery from round 5 was reused unchanged); defect count
   stands at 29. What remains open is still author-side, not analytical: licence and ethics (A1, A2), the
   convergence decision (B1), the external threshold opinion (P1-4), literature positioning (P1-7) and the
   journal's live rules (C).
11. **The seventh-round review was a pre-submission audit, not a request for a new model.** It asked the paper
   to close the remaining P0/P1 gaps and reach submission state, and named one concrete arithmetic error.
   **P0-1 was a real defect, not a rounding artefact:** the flow read `107,898 − 3,775 = 104,121` but that
   subtraction is `104,123`; on disk the gap is exactly two MHAS adults who never gave a determinable dated
   baseline stroke answer and are removed *before* the risk set (`acc["no_determinable_stroke"] = 2`), so the
   correct reconciliation is `ever − not-determinable − prevalent = at risk`. This is logged as defect 30 and
   fixed in prose, Table 1 (a new "Baseline stroke status not determinable" row), Methods and Figure 10;
   `incident_sample_flow.py` now emits the `no_determinable_stroke` column and every node reconciles. **P0-6**
   the selective-updating policy was still on the old logistic model while the primary arm was joint; it is
   re-run on the joint per-person CIF (`incident_update_policy_joint.py`, 200 reps) and replaces Table 10 —
   and the honest finding is that promotion *removed* the logistic arm's apparent "rule misses Korea" failure
   mode (Korea's joint P/O is already 1.15, so recalibration costs net benefit and the rule correctly
   declines). **P0-3** the ~3-fold headline rode on the midpoint dating of interval-censored events;
   `incident_cr_interval_eval.py` re-estimates the observed risk midpoint-free (an intercept-only joint
   competing-risks MLE, the nonparametric limit of the published likelihood) and Table 15 shows Mexico 2.98 →
   **2.10** (bracket 1.22/2.94), so the paper now states the headline as the ascertained-estimand value, not a
   measurement-free clinical fact. **P0-2** adds the outcome-observation mapping (Table 16, tying each label to
   what the survey can observe) and a synthetic unreported-pre-fatal-stroke sweep (`incident_cr_unreported_stroke_sim.py`,
   Table S6): uniform under-ascertainment barely moves the P/O, differential could take Mexico toward ~1.0 —
   an irreducible estimand limit, reported not corrected. **P0-4** rewords KLoSA to "incomplete mortality
   ascertainment limits identification of the competing-risk estimand" (dropping the lower-bound /
   bias-direction conflict); **P0-5** consolidates a weight-disclosure Table 17; **P0-7** tiers "prespecified"
   to analysis-plan-specified with no prospective-registration claim. **P1** wording (events-based sizing,
   "every evaluated split" instead of 40 independent validations, predefined-candidate framing, per-band
   detail) landed too. **Format** for npj: Funding folded into Acknowledgments, the standalone Limitations
   label folded into the Discussion. **References expanded 5 → 15**, every entry resolved against its
   EuropePMC record and cited in first-appearance order [1]-[15] (a Korea self-report-stroke validity study now
   backs the KLoSA caveat); the competing-events-prediction and multicountry-transportability candidates that
   did not resolve were dropped rather than cited from memory. A **TRIPOD+AI item-by-item checklist** is added
   (`deliverables/TRIPODAI_checklist.md`). New gate `analysis/output/audit_consistency_round7.py` (86
   assertions, PASS) runs alongside `audit_consistency_round6.py` (53, PASS). Defect count rises to **30**
   (defect 30 = the cohort-flow arithmetic gap). What remains open is still author-side (licence/ethics/
   authorship/AI disclosure, a prospective external validation, the live journal rules) plus two estimand
   limits that survey data cannot close: within-interval event times and unreported fatal strokes.


## Metadata caveat specific to the RAND HRS release

The SAS header of `randhrs1992_2022v1.sas7bdat` cannot be trusted for labels: `pyreadstat` returns
13,262 label entries for 19,880 columns, so name and label arrays are index-shifted (R1IWMID comes
back "labelled" SMOKEV, R1WTRESP comes back PRCHMEMRY), and the PDF codebook's descriptive table is
a broken multi-column layout. Every code used here was therefore established from the codebook's
"Variable Category Codes" frequency tables **and** cross-checked against the values actually present
in the data; the two agreed exactly on every variable tested (R1MSTAT 1:9837 2:57 3:385 4:310
5:1080 7:621 8:362 against the codebook's own frequency row, R5HIBP {0:9604, 1:9663, 3:7, 4:291}
likewise). Codes 3-6 on the "reports this wave" health items are record-discrepancy flags, not
answers, and are treated as missing; the "ever" items are used instead because they are clean 0/1 in
all 16 waves.

## Defects found in this project's own analysis code on 2026-11-03

These are bugs in the code that produced reported numbers, not in the data. Each one invalidates
something specific, and the invalidation is stated rather than left to be discovered.

1. **The person-clustered bootstrap was a no-op.** `run_loco_v2.bootstrap_indices` selected
   clusters with `rng.random(len(uniq)) < 1.0`, which is true for every draw, so every "resample"
   was the complete sample returned in the same order. Effect: the `*_lo`/`*_hi` columns of the
   first `loco_v2_*.csv` outputs equalled the point estimate exactly (zero-width intervals), and
   the printed CIs `[0.7592,0.7592]` were meaningless. Fixed to draw people **with replacement**
   (`rng.integers`) and expand each draw to that person's row block, wrapping the within-block
   offset so a person drawn twice contributes two copies rather than overflowing into the next
   person. Verified: resample size now varies around n (a 7-row/4-person test gives mean 7.09,
   range 4-12) and CIs are non-degenerate — CN logistic AUROC 0.7592 [0.7466, 0.7706], printed in
   `analysis/output/loco_v2_primary.log` and written to
   `data/processed/intl/corrected/loco_v2_common_wave_age0.csv`.
2. **The manuscript's international-arm CIs are row-level, not person-level.**
   `modeling.bootstrap_ci` resamples rows (`rng.integers(0, n, n)`), and the international tables
   hold 2.9-5.9 rows per adult, so those intervals are too narrow for the stated estimand. The
   person-clustered versions are wider (CN logistic: iid 0.751-0.768 vs clustered
   0.747-0.771). Table 3 must be re-quoted from the clustered arm before submission.
3. **The naive Brier reference was computed wrong.** I used `p(1-p)` with `p` = the *training*
   prevalence. That is the variance a constant predictor would have on a population whose
   prevalence equals `p`; the empirical Brier of that constant on the held-out country is
   `p²(1-q) + (1-p)²q` with `q` = the test prevalence. Where `q ≠ p` — which is the whole point of
   a cross-national test — every "Brier skill score" was wrong, and it was wrong by the exact
   amount the transport failure it was meant to measure. Two references are now reported and
   separated: `brier_naive_train` (what a frozen model degrades to) and `brier_naive_oracle`
   (the test base rate `q(1-q)`, the scaled-Brier denominator, which peeks at the labels and is
   therefore much harder to beat). The same `p(1-p)` error was present in
   `rf_probability_ablation.py` and that script has since been re-run twice — once for this
   reference, once for defect 6 — so its published tables are the corrected ones.
4. **Discrete-time hazards need interval length as a covariate.** My first incident model omitted
   `exposure_years`, so the model was asked to predict the probability of an event in an interval
   while never being told how long the interval is - in a panel that mixes 2-year and 20-year
   gaps. Adding it moved China's held-out interval AUROC from 0.695 to 0.719, and it is also what
   makes the horizon composition honest: stepping in 1-year increments must score each synthetic
   interval as a 1-year interval, otherwise four "2-year hazards" get reported as a 4-year risk
   (that error had inflated Mexico's mean predicted 4-year risk from 0.043 to 0.070).
5. **A concurrent read/write produced a fake result table.** The first `--features extended` run
   read `std_CHARLS.csv` at 23:52 while `clean_intl_std.py` was still writing it at 23:53, and
   produced a China held-out set of n=220 rows (11 events). The file was deleted; nothing from it
   was quoted. Ordering rule: harmonisation writes must complete before any modelling run starts.
6. **`rf_probability_ablation.py`'s `--features` flag was inert.** `main()` computed
   `cols = COMMON + (EXTRA if fset == "extended" else [])` and then passed the *whole* encoded
   frame to `predict()`, so the "common" and "extended" runs produced byte-identical tables and the
   NHANES-only `race_ethnicity_*` columns leaked into the run that claimed to be the harmonised
   subset. Discovered on 2026-11-03 while re-quoting Table 5, after the unrestricted numbers had
   already been printed to a log. Fixed by subsetting the design to the requested concepts; both
   arms were re-run and published as `rf_probability_ablation_common_2026-11-03.csv` and
   `..._extended_...`. The manuscript quotes the corrected common-set table (11 surviving model
   columns). Consequence for the claim, not just the digits: on the properly restricted set Mexico's
   logistic Brier skill is **negative** (−0.008), where the unrestricted run had shown +0.004 — the
   harmonised subset carries no usable absolute-risk information for Mexico, and restoring
   income/BMI/cholesterol is what turns it positive.
7. **`run_incident_internal.py` was written to answer a question the primary script could not.**
   The incident LOCO arm reports absolute held-out performance and has no internal reference, so the
   decay column the manuscript's transportability claim needs did not exist. The new script fits the
   identical pipelines under StratifiedGroupKFold on cohort|pid; its first run is what surfaced O19.
   Nothing in the primary arm was changed by it.
8. **The four-year endpoint mixed two incompatible time conventions, and it is the largest single
   error in this project.** `person_baseline` dated an interval-censored stroke to the **start** of
   the interval that found it, but judged a person's coverage from the **end** of their last
   interval, and then dropped everybody who died inside the window. The reported China four-year
   prevalence of 0.0609 is therefore not `P(stroke within 4 years)` under any single convention:
   the Aalen-Johansen cumulative incidence with midpoint dating — the convention that matches the
   discrete-time model's own uniform-within-interval assumption — is 0.0216, and the strict end-rule
   value is 0.0144. The published figure is 2.8x the defensible one.
   Consequence, and it is not cosmetic: judged against 0.0609 the frozen model *under*-predicts
   China by a factor of three (O/E 0.34) and one local intercept is worth +0.0155 net benefit.
   Judged against the corrected estimand the same frozen model is already right for China (O/E
   1.02, intercept worth +0.0001), and the panel where one parameter actually pays is **Mexico**
   (O/E 3.2, gain +0.0045). The manuscript's headline finding was substantially an artefact of the
   label definition. Fixed by `run_incident_loco.horizon_frame`, which names the estimand
   (`cif_mid` primary, `exclusive_start` retained as a published sensitivity arm), carries the IPCW
   weights that loss-to-follow-up needs, and never mixes a start-rule label with an end-rule
   eligibility test again. Evidence: `incident_competing_risks_cif.csv` and
   `incident_competing_risks_estimands.csv`.
9. **`incident_horizon_counts.json` was last-writer-wins across arms, and the published copy was
   the H=6 arm's numbers shipped under the H=4 label.** `run_incident_loco.py` overwrote one file
   on every invocation, so after the sensitivity arms ran, `publish_incident_tables.py` copied an
   H=6 accounting into `results/tables/incident_horizon_accounting_2026-11-03.json`
   (1,966 events / 5,401 deaths / 35,698 stroke-free). The runbook quoted 1,723 / 5,196 / 7,095 for
   the same key — internally inconsistent even against its own totals, since 53,638 - 41,347 =
   12,291 people are excluded, not 7,095. Both are now superseded: the file is keyed by
   `H{horizon}_{rule}_{features}_{time}` and every arm writes its own slot without erasing others.
   This is why a single filename carrying a statistic that several runs produce is a defect, not a
   convenience.
10. **The interval-expander's `exposure_years > 0` filter shifts `follow_years` by one dropped
    interval for a handful of people.** The legacy frame computed follow-up as
    `max(t_end) - min(t_start)` over the rows that survived the filter; `horizon_frame` uses
    `max(end_offset)` measured from the person's entry date. For the two CHARLS/KLoSA people whose
    *first* interval was dropped for non-positive exposure, the two definitions differ, and the
    reconstructed legacy frame reproduces the published 1,723 events and 5,196 deaths but
    39,622 rather than 39,624 stroke-free people. Immaterial to any conclusion; recorded because
    "reproduces exactly" should only ever be said after it has been checked.
11. **The design-weight coverage quoted in the runbook and the manuscript had the wrong
    denominator, and the US weight has a structural zero that "non-null" hides.**
    `personperiod_diagnostics.json` computed `weight_nonnull_pct` over *wave records* (every row in
    the panel, including the vital-status rows of people not interviewed that wave) and the runbook
    and manuscript quoted it as if it were *interval* coverage — 57.4% US / 74.5% CN / 66.8% MX
    instead of the true 100% / 99.0% / 100%. Re-checked while writing the weights paragraph:
    `wt_start` is non-null on 100% of US intervals. The statistic that actually matters is
    non-null **and positive**, because `R{w}WTRESP` is coded 0 (not missing) for in-household persons
    who are not that wave's weight-eligible respondent: 26,967 of 296,199 interviewed rows, 22.6% at
    wave 1, median age 51 where the interviewed mean is 68 (wave 8), and 2,658 of the 2,858 wave-1
    zeros carry a positive household weight. Effective interval coverage is therefore 90.9% US /
    93.4% MX / 99.0% CN / 75.8% KR. The weighted arm already restricted itself to `wt > 0`, so no
    number changes — but the *disclosed* coverage did, and a reader who took "non-null" as
    "usable" would have believed the weighted arm covered every US interval. Fixed by renaming the
    field
    `weight_nonnull_pct_of_wave_records`, adding the three interval-level weight fields, and
    measuring the mechanism with `intl/hrs_weight_zero_probe.py` rather than asserting it;
    `R{w}WTHH` is deliberately not substituted (different estimand).
12. **Two documentation claims about the RAND HRS release were plausible and wrong.** The reshape
    docstring and the data dictionary both said measured BMI comes from "the nurse-exam waves 8, 10,
    12, 14 and 16". The per-wave counts in `hrs_reshape_diagnostics.json` say waves 8-14 and 16
    (7,128-8,409 non-null each), zero in waves 1-7 **and in wave 15**, and self-reported BMI is
    non-null on 98.0-100% of every wave's interviews. Neither error moved an estimate — no model
    uses BMI in the primary arm — but both were written from a mental model of the study design
    instead of from the diagnostic that the same script already produced. Both corrected; the
    dictionary now states the counted waves and names the wave-15 gap explicitly.
13. **`run_incident_internal.py` joined the superseded three-panel LOCO table, so its decay column
    subtracted two different designs.** The default `--loco` filename was the pre-audit
    `incident_loco_common_linear_H4.csv`; the four-panel run writes `_uw`/`_w` and left the old file
    sitting beside it. The published table therefore paired `auroc_clustered` — person-clustered CV over
    four panels, 430,521 intervals — with `mean_loco` averaged over three pre-audit panels, and emitted
    `auroc_held_CN/KR/MX` equal to the *old* manuscript's Table 2 to four decimals. Discovered while
    re-quoting Table 5 (the absence of an `auroc_held_US` column was the tell). Both inputs were real;
    their difference was not a quantity worth stating. Fixed by defaulting to the `_uw` table and
    moving the three stale files to `data/processed/intl/incident/superseded/` with a README, because
    the root cause is a directory holding two generations of the same filename pattern — any script
    that globs or defaults will find the wrong one. Table 5's decay column must be re-quoted from the
    corrected run.
14. **`publish_incident_tables.py` copied working files verbatim, which is what let the `oe_ratio`
    mislabelling (O24) reach the manuscript draft.** The publisher now rewrites that one column
    (`pred_over_obs` plus its reciprocal) and prints the rename per file. Working files are unchanged,
    so any consumer that reads `data/processed/` directly still sees the ambiguous name —
    `make_figures_incident.py` is such a consumer (BLOCKING 4/5).
15. **The manuscript's adaptation section quoted paired gains that no published table contained.**
    Found while re-quoting Table 4: the Results text asserted a Mexico intercept gain of +0.004363
    (SD 0.000279), Korea +0.000550, China −0.000039, United States −0.000741, and the abstract carried
    two of them. The published cif_mid table gives +0.004287 (SD 0.000446), +0.000476, −0.000115 and
    −0.000650; the SDs in the draft (China 0.000451) match the *interval-scale* arm of a different
    script, so the sentence had been assembled from two runs and neither reproduced it. The pre-audit
    Table 4 itself was still in place (three cohorts, 5 replications, `incident_adaptation` numbers and
    a "45/45 comparisons worse" claim) together with a Discussion sentence that the interval-scale
    misfit "cost China 30 times as much as the repair gained anyone" — the true ratio to the largest
    repair gain is 1.06, the 33-fold figure is relative to China's own frozen deficit. All of it is now
    re-quoted, and the section is generated rather than typed:
    `analysis/output/make_table4_rows.py` and `analysis/output/make_table4_notes.py` print every Table 4,
    Table 4-continued and paired-gain figure in this section straight from
    `results/tables/incident_horizon_recal_2026-11-03.csv` and
    `incident_update_strategies_paired_2026-11-03.csv`. Two further claims were corrected against the
    published pre-audit table (China 0.0205 predicted vs 0.0609 observed, intercept worth +0.0153 — the
    draft said 0.0176 / 3.5-fold / +0.0155) and the Limitations sentence about strict coverage was
    relabelled: its 0.0104 → 0.0122 are *unweighted* incidences and its +0.0044 → +0.0023 is the
    whole-panel ceiling fit, not the 2% local repair.
16. **A filter written as `horizon_rule == "cif_mid"` deletes the interval-scale rows, and the figure
    came out empty rather than wrong.** The published LOCO table carries its interval-level rows with
    `horizon_rule` *null* — a per-interval event indicator is the same object under every dating
    convention, so the producer leaves the field blank — while the two horizon levels carry
    `cif_mid`/`exclusive_start`. Filtering on the reported rule therefore selected nothing for
    `incident_spread` or `incident_level_interval`, and matplotlib drew a titled empty axis: an empty
    selection plus a silent `.iloc[0]` produces a blank figure that looks like a result, which is worse
    than an error. Fixed with three guards in the figure script — `primary()` treats null-rule rows as
    part of the reported frame, `need()` aborts on an empty selection, and `cell()` aborts when the
    rows matching a panel position disagree on the value being plotted, the same trap that made
    `x[...].mean_pred.iloc[0]` depend on which arm wrote last. Verified by regenerating all 14 panels
    and reading the six new or rebuilt ones; `incident_spread` now reproduces Table 5's held-out range
    column (0.045 / 0.045 / 0.041 / 0.071 / 0.089 / 0.097 / 0.093 / 0.112 / 0.069) exactly, and
    `incident_composition` reproduces the composed-vs-single-interval risks quoted in the Results
    (China 0.0220 vs 0.0131, United States 0.0292 vs 0.0174).
17. **A diagnostics key named `_pct` held a fraction, and the manuscript, the runbook and the data
    dictionary all quoted it as "0.015% of CHARLS wave records" when the value means 1.5%.** Found
    while generating Supplementary Table S1: the same sentence quoted MHAS as 27.0%, which is the
    fraction read correctly, so one sentence carried two incompatible readings of two identically
    computed fields. `incident_personperiod.py` writes `notna().mean()` rounded to four places under
    `death_date_coverage_pct` and `iwstat_coverage_pct`. The producer now emits `*_fraction`, the
    publisher renames those keys in any JSON it copies (`publish_json`), so the already-published
    deliverable is unambiguous without re-running the expander, and the three documents now read
    1.5% / 27.0% / 53.9%. This is defect 11 again in a different field — a statistic whose name asserts
    a unit the value does not carry — and it is why the supplementary tables are generated from the
    published JSON instead of transcribed from the console.
18. **A justification for the primary coverage rule was defended in Methods and has been withdrawn, and
    testing it exposed a constraint the design did not state.** The reviewer's objection was specific and
    correct: knowing a respondent is alive is not knowing they had no stroke, yet the primary frame
    credits four-year stroke-free time to 10,693 intervals ending in a wave where the stroke item was not
    asked. The manuscript's defence was that the permissive rule is the risk-set rule the discrete-time
    model is fitted with, so re-labelling only the evaluation frame would score a model against a target it
    was never asked to estimate. That is a real invariant and the wrong conclusion: a train/test mismatch
    is repaired by changing the training target. `intl/incident_strict_frame.py` and
    `intl/incident_strict_refit.py` were written to test it, and the first thing they found is that the
    obvious version of "strict" is not available: **in all four cohorts a death is recorded on the interval
    that begins at the last answered interview**, so truncating risk time at `t_ask` deletes all 23,347
    death intervals with it and the fully strict frame estimates cumulative incidence with zero observable
    competing mortality in every panel — 1 − Kaplan–Meier in competing-risks language. Three coherent
    conventions therefore exist (permissive / partial-strict / full-strict) and the middle one is the arm
    that answers the objection without changing the estimand: non-interview tails contribute no risk time
    and their persons leave the frame unless they answered past the horizon, while a death — an actual
    observation — stays a determined non-event. Refitting the whole LOCO design on that risk set
    (419,828 intervals, evaluation frame verified identical to the published strict arm person-for-person
    before any model was fitted: 17,267 / 8,770 / 16,828 / 35,553 and 399 / 177 / 206 / 1,063) preserved
    every conclusion and *strengthened* the most exposed one: Mexico's frozen level error falls 3.22 ->
    2.61, its AUROC rises 0.6107 -> 0.6450, the one horizon-scale intercept is worth +0.001889
    (SD 0.000089, 20/20 replicates) and the repaired net benefit lands at −0.00003 at 2% and turns
    **positive** (+0.00002 to +0.00014) at 5% and above. China's ratio tightens to 1.00 and its intercept
    is worth −0.000001 (14/20 — noise, as it should be); the United States stays the only panel positive
    out of the box (+0.00286) with a *smaller* level error (1.08 vs 1.16), which strengthens the
    recommendation not to recalibrate it. The same run also answers the sample-size question the abstract
    was over-claiming: the fitted intercept's SD (0.278 / 0.644 / 0.436 / 0.244 at 2% for CN / KR / MX /
    US) tracks the binomial expectation 1/√events, so 337 Mexican adults carrying a median of four events
    is where the *direction* becomes unambiguous, not a verified minimum sample size — the manuscript now
    says so explicitly. Status: resolved by disclosure plus a new arm; the withdrawn sentence is removed
    from Methods and the three conventions are named there instead.
19. **The 1-year interval grid was built by assigning each stroke to the last sub-interval of its parent
    gap, which is an event-time assumption the data do not support — and two manuscript conclusions had
    been drawn from it.** `incident_grid_reframe.py`'s first version cut an interval of length *L* into
    ⌈*L*/*δ*⌉ equal pieces and wrote "the parent's terminal status stays on its LAST sub-interval, so no
    dated event moves", defended in the docstring as deliberate because the discrete-time likelihood
    already treats an event row as "at risk for the whole interval, event inside it". The defence is wrong
    in a way the reviewer named exactly: that sentence is true of *one* interval containing an event, and
    false as a claim about *which* of four pieces contains it. A stroke dated somewhere inside a
    1998-2002 interview gap, entered as an event in 2001-2002, asserts three stroke-free years nobody
    reported. The arm therefore changed two things at once — the grid and the within-interval event
    distribution — and the second effect is not small: forcing the event late makes every event survive
    more event-free pieces, so the fitted per-piece hazard falls. Measured, China's mean four-year
    predicted risk goes 0.0209 (unsplit) → 0.0193 (uniform weight) → 0.0189 (midpoint piece) → **0.0173
    (last piece)**, and the US held-out AUROC goes 0.7266 → 0.7313 → 0.7292 → **0.7179**, a 0.009 loss of
    *discrimination* that a finer grid cannot cause. Fix: the allocation became an argument
    (`--alloc uniform|midcell|last`), fractional events are represented as weighted 0/1 row pairs so the
    three allocations differ only in where an event's weight sits, all three are fitted and published
    side by side under allocation-named filenames, and the reframe's assertions now cover total event
    weight, the stroke-carrier set and at-most-one-event-per-window in addition to persons, dated
    terminal statuses and person-time. Consequences, all recomputed from `results/tables/` by
    `analysis/output/make_cloglog_rows.py`: **withdrawn** — "the sign of the level gap flips in two of
    the three non-Mexico panels" (honest fits: China 0.82→0.86-0.90, Korea 1.17→1.21-1.26, US
    0.90→0.95-1.08; none crosses 1.0) and "the one-intercept repair turns positive in the United States
    on a one-year grid" (6/6 cells positive under the last-piece fit, 0/6 and 2/6 under the honest ones).
    **Survived, and now better supported** — duration consistency belongs to the exposure specification,
    not the grid (covariate-length arms 4.43–5.65 unsplit and 0.02–1.35 after refit; log-exposure-offset
    exactly 1.000 under all four fits and all three allocations); Mexico over-predicts >2-fold in 12 of
    12 honest specifications (3.04–3.23) and 16 of 16 overall; the repair is worth fitting only in
    Mexico (18/18 honest cells positive, +0.00358 to +0.00429 at 2%). **These are the weighted-row numbers
    as of this entry. Defect 20 supersedes them with the interval-censored likelihood, which moves China
    and the United States across 1.0 and raises the honest-specification counts to 16/16 and 20/20; the
    three conclusions themselves are unchanged, but the "none crosses 1.0" clause above is no longer
    current.** The pre-allocation outputs are in
    `results/superseded/2026-11-03_last-piece-grid/` with a README, and the `_last` allocation is kept
    in Table 8 and Figure 8 as a grey hatched column marked "not a claim" rather than deleted, so the
    size of the artefact stays auditable. Status: resolved; the manuscript's Table 8 subsection, Methods
    paragraph, Limitations, Discussion fourth-convention passage, abstract clause and Figure 8 caption
    were rewritten on the honest allocations.
20. **The `uniform` event-time allocation was presented as "the assumption the interval-censored
    likelihood already makes", and it is not that likelihood — rebuilding it as the real thing changed two
    manuscript numbers.** After defect 19 the grid arm reported three allocations, and the write-up
    justified `--alloc uniform` (each sub-interval carrying 1/*n* of the parent's event, emitted as a
    weighted 0/1 row pair) by saying it matched what the interval-censored likelihood already assumes. The
    reviewer's second-round reading was correct and sharper than ours: matching the event *count* inside a
    gap is not the same as modelling the *probability* that the event lies in the gap. The objective the
    weighted rows maximise is ∏ pⱼ^(1/n)(1−pⱼ)^(1−1/n); the interval-censored contribution is
    1 − ∏ⱼ(1 − pⱼ). Fix: `intl/incident_ic_grid.py` maximises the actual likelihood,
    d·log(1−(1−p)ⁿ) + (1−d)·n·log(1−p), over parent intervals (430,521 rows, up to 27 pieces per gap,
    covariates held at interval-start values, L-BFGS with an analytic gradient, all 32 fits converged),
    for all four hazard specifications at two grid sizes, scored on the same `cif_mid` IPCW frame. Two
    properties make it the definitive arm rather than a third opinion. At one piece per gap it *is* the
    published likelihood, and it reproduces the three GLM arms' frozen rows to 4.4 × 10⁻⁸ / 1.5 × 10⁻⁷ /
    3.6 × 10⁻⁸ (the run aborts otherwise); and for the log-exposure-offset arm the aggregation collapses
    analytically, (1−p)ⁿ = exp(−λnD) = exp(−λL), so that specification has one answer at every grid size —
    measured at 1.4 × 10⁻¹². What changed: under the correct likelihood China's four-year level error moves
    1.018 → 0.755 and the United States' 1.170 → 0.984, i.e. **both cross the line of correct level**,
    while the weighted-row arms had them at 0.876–0.903 and 0.989–1.077 — the moment-matched device
    captured the direction of the grid effect and understated its size by 0.09–0.15. The manuscript
    sentence "the other three panels' level errors shrink toward one but do not change sign" is therefore
    withdrawn and replaced with what the corrected arm supports: Korea never crosses (1.44 → 1.17), China
    and the United States do, so the *direction* of those two panels' gap is a property of the
    specification. What survives unchanged, and is now supported by 16 rather than 12 honest
    specifications: Mexico over-predicts >2-fold in every one (3.04–3.23, and 20/20 counting the
    last-piece arm), the repair is worth fitting only in Mexico (12/12 interval-censored cells positive,
    +0.00376 to +0.00429, alongside the 18/18 weighted-row cells), duration consistency belongs to the
    exposure specification (covariate arms 0.69–1.54 on the grid under the correct likelihood, offset arm
    exactly 1.000), and discrimination moves by ≤0.0038 within a panel. Status: resolved; Table 8 gained
    the interval-censored column, Methods gained the likelihood paragraph, and the abstract, Discussion
    and Limitations were rewritten on it.
21. **The published primary model is converged to sklearn's default tolerance, not to machine precision,
    and one Table 8 digit depends on it.** Building the interval-censored arm's L2 anchor surfaced it: the
    published logistic model is `LogisticRegression(C=1.0)` at the library default `tol=1e-4`, which stops
    after 10 iterations on 390k rows. The identical objective solved to `tol=1e-10` gives US
    predicted-to-observed 1.1698 where the published row says 1.1606 (Δ 0.0091) and US AUROC 0.72664
    against 0.72628 (Δ 3.6 × 10⁻⁴); China moves 1.0196 → 1.0178. The unpenalised GLM arms of
    `incident_cloglog.py` sit at the converged values, which is why the new arm gates against its own
    converged sklearn reference (agreement 1.9 × 10⁻⁷) and reports the published-row difference as a
    disclosure. No claim depends on it — both readings over-predict the United States, and every rounded
    number in the manuscript is unchanged — but Table 8's first column is accurate to about two decimal
    places, not three, and the manuscript now says so instead of implying machine precision. Status:
    disclosed; a full re-fit of the published design at `tol=1e-10` is an author decision, not a silent
    change, because it would move ~40 published rows by their third decimal.
22. **The competing-risks arm's diagnostics JSON published one rule's horizon accounting under another
    rule's name.** `incident_cr_primary.py` looped over the three event-time conventions, kept the
    accounting in a single local `hcounts`, and then wrote
    `{r: hcounts for r in [rules[0]]}` — so `results/reports/incident_cr_primary.json` shipped the
    `cif_end` person counts inside the `cif_mid` key (`event_within_horizon` 1307 with
    `"horizon_rule": "cif_end"`, against the true `cif_mid` value of 1,845). Caught by reading the
    published JSON against `analysis/output/incident_cr_primary.log`, which prints the per-country event
    counts per rule. The script now accumulates `acct[rule]` and the shipped JSON's field was recomputed
    with the same `run_incident_loco.horizon_frame()` the script calls, leaving a
    `note_mislabelled_field_before_fix` recording what was there. No manuscript sentence quoted that
    field, so no reported number changed — but this is defect 9's shape again (a last-writer-wins label)
    in a new file, and it is the reason `analysis/output/make_cr_rows.py` re-prints the accounting rather
    than trusting it.
23. **"Recalibration costs money in the United States" was stated as a finding about the country when it
    is a finding about one composition.** The published logistic, cause-specific arm gives a US paired
    net-benefit gain of −0.00065 (1 of 20 replicates ahead of frozen), and the Results heading, the
    abstract and the Discussion each repeated it as what happens in the United States. The primary
    duration-consistent competing-risks arm (`incident_cr_primary.py`, 5% local data, `cif_mid`) gives
    +0.000004 (V1), −0.000001 (V2), +0.000344 (V3), +0.000376 (V4) — 38 of 40 splits positive under V4.
    The sign flips with the estimand, so the claim is now stated per specification, the heading reads
    "…elsewhere its sign depends on the specification", and the abstract no longer says it at all. The
    specification-robust US statement is the *frozen* model's: net benefit +0.00114 [+0.00036, +0.00181]
    under V4, positive in all four arms.
24. **Table 5 had no printer behind it, while the manuscript asserted that nothing is transcribed by
    hand.** The claim in Code availability listed six printers and Table 5 was not among them; it was
    also not produced by `make_table_rows.py`, whose header says "Tables 1, 2, 3, 5" but whose body has
    no Table 5 block. So the table's fifteen cells were unverified prose in the one place the paper said
    they could not be. Fixed by `analysis/output/make_table5_rows.py`, which reads
    `results/tables/incident_internal_clustered_2026-11-03.csv`, recomputes the held-out range from that
    file's own per-country columns, and prints the rows: all nine match the manuscript exactly (elastic
    net 0.6966 / 0.6964 / 0.6772 / +0.0194 / 0.045, logistic 0.6965 / 0.6964 / 0.6769 / +0.0196 / 0.045,
    ... age-and-sex 0.6338 / 0.6339 / 0.6308 / +0.0030 / 0.069). Renaming the column from `Decay` to
    `Internal-to-external difference` was done in the printer first and diffed against the manuscript
    block afterwards, so the label change is machine-checked too. The printer also emits the per-panel
    comparison the new Table 5 note quotes, which turns out to reverse the sign of the pooled claim:
    against the best linear model the ensembles gain +0.025 to +0.036 in China, lose −0.019 to −0.058 in
    the United States, are within −0.005 to −0.002 in Korea where all eight learners span 0.005, and
    separate only in Mexico (−0.027 to −0.0001). "Complex models travel worse" is a pooled
    average over a sign flip, and the manuscript now says which panels.
25. **"Not above treat-none" was written as "below treat-none", and the surviving wins turned out to be
    sub-person.** Treat-none net benefit is exactly zero by construction, so the complement of "above" is
    "at or below", not "below". The abstract said the Mexican repair "stayed below treating no one in 37 of
    40"; recomputing the three-way split from the published per-replicate rows
    (`incident_cr_primary_2026-11-03.csv`, `cif_mid`, V4, 5% local data) gives 3 above, **1 exactly tied**,
    36 below. The tie is a real mechanism, not float noise: in that split the repaired rule clears nobody at
    the 5% threshold (net benefit 0 at 5%, 10% and 15% together, level ratio 0.40), so it does nothing and
    scores exactly like doing nothing. Checking the other cells found the larger point: the three
    exceedances are 0.0000010, 0.0000130 and 0.0000387, i.e. 0.02, 0.25 and 0.73 **net persons** in an
    18,818-person evaluation sample. No specification therefore establishes a clinically meaningful
    advantage over doing nothing at 5% local data - the honest statement is that the paired repair is
    unambiguous (+0.00366, 40 of 40) and the absolute advantage over the no-screening default is not. The
    companion "at 2% local data in 0 of 39" is true only for the V4 arm the paragraph opens with (V1 2/39,
    V2 4/39, V3 1/39, each under half a net person), so it is now scoped to that arm. Fixed in the abstract,
    in the Results paragraph, in `cover_letter.md` finding 6, and in Methods, where the DCA paragraph now
    states the three-way convention; `make_cr_rows.py` mechanical check [4b] prints above/tied/below with
    the largest exceedance converted to net persons for all four arms, so the wording has a printer behind
    it. The opposite claim was checked and stands exactly: the United States' repaired net benefit beats
    treat-none in 40 of 40 splits with no ties at every local fraction in all four arms.
26. **The age-band sentences in the Discussion had no printer behind them, and building one immediately
    found two unresolvable quotes and one wrong range.** Review item P1-6 asked for the subgroup results to
    be promoted to a table; the numbers were already published in
    `results/tables/incident_subgroups_2026-11-03.csv` (142 rows, two models, six stratifiers) but the
    manuscript quoted eight of their cells in a Limitations sentence with no printer, which is defect 24 in
    a different drawer. `analysis/output/make_subgroup_rows.py` now prints the table, emits the paste-ready
    markdown, and checks those eight cells. Six match. Two land exactly on the rounding boundary of a table
    stored to four decimals - US 80+ `auroc_lo` is published as 0.4645 and was quoted as 0.465, Korea 80+
    `auroc` is published as 0.4865 and was quoted as 0.487 - so the stored value cannot decide the quote and
    the prose now carries the published digits instead. The printer also caught a range asserted before it
    was measured ("AUROC intervals 0.30-0.48 wide" for the small oldest bands; the three widths are 0.250,
    0.301 and 0.307) and surfaced a column nobody had read: the same table already publishes the repaired
    ratio per stratum (`pred_over_obs_offset`), which shows the panel-wide Mexican intercept taking the
    20-59 band from 2.383 to 0.728 - it manufactures an under-prediction in 60% of the panel while fixing
    the average. The first draft of the new section argued that consequence qualitatively ("whatever helps
    one band must hurt the other"); the published column says it numerically, and the section now quotes the
    column.
27. **The joint multinomial's analytic-gradient self-test was written at the wrong probe and failed on
    correct code.** `incident_cr_joint.selftest_gradient` compared the analytic gradient to central
    finite differences *at the fitted optimum*, where the true gradient is zero by construction; both
    sides were then pure floating-point noise, so the relative error reported 1.08 and the arm aborted on
    a script bug rather than a science bug. The analytic gradient is in fact exact - re-probing at a
    deliberately non-degenerate point (`probe = 0.4` everywhere, `const_s = Z-intercept = -3.0`, hazards
    neither clipped nor underflowed) gives a relative error of 1.46e-09, which is what the published
    diagnostics now record. This is a test-harness defect, not an estimator defect: nothing that was
    quoted came from the failed assertion, but had the self-test been "fixed" by loosening its tolerance
    instead of moving the probe, a genuinely wrong gradient could have passed. The probability-conservation
    assert (`interval_probability_mass_deviation` = 1.11e-16) is the independent check that the likelihood
    itself is sound.
28. **The joint arm crashed with `KeyError: ['sex_2','education_2', ...]` because `joint_cif()` fed raw
    covariate frames to a `rates()` method that expects one-hot design columns.** The class had only ever
    been exercised on synthetic single-column data in its own test, so the real feature set was never put
    through it. Fixed the same way `incident_cr_primary.compose_two` does - rebuild
    `I.design(frame, fset, time_mode).reindex(columns=jf.cols)` inside `joint_cif()` and `_mass_dev()`
    before calling `rates()` - so the joint model now scores exactly the design matrix the shipped model
    scores. Without the reindex a panel missing one harmonised column would silently train on a different
    feature set than the arm it is being compared against.
29. **A diagnostics accumulator was initialised as a list and indexed by string** (`diag = []` then
    `diag[f"cif_mid|{country}"] = ...` -> `TypeError: list indices must be integers or slices`). Only
    surfaced once the arm got past defects 27-28 and reached the write-out; fixed to `diag = {}`. No
    reported number sits on the buggy path - the run had never completed before - but the entry is here
    because a silently-skipped diagnostics block would have hidden the ladder and step-mass checks that
    are the point of the arm.
30. **The cohort-flow arithmetic was internally inconsistent by two people — an omitted exclusion, not a
    wrong count.** The prose and Table 1 read as `107,898 ever interviewed − 3,775 prevalent = 104,121 at
    risk`, but that subtraction is `104,123`. The two-person gap was real and on disk: two MHAS adults never
    gave a determinable stroke answer at any dated interview, so `expand()` removed them before the risk set
    (`acc["no_determinable_stroke"] = 2`) and they are in neither the prevalent nor the at-risk count. The
    manuscript's flow simply did not show that node. Found by the seventh-round reviewer and confirmed against
    `personperiod_diagnostics.json`. Fixed by adding the not-determinable exclusion to the prose, Table 1 (a new
    row), Methods and Figure 10, and by emitting a `no_determinable_stroke` column in
    `incident_sample_flow.py` so every node reconciles as `ever − not-determinable − prevalent = at risk` — not
    by changing any single number to force the arithmetic. This is a presentation/flow defect, not a
    computation error: every underlying count was already correct on disk.

## Cross-discipline status

- Frozen target before running: YES (config.py admission record written pre-modelling, single-
  cohort arm). The international arm's design was frozen before the LOCO fits; the corrections
  below are data-correction steps, not re-specifications, and the pre/post difference is
  reported rather than hidden.
- Check-not-read: pipeline validated end-to-end on synthetic ground truth — ALL PASS
  (leakage unit test, permuted-label≈0.5, holdout cal-slope 0.925, attenuation,
  adaptation→slope 1.01, monotonic recalibration, rising data-efficiency, DCA>0).
- BLOCKING vs OBSERVATION classification: see below.

## 7 dimensions

1. Numerical reproducibility / provenance: PASS, after defect 15 said otherwise. Seed fixed (20261101);
   BLAS/OMP threads locked to 1 before numpy import; all headline values re-derivable from scripts.
   This line used to be self-asserted rather than tested — the adaptation section of the manuscript was
   quoting paired gains that existed in no published table — and it is now tested by construction:
   `analysis/output/make_table_rows.py`, `make_table4_rows.py` and `make_table4_notes.py` print every
   number in Tables 1-5 and in the adaptation prose from `results/tables/`, and
   `make_figures_incident.py` reads only `results/tables/` and refuses to draw a panel whose selection
   is empty or ambiguous. Single source (published CSVs) feeds tables, prose and figures. The
   superseded 3-country and the as-is 4-country outputs are preserved
   (`results/tables/loco_3country_*.csv`, `loco_4country_uncorrected_*.csv`) so the effect of adding
   Mexico and the effect of fixing Korea are separately attributable
   (`results/tables/intl_run_comparison_auroc.csv`).
2. Claim ↔ evidence: PASS with framing caveat. This is CROSS-SECTIONAL discrimination of
   PREVALENT self-reported stroke, NOT incident-risk prediction. Manuscript states this and
   downgrades causal language. The incident upgrade is feasible and quantified in
   `results/reports/incident_outcome_feasibility.md` (2,632 incident cases available across the
   three panels, EPV 188) but was NOT built, per the user's decision on 2026-11-02.
3. Citations / numbering / dictionary: PASS. DCA (PMID 17099194) and TRIPOD+AI (PMID 38636956)
   verified via PubMed eutils. Data dictionary updated for `std_MHAS.csv` and the corrected pool.
4. Pipeline / leakage / circularity: PASS. Imputer+scaler fit on training folds/countries only.
   Outcome excluded from features. LOCO respects the country boundary with zero cross-country
   person overlap. NEW: the pooled internal reference was previously row-split, which lets the
   same person's waves sit in both train and validation folds — now recomputed under
   StratifiedGroupKFold on cohort+person; the reference moves by ≤0.004 for every model and the
   simple-vs-ensemble decay ordering survives, so the headline claim is not a leakage artefact.
5. Analysis unit & statistics: PASS. NHANES one row per SEQN (18,191 adults); PHQ association
   unweighted logistic with HC1 robust SE. International arm: respondent-wave unit; LOCO CIs and
   pooled reference at row level (disclosed) with the clustered companion above. Person identity
   is cohort-scoped — pooled `nunique(pid)` undercounts (80,580 vs the true 80,856) because bare
   ids collide across cohorts; all counts now use cohort+pid.
6. Execution hygiene & final checks: PASS. Atomic-ish CSV/JSON writes; per-run logs under
   `analysis/output/`; corrected tables isolated in `data/processed/intl/corrected/` so the
   `std_*.csv` glob cannot silently create a fifth "country" from the BMI sensitivity variant.
7. Standard readouts / decision log / betting: PASS. Decision log in config.py plus the mapping
   docstrings of `charls_reshape.py`, `klosa_reshape_v2.py`, `mhas_reshape.py`. Conclusions carry
   direction + confidence + the caveat most likely to overturn them.

## BLOCKING issues (as of the 2026-11-03 estimand audit)

1. **~~Every horizon-scale number in the manuscript that was quoted from the pre-audit frame must be
   re-quoted from `cif_mid`.~~** RESOLVED, and the resolution is mechanical rather than remembered:
   Tables 1/2/3/3-continued/4/4-continued/5, the Results sections "From panels to person-intervals",
   "Three label decisions moved the headline more than any model did", "Discrimination was modest…",
   "The failure was level, not rank", "One parameter, estimated on 396 local adults…", the SHAP
   paragraph, the Discussion, the Limitations, the Abstract and the title are all re-quoted from the
   `cif_mid` outputs, and the four tables plus the whole adaptation narrative are now *printed* from the
   published CSVs by `analysis/output/make_table_rows.py`, `make_table4_rows.py` and
   `make_table4_notes.py` instead of typed. Defect 15 is what that change was for: the previous
   sentence had been assembled from two runs and neither reproduced it. No manuscript number may be
   quoted from `*_preaudit_frame_*` or from `superseded/`, and the only remaining pre-audit figures are
   quarantined in `deliverables/figures/incident/superseded/`.
2. **~~`incident_horizon_accounting_2026-11-03.json` is a mislabelled H=6 artifact~~** (defect 9).
   RESOLVED: the producer keys every arm (`H4_cif_mid_common_linear`, …) and the publisher now also
   demotes the leftover unkeyed top level to `unkeyed_top_level_verbatim` with a warning string, so the
   published JSON cannot be read as if its bare scalars were the primary design. The runbook quotes the
   keyed `cif_mid` and `exclusive_start` blocks only (1,845 / 4,668 / 8,264 / 79,228 / 85,741 of 94,005
   and 3,048 / 8,748 / 16,233 / 74,724 / 77,772), both verified against the file.
3. The MHAS licence attestation (O7/O8) and the RAND HRS attestation (O22) remain the user's
   assertions, not verified readings. Both must be closed by a human before submission.
4. **~~The published tables' `oe_ratio` column must not be quoted as an observed/expected ratio~~
   (O24).** RESOLVED at the publish boundary and extended: `publish_incident_tables.py` now renames
   *any* column ending in `oe_ratio` (`hz_oe_ratio` → `hz_pred_over_obs` + reciprocal; `delta_*`
   differences get the rename but no reciprocal, which would be meaningless). The two adaptation tables
   were still shipping the ambiguous name when this was re-checked. `make_figures_incident.py` reads
   only `results/tables/`, so no figure can pick up the working-file name again.
5. **~~`make_figures_incident.py` still reads the pre-audit filenames~~.** RESOLVED, and the rewrite
   exposed defect 16. The script now reads only dated published tables, draws four countries everywhere
   (three panels were silently three-country and one was silently *zero*-country), takes `horizon_rule`
   as an explicit filter, adds the fitting-scale contrast (defect 15's finding), the Aalen–Johansen
   dating curves, the strict-coverage arm (O23) and the age-band subgroups as panels, and quarantines
   the superseded pre-audit PNG/PDF set under `deliverables/figures/incident/superseded/`.

## OBSERVATIONS (do not block, must be disclosed)
- O1 Prevalent (not incident) outcome → high AUROC reflects case-mix association; do not present
  as prospective prediction. (Handled in text; feasibility of the incident version quantified.)
- O2 Self-reported outcome AND self-reported comorbidities → shared reporting bias can inflate
  associations. (Limitation stated.)
- O3 6-model comparison reported with bootstrap CI on the primary model; no formal pairwise
  multiple-comparison test (none claimed).
- O4 NHANES income_pir (14%) and bmi (13%) median-imputed within folds; structural-missing
  recodes documented. Primary NHANES extraction re-checked and clean (all binaries strictly 0/1,
  no impossible smoking rows, BMI 14.1–86.2).
- O5 Race/ethnicity LOSO shows lowest transportability for Non-Hispanic Black adults
  (AUROC 0.789, cal-slope 0.83) → equity caveat; single-cohort, not country-level.
- O6 **KLoSA v1 features were materially wrong** and are corrected in `klosa_reshape_v2.py`:
  education 75.5% of rows altered (waves 3–9 were 100% fabricated "tertiary" because `A003` is
  only filled in wave 1 and `Series.map(lambda)` passes NaN through the lambda); alcohol used the
  wrong item entirely (`C119` = cigarettes/day, not drinking) affecting 65.3% of rows; all 10,211
  wave-1 rows were fabricated as "not partnered"; 823 rows were coded current-smoker while
  never-smoker. 13,405 Korea rows (20.5%) carried at least one fabricated category. Korea's
  outcome mapping was correct (859 strokes unchanged), and Korea's held-out AUROC barely moves
  (logistic 0.735 as-is → 0.737 corrected), so the earlier conclusion was directionally right —
  but it was right for partly wrong reasons, and Korea's transferred calibration is now worse
  (logistic calibration slope 1.28 as-is → 1.34 corrected; random forest 1.46).
- O7 **CHARLS BMI was contaminated by impossible values** — 59 rows outside 12–70 kg/m², 12 above
  500, maximum 52,734.69 kg/m², giving a cohort sd of 266. Because the linear models standardise
  on training rows, this rescaled the BMI axis for every cohort. Attributing the fix against the
  as-is four-country run (same four cohorts, uncorrected values → corrected): China's held-out
  AUROC rises for the trees (GB 0.744 → 0.754, LGBM 0.742 → 0.751, XGBoost 0.743 → 0.753,
  RF 0.752 → 0.757) while the logistic model is unmoved (0.758 → 0.759), i.e. the trees had been
  spending depth on keying errors that a linear model largely ignored.
- O8 **MHAS (Mexico) is included on the data holder's attestation.** This project previously
  withheld it on the reading that MHAS data-use terms prohibit managing/analysing the data with
  AI/LLM tools. On 2026-11-02 the user stated their authorisation covers this use, so the file was
  loaded. That attestation is the user's responsibility and is NOT an independently verified
  licence reading (mhas.org serves only a JS redirect from here); if it is ever withdrawn, delete
  `std_MHAS.csv` and fall back to `results/tables/loco_3country_*.csv`.
- O9 Honest feature gaps in the corrected arm: cholesterol is observed only in NHANES; Korea's
  total-income composite (`itot`, a six-component sum with bracketed-midpoint imputation) was not
  reconstructed, so Korea's economic axis is imputed from training countries; Mexico's BMI is
  measured-only and observed on 7.3% of rows (self-reported backfill exists as a labelled
  sensitivity variant, `data/processed/intl/sensitivity/std_MHAS_selfreport.csv`, because
  substituting it would change what BMI means in one country).
- O10 **The manuscript's earlier "no design weights in the harmonised files" claim was false.**
  CHARLS ships `r{n}wtresp`/`wtrespa`/`wtrespb`, MHAS `r{n}wtresp`, KLoSA `w0{5..9}wgt_p/_a/_ap/_ac`.
  The arm is still reported unweighted (prevalences are sample statistics, not population
  estimates); applying them is a pending, cheap improvement.
- O11 The United States shows *negative* mean decay (−0.028): it is the only cohort with the
  complete feature set, so its held-out AUROC (0.798) exceeds the pooled internal reference
  (0.770). Mean decay is composition-sensitive; per-country CIs are reported alongside it, and
  the claim is stated as a simple-vs-ensemble ordering rather than an absolute decay magnitude.
- O12 Elastic net and logistic are effectively tied (decay +0.011 vs +0.011 clustered); reported
  as the penalised-logistic family, not as two findings.
- O13 Still unverified: KLoSA wave years (documented biennial 2006–2022, not re-parsed here);
  KLoSA weight variables (seen in the creation code, not extracted); MHAS proxy-interview share;
  top-age plausibility (rows to 115 y in MHAS, 118 y in CHARLS were retained).
- O14 **Mortality is known as a STATUS but not as a DATE, and the two cohorts differ by 20-fold in
  how much.** The harmonised gates carry respondent death in `radyear`/`radmonth`, but in CHARLS
  that field is populated for 402 of 25,586 respondents (1.6%) and stops at 2014, i.e. two waves
  short of the panel's end; in MHAS it covers 27% of wave records. The reliable signal is the
  interview-status item: codes 5 = "died this wave", 6 = "died previous wave" (3,581 CHARLS and
  22,036 MHAS records). Those death-coded records carry **no fieldwork date at all** (verified:
  0 of 3,581 and 0 of 22,036 have `r{n}iwy`), so a death can be bounded only by the wave's own
  fieldwork window. The person-period builder therefore censors at the window MIDPOINT and labels
  the row `death_status` versus `death_dated`. Without this, 1,219 Chinese and 384 Mexican deaths
  would have been silently counted as ordinary attrition.
- O15 **Korea cannot censor on death from the files on disk.** None of the nine KLoSA main wave
  workbooks contains a vital-status or death field (checked column by column); mortality sits in
  the `w0{2..8}_exit_e` exit files, which are not present. Korea therefore contributes
  54,379 intervals with 0 death-terminated rows and `censor_mode="last_interview"`. This is not
  neutral: censoring at the last interview under-credits exposure for decedents, which biases
  Korea's incidence UP (4.75 per 1,000 person-years) relative to a death-censored computation,
  while China and Mexico are computed with death censoring (10.25 and 3.39). The three panels are
  reported with the censoring rule in every row of every table.
> **O16, O17 and O18 below quote horizon-scale numbers from the pre-audit frame.** They are kept as
> written because they are the audit trail, but every four-year prevalence, O/E and net-benefit
> figure in them belongs to the `exclusive_start` estimand that defect 8 replaced. Read O21 for the
> corrected values and for which of these conclusions survives. Interval-scale figures (AUROC,
> decay, the class-weight ablation) are unaffected by the estimand change.
- O16 **Incident-stroke prediction is much weaker than prevalent-stroke prediction, and the
  transport failure is in the level, not the ranking.** On the same harmonised cohorts, held-out
  discrimination falls from AUROC 0.735–0.798 (prevalent) to 0.645–0.719 per interval and
  0.657–0.683 for 4-year risk (incident). Calibration-in-the-large fails in the two panels whose
  incidence differs most from the training pair (final published values,
  `incident_loco_common_H4_2026-11-03.csv`): the logistic model predicts a mean 4-year risk of
  **0.0176 in China against 0.0609 observed** (calibration intercept +1.71, i.e. 3.5-fold
  under-prediction), 0.0147 in Korea against 0.0255, and 0.0296 in Mexico against 0.0310 — Mexico
  is the one country whose *horizon* level happens to land, while its *interval* level is grossly
  over-predicted (0.0685 against 0.0131 observed, Brier skill −0.687) because MHAS carries
  interview gaps up to 20.6 years that the training panels never exhibited. Any claim of a
  transportable *absolute* risk must therefore be dropped; only rank transport survives.
- O17 **Net benefit at screening-like thresholds is small, and in China worse than the default.**
  At a 5% 4-year-risk threshold the frozen logistic model yields NB **+0.0022 against +0.0114 for
  screening everyone** in China — the model is worth less than the least bad default — while Korea
  and Mexico yield +0.0005 and +0.0030 against treat-all −0.0258 and −0.0200 (i.e. better than
  treat-all, barely better than treat-none). The prevalent-arm DCA figure must not be reused as
  evidence for the incident model, and the manuscript's deployment language is removed accordingly.
- O18 **The repair is one parameter on 378 local adults; the expensive option is harmful.**
  Re-estimating only the intercept on a 2% local sample raises China's horizon net benefit from
  +0.00219 to +0.01666, above treat-all (+0.01147), with AUROC identical to six decimals (monotone
  map; verified maximum |Δ| = 0.000000 across all 225 replications per model at the interval scale).
  The gain does not grow with data (offset NB +0.0166 to +0.0173 from 2% to 50%). Retraining the
  whole model on the same rows loses a mean 0.0837 horizon AUROC at 2% (45/45 paired comparisons
  worse), 0.0535 at 5%, 0.0199 at 10%, 0.0152 at 25% and 0.0050 at 50% (24/45 still worse). Mexico
  is the falsification control: its frozen horizon level was already right, so the same correction
  collapsed mean predicted risk to 0.005 and net benefit to 0.0000 — adaptation must be triggered by
  an observed level gap, not applied by default. Source:
  `incident_adaptation_2026-11-03.csv`.
- O19 **The apparently best model internally travelled worst, and the ordering is not a leakage
  artefact.** Person-clustered internal AUROC: LightGBM 0.7371, XGBoost 0.7375, gradient boosting
  0.7366, random forest 0.7276 versus logistic 0.6804 — a 5–6 point internal advantage that inverts
  on transfer (mean held-out 0.630/0.658/0.652/0.665 versus logistic 0.675). Decay = internal −
  held-out: +0.005/+0.006/+0.008 for the three linear models against +0.063/+0.080/+0.085/+0.107 for
  the learners. Row-level CV gave the same internal values to within 0.002, so clustering did not
  manufacture the gradient. Source: `incident_internal_clustered_2026-11-03.csv`
  (`intl/run_incident_internal.py`).
- O20 **The random-forest "calibration failure of machine learning" was a class weight.** With
  `class_weight="balanced_subsample"` the forest ranks within 0.002–0.011 AUROC of its unweighted
  twin but its transferred Brier is 4.3–9.4-fold worse (cross-sectional arm, Mexico 0.306 against
  0.036; incident arm, Mexico 0.242 against 0.015, skill −17.6). The primary arm now uses the
  unweighted forest and the weighted one is reported only as the ablation. Caveat recorded under
  defect 6: the ablation's `--features` flag was inert when the first numbers were quoted, so the
  tables were re-run and re-published before use.

- O21 **On the corrected estimand the panel that needs an intercept repair is Mexico, not China,
  and the four-year incidence is far more sensitive to the dating convention than to the choice of
  learner.** Three measurements, all from `incident_competing_risks*.csv`:

  (a) *Dating dominates.* Aalen-Johansen 4-year cumulative incidence of first stroke, by which end
  of the interview interval the stroke is attributed to: China 0.0557 (start) / 0.0218 (midpoint) /
  0.0144 (end); United States 0.0330 / 0.0265 / 0.0175; Mexico 0.0200 / 0.0082 / 0.0085; Korea
  0.0245 / 0.0192 / 0.0158. That is up to a 3.9-fold swing on one convention, while the spread
  across nine classifiers on the same estimand is about 0.02 AUROC.
  (b) *Competing mortality is real but small in this range.* The naive Kaplan-Meier complement that
  treats death as censoring exceeds the Aalen-Johansen incidence by only 1.6-3.1% relative (pooled
  0.0207 against 0.0202), even though the 4-year CIF of death (0.051 pooled, 0.062 in the US) is
  more than twice the 4-year CIF of stroke. The inflation is modest because both hazards are small;
  the claim "competing risk matters" is therefore about the **estimand's meaning**, not about a
  large numerical correction here.
  (c) *The direction of the level failure flips.* Frozen logistic model, mean predicted 4-year risk
  against observed, **predicted-over-observed** ratio (the column is named `oe_ratio` in the working
  tables and means pred/obs — see O24) and the paired net-benefit gain from one intercept (5%
  local persons, IPCW-weighted):
  `cif_mid` — China 0.0220 vs 0.0216, pred/obs 1.02, gain +0.0001; US 0.0292 vs 0.0252, pred/obs 1.16,
  gain −0.0001; Korea 0.0269 vs 0.0187, pred/obs 1.44, gain +0.0007; Mexico 0.0306 vs 0.0095,
  pred/obs 3.22, gain
  +0.0045. `exclusive_start` — China 0.0205 vs 0.0609, pred/obs 0.34, gain +0.0155; US pred/obs 0.75, gain
  +0.0018; Mexico pred/obs 0.84, gain −0.0001; Korea pred/obs 1.06, gain +0.0002.
  Consequence for the manuscript, stated plainly: the sentence "one parameter estimated on 378 local
  adults lifts China's net benefit from +0.0022 to +0.0167" is a property of the label convention,
  not of the population. What survives unchanged is the structure of the finding — discrimination
  transports, absolute risk does not, the failure is monotone-removable, and retraining on small
  local samples is worse than not doing it. The paper's contribution has to be the estimand-and-
  calibration argument, with the four-panel evaluation as its evidence, and it must say which
  estimand every number is on. The repair figures above come from a 2-replicate probe; the 20-
  replicate run keyed in `incident_competing_risks_estimands_paired.csv` is the citable one.
- O22 **RAND HRS inclusion rests on the user's supply of the file, and its licence terms were not
  checked here.** Same status as O7/O8 for MHAS: the file arrived on 2026-11-03, was used for
  analysis, and no data-use agreement or citation requirement was retrieved or verified from this
  machine. A human step must confirm HRS/RAND distribution terms before submission. If they turn out
  not to cover this use, delete `corrected/std_HRS.csv` and `incident/hrs_times.csv`, drop HRS from
  `incident_personperiod.SPECS`, and re-run — the US panel currently supplies 4,350 of 6,979
  incident events, so the four-year calibration table shrinks by more than half its information.
  Removing it also requires deleting `incident/personperiod_HRS.csv` and
  `reports/hrs_{metadata_probe,reshape_diagnostics,weight_zero_probe}.json`, and re-running
  `intl/std_pool.py`-fed arms plus `incident_horizon_counts.json`, which is keyed and will otherwise
  keep the US slot.
- O23 **The horizon frame's coverage rule counts people as observed who were only alive, and
  correcting it halves the size of the Mexico repair.** `horizon_frame` judges whether a person was
  followed to the horizon from `t_cens` = the end of their last interval, but an interval may be
  terminated by `alive_nr` — a wave record in which the respondent is known alive and was **not
  interviewed**, so the stroke item was never asked there. RAND HRS has 9,325 such intervals, MHAS
  1,166, and because those panels' tails are long the effect is a 4-year prevalence that is partly
  manufactured by non-observation. Rebuilt with strict coverage (`t_ask` = the last wave at which the
  item was answerable; everything after it is censoring), 7,323 of 85,741 evaluable adults leave the
  frame — 4,136 US (3,137 of them `alive_nr`-terminated, median 4.8 unobserved years), 2,980 MX
  (2,341 dated deaths, median 6.0 unobserved years), 207 CN, and **0 KR**, because Korea has no
  vital-status tail to lean on. Pooled observed incidence 0.02152 -> 0.02353 (+9.3%). The consequences
  that matter for the manuscript's argument, on the identical frozen logistic model: Mexico's
  predicted/observed falls 3.22 -> 2.65 and the net-benefit gain from one local intercept
  +0.00435 -> +0.00227 (−48%); Mexican horizon AUROC *rises* 0.611 -> 0.644 because the mechanical
  stroke-free rows were the inseparable ones; US net benefit at 5% rises +0.00213 -> +0.00283 and China
  is unchanged in kind (+0.00011 -> +0.00015). No conclusion reverses; the size of the flagship one
  does. **The justification originally attached to this observation — that the permissive rule stays
  primary because it is the risk-set rule the discrete-time model is fitted with, so re-labelling alone
  would score a model against a target it never estimated — has been withdrawn** (see defect 18): the
  invariant is right and the conclusion drawn from it was wrong, because the fix for a train/test
  mismatch is to change the training target. `intl/incident_strict_refit.py` does that, and its result
  is in Table 7 of the manuscript. Source:
  `incident_ascertainment_sensitivity_2026-11-03.csv`, `reports/incident_ascertainment_summary.json`
  (`intl/incident_ascertainment_sensitivity.py`, which self-checks by reproducing the published frame
  exactly before printing anything).
- O24 **A column named `oe_ratio` was published meaning predicted-over-observed, and the manuscript
  drafted from it inverted the sign of the headline.** `run_incident_loco.py:412` computes
  `w_mean(yb, ph, wb) / qb` — mean predicted risk over observed prevalence — and prints it as "O/E".
  Read literally, "Mexico O/E 3.22" says observed is 3.2x expected, i.e. the model under-predicts;
  the same row shows mean predicted 0.0306 against 0.0095 observed, so the model **over**-predicts
  threefold. O21 above had inherited the mislabelling, and the first four-panel draft of the
  manuscript repeated it. Fixed at the single point that matters: `publish_incident_tables.py` now
  renames the column to `pred_over_obs` and adds `obs_over_pred` on every published copy, while the
  working files stay byte-identical to what the run produced (renaming the producer would
  desynchronise the arms, because the run in progress imported the old module).
- O25 **The discrete-time link was not varied.** Every hazard in this arm was fitted with a logistic
  link; complementary log-log — the discrete-time analogue of proportional hazards, and the link most
  reviewers of a survival-prediction paper will ask for — was not fitted, so the composed four-year
  absolute risks were link-specific. This matters most where intervals are long relative to the horizon
  (19.4% of Mexican intervals exceed four years, and the pooled share is 6.3%), which is precisely the
  regime where logit and cloglog diverge. **CLOSED on 2026-11-03** by
  `intl/incident_cloglog.py` + `intl/incident_grid_reframe.py` (manuscript Table 8): four
  specifications — the published L2 logistic, an unpenalised logistic GLM, a cloglog hazard with
  interval length as a covariate, and cloglog with log-length as an **offset** (the proportional-hazards
  formulation) — each refitted on a common one-year grid under three event-time allocations, all scored
  on the identical `cif_mid` horizon frame and IPCW weights. The answer is not the one a reviewer expects:
  the *link* changes nothing (logit and cloglog with length-as-covariate differ by ≤0.09 in the duration
  ratio and ≤0.004 in held-out AUROC), but the *length specification* changes the four-year level a great
  deal. Mexico's over-prediction is 3.08–3.23 under the four links on the panels' own intervals and
  3.04–3.18 after the honest grid refits — >2-fold in 12 of 12 honest specifications and 16 of 16
  overall — while China goes 0.82–1.02 → 0.86–0.90, Korea 1.17–1.44 → 1.21–1.26 and the United States
  0.90–1.17 → 0.95–1.08 on the weighted-row grids. (An earlier version of
  this entry reported "China 1.02 → 0.80, Korea 1.44 → 1.08, US 1.16 → 0.83" — that came from the
  last-piece allocation and is withdrawn; see defect 19. Defect 20 then replaced the weighted-row grids
  with the interval-censored likelihood, under which China reaches 0.755 and the United States 0.984, so
  the level gap does change sign in those two panels; the honest counts become 16/16 and 20/20.)
  The new arm's sklearn anchor
  reproduces the published frozen row to 2.2 × 10⁻¹⁶ and the script aborts if it does not, so the two
  arms are measurably the same experiment.
  **Re-opened and closed a second time on 2026-11-03 (defect 20):** the reviewer showed that the
  weighted-row `uniform` allocation is a count-matching device and not the interval-censored likelihood,
  so `intl/incident_ic_grid.py` was written to maximise the actual one. Under it China goes 1.018 → 0.755
  and the United States 1.170 → 0.984 — both cross 1.0, which the weighted-row arms had said they did not
  — Korea stays above one (1.441 → 1.165) and Mexico stays 3.08–3.20. The "none changes sign" clause above
  is superseded by defect 20; the Mexico and duration-consistency findings are not.
- O26 **The two arms do not share a US panel, and the manuscript now says so.** The incident design
  uses RAND HRS (45,233 ever interviewed, 257,794 intervals, 4,350 events); the retained cross-sectional
  comparison uses NHANES (18,191 adults, one row each). Table S3 therefore compares a different
  four-cohort pool to Table 2's, and a reader who assumes "United States" means the same people in both
  would over-read the prevalent-versus-incident AUROC gap as a pure estimand effect when part of it is a
  population change. Stated in the first sentence of S3; the honest like-for-like statement is that the
  prevalent arm is retained for the outcome-definition contrast within CHARLS/KLoSA/MHAS, where the two
  arms do use the same cohorts.
- O27 **Every four-year risk the manuscript headlines comes from a specification that is not
  duration-consistent, and the paper now says which numbers that makes.** The published composition
  multiplies two-year interval hazards; with interval length as a covariate the same person's four-year
  risk composed from eight half-year pieces is 4.43–5.65× the answer from one four-year piece (China 5.51,
  Korea 5.41, Mexico 4.43, US 5.64 for the published model), and the same model asked for a single
  four-year interval returns 0.0132 rather than 0.0221 in China. Only log-exposure-as-offset is
  invariant (ratio exactly 1.000, before and after every grid refit and under every event-time
  allocation — and under the interval-censored likelihood the invariance is algebra, since
  (1−p)ⁿ = exp(−λ·n·D) = exp(−λ·L), measured at 1.4 × 10⁻¹²), and refitting the covariate-length arms on
  the 1-year grid does not repair them — their
  ratios move to 0.020–1.080 (uniform weights), 0.019–1.352 (midpoint weights) and 0.69–1.54 (the correct
  interval-censored likelihood), i.e. still nowhere near one and now scattered in both directions. This is disclosed rather than
  quietly fixed, because the whole published table set is built on the two-year composition; the
  offset arm is reported beside it (Table 8) as the level-invariant comparison, and the manuscript's
  Limitations now names it as the arm whose level estimates should be believed. The reviewer's follow-up
  question — why promote a duration-consistent model to primary — is answered with its price in the
  Discussion: a log-exposure offset cannot be given to the tree ensembles, so a proportional-hazards
  primary analysis would cost the nine-classifier transport comparison, and the measured effect of the
  choice on this paper's conclusions is nil.
- O28 **A single replicate of the 2% local sample is not a representative one, and a repaired level
  read from one row of the table is a different quantity from the arm's.** Mexico's horizon-evaluable
  prevalence is 0.0104 unweighted / 0.0095 IPCW, but the drawn 396-adult local sample carries 9 events in
  replicate 0 (0.0227) and a median of 4 across the 20 replicates (mean 0.0097). Because the intercept is
  fitted to the *local* rate, replicate 0's repaired panel-level pred ÷ obs is 2.4 while the 20-replicate
  mean is 1.015 — and the same seed formula, so the same samples, give −0.34 in the natural-grid arm and
  −0.20 in the grid arm for that replicate. Every repair number quoted in the manuscript is therefore a
  mean over replicates with the complete-pair count printed next to it; `make_cloglog_rows.py` prints
  means only. This is the same phenomenon the Table 7 stability row records as SD 0.44 on the log-odds
  shift, seen from the sample side instead of the parameter side.
- O29 **`pid` is unique inside a panel and not across panels: 14 values collide.** The pooled four-year
  frame has 85,741 rows and 85,727 distinct `pid` values, and the 14 collisions are Korea/Mexico pairs of
  *different people* whose cohort respondent numbers happen to agree. Checked rather than assumed: the
  horizon frame has 0 duplicate `pid` rows inside each of the four panels (`assert` in
  `intl/incident_adaptation_leakage_audit.py`), every adaptation/evaluation split is drawn within one
  held-out country, and the only pooled person-keyed arm already concatenates the cohort
  (`run_incident_internal.py:68`, `grp = cohort + "|" + pid`). So no published statistic is affected — the
  exposure is future-facing: anyone clustering pooled rows on bare `pid` would merge 14 pairs of people
  into single clusters. Recorded in
  `results/tables/incident_adaptation_leakage_audit_2026-11-03.csv` as question 0.
- O30 **The IPCW censoring distribution is estimated on all four panels' follow-up, and that is a choice
  with a measured price.** `run_incident_loco.horizon_frame()` builds `G` from the pooled person clock, so
  a held-out country's weights use its own *follow-up pattern* (never its outcomes) together with the
  other three. A deployment would have its own follow-up and none of the source panels'. Rebuilding `G`
  three ways (audit, question 3) moves the observed four-year incidence by up to 14% relative — Mexico
  0.009496 pooled / 0.009969 source-only / 0.008200 target-only, which would read its published 3.22-fold
  level error as 3.07 or 3.73 — while the other three panels move by at most 5% relative (under V1: China
  0.746-0.757, Korea 1.133-1.169, United States 0.937-1.025, which is to say the United States straddles
  correct level whichever follow-up built `G`). No
  conclusion turns on the choice; the interval on Mexico's level error should be
  read as roughly ±0.3 to include it, and the audit prints it so the reader does not have to take that on
  trust.

## Verdict: 有条件通过 (CONDITIONAL PASS) — the incident arm must clear before submission

The four-country prevalent-stroke arm is reproducible and its data defects are documented with
before/after tables rather than silently overwritten. But its role has changed: on 2026-11-02 the
study's identity was moved to a **new-onset (incident) stroke** design, because the reviewer's
first objection was correct — a cross-sectional "ever reported stroke" outcome cannot support a
prospective-prediction claim, and once the outcome is rebuilt as first-event-in-interval, the
headline numbers change materially (O16, O17). The prevalent arm survives as the sensitivity arm
that shows what the old outcome was measuring.

Before this can be called submission-ready, four things must be true — status as of 2026-11-03 late:
1. Table 3's CIs re-quoted from the person-clustered arm, not from `modeling.bootstrap_ci`
   (defect 2), and every Brier skill / scaled-Brier number re-quoted from the corrected
   references (defect 3, including the re-run of `rf_probability_ablation.py`).
   **DONE for the incident arm** (all CIs come from `V2.bootstrap_indices`, person-clustered,
   1,000–2,000 resamples; both naive references are quoted per row). **DONE for the ablation**
   (re-run twice: references corrected, then defect 6). The cross-sectional arm now survives only
   as Supplementary material, quoted from `loco_4country_corrected_2026-11-02.csv`, and its
   Table S3 decay column is still the row-level-reference version.
2. The incident LOCO arm completed at full bootstrap and its interval/horizon tables frozen into
   `results/tables/`, with `censor_mode` present in every table (O15). **DONE** —
   `incident_loco_common_H4_2026-11-03.csv` (B=2,000), the four sensitivity arms
   (`..._none_H4`, `..._extended_linear_H4`, `..._H6`, `..._H4_weighted`),
   `incident_adaptation_2026-11-03.csv`, `incident_internal_clustered_2026-11-03.csv`,
   `incident_personperiod_diagnostics_2026-11-03.json` and
   `incident_horizon_accounting_2026-11-03.json`, all via `intl/publish_incident_tables.py`.
3. The manuscript's title, abstract and limitations rewritten around O16/O17. **DONE, three times** —
   the draft is incident-centred, and its framing has moved again since the second-round rewrites. The
   title is now "Transportability of absolute stroke risk and the value of local recalibration across
   four national ageing cohorts": the previous title led with "which country needs recalibration", which
   the third-round review correctly identified as reading like a country ranking rather than a methods
   finding, and the new primary analysis makes the estimand-and-composition work supporting rather than
   headline. The abstract is 174 words (counted by the printed snippet in the runbook, not eyeballed) and
   now leads with the corrected competing-risks result plus the decision rule rather than with the
   conventions; the phrase "clinically actionable target" is gone in favour of "prospectively ascertained
   outcome", and the US-level verdict is gone with defect 23. The Results section opens with a paragraph
   saying why the estimand sections come before the performance sections. The revision-history narrative
   the review objected to ("the reviewer was entitled to press us", "the previous version could not write
   this sentence", "our first response was wrong in its conclusion") has been rewritten out of the
   Results and Discussion in favour of stating the final method and its result; the audit trail stays
   where it belongs, in this file and in the code comments. The abstract was cut from 454 words to 167,
   which replaced "…and with the hazard's link and interval grid, while Mexico's 2.8–3.2-fold
   over-prediction survived all eight specifications" with the honest-likelihood version. O18 remains
   the primary contribution: rank transport
   survives, absolute risk transport does not, and a one-parameter level repair is worth more than local
   retraining — *conditional on the specification being reported*.
4. The MHAS attestation (O8) still stands, since the incident arm's Mexico panel depends on it as
   much as the prevalent arm did. **OPEN — author action.** Mexico contributes 933 of the 6,979
   incident events and the entire falsification control in Table 4. If the attestation is withdrawn,
   delete `std_MHAS.csv`, re-run `incident_personperiod.py` and `run_incident_loco.py`, and the
   design becomes a two-panel (CN/KR) leave-one-country-out test — which weakens O18 to a single
   repaired cohort and removes the "correction is not universally indicated" evidence.

Still open, not blocking: subject-specific references must be supplied and verified by the authors
(no placeholder citations were inserted); author names, contributions and funding must be confirmed; the
abstract is 187 words and must be trimmed to the journal's limit at typesetting; and the abstract's
150-word version should keep the rank-versus-level sentence rather than the convention sentence, since
the latter is now carried by Tables 7 and 8 in the body. Closed 2026-11-03: SHAP on the frozen models IS
run and reported (`intl/incident_shap.py`, exact Shapley attributions, Table S5); the complementary
log-log arm the reviewer required before submission IS run (O25, Table 8), as is the strict-coverage
refit (O23, Table 7) — and the link/grid arm has been rebuilt twice, once to remove the last-piece
event placement (defect 19) and once to replace fractional event weighting with the interval-censored
likelihood itself (defect 20), which is the version the manuscript quotes.

## Round-10 closure (2026-11-04): model-identity unification + complete SI booklet

Round 10 was a "final comprehensive review" (verdict: Major revision before submission). Its central
scientific-presentation issue was that the joint multinomial competing-risks model is declared the primary
estimator, yet the formal main tables, the Methods probability construction and the central figures still
reported the OLD logistic / separately-fitted model. This pass unified the model identity against disk and
completed the standalone Supplementary Information.

What was actually run / verified (nothing asserted from prose alone):

- **Model identity unified.** The joint model is now the primary estimator everywhere it is formally reported:
  appendix Table 3 = joint frozen four-country calibration / discrimination / decision-utility (AUROC, P/O,
  CI, n_eval, events reverse-checked against `incident_cr_joint.csv`); Table 4 = joint local-update trajectory;
  Methods "How the predicted probability is built" leads with the joint likelihood and its exclusive first-event
  probability α_s,j (F_s(4)=Σ S(t_{j−1})·α_s,j), with the separately-fitted two-hazard Aalen–Johansen composition
  demoted to a labelled sensitivity arm and the "one-piece equals cause-specific risk exactly" claim qualified as
  a single-step algebraic property; main Figures 1-6 are the joint model's own output. The classifier grid moved
  to Supplementary Table S7, the logistic update grid to Supplementary Table S8, and the old logistic / XGBoost /
  fitting-scale / ranking-vs-level / complexity / class-weight / specification-grid / logistic-calibration figures
  to Supplementary Figures S1-S8, each labelled with the model it actually plots.
- **Partial-strict contradiction closed with a real refit.** The false "permissive is the only frame retaining
  competing death" claim was deleted from Methods and Results (partial-strict and permissive both retain all
  23,347 death intervals; only full-strict deletes them). `incident_cr_joint_strict_refit.py` (40 person-disjoint
  splits) refit the JOINT model under partial-strict coverage and was added as Table 7b: Mexico stays the only >2
  over-prediction (2.54) and its repair is worth +0.00194 net benefit, beating the frozen model in 100% of splits,
  so the primary estimator's headline survives stricter coverage — closed with a genuine refit, not a downgrade.
- **Standalone SI booklet completed.** `Supplementary_technical.md` is now a full Supplementary Information:
  Supplementary Methods S-A (known-truth competing-risks simulation, mean biases reverse-checked against
  `incident_cr_simulation.csv`: realistic M1 −0.05%, severe M2 −24.13%, severe M3 +31.75%), S-B (exclusivity
  identity + probability-conservation ladder), S-C (interval-censored likelihood + the three observed-risk
  allocation rules); Notes S-D (cross-sectional) and S-E (SHAP); and all Supplementary Tables S1-S8 and Figures
  S1-S8 that the main text cites. The main article keeps only pointers.
- **Reference-4 corrected** to Ann Intern Med. 2015;162(1):55-63, doi:10.7326/M14-0697, PMID 25560714, verified
  against EuropePMC (PMID 25560714) before writing; the erroneous 735-744 / M15-1376 / 25984857 fields removed.
- **Three joint-model figures regenerated** with `incident_figures_joint.py` (calibration deciles, update
  net-benefit, observed-risk under four estimators), each reverse-checked against its source CSV.

Gates: `audit_consistency_round10.py` (113 assertions) PASS, alongside round6/7/8/9 (53 / 86 / 123 / 64) all PASS.
`manuscript.docx` (3465 paragraphs) and `Supplementary_technical.docx` (1119 paragraphs) rebuilt and validated.
The stale note above ("the abstract is 187 words") is superseded: the round-10 abstract is **145 words**.

Still open, author-only (cannot be auto-filled, never invented): the **36 [AUTHOR-SPECIFIC]** placeholders
(author list / affiliations / corresponding author / per-cohort ethics + consent / data-use terms / CRediT /
funding / code DOI), and specifically the **MHAS AI-assisted-processing attestation** and **KLoSA registration /
licence terms**, which the real authors must read from the licence text and retain proof for. Until those are
supplied and signed, the package is a complete, audited scientific draft but not an uploadable submission.
