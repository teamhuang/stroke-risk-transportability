# Data-integrity findings in the international arm (2026-11-02)

Triggered by adding the Mexican cohort (MHAS): building `std_MHAS.csv` forced a per-cohort
descriptive table (`results/tables/intl_arm_characteristics.csv`), and Korea's column did not
survive contact with reality. Every defect below is in the **already-reported** three-country arm
(`manuscript.md` Table 3 / Figure 10), not in the new cohort. Impact numbers are appended after
the corrected re-run.

## Severity, measured by diffing old vs corrected Korea (`65,494` rows, join on pid x wave)

| feature | rows changed | of which the old value was a fabrication (coded where nothing was observed) |
|---|---|---|
| education | 49,479 (75.5%) | 3,202 |
| alcohol | 42,749 (65.3%) | 0 (wrong item, but always an observed item) |
| current_smoker | 27,062 (41.3%) | 0 |
| bmi | 64,176 (98.0%) | 0 (previously NaN, now observed) |
| marital | 10,212 (15.6%) | 10,212 - every wave-1 row |
| hypertension / diabetes / heart_attack | 0 | 0 |

- **13,405 Korea rows (20.5%) carried at least one feature that was pure fabrication**, i.e. a
  category the respondent was never asked for.
- Row count and the **outcome are unchanged**: 65,494 rows, 859 strokes, identical `stroke`
  vector. So this is a feature-side correction, not a redefinition of the cohort.

## Defect 1 — `Series.map(callable)` turned missing values into real categories (KLoSA)

Root cause, demonstrated rather than asserted:

```
pd.Series([1,2,np.nan,9]).where(between(1,3)).map(lambda v: 1 if v<=1 else 3)
  -> [1, 3, 3, 3]      # NaN reaches the lambda; NaN <= 1 is False -> category 3
... .map({1:1, 2:2, 3:3})
  -> [1.0, 2.0, nan, nan]   # a dict cannot do this
```

`klosa_reshape.py` used a callable for `education`, `marital` and `alcohol`; `charls_reshape.py`,
`build_nhanes_std.py` and the new `mhas_reshape.py` all use dicts, which is why the bug is
Korea-only.

| feature | what the paper says | what the data says |
|---|---|---|
| education | Korea 85.5% tertiary | `w{v}A003` is populated **only in wave 1** (w3-w7 non-null = 0; w8/w9 column absent), so waves 3-9 were 100% fabricated "tertiary". Wave-1 truth: low 62.4% / upper-secondary 26.4% / tertiary 11.2% |
| marital | — | wave 1 has no `marital` column, and all 10,211 wave-1 rows became "not partnered" |
| alcohol | Korea 99.9% drinking, incl. 100.0% of women | see Defect 2 |

## Defect 2 — KLoSA's alcohol feature was the wrong questionnaire item

`klosa_reshape.py` mapped `w{v}C119` to alcohol. In the official Gateway creation code that
variable is defined as **"R # cigarettes/day"**:

```
7043: replace r`wv'smokef = w01C119 if inrange(w01C119,1,200)
7044: label var r`wv'smokef "r`wv'smokef:w`wv' R # cigarettes/day"
```

The drinking item is `w{v}C122` ("drinks now", 1=yes/5=no), present in all nine waves; combined
with `C111a` for wave 1 exactly as the Gateway does at line 6832. Observed C122 = 37.3% yes in
wave 1, versus the 99.9% the miscoded feature produced.

## Defect 3 — KLoSA smoking was logically impossible

`current_smoker` (23.4%) exceeded `ever_smoker` (15.1%), with 823 rows coded "currently smokes"
but "never smoked". `C117` is asked only of ever-smokers in waves 1-4 and of everyone from wave
5; the Gateway closes this with the structural rule `smoken = 0 if C116 == 5` (line 7024), which
v1 omitted.

## Defect 4 — "KLoSA has no clean BMI source" was wrong, twice over

The manuscript Methods and `INTL_DATA_RUNBOOK.md` state that KLoSA lacks a clean measured BMI
(and income), so those cells are imputed from the training countries. But `w{v}C105` (weight, kg)
and `w{v}C107` (height, cm) are present and **fully non-null in all nine waves**, and the Gateway
itself computes Korean BMI from exactly those two columns:

```
6739: replace r`wv'bmi = w01C105/((w01C107/100)^2) if inrange(w01C105,20,140) & inrange(w01C107,100,200)
```

Korea now contributes an observed BMI on 98.0% of rows (mean 23.26, sd 2.74 - plausible for a
45+ Korean sample) instead of an imputed constant.

**Still absent, now for a stated reason:** KLoSA `income_pir`. The Gateway's `r{wv}itot` is the sum
of six components (`itearn + icap + ipena + igxfr + itothr + ipubpen`), each rebuilt from
bracketed income items with midpoint imputation and `_I` flags via `H_KLoSA_imputflag`. That is a
reconstruction task, not a column lookup, so Korea's economic axis remains NaN and is
median-imputed from the training countries - disclosed rather than guessed. `high_cholesterol`
stays absent for all three panels (only NHANES observes it).

## Defect 5 — impossible BMI in CHARLS

`std_CHARLS.csv` contained 59 BMI values outside 12-70 kg/m^2, including 12 above 500 and a
maximum of **52,734.69 kg/m^2**. Mean/sd for Chinese BMI was 25.57 (266.11). Because
`modeling.get_pipeline` fits a `StandardScaler` on the training rows for the linear models, a
handful of impossible numbers re-scales the BMI axis for *every* cohort and *every* held-out
country - this was contaminating the US and China results too, not just Korea.

`clean_intl_std.py` now applies one rule to all four cohorts and counts what it removed:
NHANES 4 values (max 86.2), CHARLS 59 (max 52,734.69), MHAS 3 (max 90.8). Post-clean CHARLS BMI
= 23.72 (3.91). Also enforced, cohort-wide: adults only (age >= 20, dropping 394 CHARLS rows) and
`current_smoker = 0 where ever_smoker = 0` (the NHANES-arm structural rule already documented in
`data_dictionary.md`; 15 CHARLS rows).

## What is NOT a defect

- The KLoSA **outcome** mapping was correct: 859 strokes, 1.31% prevalence, unchanged between v1
  and v2. The defects are in Korea's *features*, i.e. in what the model gets to see.
- The CHARLS mapping itself (0/1 with letter-coded specials, `raeducl` 3-level, `mstat` 2-level,
  wealth `h{n}atotb`) verified clean; only its value ranges needed the shared filter.
- MHAS verified against the file's own value labels and matched CHARLS's coding scheme exactly.

## Files

| artefact | role |
|---|---|
| `analysis/scripts/intl/klosa_reshape_v2.py` | rebuilt Korea (docstring carries the line-number evidence) |
| `analysis/scripts/intl/clean_intl_std.py` | shared plausibility rules for the other three |
| `data/processed/intl/corrected/std_*.csv` | corrected four-cohort pool |
| `analysis/scripts/intl/mhas_reshape.py` | new Mexico table |
| `results/reports/mhas_metadata_dump.json` | MHAS variable/label evidence |
| `results/tables/loco_3country_NHANES_CHARLS_KLoSA_2026-11-02.csv` | the old reported numbers, preserved |

## Consequence for the manuscript

Two sentences in `manuscript.md` Methods are now known to be false and must be replaced: the KLoSA
"no clean measured BMI" claim and the "harmonised files do not carry design weights" claim
(CHARLS ships `r{n}wtresp`/`wtrespa`/`wtrespb`, MHAS `r{n}wtresp`, KLoSA `w0{5..9}wgt_p/_a/_ap/_ac`).
And Korea's transportability decay - the cohort that anchors the paper's "complexity costs
transportability" claim - has to be re-estimated on features that are actually observed, because
"Korea decays more" and "Korea's three most informative features were fabricated constants" were
previously indistinguishable.
