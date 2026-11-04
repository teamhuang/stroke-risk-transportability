# TRIPOD+AI item-by-item checklist

Manuscript: *Transportability and local recalibration of absolute stroke risk across four national ageing
cohorts* (target: npj Digital Medicine).

Aligned to the TRIPOD+AI statement (Collins GS, Moons KGM, Dhiman P, et al. BMJ 2024;385:e078378; PMID
38626948; DOI 10.1136/bmj-2023-078378 — reference [5] of the manuscript). Item numbers and descriptors follow the
TRIPOD+AI *Article* checklist. "Where reported" cites the manuscript's own sections, tables and figures;
"Status" is honest — Partial or Author-input-needed items are flagged rather than claimed complete. This file
is a submission deliverable; it is not part of the manuscript body.

Legend: **R** = reported in the manuscript; **P** = partially reported / needs author input; **NA** = not
applicable to this study design (reason given).

## Title and abstract

| Item | Descriptor (abridged) | Where reported | Status |
|---|---|---|---|
| 1 | Title: identify as prediction-model development/evaluation, target population, outcome | Title: "Transportability and local recalibration of absolute stroke risk across four national ageing cohorts"; outcome = survey-ascertained first-reported stroke; population = adults in HRS/CHARLS/KLoSA/MHAS | R |
| 2 | Structured abstract | Unstructured abstract ≤150 words (journal Article format); reports design, four cohorts, joint competing-risks primary estimator, headline P/O, repair, age-aware result | R |

## Introduction

| Item | Descriptor | Where reported | Status |
|---|---|---|---|
| 3a | Rationale / healthcare context | Introduction ¶1–2: discrimination ≠ usability; threshold is a statement about absolute risk; prevalent cross-sectional outcome cannot support a screening claim [refs 2–8] | R |
| 3b | Target population, intended purpose and users | Introduction ¶3 and Discussion: deploying health system licensing a frozen model; intended use = flagging for further cardiovascular assessment, not prescribing | R |
| 3c | Known health inequalities between sociodemographic groups | Age-band heterogeneity (Table 13, "Calibration is not uniform across ages"); cross-national differences are the study object | R |

## Methods

| Item | Descriptor | Where reported | Status |
|---|---|---|---|
| 4 | Sources of data; where protocol / code / dataset available | Methods "Data sources"; Code availability (all scripts named); Data availability (per-cohort gated routes); reproducibility README | R |
| 5a | Eligibility criteria and setting | Methods cohort assembly: adults ≥20 with a determinable stroke item; prevalent-at-entry excluded; 2 not-determinable removed (Table 1, Figure 10) | R |
| 5b | Dates of data collection, accrual and follow-up | Methods: first waves (1992/2011/2006/2001), wave counts and releases in Table 1; horizon rules cif_mid/start/end | R |
| 6a | Outcome definition incl. time horizon | Methods "The four-year estimand, stated before it is estimated" (7 declared elements); primary estimand = exclusive first-stroke CIF at 4 y | R |
| 6b | Outcome measurement / assessors (subjective) | Survey self-report; Table 16 outcome-observation mapping; validity literature [6–8] | R |
| 6c | Blinding of outcome assessment | NA — self-reported survey outcome, no adjudication panel to blind; disclosed as a limitation | NA |
| 7 | Predictors, how and when measured | Methods covariates (age, sex, hypertension, diabetes, heart disease, smoking, alcohol, education, marital); measured at interval's starting wave; excluded (chol/income/BMI) justified | R |
| 8a | Sample size: participants and events | Results "Study population": 104,121 at risk, 94,005 analysable, 6,979 events; per-country in Table 1 | R |
| 8b | Missing data handling | Methods: median-impute on training rows; degenerate columns dropped; extended arm imputes chol/income/BMI from training countries | R |
| 8c | Actions to blind predictor assessment | NA — survey items, no assessor blinding; disclosed | NA |
| 9 | Statistical analysis / software; reproducibility | Methods "Software and reporting" (Python pandas/sklearn/xgboost/lightgbm; seeds; BLAS-thread lock); end-to-end synthetic validation; Code availability | R |
| 10 | Model development: type, building steps, hyperparameters, internal validation | Methods: logistic/cloglog discrete-time hazards, joint multinomial competing-risks (primary), boosted learners; LOCO design; internal CV on pooled panels | R |
| 11 | Model evaluation: internal/external, and how predictions computed | LOCO external validation; person-clustered bootstrap; AUROC, calibration slope/intercept, P/O, net benefit; prediction formula = joint CIF ladder (Methods) | R |
| 12a | Performance measures and rationale (discrimination, calibration, utility) | Methods estimand block + Tables 2/12 (AUROC), 4/12 (P/O, calibration), 7/10 (net benefit / DCA) | R |
| 12b | Handling of predictors in analysis (functional form, standardisation) | Methods: standardisation, spline/linear time arms, log-exposure offset (Table 8) | R |
| 12c | Model type, rationale, all building steps, internal validation | Methods "The primary estimand"; joint multinomial rationale (exclusive first event) | R |
| 12d | Heterogeneity across clusters (countries) handled/quantified | The whole study: four-country LOCO, between-country variance (Results "Discrimination travels"); TRIPOD-Cluster considered | R |
| 12e | Measures/plots to evaluate performance and compare models | KM/DCA curves (Figures 1, 9b), calibration plots, Tables 4/10/12/13/15 | R |
| 12f | Model updating / recalibration (incl. sociodemographic groups) | Table 4 (intercept), Table 10 (selective-updating policy on joint model), Table 13 (age-aware updates A–E) | R |
| 12g | How predictions calculated for evaluation | Methods: joint CIF composed on discrete grid; code in incident_cr_joint.py / incident_cr_joint_primary.py | R |
| 13 | Usability / interpretability (incl. SHAP for AI) | Supplementary Table S5 (exact Shapley attributions) with scope note that attributions ≠ causal effects | R |

## Results

| Item | Descriptor | Where reported | Status |
|---|---|---|---|
| 14 | Participant flow | Figure 10 (per-panel cascade) + Table 1 (ever − not-determinable − prevalent = at risk = 104,121) | R |
| 15 | Participant characteristics | Table 1 (waves, incidence, person-years, interval-length tails); Table S1/S2 | R |
| 16 | Outcome / event numbers | Table 1 (incident strokes, intervals terminated by death); horizon accounting | R |
| 17 | Missing-data amounts | Methods and Table S1 (weight coverage 90.9–99.0%; US zero-weight rows characterised) | R |
| 18 | Model development results (coefficients / final model) | Methods model spec; Tables 2/4; coefficients in results/tables; joint hazards in incident_cr_joint.csv | R |
| 19 | Model performance estimates with CIs | Tables 2/12 (AUROC + person-clustered CI), 4 (P/O), 15 (interval-censored P/O) | R |
| 20 | Model comparison / transportability across settings | Results "Discrimination travels"; Table 11 (definitional ablation); Table S2 (specification arms) | R |

## Discussion

| Item | Descriptor | Where reported | Status |
|---|---|---|---|
| 21 | Overall interpretation of main results | Discussion: transportability is a property of the estimand and local sample, not the algorithm | R |
| 22 | Limitations | Discussion limitations paragraph (folded, no standalone label): self-report, interval censoring, competing-risk identification in KLoSA, differential ascertainment (Table S6), design-weight scale caveat | R |
| 23a | Interpretation vs current literature | Discussion situates against external-validation guidance [2–5] and updating methods [12] | R |
| 23b | Heterogeneity across clusters (countries) | Four-country results; KLoSA partial-outcome caveat | R |
| 24 | Generalisability / next steps | Discussion: deployment-before-validation framework; retrospective multi-cohort, not prospectively validated | R |

## Other information

| Item | Descriptor | Where reported | Status |
|---|---|---|---|
| 25 | Funding | Acknowledgments: "No external funding" + [AUTHOR-SPECIFIC] grant placeholders | P (author input) |
| 26 | Data availability | Data availability statement with per-cohort gated routes (CHARLS/KLoSA/MHAS/HRS; NHANES public) | R |
| 27a | Code availability / reproducibility | Code availability names every script incl. round-7 additions; README_reproducibility.md; seeds + thread lock | R |
| 27b | User interaction / expertise for the model | Discussion: illustrative 5% threshold, flagging for further assessment; deployment framework described | R |
| 27c | Next steps for future research / applicability | Discussion limitations + prospective-validation and common-core re-fit as open items | R |

## Honest gaps (must be closed by authors before submission)

- Item 25 (Funding) and the author-contribution/competing-interest/ethics statements carry [AUTHOR-SPECIFIC]
  placeholders — they cannot be completed by the analysis pipeline and must be supplied and confirmed by the
  named authors.
- Items 6c and 8c (blinding) are NA by design (self-reported survey outcome) and are stated as such rather
  than filled with an untrue "blinding performed".
- The estimand-dependence items (12e/19/22) now point to the round-7 interval-censored evaluation (Table 15)
  and the unreported-stroke sensitivity (Table S6); these strengthen but do not remove the fundamental
  limitation that a two-yearly survey cannot identify within-interval event times or unreported fatal strokes.
