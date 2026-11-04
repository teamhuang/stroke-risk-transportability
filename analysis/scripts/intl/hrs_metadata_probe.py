"""Empirical verification of RAND HRS v1 variable coding.

The SAS header in this release maps variable names to format names inconsistently (R1IWMID is
labelled SMOKEV, R1WTRESP is labelled PRCHMEMRY), and the PDF codebook's descriptive table is
rendered as a broken multi-column layout. So neither the header nor the codebook text can be
trusted for value codes. This script reads only the columns the harmonisation needs and reports
the observed value sets, which is the only ground truth available locally.

    python intl/hrs_metadata_probe.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pyreadstat

ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "data/raw/intl/HRS/randhrs/randhrs1992_2022v1.sas7bdat"
OUT = ROOT / "results/reports/hrs_metadata_probe.json"

FAMILIES = [
    "STROKE", "STROKE2", "HIBP", "HIBPE", "DIAB", "DIABE", "HEART", "HEARTE",
    "SMOKEV", "SMOKEN", "DRINK", "MSTAT", "BMI", "PMBMI", "HEIGHT", "WEIGHT",
    "AGEY_M", "AGEY_E", "WTRESP", "IWSTAT", "IWBEG", "IWMID", "IWEND",
]
RA = ["HHIDPN", "RAGENDER", "RAEDUC", "RAEDYRS", "RABYEAR", "RACOHBYR",
      "RADYEAR", "RADMONTH", "RADDATE", "RADSRC", "RADAGE_Y", "RAHHIDPN"]
H = [f"H{n}ITOT" for n in range(1, 17)]

names = set(json.loads((SRC.parent / "hrs_labels.json").read_text(encoding="utf-8")))
cols = [c for c in RA + H if c in names]
cols += [f"R{n}{f}" for f in FAMILIES for n in range(1, 17) if f"R{n}{f}" in names]
cols = sorted(set(cols))

print(f"reading {len(cols)} of {len(names)} columns", flush=True)
df, meta = pyreadstat.read_sas7bdat(SRC, usecols=cols, formats_as_category=False)
print(f"rows={len(df)}  read ok", flush=True)

summary: dict[str, dict] = {}
for c in df.columns:
    s = df[c]
    vals = s.dropna().unique()
    numeric = pd.to_numeric(s, errors="coerce")
    nv = np.sort(np.asarray(vals, dtype=float))
    entry = {
        "n_nonmissing": int(s.notna().sum()),
        "dtype": str(s.dtype),
        "n_distinct": int(len(nv)),
        "min": float(nv.min()) if nv.size else None,
        "max": float(nv.max()) if nv.size else None,
    }
    # pyreadstat keeps SAS letter-missings as distinct negative category codes in some builds;
    # any value outside the plausible range is reported so nothing is silently coerced.
    if entry["n_distinct"] <= 30:
        entry["values"] = [round(float(v), 6) for v in nv]
        entry["counts"] = {str(round(float(v), 6)): int((np.isclose(numeric, v)).sum()) for v in nv}
    else:
        qs = [0.0, 0.01, 0.25, 0.5, 0.75, 0.99, 1.0]
        entry["quantiles"] = {str(q): (None if pd.isna(x) else round(float(x), 4))
                              for q, x in zip(qs, numeric.quantile(qs))}
    summary[c] = entry

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(summary, indent=1), encoding="utf-8")
print(f"wrote {OUT}", flush=True)

show = ["R1STROKE", "R5STROKE", "R12STROKE", "R1HIBP", "R5HIBP", "R9HIBP", "R1DIAB", "R5DIAB",
        "R11DIAB", "R1HEART", "R5HEART", "R1SMOKEV", "R1SMOKEN", "R1DRINK", "R1MSTAT",
        "R1IWSTAT", "R5IWSTAT", "RAEDUC", "RAGENDER", "RADYEAR", "R1AGEY_M", "R1BMI",
        "R8BMI", "R8PMBMI", "R1WTRESP", "H1ITOT", "R1IWBEG", "R1IWMID", "R1IWEND"]
for c in show:
    if c in summary:
        e = summary[c]
        print(f"{c:12s} n={e['n_nonmissing']:6d} rng=[{e['min']},{e['max']}] "
              f"distinct={e['n_distinct']:4d} "
              f"{e.get('values') or e.get('quantiles')}")
