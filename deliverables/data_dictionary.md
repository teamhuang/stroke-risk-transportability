# Data dictionary — `data/processed/nhanes_stroke_harmonized.csv`

One row per adult participant (SEQN) aged >= 20 with a determinable stroke status.
n = 18,191 (derivation 2015-2018: 10,756; external 2021-2023: 7,435).

| Column | Type | Meaning | Coding |
|---|---|---|---|
| seqn | float | NHANES participant ID | unique |
| cycle | str | survey-cycle code | _I=2015-16, _J=2017-18, _L=2021-23 |
| cycle_label | str | human label | — |
| weight | float | MEC 2-year survey weight (WTMEC2YR) | for design-weighted prevalence |
| psu | float | primary sampling unit (SDMVPSU) | cluster-bootstrap unit |
| strata | float | variance stratum (SDMVSTRA) | — |
| stroke | int | OUTCOME: prevalent self-reported stroke | 1=yes (MCQ160F=1), 0=no (MCQ160F=2) |
| age | float | age (years) | >=20 |
| sex | int | sex | 1=male, 0=female (recoded) |
| race_ethnicity | int | race/Hispanic origin (RIDRETH1) | 1 MexAm,2 OtherHisp,3 NH-White,4 NH-Black,5 Other |
| education | int | adult education (DMDEDUC2) | 1 <9th grade, 2 9th-11th (no diploma), 3 HS graduate or GED, 4 some college or AA degree, 5 college graduate or above |
| marital | int | marital status (DMDMARTL/_Z) | 1 married,2 widowed,3 divorced,4 separated,5 never,6 partner |
| income_pir | float | family income-to-poverty ratio (INDFMPIR) | ~0-5; ~14% missing |
| bmi | float | body mass index (BMXBMI) | kg/m^2; ~13% missing |
| ever_smoker | int | >=100 cigarettes lifetime (SMQ020) | 1/0 |
| current_smoker | int | now smokes (SMQ040) | 1/0; never-smokers set 0 (structural) |
| alcohol | int | >=12 drinks past yr (ALQ101/_111) | 1/0; below-screener set 0 (structural) |
| hypertension | int | ever told high BP (BPQ020) | 1/0 |
| high_cholesterol | int | told high cholesterol (BPQ080) | 1/0 |
| diabetes | int | told diabetes (DIQ010) | 1/0 |
| heart_attack | int | told heart attack (MCQ160E) | 1/0 |
| phq_DPQ010..DPQ090 | float | PHQ-9 depression items (DPQ file) | 0-3; used only for secondary association |

Notes
- Refusal/don't-know codes (7,9,77,99,777,999,...) -> missing.
- **DMDEDUC2 label correction (2026-11-03).** This row previously read
  "1 <HS, 2 HS/GED, 3 some college, 4 college, 5 postgrad", which is not the CDC scheme: DMDEDUC2
  has no "postgrad" category and code 2 is *9th-11th grade without a diploma*. The observed
  distribution in this file is what exposed it (all three cycles carry five populated levels,
  1,448 / 1,889 / 4,100 / 5,579 / 5,133, i.e. design-weighted 4.5 / 7.4 / 24.7 / 30.9 / 32.4% —
  63% "college or above" is impossible for US adults, whereas 32% at level 5 is the published
  college-or-above share). `intl/build_nhanes_std.py` already used the correct reading when it
  collapses to three levels (`1->1, 2->1, 3->2, 4->3, 5->3`, codes 1-2 both below upper secondary);
  only this dictionary was stale. The NHANES .xpt files carry no embedded value labels and
  DEMO_L cannot be read for its character set, so the mapping is documented from the codebook
  statement in `build_nhanes_std.py` and the empirical shares, not read off the file.
- Physical activity deliberately excluded (2021-2023 instrument not harmonisable).
- PHQ items are NOT model features (avoid leakage); used for the risk-score <-> mental
  health association only.

## International arm — reported pool `data/processed/intl/corrected/std_{NHANES,HRS,CHARLS,KLoSA,MHAS}.csv`

Used for the leave-one-country-out analyses. Unit = respondent x wave.
Shared columns: `cohort, country, wave, pid`, then the 14 canonical features
`stroke, age, sex, education, marital, income_pir, bmi, ever_smoker, current_smoker,
alcohol, hypertension, high_cholesterol, diabetes, heart_attack`.

Shared coding: sex 1=male / 2=female; education 1=low / 2=upper-secondary / 3=tertiary;
marital 1=partnered / 2=not partnered; income_pir = within-cohort z-score of log income/
wealth; all conditions and smoking/alcohol are 0/1. `race_ethnicity` is intentionally
omitted so every cohort shares an identical feature set. Person identity is cohort-scoped,
so pooled adult counts must be taken on cohort+pid (bare pid collides across cohorts).

The `std_*.csv` files one level up are the pre-correction build, kept only for attribution;
see `results/reports/intl_arm_data_defects_2026-11-02.md`.

| File (corrected) | country | rows | adults | strokes | prevalence | used by |
|---|---|---|---|---|---|---|
| std_NHANES.csv | US | 18,191 | 18,191 (1/cycle) | 784 | 4.31% | cross-sectional arm only |
| std_HRS.csv | US | 296,195 | 45,233 | 23,925 | 8.08% | incident arm (the US panel) |
| std_CHARLS.csv | CN | 71,694 | 24,458 | 3,123 | 4.36% | both arms |
| std_KLoSA.csv | KR | 65,494 | 11,115 | 859 | 1.31% | both arms |
| std_MHAS.csv | MX | 91,709 | 27,092 | 3,415 | 3.72% | both arms |

**Why `std_pool.py` exists.** NHANES and RAND HRS are both country `US`, so any `std_*.csv` glob
would silently merge two US panels into one held-out "country" and change the published four-country
cross-sectional numbers without raising an error. `std_pool.std_files()` is therefore the only
loader the prevalent arm uses, and it excludes HRS by name with the reason printed. The incident arm
selects its cohorts explicitly through `incident_personperiod.SPECS`, where NHANES contributes zero
intervals and HRS is the sole US panel.

Shared plausibility rules applied to all five (`intl/clean_intl_std.py`, applied inline by
`intl/hrs_reshape.py` and `intl/klosa_reshape_v2.py`): adults aged >= 20; measured BMI kept only
inside 12-70 kg/m^2 (removes 4 NHANES, 59 CHARLS - including a maximum of 52,734.69 - 3 MHAS and 23
HRS values); `current_smoker = 0` wherever `ever_smoker = 0`.

Honest per-cohort gaps (left missing, never fabricated):
- CHARLS: `high_cholesterol` entirely missing (not in the harmonised gate); `bmi` missing in
  wave 4 (no measured exam); `heart_attack` proxied by an ever-heart-problem item; 394
  respondent-waves removed for age <20 or no recorded age.
- KLoSA: `high_cholesterol` and `income_pir` missing (no harmonised diagnosis item; the
  six-component income composite was not reconstructed); `marital` genuinely absent in wave 1, so
  it stays missing there. `bmi` IS observed (98.0% of rows), computed as
  `w{v}C105 / (w{v}C107/100)^2` on the Gateway 20-140 kg / 100-200 cm window; education is the
  wave-1 `A003` value carried forward, because KLoSA asks it only at baseline.
- MHAS: `high_cholesterol` missing — its only cholesterol item (`r{n}cholst`) asks whether
  cholesterol was *checked* in the last two years, which is health utilisation, not a diagnosis.
  `bmi` is measured only (`r{n}mbmi`, releases 1-3, non-null 7.3% of kept rows); releases 4-6
  have no measured exam and self-reported `r{n}bmi` is deliberately not substituted, so NHANES
  and CHARLS are not mixed with a different BMI definition. `heart_attack` uses the *specific*
  ever-heart-attack item (`r{n}hrtatte`), which is narrower than the CHARLS proxy.

MHAS construction notes (`analysis/scripts/intl/mhas_reshape.py`):
- 27,159 source rows, `rahhidnp` unique -> one row per person; `r{n}VAR` is that person's own
  release-n interview and `s{n}VAR` is a copy of their spouse's data, so only the `r{n}` series
  is used (appending spouses would double-count people who are rows in their own right).
- Releases map to interview years 2001, 2003, 2012-13, 2015, 2018-19, 2021-22 (`r{n}iwy`).
- Letter-coded Stata missings (`.a` not-asked-below-50, `.d` DK, `.m`, `.p` proxy, `.r` refuse,
  `.s` skip, `.u`, `.v`, `.g`, `.n`, `.i`) become NaN, exactly as in `charls_reshape.py`.
- Education 1/2/3, marital 1/3 vs 4/5/7/8, sex 1/2: source codings verified against the file's
  own value labels and already identical to CHARLS.
- `income_pir` = within-MHAS z of log1p(`h{n}atotb`, household total assets incl. second home).
- Rows under age 20 dropped (27 rows), matching the NHANES inclusion rule.

Sensitivity variant: `data/processed/intl/sensitivity/std_MHAS_selfreport.csv` is identical
except that measured BMI is backfilled with self-reported `r{n}bmi` (85.5% non-null vs 7.3%).
It lives in a subdirectory on purpose: the LOCO runners glob `std_*.csv`, so a second MX file
beside the primary one would silently become a fifth "country".
During LOCO these missing cells are median-imputed from the TRAINING countries only.

Honest per-cohort gaps — **United States, RAND HRS 1992-2022 v1** (`intl/hrs_reshape.py`):
- Source: `data/raw/intl/HRS/randhrs/randhrs1992_2022v1.sas7bdat`, 45,234 respondents x 19,880
  columns, one row per person, `HHIDPN` unique. Only the `R{n}VAR` (respondent) series is used; the
  parallel `S{n}VAR` series repeats each person's spouse and appending it would double-count people
  who are rows in their own right — the same rule MHAS applies to `r{n}` vs `s{n}`.
- **The SAS header's labels cannot be used.** `pyreadstat` returns 13,262 label entries for 19,880
  columns, so names and labels are index-shifted (R1IWMID is labelled SMOKEV, R1WTRESP is labelled
  PRCHMEMRY); the PDF codebook's descriptive-statistics block is a broken multi-column layout. Every
  value code was therefore taken from the codebook's "Variable Category Codes" frequency tables and
  then verified against the counts actually observed in the data — the two agreed exactly for every
  variable checked. `results/reports/hrs_metadata_probe.json` is the machine-readable record.
- `R{n}STROKE` = "ever had stroke", clean 0/1 in all 16 waves. Transient ischaemic attack is folded
  into "yes" by RAND's own derivation of `RwSTROKE`, so the US outcome is slightly broader than a
  pure stroke item; disclosed rather than corrected, because the raw TIA field is not the same
  question across waves.
- Hypertension / diabetes / heart_attack use the **"ever" items** (`HIBPE` / `DIABE` / `HEARTE`),
  which are clean 0/1. The "this wave" items (`HIBP` / `DIAB` / `HEART`) additionally carry codes
  3-6 = record-discrepancy flags (7-508 rows per wave) and are not used. `HEARTE` is "ever had heart
  **problems**" — the same broad proxy CHARLS uses; MHAS's narrower myocardial-infarction item
  remains the one known asymmetry across panels.
- `R{n}DRINK` = "ever drinks any alcohol", slightly broader than CHARLS's last-year item.
- Marital: HRS `MSTAT` is **not** the CHARLS/MHAS coding. 1 married, 2 married-spouse-absent and
  3 partnered are partnered; 4 separated, 5 divorced, 6 separated/divorced (wave 3 only), 7 widowed
  and 8 never married are not. Reusing the CHARLS dictionary here would have put "separated" on the
  partnered side of the variable.
- Education: RAEDUC 1 lt-high-school, 2 GED, 3 high-school-graduate, 4 some-college, 5 college+ maps
  to the shared 3-level scale as {1->1, 2->2, 3->2, 4->3, 5->3}. GED joins high-school completion
  because that is how `build_nhanes_std.py` treats NHANES DMDEDUC2 code 3 ("high school graduate OR
  GED"), so the two US sources stay comparable.
- Age: `R{n}AGEY_M` is age in **years** at the mid-month of the interview (the `_M` is mid, not
  months) — verified against the codebook long name and the observed 23-85 range at wave 1.
- `income_pir` = within-HRS z of log1p(`H{n}ATOTB`, "Total of all Assets - Cross-wave", USD), i.e.
  the same asset concept CHARLS (`hh{n}atotb`) and MHAS (`h{n}atotb`) use, not the income concept
  NHANES uses. RAND HRS reports **negative** assets for indebted households (1,019-3,002 rows per
  wave) and the shared log1p rule cannot take them, so they stay missing: income_pir is non-null on
  90.0% of kept US rows.
- `bmi` = `R{n}PMBMI`, the physical-measurement-based BMI, which is non-null only in waves 8-14 and
  16 (0 rows in waves 1-7 and in wave 15) and covers 35-40% of those interviews (7,128 of 18,469 at
  wave 8), so it is non-null on 19.4% of kept US rows. `R{n}BMI` is **self-reported** (built from
  `R{n}HEIGHT`/`R{n}WEIGHT`, both labelled self-reported) and is used only in `--bmi selfreport`,
  which writes `corrected/sensitivity/std_HRS_selfreport.csv` (self-reported BMI is non-null on
  98.0-100% of each wave's interviews, which is exactly why it is not the primary definition).
  Keeping measured BMI as the primary definition is what preserves one BMI concept across the four
  panels. The wave-15 zero is a real gap, not a parse failure: the diagnostic counts it per wave
  (`assets_and_bmi_by_wave`) and a documentation-derived claim about which waves carry the nurse exam
  would have been wrong in the first draft of this file.
- `high_cholesterol` is **ABSENT**, on the same grounds as MHAS: the only cholesterol item in this
  release, `R{n}CHOLST` ("Prev Cholesterol"), sits in the section on preventative tests and
  procedures ("a blood test for cholesterol, a flu shot, monthly self-checks"), which is screening
  utilisation, not a diagnosis. CHARLS and KLoSA have no such item either.
- Calendar time and vital status go to `data/processed/intl/incident/hrs_times.csv` (one pass over
  the 7.2 GB source, so no downstream rerun has to re-read it): `R{n}IWMID` as a day-precision
  interview date, `R{n}IWSTAT` (1 respondent alive, 4 non-response alive, 5 died this wave, 6 died
  previous wave, 7 dropped from sample, 0 inapplicable), `RADDATE` as a day-precision death date
  from the Tracker file (populated for 19,144 of 45,234 respondents), and `R{n}WTRESP`.
  Rows with `IWSTAT` 0 are left out of the extract: they are not in that wave's sample, so they carry
  neither an interview nor a vital status.
- 4 rows dropped for age < 20; 23 impossible BMI values -> NaN; 0 current-smoker contradictions
  (the structural rule was already satisfied in the source).

RAND HRS v1 1992-2022 includes **all eight birth-year cohorts** of the HRS programme — AHEAD (born
before 1924), CODA (1924-30), HRS (1931-41), WB (1942-47), EBB (1948-53), MBB (1954-59), LBB
(1960-65), EGENX (1966-71), plus `RACOHBYR = 0` for the small number born after 1971, mostly
spouses; `RABYEAR` spans 1890-1995. The cohorts entered at different times (HRS 1992, AHEAD 1993,
CODA and WB 1998, EBB 2004, MBB 2010, LBB 2016, EGENX 2022), which is precisely the left-truncation
the person-interval design absorbs: a person enters the risk set at their own first determinable
stroke item, not at the study's start. Interview dates span 1992-03 to 2022-12. "United States" here
is therefore a nationally representative panel of older Americans, not one enrolment cohort.

## Incident arm — reported pool `data/processed/intl/incident/personperiod_pooled.csv`

**This is the manuscript's main analysis.** Unit = person x interval between two consecutive
determinable interviews, built by `intl/incident_personperiod.py` from the same corrected
`std_*.csv` tables plus a per-cohort time/vital-status extract. **430,521 rows from 94,005 adults,
1,062,341 person-years, 6,979 incident strokes**; 104,121 people entered the risk set and 94,005 of
them contributed at least one analysable interval (15,052 had only a single determinable interview).
`country` is added at run time by the modelling scripts (`cohort` -> US / CN / KR / MX); it is not a
column of the file.

Two derived files have the **same columns and the same coding**, differing only in how follow-up is
sliced: `personperiod_strict.csv` (`incident_strict_frame.py`) truncates every interval at `t_ask`, the
last wave at which the stroke item was answerable, and is the risk set Table 7 is fitted on; and
`personperiod_grid1_{uniform,midcell,last}.csv` (`incident_grid_reframe.py --delta 1 --alloc …`) re-cuts
each interval into equal pieces of at most one year, `k` renumbered within person and
`t_start`/`t_end`/`exposure_years`/`t_since_entry_years` on the same entry-relative clock, and is the risk
set Table 8's grid columns are fitted on. The grid files add one column, `row_weight`: a sub-interval
that carries a fraction *q* of its parent's stroke is emitted twice, as an event row of weight *q* and a
non-event row of weight 1−*q* (the zero-weight half is dropped), which is how the `uniform` allocation
represents an interval-censored event without pretending to know which year it happened in. Row counts
and preserved quantities, all asserted by the script: uniform 1,273,994 rows and 1,062,340.9 person-years
(identical to the unsplit file), last 1,251,843 and 1,062,340.9, midcell 1,245,851 and 1,057,247.5 — the
5,093.5 years it drops are the person-time after the midpoint-containing piece, which that allocation
truncates by construction. All three carry the same 94,005 persons, the same 6,979 total event weight and
the same dated terminal statuses. Neither kind of derived file should be used to build a horizon frame:
their interval midpoints differ from the
parent intervals', so `person_clock` would date events up to half a grid step away from where the
reported `cif_mid` frame dates them. Evaluation always uses `personperiod_pooled.csv`.

| cohort | country | persons with >=1 interval | intervals | incident strokes | person-years | median / p95 / max interval (y) | incidence per 1,000 py (unweighted, design-weighted) | intervals ending in death |
|---|---|---|---|---|---|---|---|---|
| HRS | US | 40,367 | 257,794 | 4,350 | 561,376.3 | 1.999 / 3.792 / 26.009 | 7.75, 6.81 | 14,877 |
| CHARLS | CN | 18,910 | 47,387 | 1,160 | 113,135.7 | 2.083 / 3.083 / 7.167 | 10.25, 10.19 | 1,557 |
| MHAS | MX | 25,156 | 70,961 | 933 | 274,945.7 | 3.000 / 9.333 / 20.583 | 3.39, 3.36 | 6,913 |
| KLoSA | KR | 9,572 | 54,379 | 536 | 112,883.2 | 2.000 / 2.167 / 16.250 | 4.75, 4.14 | 0 |

| Column | Type | Meaning | Coding / provenance |
|---|---|---|---|
| pid | str | adult identity **within a cohort** | must be pooled as cohort+pid; bare pid collides across panels |
| cohort | str | HRS / CHARLS / KLoSA / MHAS | — |
| k | int | interval index for this person, 0-based | consecutive determinable interviews only |
| wave_start, wave_end | int | panel wave at each end of the interval | `R{n}` / `r{n}` / `w{n}` series |
| gap_waves | int | waves skipped between start and end | 2.1-4.4% of rows; a gap means a release the harmonised file lacks |
| t_start, t_end | float | calendar time, decimal years | interval start = the start wave's interview date; end = next interview, death, or administrative close. HRS dates are day-precision (SAS dates from `R{n}IWMID` and `RADDATE`); CHARLS/MHAS are year+month; KLoSA year+month+day |
| exposure_years | float | t_end - t_start | **model covariate**; see the table above |
| t_since_entry_years | float | t_start minus this person's first interval start | **model covariate**; the time term of the discrete-time hazard |
| event | int | OUTCOME: 1 if the stroke item turns positive at the interval's end wave | first reported stroke; 0 otherwise |
| end_status | str | how the interval closed | continued / stroke / death_dated / death_status / vital_status_unknown / alive_nr / administrative_end |
| censor_mode | str | risk-set rule applied to this cohort | `death` (HRS, CHARLS, MHAS) or `last_interview` (KLoSA - no vital-status field in the nine main waves) |
| wt_start | float | person-level design weight of the **start** wave | HRS/CHARLS/MHAS `R{n}WTRESP` / `r{n}wtresp`, KLoSA `w0{n}wgt_p`; non-null 57.4% US / 74.5% CN / 66.8% MX / 75.6% KR |
| age, sex, education, marital, income_pir, bmi, ever_smoker, current_smoker, alcohol, hypertension, high_cholesterol, diabetes, heart_attack | float | the ten-concept harmonised profile, measured at the interval's **starting** wave | nothing measured after the event can enter a risk set |

Entry and exclusion rules, each audited into `personperiod_diagnostics.json`:
1. adults >= 20 with a determinable stroke item;
2. a person reporting stroke at their first determinable interview is a **prevalent** case and is
   excluded (2,205 US / 682 CN / 323 KR / 565 MX);
3. intervals are formed only between consecutive determinable interviews of the same person;
4. vital status is read from the interview-status item (`R{n}IWSTAT` / `r{n}iwstat`: 1 respondent
   alive, 4 non-response but alive, 5 died this wave, 6 died previous wave, 7 dropped from the
   sample [RAND HRS only], 9 status unknown), because death DATES are sparse in CHARLS (1.5% of
   wave records) and MHAS (27.0%) and death-coded records carry no fieldwork date at all;
5. undated deaths are censored at the **midpoint** of the wave's nominal fieldwork window, where the
   window is the median dated interview per wave derived from the data (`wave_nominal_dates`), not a
   documented fieldwork year. RAND HRS rarely needs this: 14,724 of its 14,877 death-terminated
   intervals have an exact Tracker death date and only 153 fall back on status alone;
6. `iwstat` 9 or 4 closes the interval at the last interview and labels it accordingly, so attrition
   and death are never pooled into the stroke-free risk set; `iwstat` 7 credits no exposure and is
   not a death;
7. contradictory records (a person-level death date earlier than that person's last dated
   interview: 6 US, 4 CN, 117 MX) are counted and handled by the window rule rather than silently
   dropped.

### The four-year endpoint is an estimand choice, and both are reported

`run_incident_loco.horizon_frame` builds the person-level four-year frame on ONE named rule, with
the IPCW weight that rule needs. A stroke found between two interviews is interval-censored, so it
can be dated to the interval start, midpoint or end; a person who dies inside the window can be
treated as a non-event (that is what "probability of a first stroke within four years" means) or
dropped. These choices are worth more than any model comparison in this paper, so they are columns
rather than assumptions. Full evidence in `incident_competing_risks_cif.csv` and
`incident_competing_risks_estimands.csv`, and in `docs/SELF_AUDIT.md` defect 8.

Aalen-Johansen cumulative incidence of a first stroke within 4 years, competing death kept in, by
the dating rule applied to the stroke interval (US/CN/MX from death-aware censoring, KR has no death
data at all so its AJ and naive curves coincide):

| country | stroke dated to start | **midpoint** | end | 4-y CIF of death | naive 1-KM at midpoint | naive / AJ |
|---|---|---|---|---|---|---|
| US | 0.0330 | **0.0265** | 0.0175 | 0.0624 | 0.0273 | 1.031 |
| CN | 0.0557 | **0.0218** | 0.0144 | 0.0495 | 0.0225 | 1.030 |
| MX | 0.0200 | **0.0082** | 0.0085 | 0.0533 | 0.0083 | 1.016 |
| KR | 0.0245 | **0.0192** | 0.0158 | 0.0000 | 0.0192 | 1.000 |
| pooled | 0.0335 | **0.0202** | 0.0145 | 0.0511 | 0.0207 | 1.025 |

Horizon accounting, H = 4 years, both estimands, from `incident_horizon_counts.json`:

| rule | persons | stroke within H | died within H | counted as non-event | lost before H | stroke-free through H | evaluable | observed prevalence (unweighted / IPCW) |
|---|---|---|---|---|---|---|---|---|
| `cif_mid` (primary) | 94,005 | 1,845 | 4,668 | 4,668 | 8,264 | 79,228 | 85,741 | 0.0215 / 0.0202 |
| `exclusive_start` (pre-audit, sensitivity) | 94,005 | 3,048 | 8,748 | 0 (dropped) | 16,233 | 74,724 | 77,772 | 0.0392 / 0.0392 |

`cif_mid` therefore keeps competing deaths in the denominator as non-events and reweights for loss
to follow-up (median IPCW weight 1.102, max 1.102, because only a person lost before their endpoint
is determined can be reweighted); `exclusive_start` drops both groups and dates the surviving events
at the interval start, which is why its apparent prevalence is nearly double.

Korea's realised horizon is 3.0 years, not 4: composition steps over the training panel's own median
interval length, and Korea's is 2.0 years.

## Derived outputs behind the fifth-round tables (Table 9b, Table 13, Figure 9b)

These live under `data/processed/intl/incident/` and are regenerated by the scripts named in
`README_reproducibility.md`; `analysis/output/make_p0_rows.py` prints both tables straight from them and
asserts the manuscript matches, and `analysis/output/audit_consistency_round.py` re-checks every cell.

`incident_cr_joint.csv` (4,810 rows) is the joint-multinomial arm. One row per (horizon_rule, held
country, composition_arm ∈ {joint_multinomial, shipped_product}, strategy ∈ {frozen_all, frozen_sub,
offset_logit}, frac, rep, step_years). Columns are the standard metric bundle (`pred_over_obs` with its
person-clustered `ci_po_lo`/`ci_po_hi`, `auroc`, `brier`, `scaled_brier`, net benefit at 2/5/10/15%,
`mean_repair_shift`). Table 9b's "Joint multinomial" column is the `joint_multinomial` / `frozen_all` /
`frac=0.0` / `cif_mid` rows; the "V4 shipped product" point and CI come from the published primary table
`results/tables/incident_cr_primary_2026-11-03.csv` (variant `V4_ph_competing`, same slice), and the
"V5 exact on marginal fits" column is `incident_cr_exact_diagnostics.json → diagnostics[cif_mid|<panel>].V5_pred_over_obs`.
The joint model's integrity gates are in `incident_cr_joint_diagnostics.json`: the analytic-gradient
self-test relative error (1.5e-09, measured at a deliberately non-degenerate probe — see SELF_AUDIT defect
27) and the probability-conservation deviation of the interval mass (1.1e-16), plus a flat step ladder
(`ladder_ratio_8_over_1 = 1.0`). `incident_cr_exact_ladder.csv` carries the V4 shipped ladder that drifts
to 0.9424 at eight steps (the exclusivity error), which the V5 and joint arms flatten.

`incident_age_recalibration.csv` (500 rows) and `_summary.csv` (100 rows) are Table 13. The summary is
keyed by (held, frac, strategy ∈ {A_frozen, B_overall, C_band, D_age_linear, E_band_shrunk}) and reports
`pooled_pred_over_obs`, the sign-error measures `mean_abs_band_log_po` / `max_abs_band_log_po` (the worst
band is `exp(max_abs_band_log_po)`, the "Worst age band (×)" column), `mean_nb_at_05` / `sd_nb_at_05`, and
`n_bands_evaluated`; bands are evaluated only on eval rows with n ≥ 20 and ≥ 5 events. Adaptation and
evaluation sets are disjoint by `person_id`, asserted per replicate. The analysis unit is the person (one
horizon frame row per person); the frozen prediction arm is the logistic discrete-time hazard, `cif_mid`,
common features, comparable to Table 12.

`incident_calibration_smooth.csv` (480 rows) is Figure 9b: a spline (`cr(lp, df=4)`) observed-versus-
predicted risk curve per panel and arm (frozen, repaired) with a person-clustered bootstrap band, so the
residual *shape* (not only the decile table) is visible; Mexico's high-risk tail still misses after the
intercept repair.


## Joint-PRIMARY outputs behind the sixth-round tables and figures

The sixth round made the joint multinomial competing-risks model the single primary absolute-risk arm, so
`intl/incident_cr_joint_primary.py` regenerates every joint sub-analysis from the shared per-person joint
CIF on the `cif_mid` horizon frame. All five outputs are suffixed `_joint` and cross-reconcile to the same
Mexico panel P/O 2.975 that Table 9b and the abstract report; `analysis/output/make_joint_primary_rows.py`
prints Table 12, Table 13 and the three-level deployability Table 14 from them, and
`analysis/output/audit_consistency_round6.py` re-derives every joint-primary cell from these files and fails
the build on any desync.

  incident_cr_joint_subgroups.csv    held x age band (20-59 / 60-69 / 70-79 / 80+ / ALL): frozen and
    single-national-intercept-repaired pred_over_obs, AUROC with person-clustered CI, IPCW prevalence and
    mean prediction, calibration slope/intercept, net benefit at 5%, and the per-band repair offset - the
    joint counterpart of the V4 incident_subgroups arm, and the source of Table 12.
  incident_cr_joint_deciles.csv      held x predicted decile: frozen/repaired predicted risk against IPCW
    observed risk with a person-clustered bootstrap interval - the joint calibration-decile object.
  incident_cr_joint_calibration_smooth.csv (+ deliverables/figures/incident/..._joint.{png,pdf})  spline
    cr(lp, df=4) observed-vs-predicted curve per panel, frozen and repaired - the joint Figure 9b.
  incident_cr_joint_age_recalibration.csv / _summary.csv  the five update strategies (A frozen / B
    population intercept / C naive per-band / D intercept+linear-age / E shrunk per-band) under the joint
    arm, with pooled P/O, the worst-band sign-error exp(max|log P/O|), and net-benefit mean/SD - Table 13.
  incident_cr_joint_dca.csv          held x threshold (0.01-0.25): net benefit of the frozen joint model,
    the repaired joint model, treat-all and treat-none - the joint decision-curve object and the source of
    the clinical-utility column in Table 14.

The V4 files (incident_cr_primary_*.csv, incident_subgroups.csv, incident_calibration_curves.csv,
incident_age_recalibration.csv, incident_calibration_smooth.csv) remain on disk unchanged as the labelled
separately-fitted marginal-hazard sensitivity arm; the joint and marginal arms agree to within the ~3.4%
composition shift documented in the composition audit.

## Round-7 outputs (submission-hardening)

The seventh round added four on-disk artifacts and one column, all reading the same horizon frame and joint
CIF as the primary tables so nothing drifts; `analysis/output/make_round7_rows.py` prints the two data-derived
tables and `analysis/output/audit_consistency_round7.py` re-derives every round-7 cell and fails on desync.

  incident_sample_flow_cif_mid.csv   now carries a `no_determinable_stroke` column (2 for MHAS, 0 elsewhere),
    so every panel's flow reconciles as adults_ever_interviewed = no_determinable_stroke +
    prevalent_at_entry_excluded + at_risk_persons; pooled 107,898 = 2 + 3,775 + 104,121. Source of the
    reconciled Table 1 row and Figure 10 exclusion labels.
  incident_update_policy_joint_cif_mid.csv (+ _decisions_ and _summary_)   the always-frozen / always-recalibrate
    / selective / selective-with-magnitude-gate policies re-run on the joint model's per-person horizon CIF over
    200 person-disjoint splits x {2,5,10,25,50}% local sample; the summary is the source of Table 10 (MX fires
    70% at 2%, paired +0.00261; 100% at 5%, paired +0.00370). The logistic `incident_update_policy_*.csv` files
    remain unchanged as a labelled sensitivity arm.
  incident_cr_interval_eval_cif_mid.csv   per held country: the transported joint model mean 4-year prediction,
    the observed ascertained incidence under cif_mid/start/end, and the midpoint-free interval-censored observed
    CIF (intercept-only joint competing-risks MLE + 400-draw person-clustered bootstrap) with its P/O - the
    source of Table 15 (MX P/O 2.98 midpoint -> 2.10 interval-censored, bracket 1.22/2.94).
  incident_cr_unreported_stroke_sim.csv   a synthetic sweep of the unreported-pre-fatal-stroke fraction pi over
    {0,0.05,0.10,0.20,0.30,0.50}, per held country, giving the clinical P/O under uniform and differential
    ascertainment - the source of Supplementary Table S6 (ground truth is synthetic; the reported headline is not
    adjusted). The outcome-observation mapping (Table 16) and weight disclosure (Table 17) are documentation of
    `expand()` and the weight pipeline, not new computed files.

## Round-8 outputs (post-review reconciliation and robustness)

The eighth round added five computed artifacts, all reading the same horizon frame + joint CIF so nothing drifts;
`analysis/output/audit_consistency_round8.py` re-derives every round-8 cell and fails on desync or any retired phrase.

  incident_cr_interval_flexhaz_cif_mid.csv   per held country the observed 4-year risk refitted with time-varying
    cause-specific hazards - piecewise-constant (3 bands) and log-linear-in-time-since-entry - integrated to the
    exclusive competing-risks CIF on a 0.05-year grid, with a 300-draw person-clustered bootstrap of each, plus the
    frozen and 5%-repaired P/O. Source of Table 18. Establishes that the pooled-hazard MLE inflates China ~2x and is
    robust to hazard shape (so it is not a constant-hazard artefact). Reuses the tested JointCrFit optimizer.
  incident_cr_alloc_only_ic_comparator_cif_mid.csv   the estimand-MATCHED midpoint-free check: per country the
    transported mean prediction and observed 4-year risk when ONLY the within-interval allocation is relaxed to
    clip((H-t_start)/(t_end-t_start)) on the identical cif_mid evaluable frame and IPCW weights (obs_mid, obs_ic,
    ratio, P/O_mid, P/O_ic). Source of Table 19 left block. Shows China invariant (ratio 1.00), Mexico alone moves
    (2.98 -> 2.18), so the round-7 'China 0.43' is an estimand re-specification, not an allocation effect.
  incident_update_policy_joint_ic_cif_mid.csv (+ _summary_)   the four prespecified policies re-run on the
    interval-censored outcome (midpoint and IC arms) on identical person-disjoint splits x 5 fractions. Source of
    Table 19 right block: at 5% local data the rule fires Mexico 98%/IC (paired +0.00290) and China only 24% (paired
    negative) - the update recommendation is unchanged by interval censoring.
  incident_cr_clinical_baseline_cif_mid.csv   the full transported joint model vs a five-variable clinical joint
    model (age, sex, hypertension, diabetes, current_smoker) on the same estimand / external validation / threshold;
    transferred AUROC, panel P/O, NB@5%, AUROC diff, P/O ratio. Source of Table 20 (120 adaptation splits).
  incident_cr_unreported_stroke_2d.csv   the unreported-pre-fatal-stroke sweep generalised to an independent
    pi_source x pi_target grid (hypothetical sensitivity parameters), per held country. Source of the rewritten
    Supplementary Table S6 (uniform-diagonal Mexico >=1.48; only an extreme differential crosses 1.0; Korea
    invariant to pi_target because KLoSA ascertains no deaths).

## Round-9 output (allocation-estimator cross-check)

  incident_cr_alloc_variants_cif_mid.csv   per held country the observed four-year risk and P/O under three
    estimand-matched allocation rules on the identical cif_mid frame + IPCW weights - midpoint, uniform-within-interval
    (`clip((H-t_start)/(t_end-t_start))`), and a joint-model-based conditional (truncated-exponential in the fitted
    total hazard lam_s+lam_d) - with the model/uniform ratio. Source of Table 19 (both allocation arms) and of the
    round-9 reviewer cross-check that 'only Mexico moves materially' is not a uniform-allocation artefact
    (China 0.80 under all three; Mexico 2.98 -> 2.18 uniform -> 2.14 model-based). `intl/incident_cr_alloc_variants.py`;
    reverse-checked by `analysis/output/audit_consistency_round9.py`. The relocated Notes S-C (cross-sectional) and
    S-D (exact-Shapley) now live in `deliverables/Supplementary_technical.md`, not the main article.
