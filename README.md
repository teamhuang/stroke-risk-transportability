# stroke-risk-transportability — frozen reproduction package

Companion code, published aggregate results, and rendered figures for the manuscript
**"Transportability of first-reported-stroke risk across four nationally representative
ageing cohorts"** (target: *npj Digital Medicine*).

This is a **frozen** snapshot of the analysis that produced every number in the manuscript.
It contains the full modelling code, the de-identified aggregate result tables and working
model outputs, all figures, the manuscript and supplementary text, the self-audit, and the
deterministic consistency gates that tie the reported numbers back to the tables. It
contains **no person-level or restricted data** (see *What is intentionally NOT included*).

> Repository: `https://github.com/teamhuang/stroke-risk-transportability`
> Cite the archived version (DOI / release tag) created for this release.

---

## Study at a glance

- **Analysis unit / estimand:** the survey-ascertainable probability of a *first reported*
  stroke over a 4-year horizon, per respondent, in each of four panels —
  **US** (RAND HRS), **China** (CHARLS), **Korea** (KLoSA), **Mexico** (MHAS).
- **Primary model:** a joint multinomial competing-risks model (exclusive outcomes:
  stroke-first / death-first / neither) fitted as cause-specific interval-censored hazards
  and composed into an Aalen–Johansen CIF. The earlier logistic / "V4" arm is retained and
  explicitly labelled as a sensitivity analysis, never as the headline.
- **Frozen transport metric (predicted/observed, P/O):** China 0.802 · Korea 1.147 ·
  Mexico 2.975 · US 0.897.
- **Central claim:** calibration transport is country-specific; a small (5%) local
  recalibration removes most of the Mexican excess risk, but the net-clinical-benefit of
  deploying any of these models prospectively is **not** established by this study.

## Environment (frozen)

Reproducing bit-identical numbers requires the same toolchain, a single compute thread,
and the fixed seed. All three are pinned in this package:

- Python **3.10.5**
- `numpy 1.26.4 · pandas 2.2.2 · scikit-learn 1.7.2 · scipy 1.14.1 · statsmodels 0.14.6 ·
  xgboost 1.7.6 · lightgbm 4.6.0 · shap 0.49.1 · pyreadstat 1.3.6 · python-calamine 0.8.3 ·
  matplotlib 3.8.4 · pillow 12.1.0 · joblib 1.5.3` — see `requirements.txt`.
- Fixed seed `SEED = 20261101` (`analysis/scripts/config.py`).
- BLAS / OpenMP thread counts are forced to `1` **before** `numpy` is imported (thread count
  changes floating-point summation order, which breaks bit-level reproduction).

Install and self-check the modelling pipeline on synthetic data (needs **no** external data):

```bash
pip install -r requirements.txt
cd analysis/scripts
python synthcheck.py        # ALL PASS gate: validates the estimator stack on known ground truth
```

## Layout

```
analysis/scripts/            modelling code
  config.py                  frozen design + decision log + SEED (the admission record)
  modeling.py                leakage-aware pipelines, metrics, adaptation
  synthcheck.py              synthetic ground-truth validation (no external data needed)
  intl/                      the international incident arm (68 scripts) — see run order in
                             deliverables/README_reproducibility.md
analysis/output/             working numbers + the deterministic audit gates:
  audit_consistency_round6..12.py   cross-file / cross-table consistency checks
data/processed/intl/incident/       aggregate model outputs the audit gates read
                             (88 de-identified incident_*.csv/.json files; the person-level
                              personperiod_* and hrs_times files are NOT included)
results/tables/              dated, published AGGREGATE copies of every reported number
results/reports/             data-defect records, feasibility / build reports
deliverables/figures/        rendered figures (PNG + editable-text PDF, 300 dpi)
deliverables/                manuscript.md, Supplementary_technical.md, cover_letter.md,
                             TRIPODAI_checklist.md, SUBMISSION_BLOCKERS.md, data_dictionary.md,
                             INTL_DATA_RUNBOOK.md, README_reproducibility.md
                             (+ the build documents manuscript_round11.docx and
                              Supplementary_Information_round11.docx, figures embedded)
docs/SELF_AUDIT.md           7-dimension pre-delivery audit, defect log (30 defects) and verdict
data/processed/intl/_synthetic_demo/   demo output figures only (no input data)
requirements.txt  .gitignore
```

For the complete run order, table-printer scripts, and data-provenance detail see
**`deliverables/README_reproducibility.md`** (the authoritative guide) and
**`deliverables/INTL_DATA_RUNBOOK.md`**.

## How to verify the numbers (runs on this package alone)

The audit gates are deterministic and self-contained: they read the published aggregate and
working tables on disk and assert that every headline figure quoted in the manuscript text
matches. They require **no** restricted data. From the repository root:

```bash
cd analysis/output
for r in 6 7 8 9 10 11 12; do python audit_consistency_round${r}.py; done
```

All seven PASS on this frozen package. Each prints its assertion count and a summary line.
A quoted number that no printer script can reproduce is treated as a defect, not rounded
into agreement.

## Reproducing from source data (requires cohort access)

Full end-to-end re-derivation from raw panels is **not** possible from this package alone
because the parent cohorts are access-restricted and not redistributable. To reproduce from
scratch you must, in this order:

1. Obtain harmonised **CHARLS**, **MHAS**, and **RAND HRS** release-D files from the
   Gateway to Global Aging Data, and the **KLoSA** original wave workbooks (KLISSA waves
   1–9) from the KLoSA portal. Review each portal's current terms of use before loading.
2. Place them under `data/raw/intl/` and run the reshape scripts
   (`hrs_reshape.py`, `charls_reshape.py`, `klosa_reshape_v2.py`, `mhas_reshape.py`,
   then `clean_intl_std.py`) to regenerate `data/processed/intl/corrected/`.
3. Expand to person-interval form (`incident_personperiod.py`) and run
   `bash analysis/run_incident_pipeline.sh`, then the arms listed in
   `deliverables/README_reproducibility.md`.

This package ships the aggregate *outputs* of those steps so the reported numbers can be
checked without the restricted inputs, and the *code* so the whole chain can be rebuilt by
an authorised user.

## What is intentionally NOT included (data policy)

- **No person-level data.** `data/raw/` (~8 GB) and every person-interval file whose header
  carries a respondent id (`personperiod_*.csv`, `hrs_times.csv`,
  `*personperiod_pooled*`, the person-level `incident_adaptation_leakage_audit*.csv`) are
  excluded; they are individually identifiable and governed by cohort data-use agreements
  that forbid redistribution. The assembler verifies this by scanning each CSV header, and
  `.gitignore` re-excludes them if a local re-run regenerates them.
- **The `incident_*` tables that ARE shipped are aggregate only** (per country × strategy ×
  replication × step, or per country / per horizon). The two files whose name contains
  "personperiod" but which are kept — `incident_personperiod.py` (source code) and
  `incident_personperiod_diagnostics_*.json` (four per-cohort coverage/count records) —
  carry no person identifiers.
- **No NHANES raw files** (regenerable from the public CDC SAS-XPT URLs in the guide).

## Honest status of author-only items

These are **not** resolved in code and are left as `[AUTHOR-SPECIFIC]` placeholders (34 in
`manuscript.md`) — they must be completed by the human authors before submission and cannot
be fabricated here:

- ORCID iDs; final pass over institutional affiliations.
- Ethics / IRB approvals and informed-consent statements for each cohort.
- Data-use / licence attestations — **MHAS** and **KLoSA** in particular: MHAS's terms must
  be confirmed to permit AI-assisted analysis, and KLoSA requires a creation code. Any
  AI-assisted pipeline must **exclude MHAS** unless the holder's written authorisation is
  verified (see `docs/SELF_AUDIT.md` O7/O8/O22).
- CRediT author contributions, funding statements, competing-interest declarations.
- The archived **DOI** for this repository is minted when the GitHub Release / tag is
  connected to Zenodo and published by the author.

## Licence & citation

Please cite the manuscript and this archived version. Cohort data remain subject to their
own access terms; this repository redistributes **no** individual-level records.
