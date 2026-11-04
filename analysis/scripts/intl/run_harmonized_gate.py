"""One-command drop-and-run for the international LOCO.

Put each cohort's HARMONISED gate Stata file (.dta) into  data/raw/intl/  named
CHARLS*.dta / ELSA*.dta / HRS*.dta / SHARE*.dta , then:

    python run_harmonized_gate.py

For each file it (1) applies the shared h* mapping from config_intl, (2) reports any
concept the cohort lacks (ABSENT) so gaps are disclosed not fabricated, (3) writes
std_<cohort>.csv, then (4) runs country-level LOCO + figures via assemble_loco.

Because CHARLS/ELSA/HRS/SHARE harmonised gate files share the h* naming convention,
one mapping serves all four; per-file confirmation is printed for your review.
"""
import os, sys, glob, subprocess, numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)
import config_intl as CI
from discover_intl import read_any
import harmonize_intl as H

RAW = os.path.abspath(os.path.join(HERE, "..","..","..","data","raw","intl"))
STD = os.path.abspath(os.path.join(HERE, "..","..","..","data","processed","intl"))
os.makedirs(STD, exist_ok=True)

def cohort_of(fname):
    up = fname.upper()
    for c in ["CHARLS","ELSA","HRS","SHARE"]:
        if c in up: return c
    return os.path.splitext(fname)[0]

def main():
    files = sorted(glob.glob(os.path.join(RAW,"*.dta"))) + sorted(glob.glob(os.path.join(RAW,"*.sav")))
    if not files:
        print("No .dta/.sav in", RAW, "\nDrop the harmonised gate files there first."); return
    for f in files:
        coh = cohort_of(os.path.basename(f)); country = CI.COUNTRY.get(coh, coh[:2].upper())
        df, labels, vlab = read_any(f)
        # build a mapping using shared h* names, but only for variables actually present
        mapping = {}
        for concept, spec in CI.HARMONISED_MAP.items():
            v = spec["var"]
            if v in df.columns:
                mapping[concept] = {"var": v, "recode": spec["recode"]}
            else:
                # try a couple of documented aliases before declaring ABSENT
                alts = {"income_pir":["hwbat","hhhweal","hewhoh1","hwtotcor"],
                        "current_smoker":["hsmokev","hsmoknow"],"alcohol":["hdrink1","hdrink2"],
                        "bmi":["hbmib","hbmi"]}.get(concept, [])
                for a in alts:
                    if a in df.columns: mapping[concept]={"var":a,"recode":spec["recode"]}; break
        absent = [c for c in H.CANON if c not in mapping]
        print(f"\n=== {coh} ({country}) | {os.path.basename(f)} | rows {len(df)} ===")
        print("  mapped:", {k:v['var'] for k,v in mapping.items()})
        print("  ABSENT (will be NaN, disclosed):", absent)
        # write std via harmonize logic
        out = pd.DataFrame({"cohort":[coh]*len(df),"country":[country]*len(df)})
        for concept in H.CANON:
            if concept in mapping:
                out[concept] = H.recode(df[mapping[concept]["var"]].values, mapping[concept]["recode"]).values
            else:
                out[concept] = np.nan
        if "sex" in out and pd.to_numeric(out["sex"],errors="coerce").max() and pd.to_numeric(out["sex"],errors="coerce").max()>1:
            out["sex"]=pd.to_numeric(out["sex"],errors="coerce").map({1:1,2:0}).astype("float64")
        out = out[out["stroke"].isin([0,1])].copy()
        out.to_csv(os.path.join(STD,f"std_{coh}.csv"), index=False)
        print(f"  -> std_{coh}.csv | adults {len(out)} | stroke events {int(out['stroke'].sum())}")
    print("\nRunning country-level LOCO ...")
    subprocess.run([sys.executable, os.path.join(HERE,"assemble_loco.py")])

if __name__=="__main__":
    main()
