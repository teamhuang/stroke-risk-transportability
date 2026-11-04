# International data runbook — get the four HARMONISED gate files, then one command

Goal: a genuine country-level LOCO. Landed as China (CHARLS) / Korea (KLoSA) / Mexico (MHAS) /
United States (NHANES); the reported prospective analysis is the three-panel incident arm below,
because NHANES has no repeat interviews. England (ELSA) and continental Europe (SHARE) were the
original targets and remain enclave/human-step only — see "Access findings".
All four studies publish a **harmonised gate file** that shares the same `h*` variable
naming, so one mapping (config_intl.py) serves them all.

## Where to drop the files
Save each cohort's **Stata `.dta`** file into:
```
H:\脑出血国际队列\data\raw\intl\
```
Name them so the cohort is detectable, e.g. `CHARLS_harmonized.dta`, `HRS_harmonized.dta`,
`ELSA_harmonized.dta`, `SHARE_harmonized.dta`. Then run:
```
cd H:\脑出血国际队列\analysis\scripts\intl
python run_harmonized_gate.py
```
It auto-maps the `h*` variables, reports any concept a cohort lacks (disclosed, never
fabricated), builds the standardised tables, runs country-level LOCO, and writes
`data\processed\intl\loco_intl_results.csv` + `figures\loco_*.png/pdf`.

## STATUS — four countries landed (China, Korea, Mexico, United States)

Acquired and processed (all real data). Row/person/event counts below are for the **corrected**
tables that the reported analysis uses.
- **China — CHARLS** Harmonised release D (`data/raw/intl/CHARLS/H_CHARLS_D_Data.dta`,
  document 1140, downloaded after approval) → `std_CHARLS.csv` via `charls_reshape.py`, then
  plausibility-cleaned to `corrected/std_CHARLS.csv` (71,694 respondent-waves, 24,458 adults,
  3,123 strokes; 59 impossible BMI values removed, 394 rows dropped for age <20 or absent age).
- **Korea — KLoSA** original waves 1–9 (`data/raw/intl/KLoSA/w01..w09_e.xlsx`); the Gateway
  `KLoSA Stata Creation Code.do` was used ONLY as a mapping reference (no Stata available).
  `klosa_reshape_v2.py` rebuilds `corrected/std_KLoSA.csv` (65,494 respondent-waves, 11,115
  adults, 859 strokes). Confirmed mappings: chronic block 1=yes/5=no (C006 htn, C011 diab,
  C033 heart, C038 stroke; code 3 on the stroke item -> NaN), ever-smoker C116, current-smoker
  C117 **with the structural rule `smoken=0 if C116==5`**, alcohol **C122 (plus C111a in wave 1)
  — NOT C119, which is cigarettes/day**, education `w01A003` carried forward as the time-invariant
  baseline attribute, marital from wave 2 onward (wave 1 does not ask it, so it stays missing),
  BMI computed as C105/((C107/100)²) on the Gateway plausibility window. `income_pir` remains
  unobserved: `itot` is a six-component sum with bracketed-midpoint imputation and flags, which
  was not reconstructed. Excel workbooks the default reader could not parse were read with the
  calamine engine.
- **United States — NHANES** re-encoded to the shared scheme → `std_NHANES.csv` via
  `build_nhanes_std.py` (18,191 rows, 784 strokes; 4 impossible BMI values removed by the shared
  plausibility pass). Source `sex` is 1=male/0=female and is
  remapped to 1/2 so it is not silently dropped by `modeling.encode`.
- **Mexico — MHAS** Gateway Harmonized MHAS Ver.D (`H_MHAS_d.dta`, 27,159 person rows x 6,542
  columns, created May 2025) → `std_MHAS.csv` via `mhas_reshape.py` (91,709 respondent-waves,
  27,092 adults, 3,415 strokes, releases 2001/2003/2012/2015/2018/2021). Mapping confirmed
  against the file's own labels and value labels before use
  (`results/reports/mhas_metadata_dump.json`). Licence: this cohort was withheld from the
  three-country arm on 2026-11-02 because its data-use terms were read as prohibiting
  AI/LLM processing; on 2026-11-02 the data holder confirmed in this project that their
  authorisation covers AI-assisted analysis, so the file was loaded. The attestation is the
  user's, not an independent verification — see `docs/SELF_AUDIT.md` O7.

Shared cross-cohort encoding: 3-level education, 2-level partnered/not marital,
within-cohort standardised log income, sex 1/2, binary conditions 0/1.

Reproduce the four-country LOCO + figures. The **reported arm is the corrected pool** in
`data/processed/intl/corrected/`; the uncorrected files beside it are kept only so the
corrections can be shown to matter, not to be re-analysed.

```
cd H:\脑出血国际队列\analysis\scripts\intl
python charls_reshape.py                 # -> ../..data/processed/intl/std_CHARLS.csv
python build_nhanes_std.py               # -> std_NHANES.csv
python klosa_reshape_v2.py               # -> corrected/std_KLoSA.csv  (v1 is superseded)
python mhas_reshape.py                   # -> std_MHAS.csv
python clean_intl_std.py                 # -> corrected/std_{NHANES,CHARLS,MHAS}.csv
python run_loco_models.py "<abs path>/data/processed/intl/corrected"   # corrected LOCO
python run_loco_internal_clustered.py "<abs path>/data/processed/intl/corrected"
python make_figures_intl.py "<abs path>/data/processed/intl/corrected"
python make_intl_table1.py "<abs path>/data/processed/intl/corrected"  # Table 5
python compare_intl_runs.py old3=... new4=... corrected=...            # attribution
```

`klosa_reshape.py` (v1) is left in place as the object of the correction record; nothing in the
reported pipeline calls it. See `results/reports/intl_arm_data_defects_2026-11-02.md`.
The previous three-country output is preserved at
`results/tables/loco_3country_NHANES_CHARLS_KLoSA_2026-11-02.csv` so the four-country numbers
can be shown beside it.

## STATUS — the reported study is the INCIDENT arm (four panels, person-intervals, named estimand)

As of 2026-11-03 the manuscript's main analysis is a first-event (new-onset) stroke design on
**RAND HRS (US) / CHARLS (CN) / KLoSA (KR) / MHAS (MX)**: 430,521 person-intervals from 94,005
at-risk adults, 1,062,341 person-years, 6,979 incident first strokes. NHANES contributes no
intervals — its cycles resample different people, so treating 2015-16 / 2017-18 / 2021-23 as a panel
would be a mislabelled prevalence model — and stays in the cross-sectional comparison arm only. The
United States in this design is RAND HRS 1992-2022, which is a genuine 16-wave panel with
day-precision interview dates, an interview-status item and Tracker death dates.

**The four-year estimand is named in every table.** A stroke found between two interviews is
interval-censored, and a person who dies inside the window is either a non-event or an exclusion.
`run_incident_loco.horizon_frame` implements both choices and every row carries `horizon_rule`:
`cif_mid` (primary: Aalen-Johansen cumulative incidence, midpoint dating, deaths as non-events,
loss to follow-up carried by IPCW) and `exclusive_start` (the pre-audit frame, retained as the
sensitivity arm). These are not equivalent: China's apparent four-year prevalence is 0.0609 under
`exclusive_start` and 0.0202-0.0215 under `cif_mid`, and which panel needs an intercept repair
changes with the choice. See `docs/SELF_AUDIT.md` defect 8.

```
cd H:\脑出血国际队列\analysis
bash run_incident_pipeline.sh           # the whole chain below, one log per step in output/pipeline/

# or step by step:
cd scripts/intl
python hrs_reshape.py                   # -> corrected/std_HRS.csv + incident/hrs_times.csv  (7.2 GB source, ~4 min)
python hrs_weight_zero_probe.py         # -> reports/hrs_weight_zero_probe.json (why WTRESP is 0 on 9% of US interviews)
python incident_personperiod.py         # -> incident/personperiod_{HRS,CHARLS,KLoSA,MHAS,pooled}.csv
                                        #    + personperiod_diagnostics.json (per-cohort rule audit)
python run_incident_loco.py --boot 2000 --horizon 4     # primary: BOTH estimands in one table
python run_incident_loco.py --boot 1000 --horizon 4 --time none --horizon-rules cif_mid
python run_incident_loco.py --boot 1000 --horizon 4 --features extended --horizon-rules cif_mid
python run_incident_loco.py --boot 1000 --horizon 4 --weights --horizon-rules cif_mid
python run_incident_loco.py --boot 1000 --horizon 6 --horizon-rules cif_mid
python run_incident_internal.py         # person-clustered internal reference -> decay column
python incident_adaptation.py --horizon-rule cif_mid --reps 10       # frozen/offset/recalibrate/retrain
python incident_adaptation.py --horizon-rule exclusive_start --reps 10
python incident_horizon_recalibration.py --horizon-rule cif_mid --reps 20   # P0: interval- vs horizon-scale fitting
python incident_horizon_recalibration.py --horizon-rule exclusive_start --reps 20
python incident_competing_risks.py --models logistic,elasticnet,xgboost --rules cif_mid,exclusive_start \
        --fractions 0.02,0.05,0.10,0.25,0.50 --reps 20   # P0: Aalen-Johansen CIF, dating rules, IPCW
python incident_update_strategies.py --models logistic,elasticnet,spline_logistic \
        --fractions 0.02,0.05,0.10,0.25,0.50 --reps 20   # P1: pooled / revised / time-only / refit arms
python incident_ascertainment_sensitivity.py --models logistic,random_forest,xgboost
        # P0: does the horizon frame count people as observed who were only alive? (O23)
        # self-checks by reproducing horizon_frame exactly, then re-prices incidence/IPCW/pred-over-obs
        # and the one-intercept net benefit under strict coverage -> reports/incident_ascertainment_summary.json
python incident_subgroups.py
        # who the transported model is right for: age/sex/hypertension/education/interval-length strata,
        # person-clustered CIs (B=500), and each cell's own one-intercept re-priced. Defaults are the
        # published run: --rule cif_mid --models logistic,random_forest --features common --time linear
        # -> incident_subgroups.csv + reports/incident_subgroups_summary.json
python incident_strict_frame.py
        # coverage objection, part 1: truncate every interval at t_ask (the last wave where the stroke
        # item was answerable) -> personperiod_strict.csv. Self-check compares it with the published
        # strict arm and documents the difference: full truncation deletes ALL 23,347 death intervals,
        # because a death is recorded on the interval that BEGINS at the last answered interview.
python incident_strict_refit.py --models logistic,elasticnet,xgboost --reps 20
        # coverage objection, part 2: refit the whole LOCO design on the PARTIAL-strict risk set
        # (non-interview tails dropped, death intervals retained) and score it on the strict horizon
        # frame, which is verified person-for-person against incident_ascertainment_sensitivity.csv
        # before any model is fitted -> incident_strict_refit.csv (Table 7)
python incident_grid_reframe.py --delta 1 --alloc uniform
        # link objection, part 1: re-cut every interval into equal pieces of <= 1 year. Which piece
        # carries an interval-censored stroke is an argument, not a hard-coded choice: `uniform` gives
        # every sub-interval 1/n of the parent's event (a count-matching device - see the IC arm below,
        # which maximises the actual interval-censored likelihood instead), `midcell` puts it whole on
        # the piece containing the parent's declared midpoint
        # and truncates there, `last` keeps it on the final piece - which asserts event-free time the
        # panel never reported and is run only to keep the pre-submission arm reproducible. Aborts
        # unless persons, total event weight, the stroke-carrier set, every dated terminal end-status
        # count and each person's last date are unchanged, and (except under midcell) unless total
        # person-time is unchanged: uniform 1,273,994 rows / 1,062,340.9 py, last 1,251,843 rows /
        # 1,062,340.9 py, midcell 1,245,851 rows / 1,057,247.5 py (5,093.5 py after the event cell
        # leaves the risk set by construction), from 430,521 rows in the unsplit file
        # -> personperiod_grid1_{uniform,midcell,last}.csv
python incident_cloglog.py --reps 20
        # link objection, part 2: four hazard specifications on identical rows and identical splits -
        # the published L2 logistic (anchor), an unpenalised logistic GLM, a cloglog hazard with
        # interval length as a covariate, and cloglog with log(length) as an OFFSET
        # (the proportional-hazards formulation). Scores each on the cif_mid horizon frame with its
        # IPCW weights, refits the one-intercept repair in the arm's own link space AND in log-odds
        # space, and reports duration consistency (compose H from 1/2/4/8 pieces at fixed covariates).
        # Raises unless the anchor reproduces incident_horizon_recalibration_cif_mid.csv exactly.
        # -> incident_cloglog_cif_mid.csv + reports/incident_cloglog_cif_mid.json (Table 8)
for a in uniform midcell last; do
python incident_cloglog.py --reps 20 --pp personperiod_grid1_$a.csv
done
        # the same four arms refitted on each one-year grid; --frame-pp stays on the UNSPLIT file, so
        # all four fits are scored on identical persons with identical labels and identical weights.
        # The output name takes the allocation from the --pp filename.
        # -> incident_cloglog_cif_mid_grid1_{uniform,midcell,last}.csv (Table 8)
python incident_ic_grid.py --reps 20 --deltas 0,1
        # the reviewer's second point: a fractional-event allocation matches the event COUNT inside an
        # interview gap, but an interval-censored observation contributes 1 - prod_j(1 - p_j), the
        # PROBABILITY that the event lies in the gap. This arm maximises that likelihood directly,
        # d*log(1-(1-p)^n) + (1-d)*n*log(1-p), over parent intervals - no re-cut file is needed, because
        # covariates are constant within a gap so one hazard serves every piece. Four specifications at
        # delta=0 (one piece per gap) and delta=1 (up to 27 pieces), L-BFGS with an analytic gradient.
        # Two hard gates: at one piece the objective collapses to the published Bernoulli likelihood, so
        # the unsplit rows must reproduce incident_cloglog_cif_mid.csv (observed 4.4e-8 / 1.5e-7 / 3.6e-8),
        # and the log-exposure-offset arm must be grid-invariant because (1-p)^n = exp(-lambda*L) at any
        # n (observed 1.4e-12). Recorded as a DISCLOSURE rather than a gate: the published primary model
        # is sklearn at its default tol=1e-4, and the identical objective solved to 1e-10 moves the US
        # pred/obs from 1.161 to 1.170 (defect 21).
        # -> incident_ic_likelihood_cif_mid.csv + reports/incident_ic_likelihood_cif_mid.json (Table 8)
python incident_shap.py --rows 4000     # exact Shapley attributions of the frozen models (Table S5)
python rf_probability_ablation.py --features common      # class-weight ablation (cross-sectional arm)
python rf_probability_ablation.py --features extended
python publish_incident_tables.py       # -> results/tables/incident_*_<date>.csv|.json
        # also the single normalisation point: any *_oe_ratio column is republished as
        # *_pred_over_obs with its reciprocal, and the horizon-accounting JSON's leftover unkeyed
        # top level is demoted to "unkeyed_top_level_verbatim" (defects 14/16, BLOCKING 2)
python make_figures_incident.py         # -> deliverables/figures/incident/*.png|.pdf (15 panels)
        # reads only results/tables/; primary()/need()/cell() abort on an empty or ambiguous
        # selection rather than drawing a blank panel (defect 16)

# Manuscript numbers are printed, not typed. Run these after publishing and diff against the
# manuscript; a table row that cannot be reproduced from results/tables/ is defect 15 recurring.
cd ../../analysis/output
python make_table_rows.py               # Tables 1, 2, 3, 5
python make_table4_rows.py              # Table 4, logistic and XGBoost blocks
python make_table4_notes.py             # paired gains, scale contrast, Table 4-continued, learning curves
python make_tableS_rows.py              # Supplementary S1 (LOCO by cohort) and S2 (sensitivity arms)
python make_strict_rows.py              # Table 7 (strict-coverage refit) + intercept-stability rows
python make_cloglog_rows.py             # Table 8 (link x grid), repair gains, duration-consistency ratios
python make_ic_rows.py                  # Table 8's interval-censored column, its anchors and its gates
```

Person-period rules, all of them audited into `personperiod_diagnostics.json`:
- Entry requires a determinable stroke item answered "no"; 3,775 prevalent cases at entry were
  excluded (2,205 US / 682 CN / 323 KR / 565 MX). Covariates come from the interval's **starting**
  wave.
- Vital status is taken from the interview-status item (`R{n}IWSTAT` / `r{n}iwstat`: 1 alive and
  interviewed, 4 non-response but alive, 5 died this wave, 6 died previous wave, 7 dropped from the
  sample, 9 status unknown), **not** from a death-date field where one exists: the death-year field covers
  1.5% of CHARLS and 27.0% of MHAS wave records (`death_date_coverage_fraction`, a fraction of rows —
  the key was named `_pct` until 2026-11-03 and quoting 0.0152 as "0.015%" is a hundredfold error, see
  SELF_AUDIT defect 17) and death-coded records carry no fieldwork date at
  all. RAND HRS is the exception that proves the rule — `RADDATE` gives an exact date for 19,144 of
  its 45,234 respondents, so 14,724 of its 14,877 death-terminated intervals are date-known and only
  153 fall back on status. Undated deaths are censored at the midpoint of the wave's own fieldwork
  window, and the window is derived from the data as the median dated interview per wave rather than
  taken from documentation.
- `censor_mode` is a column of every output row: `death` for HRS, CHARLS and MHAS;
  `last_interview` for KLoSA, whose nine main wave workbooks contain no vital-status field
  (mortality is in the `w0{2..8}_exit_e` exit files, not on disk). Korea's 536 events and its
  zero-observable competing mortality are therefore lower bounds, and its Aalen-Johansen incidence
  coincides with the naive Kaplan-Meier complement by construction rather than by agreement.
- `exposure_years` and `t_since_entry_years` are model covariates. Omitting them makes a discrete-time
  model assert a constant hazard across panels that mix 2-year and 20.6-year gaps.
- Horizon accounting, H = 4 years, both estimands (from `incident_horizon_counts.json`, now keyed by
  `H{horizon}_{rule}_{features}_{time}` so no arm can overwrite another):
  `cif_mid` = 1,845 strokes / 4,668 deaths counted as non-events / 8,264 lost before H / 79,228
  stroke-free through H / 85,741 evaluable of 94,005 adults, observed prevalence 0.0215 unweighted
  and 0.0202 IPCW; `exclusive_start` = 3,048 / 8,748 excluded / 16,233 excluded / 74,724 / 77,772,
  prevalence 0.0392.
- The horizon is composed over the **training** panel's median interval length and the realised years
  are reported per row (Korea's realised horizon is 3.0 years, not 4).

Weights: all four panels' person-level design weights are attached to each interval's starting wave
(`wt_start`). Usable — non-null **and positive** — on 90.9% US / 99.0% CN / 75.8% KR / 93.4% MX of
*interval rows*. Do not quote the `weight_nonnull_pct_of_wave_records` field (57.4% US / 74.5% CN /
75.6% KR / 66.8% MX) as an interval coverage: its denominator is every wave record in the panel,
including the vital-status rows of people who were not interviewed that wave, so it understates
coverage. Two US specifics, both measured by `intl/hrs_weight_zero_probe.py`
(-> `results/reports/hrs_weight_zero_probe.json`):
- `R{w}WTRESP` is **zero, not missing**, on 26,967 of 296,199 interviewed rows (22.6% at wave 1, 6-7%
  later). Those rows are much younger than the interviewed average (median 51 vs mean 68 at wave 8)
  and 2,658 of the 2,858 wave-1 zeros carry a positive household weight `R{w}WTHH`, so they are
  in-household persons who are not the weight-eligible respondent of that wave's frame. `R{w}WTHH` is
  deliberately **not** substituted: it weights a different estimand.
- 2,728 wave-16 interview rows have a missing `WTRESP`. Harmless here, because a wave-16 respondent
  starts no interval.

The weighted arm therefore drops ~9% of US intervals — a documented, non-random omission of
in-household non-respondent-weight persons, which is one more reason the primary arm is unweighted.
Incidence is reported both unweighted and design-weighted, and `--weights` runs a weighted
fit-and-evaluate arm. The primary arm stays unweighted, by choice and not by necessity. Design weights
are frequency-like person weights and are not a substitute for a survey-design variance estimator —
strata and PSUs are not carried in these extracts, so all intervals here use IPCW / person-clustered
bootstrap rather than Taylor linearisation.

## Access findings (why not more countries yet)
- **MHAS (Mexico) — INCLUDED as of 2026-11-02 on the data holder's attestation.** It was
  originally withheld because its terms were read as prohibiting management or analysis of
  MHAS / Gateway-Harmonised-MHAS data with AI/LLM tools. Re-verification of that clause online
  was not possible from this machine (mhas.org serves only a JS redirect), so the inclusion
  rests on the user's confirmation of authorisation, which is recorded rather than independently
  verified. If the attestation is ever withdrawn, delete `std_MHAS.csv`, drop MHAS from
  `incident_personperiod.SPECS`, and re-run the incident arm on US/CN/KR only; Mexico currently
  supplies 933 of the 6,979 incident events and the whole low-incidence falsification case, so its
  removal changes which panel the calibration result is about.
- **RAND HRS 1992-2022 v1 — INCLUDED as the US panel of the incident arm.** Supplied on
  2026-11-03 (`data/raw/intl/HRS/randhrs/`, 7.18 GB SAS + codebook PDF + format catalog). This is
  the analysis-grade HRS release, not the Gateway gate file: it carries `RADDATE` (day-precision
  death from the Tracker file) and `R{w}IWSTAT`, which `H_HRS_d.dta` does not, and those two fields
  are what make US competing mortality observable instead of folding it into attrition.
  `data/raw/intl/HRS/H_HRS_d.dta` (855 MB) remains on disk, unprocessed, and is now redundant for
  this design. **Licence status here is the user's, not a verified reading**: the file was supplied
  as available for this project and no terms document was retrieved or checked from this machine.
  Before submission, the HRS/RAND data-use and citation requirements must be confirmed by a human
  step exactly as MHAS's were (see `docs/SELF_AUDIT.md` O7/O8).
- **ELSA / LASI / CRELES / KSHAP — enclave or human step.** ELSA and LASI are Gateway-harmonised in
  the same layout as CHARLS/MHAS and would extend the LOCO to England and India with no new code
  beyond a SPECS entry; both require the AD Workbench or an approved access request.
- **SHARE (~20 European countries) — human step**: download, sign and submit the SHARE
  User Statement at share-eric.eu (granted in a few days). Once obtained, drop the
  harmonised file and split by its country code for a large multi-country LOCO.
- **TILDA (Ireland) — human step**: microdata is `restricted` (HTTP 403) and needs an
  ISSDA Data Request Form; its open codebook confirms stroke + the full feature set, so it
  is worth requesting.

## Honest feature gaps (disclosed, never fabricated) — as of the corrected arm
- CHARLS: no measured cholesterol; no measured BMI in wave 4.
- KLoSA: no harmonised cholesterol-diagnosis item, and `income_pir` unobserved because the
  six-component total-income composite (`itot`, with bracketed-midpoint imputation and flags) was
  not reconstructed — imputed from the training countries during LOCO. Its measured BMI **is**
  available and is now extracted from `w{v}C105` (kg) / `w{v}C107` (cm); the earlier line here
  claiming KLoSA had "no clean measured BMI" was wrong and is the reason v1 exists on record.
- MHAS: no cholesterol *diagnosis* item (only a screening-utilisation item); measured BMI in
  releases 1-3 only, and present for just 7-9% of person-rows (92.7% of analytic rows imputed).
- **CORRECTION (2026-11-02): the earlier line "No survey weights in the international arm
  (harmonised files lack design weights)" is FALSE.** The gate files do carry them: CHARLS
  `r{n}wtresp` / `r{n}wtrespa` / `r{n}wtrespb` (+ `r2wtrespl`), MHAS `r{n}wtresp`, and KLoSA
  `w0{5..9}wgt_p/_a/_ap/_ac` in its creation code. **Status 2026-11-03: weights are attached and a
  design-weighted incident arm has been run** (`incident_loco_common_linear_H4_w.csv`, published as
  `incident_loco_common_linear_H4_weighted_2026-11-03.csv`); the primary arm remains unweighted and
  says so. Weighted prevalence is quoted per cohort in the diagnostics file (CN 10.19, KR 4.14,
  MX 3.36 per 1,000 person-years versus 10.25 / 4.75 / 3.39 unweighted).
- **Feature-set naming, to avoid a repeat of the ablation bug (SELF_AUDIT defect 6).** In
  `run_loco_v2.py` / `run_incident_loco.py`, `common` = the ten concepts observed in every cohort
  (age, sex, education, marital, ever-smoker, current-smoker, alcohol, hypertension, diabetes,
  cardiac disease) and `extended` adds `income_pir`, `bmi`, `high_cholesterol`. The incident arm's
  primary model is `common` plus the two time terms. A `--features` flag that is computed but never
  applied is a defect, not a style choice: it silently changes what a table means.

## Adding SHARE / TILDA later
1. Place the harmonised file under `data/raw/intl/<COHORT>/`.
2. Confirm names with `python intl/discover_intl.py <file>` (never guess).
3. Write a cohort reshape (like `charls_reshape.py`) → `std_<COHORT>.csv` in the shared encoding.
4. Re-run `run_loco_models.py` + `make_figures_intl.py`; update manuscript Table 3 / Figure 10.

## Integrity rules that governed this arm
- Only country-level results actually computed on real data are reported.
- Variable mappings were checked against the real files before use.
- Missing concepts are left missing and disclosed, not imputed from guesses.
- MHAS was withheld on licence grounds while the file sat on disk, and was only loaded after
  the data holder attested that their authorisation covers AI-assisted analysis; the attestation
  is recorded in `docs/SELF_AUDIT.md` O7 rather than presented as a verified licence reading.
