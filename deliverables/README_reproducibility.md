# Reproducibility guide

Project: **incident (first reported) stroke** risk prediction and transportability across four
nationally representative ageing cohorts — US RAND HRS, China CHARLS, Korea KLoSA, Mexico MHAS — with
the earlier NHANES cross-sectional work retained as the comparison arm (npj Digital Medicine target).
All data are publicly downloadable or released to the authors; no restricted or identifiable data were
used. MHAS and RAND HRS are covered by the attestation recorded under "Data provenance" below.

## Environment
- Python 3.10 (D:/Python/Python310/python.exe)
- numpy 1.26, pandas 2.2, scikit-learn 1.5, scipy 1.14, statsmodels 0.14,
  xgboost 1.7, lightgbm 4.6, shap 0.49, pyreadstat (SAS-XPT / Stata-DTA variable labels),
  python-calamine (the KLoSA workbooks cannot be read by openpyxl)
- Threads locked to 1 (BLAS/OpenMP) before numpy import; fixed seed 20261101 for
  bit-level reproducibility.

## Layout
```
data/raw/                     downloaded NHANES SAS-XPT files
data/raw/intl/                harmonised gate files (CHARLS, MHAS) + KLoSA original waves
data/processed/               nhanes_stroke_harmonized.csv  (patient-level, 1 row/adult)
data/processed/intl/          std_{COHORT}.csv (pre-correction) / corrected/ / incident/
analysis/scripts/
  config.py                   FROZEN design + decision log (admission record)
  extract_harmonize.py        download-time harmonisation -> processed CSV + tallies
  modeling.py                 leakage-aware pipelines, metrics, validation, adaptation
  run_analysis.py             NHANES cross-sectional arm -> output/*.csv|json|npz
  make_figures.py             figures generated FROM saved outputs (no recompute)
  synthcheck.py               synthetic ground-truth pipeline validation (must ALL PASS)
  loco_multicohort.py         pluggable international LOCO (CHARLS/ELSA/HRS/SHARE)
  intl/                       the international arm - see run order below
analysis/output/              all numbers (CSV/JSON) + figures/ (PNG+PDF)
results/tables/               dated, published copies of every reported number (2026-11-02/-03)
results/reports/              data-defect records, feasibility and build reports
docs/SELF_AUDIT.md            7-dimension pre-delivery audit + defect log + verdict
deliverables/                 manuscript.md, cover_letter.md, figures/, data_dictionary.md,
                              INTL_DATA_RUNBOOK.md
```

## Run order — incident arm (the reported study)
```
cd analysis/scripts/intl
python hrs_reshape.py                           # RAND HRS SAS-XPT -> corrected/std_HRS.csv
python incident_personperiod.py                 # person-interval expansion + mortality audit (4 panels)
bash ../../../analysis/run_incident_pipeline.sh # the modelling chain, one log per step in output/pipeline/
  # inside it:
  run_incident_loco.py --boot 2000 --horizon 4              # primary LOCO, both dating rules
  run_incident_internal.py                                  # person-clustered internal reference -> decay
  incident_adaptation.py --horizon-rule cif_mid|exclusive_start
  incident_horizon_recalibration.py --horizon-rule cif_mid|exclusive_start --reps 20
  incident_competing_risks.py --rules cif_mid,exclusive_start --reps 20   # AJ CIF + IPCW
  incident_update_strategies.py --reps 20                   # pooled / revised / time-only / refit
  run_incident_loco.py --time none / --features extended / --weights / --horizon 6
  incident_shap.py --rows 4000
# then the two audit arms, run outside the shell script:
python incident_ascertainment_sensitivity.py --models logistic,random_forest,xgboost
python incident_subgroups.py
# then the coverage-objection arm (refit under strict ascertainment; see the runbook for why the
# "fully strict" variant is not available in these panels):
python incident_strict_frame.py
python incident_strict_refit.py --models logistic,elasticnet,xgboost --reps 20
# then the link / interval-grid arm (Table 8): four hazard specifications, the panel's own intervals
# and a common sub-year grid under three event-time allocations, always scored on the horizon frame
# from the UNSPLIT file
python incident_grid_reframe.py --delta 1 --alloc uniform   # -> personperiod_grid1_uniform.csv
python incident_grid_reframe.py --delta 1 --alloc midcell   # -> personperiod_grid1_midcell.csv
python incident_grid_reframe.py --delta 1 --alloc last      # -> personperiod_grid1_last.csv
python incident_cloglog.py --reps 20              # logit / logit GLM / cloglog / cloglog-offset
for a in uniform midcell last; do
  python incident_cloglog.py --reps 20 --pp personperiod_grid1_$a.csv
done
# and the arm that replaces the weighted-row grid as the grid check: the interval-censored likelihood
# itself, maximised over parent intervals at one piece per gap (must reproduce the fits above) and at
# one-year pieces (the offset arm must be identical at both)
python incident_ic_grid.py --reps 20 --deltas 0,1 # -> incident_ic_likelihood_cif_mid.csv

# and the arm the third-round review requires: the primary absolute-risk analysis rebuilt as two
# cause-specific interval-censored hazards (stroke, death) composed into an Aalen-Johansen CIF,
# duration-consistent and not, under three event-time conventions, with person-clustered bootstrap
# intervals and an adaptation/evaluation overlap counter that aborts if it is ever non-zero
python incident_cr_primary.py --reps 40 --boot 500 --rules cif_mid,cif_start,cif_end
python incident_update_policy.py --reps 200 --fractions 0.02,0.05,0.10,0.25,0.50
python incident_adaptation_leakage_audit.py --reps 25 --frac 0.05
python incident_calibration_curves.py --boot 500 --splits 200 --frac 0.05
python incident_sample_flow.py

# and the arm the fourth-round review calls P1-5: the same two hazards refitted from scratch with the
# concepts whose QUESTION differs between panels removed (Tier 2) and with the availability-mismatched
# items removed too (Tier 3). Tier 1 is the published primary arm re-derived through this script's own
# code path and must reproduce all eight frozen cells to within 1e-6, or the file aborts loudly
python incident_cr_definition.py --reps 20 --boot 200

# and the arms the fifth-round review calls P0-1, P1-2 and P1-1:
#   P0-1  is the composed CIF a valid competing-events probability? the shipped ladder multiplies marginal
#         step hazards, so a step carries mass 1 + p_s*p_d > 1. V5 re-derives the same estimand exactly on
#         the marginals and a joint multinomial likelihood (three exclusive interval outcomes, analytic
#         gradient self-tested at a non-degenerate probe, probability-conservation assert) is fitted beside
#         it; the known-truth simulation puts a number on the composition bias. Headline is invariant
#         (Mexico 3.00 shipped / 2.93 V5 / 2.98 joint), Table 9b.
#   P1-2  can the calibration repair be made age-aware? five update strategies on persons disjoint from the
#         adaptation sample, judged on the worst age band and not only the panel average (Table 13).
#   P1-1  smooth calibration curves with a person-clustered bootstrap band, decile plot replaced by a curve
#         so the residual shape (Mexico's high-risk tail) is visible (Figure 9b).
python incident_cr_joint.py --reps 40 --boot 500 --rules cif_mid,cif_start,cif_end
python incident_age_recalibration.py --reps 120 --horizon 4 --horizon-rule cif_mid
python incident_calibration_smooth.py --boot 200 --frac 0.05
#   Sixth round: the joint multinomial model is now declared the PRIMARY absolute-risk estimator, so every
#   joint sub-analysis the primary tables cite (age bands, deciles, smooth curve, age-aware update strategies,
#   decision curves) is regenerated from the shared per-person joint CIF by one script, leaving the V4/marginal
#   outputs untouched as the labelled sensitivity arm. All five _joint outputs cross-reconcile to the same
#   Mexico panel P/O 2.975 (Table 9b = subgroup ALL row = age-recal frozen).
python incident_cr_joint_primary.py --horizon 4 --rule cif_mid --frac 0.05 --splits 120 --boot 200 --dboot 200 --reps 120
#   ROUND 7 (submission-hardening): three new analyses, all reading the same horizon frame + joint CIF as the
#   primary tables so nothing drifts. The selective-updating policy is re-run on the JOINT model (Table 10 no
#   longer logistic); the observed four-year risk is re-estimated midpoint-free with an intercept-only joint
#   competing-risks MLE (Table 15); and a synthetic unreported-pre-fatal-stroke sweep bounds how much of the
#   Mexican P/O is ascertainment rather than miscalibration (Table S6). incident_sample_flow.py was also rerun
#   to emit a `no_determinable_stroke` column so the cohort flow reconciles as ever - not-determinable - prevalent = at risk.
python incident_update_policy_joint.py --reps 200 --fractions 0.02,0.05,0.10,0.25,0.50 --horizon-rule cif_mid
python incident_cr_interval_eval.py --horizon 4 --boot 400
python incident_cr_unreported_stroke_sim.py --horizon 4
python incident_sample_flow.py --horizon 4 --rule cif_mid
python publish_incident_tables.py               # -> results/tables/incident_*_2026-11-03.*
python make_figures_incident.py                 # -> deliverables/figures/incident/ (17 panels)
```

Nothing in the manuscript is transcribed by hand. After publishing, the tables and the adaptation
prose are regenerated from `results/tables/` and diffed against the draft:
```
cd analysis/output
python make_table_rows.py                       # Tables 1, 2, 3
python make_table5_rows.py                      # Table 5 + the per-panel check behind its claims
python make_table4_rows.py                      # Table 4 (four panels, both fitting scales)
python make_table4_notes.py                     # paired gains, Table 4-continued, learning curves
python make_tableS_rows.py                      # Supplementary S1 and S2
python make_strict_rows.py                      # Table 7 (strict-coverage refit) + intercept stability
python make_cloglog_rows.py                     # Table 8 (link x grid) + duration-consistency ratios
python make_ic_rows.py                          # Table 8's interval-censored column, anchors and gates
python make_cr_rows.py                          # Table 9, the CIF decomposition, the policy table,
                                                # the three-way treat-none accounting [4b], and the
                                                # mechanical "does this claim still hold" checks
python make_definition_rows.py                  # Table 11 (definitional ablation) + its replication gate
python make_subgroup_rows.py                    # Table 12 (age bands) + the 8 quoted stratum numbers
python make_p0_rows.py                          # Table 9b (three compositions) + Table 13 (age-aware)
                                                # from the joint / exact / age-summary outputs on disk
python make_joint_primary_rows.py               # joint-PRIMARY: Table 12 age bands, Table 13 age-aware,
                                                # Table 14 three-level deployability + headline, from _joint files
python make_round7_rows.py                      # ROUND 7: Table 15 (interval-censored observed risk) +
                                                # Supplementary Table S6 (unreported-stroke sweep) from the new CSVs;
                                                # `--check` asserts the manuscript strings match disk
```
If a quoted number cannot be reproduced by one of those scripts, that is defect 15 recurring
(the first draft did exactly that) and the number is wrong until proven otherwise. Table 5 was the
counter-example found in this round: it had no printer behind it, so `make_table5_rows.py` now exists,
and its output was diffed against the manuscript block row by row (identical) before the table's
`Decay` column was renamed.

The abstract's word count is printed, not eyeballed, and the convention matters because em-dashes
count as zero-width tokens. The abstract now sits under a `## Abstract` heading, and the current count


#   ROUND 8 (post-review reconciliation): four new analyses on the same horizon frame + joint CIF, all
#   reverse-checked by analysis/output/audit_consistency_round8.py (127 assertions).
#     intl/incident_cr_interval_flexhaz.py --horizon 4 --boot 300 --dt 0.05 --bands 3
#         -> observed 4-y risk under piecewise-constant and log-linear cause-specific hazards (Table 18);
#            China inflated ~2x by the pooled-hazard MLE, robust to hazard shape.
#     intl/incident_update_policy_joint_ic.py --reps 200 --fractions 0.02,0.05,0.10,0.25,0.50 --horizon 4
#         -> the four policies re-run on the interval-censored outcome (midpoint and IC arms on identical
#            person-disjoint splits); Table 19 right block - at 5% the rule fires Mexico 98%/IC (+0.00290),
#            China 24%/IC (net loss). Also writes incident_cr_alloc_only_ic_comparator via the evaluable-frame
#            interval-censored expectation (Table 19 left block: China ratio 1.00, Mexico 1.37, P/O 2.98->2.18).
#     intl/incident_cr_clinical_baseline.py  -> five-variable clinical joint model vs full model on the same
#            estimand/validation/threshold (Table 20, 120 splits; AUROC within 0.009, Mexico ~3x for both).
#     intl/incident_cr_unreported_stroke_2d.py --horizon 4 --grid 0,0.1,0.2,0.3,0.4,0.5
#            -> 2-D source x target under-ascertainment grid (Supplementary Table S6, hypothetical sensitivity
#               parameters; uniform diagonal keeps Mexico >=1.48, only extreme differential crosses 1.0).

is `tokens 137 | words 137` (the round-7 edits — adding "2.10 midpoint-free" and reframing "every evaluated
split" — brought it to 137, still under the 150 cap with headroom); the manuscript's own label must match that
second number and the delivery audit asserts both `<= 150` and the `125-148` window
(`audit_consistency_round7.py`; `audit_consistency_round6.py` asserts the tighter 125-145 band):
```
cd ../.. && python - <<'EOF'
import re
lines = open('deliverables/manuscript.md', encoding='utf-8').read().split('\n')
i = next(k for k, l in enumerate(lines) if l.strip() == '## Abstract')
j = next(k for k, l in enumerate(lines) if l.strip() == '## Introduction')
body = '\n'.join(lines[i + 1:j])
toks = [w for w in re.split(r'\s+', body.replace('\n', ' ')) if w.strip()]
print('tokens', len(toks), '| words (tokens containing a digit or letter)',
      len([t for t in toks if re.search(r'[A-Za-z0-9]', t)]))
EOF
```
Do NOT count with `tr -d '\n'` first: joining lines fuses the last word of one line to the first of
the next and undercounts by roughly fifteen.

## Run order — harmonisation and the cross-sectional comparison arm
```
cd analysis/scripts/intl
python charls_reshape.py ; python build_nhanes_std.py ; python klosa_reshape_v2.py
python mhas_reshape.py ; python clean_intl_std.py          # -> corrected/std_*.csv
python run_loco_models.py "<abs>/data/processed/intl/corrected"
python run_loco_v2.py --features common --unit wave --min-age 0 --boot 2000
python run_loco_internal_clustered.py "<abs>/data/processed/intl/corrected"
python rf_probability_ablation.py --features common        # and --features extended
python make_intl_table1.py "<abs>/data/processed/intl/corrected"
python make_figures_intl.py "<abs>/data/processed/intl/corrected"
```
`klosa_reshape.py` (v1) and `run_loco_models.py` are kept as the objects of the correction records;
the reported cross-sectional tables come from the corrected pool.

## Run order — NHANES single-cohort arm (supplementary)
```
cd analysis/scripts
python extract_harmonize.py      # rebuild harmonised table + verify EPV/missingness
python synthcheck.py             # ALL PASS gate before trusting any real number
python run_analysis.py           # real results -> output/
python make_figures.py           # 16 panels -> output/figures/
```

## Data provenance
- NHANES: public SAS-XPT, base `https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/<year>/DataFiles/`,
  cycles 2015 (_I), 2017 (_J), 2021 (_L); files DEMO, MCQ, BMX, BPQ, DIQ, SMQ, ALQ, DPQ.
- CHARLS / MHAS / RAND HRS: Gateway to Global Aging Data harmonised release D files; KLoSA: original
  KLISSA wave workbooks 1-9, mapped with the Gateway creation code as reference only (no Stata
  available). RAND HRS 1992-2022 v1 was read from the SAS-XPT release supplied to the authors
  (`randhrs1992_2022v1_SAS.zip`, 7.2 GB, `pyreadstat`), and only the columns listed in
  `results/tables/hrs_metadata_probe_2026-11-03.json` are used.
- Access terms are the authors' responsibility. MHAS was loaded on the data holder's attestation that
  their authorisation covers AI-assisted analysis, and RAND HRS on the authors' own supply of the file;
  **neither attestation has been independently verified from this machine** (SELF_AUDIT O7/O8 and O22).
  A human must read the current GGAID/RAND terms for both before submission; if either is withdrawn,
  the deletion checklist in SELF_AUDIT applies.

## Integrity guarantees
- Preprocessing (imputation/scaling/spline basis) fit on TRAINING rows only — unit-tested; columns
  constant or wholly unobserved in training are dropped before fitting.
- Every confidence interval in the international and incident arms is a **person-clustered** bootstrap
  (a person's whole interval block enters or leaves together), not a row-level one.
- Absolute-risk metrics always quote two naive references: the Brier of a constant frozen at the
  training prevalence, and the oracle base rate q(1-q) that underlies the scaled Brier.
- Decay is defined once: internal minus external, positive = transport loss, computed against a
  person-clustered internal reference.
- Survey design weights are attached and a weighted arm is reported; frequency weights are never
  presented as design weights, and HC1 standard errors are never presented as a substitute for a
  complex-design variance.
- Figures are newer than, and generated from, the same dated CSVs the tables quote, and the figure
  script reads only `results/tables/`. It refuses to draw a panel whose filter matched no row or whose
  matched rows disagree on the value being plotted (defect 16), because an empty selection plus a
  silent `.iloc[0]` produces a blank figure that looks like a result.
- `results/tables/` is the single normalisation point: `publish_incident_tables.py` renames every
  `*_oe_ratio` column to `*_pred_over_obs` with its reciprocal, and demotes the horizon-accounting
  JSON's leftover unkeyed top level and the diagnostics JSON's `*_pct`-named fractions to correct
  names (defects 14 and 17). Working files stay byte-identical to what the run produced.
- `incident_grid_reframe.py` dies rather than write a bad risk set: persons, the total event weight,
  the set of stroke-carrying persons, every dated terminal end-status count, each person's last observed
  date and (except under the `midcell` allocation, which truncates after the event by construction) the
  total person-time must all match the unsplit file; no sub-interval may exceed the grid, no row weight
  may be non-positive, and no person-window may carry two events. Which sub-interval carries an
  interval-censored stroke is `--alloc`, not a hard-coded choice, because placing it in the parent's
  *last* piece asserts event-free time the panel never reported — see `docs/SELF_AUDIT.md` defect 19 and
  `results/superseded/2026-11-03_last-piece-grid/`.
- `incident_cloglog.py` carries its own consistency gate: its sklearn logistic anchor must reproduce the
  published frozen horizon row (`incident_horizon_recalibration_cif_mid.csv`) to machine precision
  (observed maximum absolute difference 2.2e-16), and it raises if it does not — a new arm that cannot
  recreate the old number is measuring something else.
- `incident_ic_grid.py` carries two gates of the same kind, and they are what make its grid column
  evidence rather than a third opinion: at one piece per interval the interval-censored objective
  collapses to the published Bernoulli likelihood, so its unsplit rows must reproduce the three GLM arms
  (observed 4.4e-8 / 1.5e-7 / 3.6e-8), and the log-exposure-offset arm must be identical at every grid
  size because the aggregation collapses to exp(-lambda*L) (observed 1.4e-12). It also reports, as a
  disclosure it does not gate on, that the published primary model is converged only to sklearn's default
  tolerance 1e-4 (`docs/SELF_AUDIT.md` defect 21).
- `docs/SELF_AUDIT.md` lists thirty defects found in this project's own analysis code, each with
  the specific number it invalidated and its status; a superseded table is never quietly overwritten
  without saying which figure it changed, and superseded outputs are moved to a `superseded/` folder
  with a README rather than left beside the live ones.
- Design-weighted NHANES prevalence uses a PSU-within-stratum cluster bootstrap.
- The pipeline was validated end-to-end on synthetic data with known ground truth
  (`synthcheck.py`) before any real-data run.

#   ROUND 9 (allocation-estimator cross-check): 
#     intl/incident_cr_alloc_variants.py --horizon 4
#         -> three estimand-matched observed-risk allocations (midpoint / uniform-within-interval / joint-model
#            truncated-exponential conditional), confirming Table 19's 'only Mexico moves materially' is robust to
#            the within-interval allocation rule (China 0.80 under all three). audit_consistency_round9.py (64) PASS.
#   ROUND 10 (model-identity unification + complete SI booklet):
#     intl/incident_cr_joint_strict_refit.py --horizon 4 --reps 40
#         -> refits the JOINT multinomial competing-risks primary model under partial-strict coverage (training rows
#            = pooled minus non-interview tails, all 23,347 death intervals retained; eval frame asserted person-for-
#            person equal to the published strict arm 17,267/8,770/16,828/35,553), writes
#            incident_cr_joint_strict_refit_cif_mid.csv -> Table 7b (MX 2.54 still >2, repair +0.00194 beats frozen 100%).
#     intl/incident_figures_joint.py
#         -> regenerates the three joint-model MAIN figures (incident_joint_fig1_calibration, incident_joint_fig2_update,
#            incident_joint_fig3_observed_risk) as 300-dpi PNG + vector PDF into deliverables/figures/incident, each read
#            from the joint CSVs so figure and table cannot disagree.
#     audit_consistency_round10.py (113) PASS alongside round6/7/8/9 (53/86/123/64). Supplementary_technical.md completed
#     as a standalone SI booklet (Methods S-A/S-B/S-C, Notes S-D/S-E, Tables S1-S8, Figures S1-S8); manuscript.docx and
#     Supplementary_technical.docx rebuilt and validated.
#   ROUND 11 (11-point restructure + reviewer correctness fixes):
#     intl/nature_style.py  (NEW shared house-style module: Arial, Okabe-Ito, exact 5 cm tall x 5 cm single /
#         6.5 cm multi-panel canvas saved WITHOUT a tight bbox so physical size is exact, bold a/b/c/d panel
#         letters, no on-figure note text, 300-dpi PNG + editable-text PDF).
#     intl/incident_figures_joint.py  -> main Figures 1-4 (joint calibration deciles, joint update NB,
#         observed-risk allocation grouped 3-vs-1, smooth calibration redrawn from incident_cr_joint_calibration_smooth.csv).
#     intl/make_figures_incident.py   -> Figures 5-6 + Supplementary Figures S1-S8, all routed through nature_style
#         (suptitle notes stripped, conclusion titles neutralised, exact sizes); logistic smooth S7 redrawn from CSV.
#     deliverables/manuscript.md      -> Round-11 correctness fixes (Fig1 below-diagonal, Fig3 3-vs-1 grouping,
#         Fig4 x=predicted probability, P0-2 identifiability coding, P1-1 simulation tone, P1-3 V4 ablation label,
#         P1-4 joint-first selective updating, P1-7 pre-deployment wording); Code availability collapsed to a
#         repository pointer; all 22 tables renumbered 1..22 (no gaps, no 'b') and moved to the end; bold stripped
#         to captions only; dev-history/AI phrases polished.
#     deliverables/Supplementary_technical.md -> reduced to Supplementary Tables S1-S9 + Figures S1-S8 (prose
#         Methods/Notes removed; the known-truth simulation table is now Table S9; the interval-censored likelihood
#         and event-time allocation assumptions are stated in the main Methods).
#     analysis/output/audit_consistency_round6-10.py remapped to the new table numbering; NEW
#     audit_consistency_round11.py (81) verifies the restructure. All six gates PASS; manuscript_round11.docx and
#     Supplementary_Information_round11.docx rebuilt and validated.
#   ROUND 12 (GitHub frozen-repository publication):
#     The reproduction code is PUBLISHED at https://github.com/teamhuang/stroke-risk-transportability (frozen release
#         tag v1.0.0). Assembled by _round12_build_repo.py, which copies code + de-identified aggregate results +
#         figures + manuscript/SI/READMEs and DROPS every person-level file (personperiod_*, hrs_times.csv, the 74 MB
#         incident_personperiod_pooled_*.csv and the person-level leakage_audit CSV) by header id-column scan; the
#         aggregate incident working layer that audit gates round6-11 read is shipped so all seven gates PASS
#         self-contained from the package (132 MB, 405 files, largest object 13.87 MB). .gitignore re-excludes
#         person-level files on any local re-run. manuscript.md Code availability updated to the real URL + v1.0.0
#         (Zenodo DOI remains [AUTHOR-SPECIFIC] until the authors connect the release and publish it); SUBMISSION_
#         BLOCKERS updated; round12 gate re-contracted to assert the published URL/tag (45 assertions). A top-level
#         README.md (scope / environment / layout / how to run the gates / reproduce-from-source / data policy /
#         author-only items) and pinned requirements.txt are written into the repo. The archived Zenodo DOI is still
#         author-issued and intentionally unfilled.
