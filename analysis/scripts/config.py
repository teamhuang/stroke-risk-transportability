"""Frozen design ("admission record") — written BEFORE any modelling is run.

Claim + metric + direction + expected value +/- tolerance are fixed here.
If a result does not meet the pre-registered expectation it is reported as a
finding; hyper/filters/endpoints must NOT be tuned afterwards to close the gap.
Any change spawns a NEW, separately-reported experiment.
"""

# ---------------------------------------------------------------------------
# STUDY
# ---------------------------------------------------------------------------
TITLE = (
    "Clinically actionable risk stratification for prevalent stroke from a "
    "compact, internationally harmonisable socio-behavioural profile: "
    "development in NHANES 2015-2018 and external / subgroup transportability "
    "validation with decision-curve net benefit"
)

# Primary claim (direction + expected magnitude + tolerance) are pre-specified.
PRIMARY_CLAIM = {
    "statement": (
        "A 14-variable socio-demographic + behavioural + cardiometabolic profile "
        "carries real, repeatable discriminative signal for prevalent (self-reported) "
        "stroke in US adults >=20 y, but the incremental gain of complex ensembles "
        "over a penalised logistic model is small (<=0.02 AUROC) while calibration "
        "and net benefit are the deployment-relevant axes."
    ),
    "metric": "AUROC (mean over folds) + Brier + calibration slope + net benefit (DCA)",
    "expected_direction": "AUROC > 0.65 for logistic baseline on internal CV",
    "expected_range_and_tolerance": "logistic internal CV AUROC 0.72-0.82; ensemble gain over logistic 0.000-0.020",
    "transportability_expectation": (
        "external (2021-2023) and leave-one-race-group-out validation show AUROC "
        "decay and, crucially, calibration-slope drift; if slope moves far from 1 "
        "or net benefit collapses, 'high AUC != transportable' is the finding."
    ),
}

# ---------------------------------------------------------------------------
# DATA (fully open NHANES, anonymously downloadable, already fetched)
# ---------------------------------------------------------------------------
# cycle folder -> survey-suffix on the CDC "Public" endpoint (verified empirically)
CYCLES = {"2015": "_I", "2017": "_J", "2021": "_L"}
CYCLE_LABELS = {"_I": "NHANES 2015-2016", "_J": "NHANES 2017-2018", "_L": "NHANES 2021-2023"}

DERIVATION = ["_I", "_J"]          # pooled 2015-2018 = development
EXTERNAL   = ["_L"]                # 2021-2023 = temporally external validation
MIN_AGE    = 20

# ---------------------------------------------------------------------------
# OUTCOME
# ---------------------------------------------------------------------------
OUTCOME = {"name": "stroke", "var": "MCQ160F", "yes": 1, "no": 2, "positive_label": 1}

# ---------------------------------------------------------------------------
# 14 HARMONISED FEATURES  (verified present & semantically identical in all 3 cycles)
# per-cycle code aliases are handled here; physical activity EXCLUDED (2021 instrument
# incompatible) -- see DECISION_LOG.
# ---------------------------------------------------------------------------
FEATURE_CODES = {
    # canonical name : {suffix: (source_file, variable, recode_key)}
    "age":            {"*_": ("DEMO", "RIDAGEYR",  "cont")},
    "sex":            {"*_": ("DEMO", "RIAGENDR",  "binary")},
    "race_ethnicity": {"*_": ("DEMO", "RIDRETH1",  "cat5")},
    "education":      {"*_": ("DEMO", "DMDEDUC2",  "cat5")},
    "marital":        {"_I": ("DEMO", "DMDMARTL",  "cat"),
                       "_J": ("DEMO", "DMDMARTL",  "cat"),
                       "_L": ("DEMO", "DMDMARTZ",  "cat")},
    "income_pir":     {"*_": ("DEMO", "INDFMPIR",  "cont")},
    "bmi":            {"*_": ("BMX",  "BMXBMI",    "cont")},
    "ever_smoker":    {"*_": ("SMQ",  "SMQ020",    "binary")},
    "current_smoker": {"*_": ("SMQ",  "SMQ040",    "binary_01_2to3")},
    "alcohol":        {"_I": ("ALQ",  "ALQ101",    "binary"),
                       "_J": ("ALQ",  "ALQ111",    "binary"),
                       "_L": ("ALQ",  "ALQ111",    "binary")},
    "hypertension":   {"*_": ("BPQ",  "BPQ020",    "binary")},
    "high_cholesterol":{"*_": ("BPQ", "BPQ080",    "binary")},
    "diabetes":       {"*_": ("DIQ",  "DIQ010",    "binary")},
    "heart_attack":   {"*_": ("MCQ",  "MCQ160E",   "binary")},
}
FEATURES = list(FEATURE_CODES.keys())
assert len(FEATURES) == 14

# Secondary association (NOT a model feature): PHQ-9 depressive symptoms.
PHQ_ITEMS = ["DPQ010","DPQ020","DPQ030","DPQ040","DPQ050","DPQ060","DPQ070","DPQ080","DPQ090"]
PHQ_CUTOFF = 10   # >=10 => clinically significant depressive symptoms

# Survey design (design-based prevalence / CI only).
WEIGHT_VAR = "WTMEC2YR"; PSU_VAR = "SDMVPSU"; STRATA_VAR = "SDMVSTRA"
POOL_DIVISOR = len(CYCLES)  # combine 3 2-year-equivalent cycles -> weight/n_cycles

# ---------------------------------------------------------------------------
# MODELS (6, mirroring the inspiring multi-cohort template's model zoo)
# ---------------------------------------------------------------------------
MODELS = ["logistic", "elasticnet", "random_forest", "gradient_boosting", "xgboost", "lightgbm"]
PRIMARY_METRIC = "brier"   # npj-DM reliability-first framing
SECONDARY_METRICS = ["auroc", "auprc", "calibration_intercept", "calibration_slope", "net_benefit"]

SEED = 20261101
RANDOM_STATES = 4  # repeated data splits (patient-level), reported with bootstrap CI

# ---------------------------------------------------------------------------
# VALIDATION DESIGN
# ---------------------------------------------------------------------------
# 1. internal repeated stratified CV (5-fold x 5 repeats) within derivation pool
# 2. TEMPORAL external transportability: fit derivation(2015-2018) -> test 2021-2023
# 3. SUBGROUP transportability: leave-one-race/ethnicity-group-out (LOSO)
# 4. local adaptation (retrain-on-tiny-slice / intercept-rescale / intercept+slope)
#    vs frozen, as data-efficiency curve -> "how many local cases to reach calibration"
# 5. calibration (Brier, Hosmer-Lemeshesh-style slope/intercept), DCA net benefit,
#    permutation importance, prediction-score vs PHQ>=10 association.

# ---------------------------------------------------------------------------
# DECISION LOG  (every analyst-fork recorded: choice / alternative / reason)
# ---------------------------------------------------------------------------
DECISION_LOG = [
    {"fork": "primary outcome",
     "choice": "prevalent self-reported stroke (MCQ160F)",
     "alternative": "measured cognitive impairment (2011-2014 battery)",
     "reason": "cognition battery and stroke question never co-occur in a cycle; "
               "stroke is neurosurgeon-relevant and present 2015/2017/2021.",
     "outcome_of_alt": "n/a - not run (outcome would need a different data family)"},
    {"fork": "physical activity feature",
     "choice": "EXCLUDE physical activity",
     "alternative": "harmonise PAQ605/620/650/665 across cycles",
     "reason": "2021-2023 replaced the self-report PA instrument with incompatible "
               "codes (PAD680/800/820); honest harmonisation impossible -> excluded, "
               "not fabricated.",
     "outcome_of_alt": "would create a phantom-comparable variable; rejected"},
    {"fork": "LOCO international",
     "choice": "temporal (2015-18->2021-23) + race/ethnicity LOSO with real data",
     "alternative": "country-level leave-one-cohort-out on CHARLS/ELSA/HRS/SHARE",
     "reason": "the 5 international cohorts are registration-gated and not anonymously "
               "downloadable here; the multi-cohort LOCO module ships ready-to-run for "
               "when the user obtains them. Real numbers use the one open cohort we can "
               "actually pull.",
     "outcome_of_alt": "pending user registration (framework pre-built, tested on synthetic)"},
    {"fork": "imputation",
     "choice": "median imputation fitted on TRAINING folds only + missing-indicator off",
     "alternative": "mean / whole-sample imputation",
     "reason": "avoid test-set leakage; keep identical config in every branch.",
     "outcome_of_alt": "n/a"},
    {"fork": "structural-missing (current_smoker, alcohol)",
     "choice": "recode never-smoker->current_smoker=0; no-regular-drinking->alcohol=0",
     "alternative": "leave as missing (58% / 21% 'missing')",
     "reason": "the apparent missingness is skip-logic structure, not item non-response; "
               "recoding restores the correct at-risk denominator for these behavioural flags.",
     "outcome_of_alt": "raw missing fractions reported in Table (S-missingness)"},
]
