"""Why is `R{w}WTRESP` exactly zero on 9.1% of interviewed RAND HRS rows?

`incident_personperiod.py` attaches `R{w}WTRESP` to each interval's starting wave and the weighted arm
uses only rows with weight > 0. Before quoting that arm, the zeros need a mechanism: are they
"minimum-core/low respondent-level" interviews that carry the *household* weight instead, or is the
series simply not defined for some cohorts (children added at wave 5, warps at wave 13)?

Reads the 7.2 GB SAS file once for twelve columns only.

    python intl/hrs_weight_zero_probe.py
"""
import json
import os

import numpy as np
import pandas as pd
import pyreadstat

SRC = os.path.join("H:\\", "脑出血国际队列", "data", "raw", "intl", "HRS", "randhrs",
                   "randhrs1992_2022v1.sas7bdat")
OUT = "H:\\脑出血国际队列\\results\\reports\\hrs_weight_zero_probe.json"
WAVES = [1, 2, 3, 8, 13, 16]


def main():
    cols = []
    for w in WAVES:
        cols += [f"R{w}IWSTAT", f"R{w}WTRESP", f"R{w}WTHH", f"R{w}AGEY_M"]
    df, _ = pyreadstat.read_sas7bdat(SRC, usecols=cols, formats_as_category=False)
    print(f"read {df.shape}", flush=True)
    out = {}
    for w in WAVES:
        iw = df[f"R{w}IWSTAT"].astype("float")
        wr = df[f"R{w}WTRESP"].astype("float")
        wh = df[f"R{w}WTHH"].astype("float")
        age = df[f"R{w}AGEY_M"].astype("float")
        iwc = iw.value_counts(dropna=False)
        m = iw == 1
        z = m & (wr == 0)
        rec = {
            "iwstat_counts": {str(int(k)): int(v) for k, v in iwc.items() if not np.isnan(k)},
            "interviewed": int(m.sum()),
            "wtresp_zero": int(z.sum()),
            "wtresp_zero_pct_of_interviewed": round(float(z.sum()) / max(int(m.sum()), 1), 4),
            "wtresp_null": int((m & wr.isna()).sum()),
            "hh_weight_present_at_zeros": int((z & (wh > 0)).sum()),
            "hh_weight_positive_overall": int((m & (wh > 0)).sum()),
            "wtresp_sum_over_interviewed": round(float(wr[m].sum()), 1),
        }
        if z.any():
            rec["age_at_zeros"] = {
                "median": (None if age[z].dropna().empty else round(float(age[z].median()), 1)),
                "min": (None if age[z].dropna().empty else int(age[z].min())),
                "max": (None if age[z].dropna().empty else int(age[z].max())),
            }
            rec["mean_age_interviewed"] = round(float(age[m].mean()), 1)
        out[f"wave{w}"] = rec
        print(json.dumps(rec, ensure_ascii=False), flush=True)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(out, open(OUT, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    print("->", OUT)


if __name__ == "__main__":
    main()
