"""Shared mapping for the cross-cohort HARMONISED gate files (CHARLS/ELSA/HRS/SHARE).

These four studies are harmonised by the same 'gateway to global aging' network and
share a common h* variable naming convention, so ONE mapping serves all four.

IMPORTANT: the h* names below are a TEMPLATE. Before trusting any cohort, run
    python intl/discover_intl.py <that cohort's .dta>
and confirm each variable actually exists with the right value coding; edit this file
if a cohort deviates. Do NOT ship results whose variable mapping was not confirmed
against the real file (integrity rule: check, don't assume).

Country codes: CHARLS=CN, ELSA=EN(England), HRS=US, SHARE=EU (or a chosen SHARE country).
"""

# canonical concept -> harmonised-gate variable (template; CONFIRM per cohort)
HARMONISED_MAP = {
    "stroke":            {"var": "hstrok",  "recode": "yes_no"},
    "age":               {"var": "hage",    "recode": "cont"},
    "sex":               {"var": "hgender", "recode": "yes_no"},   # 1 male / 2 female
    "education":         {"var": "heducl",  "recode": "cat"},
    "marital":           {"var": "hmaritl", "recode": "cat"},
    "income_pir":        {"var": "htotinc", "recode": "cont"},     # or wealth hwbat if PIR n/a
    "bmi":               {"var": "hbmi",    "recode": "cont"},
    "ever_smoker":       {"var": "hsmoke",  "recode": "yes_no"},
    "current_smoker":    {"var": "hsmoke",  "recode": "yes_no"},   # refine with hsmokev if present
    "alcohol":           {"var": "hdrink",  "recode": "yes_no"},   # hdrink1/hdrink2 per cohort
    "hypertension":      {"var": "hhypert", "recode": "yes_no"},
    "high_cholesterol":  {"var": "hhighl",  "recode": "yes_no"},
    "diabetes":          {"var": "hdiab",   "recode": "yes_no"},
    "heart_attack":      {"var": "hheart",  "recode": "yes_no"},
}

COUNTRY = {"CHARLS": "CN", "ELSA": "EN", "HRS": "US", "SHARE": "EU"}

# known harmonised-gate yes/no coding: 1=yes, 2=no, 3/7/9=refusal/NA -> handled by recode
YESNO = {"yes": 1, "no": 2}
