"""Discover concept-relevant variables in a raw cohort file (CHARLS/ELSA/HRS/SHARE).

Label-driven, so we never guess variable names: it lists every variable whose NAME or
VARIABLE-LABEL matches each target concept, plus (for Stata) its value labels, so a human
can confirm the mapping before harmonisation.

Usage:  python discover_intl.py path/to/raw_file.dta|csv
"""
import os, sys, re, json
import numpy as np, pandas as pd

CONCEPTS = {
 "stroke":      r"stroke|cerebral|cerebro-?vascular",
 "age":         r"\bage\b|age_|_age|rage|yrag|agea",
 "sex":         r"\bgender\b|\bsex\b|gnd|gend",
 "education":   r"educat|\beduc\b|schooling|qualification|isced",
 "marital":   r"marital|maritalstatus|partner|spouse|living.*partner",
 "income":      r"income|earnings|pay|wage|total.*income|household.*income",
 "wealth":      r"wealth|net.*worth|assets|capital",
 "bmi":         r"\bbmi\b|body.*mass|weight.*height|obes",
 "smoking":     r"smok|cigarette|tobacco|ever.*smok|current.*smok",
 "alcohol":     r"alcoh|drink|beer|wine|liquor",
 "hypertension":r"hypertens|high.*blood.*press|blood pressure|\bbp\b",
 "diabetes":    r"diabet|sugar|glucose|hba1c",
 "cholesterol": r"cholesterol|lipid|hyperlip",
 "heart":       r"heart|cardiac|myocardial|\bmi\b|cardio",
 "country":     r"\bcountry\b|nation|region|sample.*country",
}

def read_any(path):
    ext = os.path.splitext(path)[1].lower()
    if ext in (".dta",):
        import pyreadstat
        df, meta = pyreadstat.read_dta(path)
        labels = {v: (meta.column_names_to_labels.get(v) or "") for v in df.columns}
        vlab = getattr(meta, "variable_value_labels", {}) or {}
        return df, labels, vlab
    if ext in (".sav", ".zsav"):
        import pyreadstat
        df, meta = pyreadstat.read_sav(path)
        labels = {v: (meta.column_names_to_labels.get(v) or "") for v in df.columns}
        vlab = getattr(meta, "variable_value_labels", {}) or {}
        return df, labels, vlab
    if ext in (".xpt",):
        import pyreadstat
        df, meta = pyreadstat.read_xport(path)
        labels = {v: (meta.column_names_to_labels.get(v) or "") for v in df.columns}
        return df, labels, {}
    # csv
    df = pd.read_csv(path, low_memory=False)
    return df, {c: "" for c in df.columns}, {}

def main():
    if len(sys.argv) < 2:
        print(__doc__); sys.exit(0)
    path = sys.argv[1]
    df, labels, vlab = read_any(path)
    print(f"{os.path.basename(path)}: {df.shape[0]} rows x {df.shape[1]} cols\n")
    hits = {}
    for concept, pat in CONCEPTS.items():
        rx = re.compile(pat, re.I)
        matched = []
        for col in df.columns:
            hay = f"{col} {labels.get(col,'')}"
            if rx.search(hay):
                sample = df[col].dropna()
                vals = list(pd.unique(sample))[:6] if len(sample) else []
                vl = vlab.get(col, {})
                matched.append({"var": col, "label": labels.get(col, ""),
                                "n_missing": int(df[col].isna().sum()),
                                "values": [str(v) for v in vals],
                                "value_labels": {str(k): str(v) for k, v in list(vl.items())[:6]}})
        hits[concept] = matched
        print(f"[{concept}] {len(matched)} candidate(s)")
        for m in matched[:6]:
            print(f"    {m['var']:16s} | {m['label'][:40]:40s} | miss={m['n_missing']:6d} | vals={m['values']} | vlab={m['value_labels']}")
        print()
    out = os.path.join(os.path.dirname(path) if os.path.dirname(path) else ".", 
                       os.path.basename(path) + ".discovery.json")
    json.dump(hits, open(out, "w"), indent=1, default=str)
    print("wrote", out)

if __name__ == "__main__":
    main()
