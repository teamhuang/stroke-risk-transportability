"""Extract + harmonise the 3 NHANES cycles into one patient-level table.

One row per adult (>=20 y) with a non-missing stroke determination.
Preprocessing decisions here are frozen by config.py. Refusal/don't-know codes
(7,9,77,99,777,999,...) -> NaN. Binary Y/N questions -> 1/0. Categories kept as
integer codes (one-hot happens downstream). Weights + design vars retained for
design-based prevalence/CI only.
"""
import os
for _v in ("OMP_NUM_THREADS","MKL_NUM_THREADS","OPENBLAS_NUM_THREADS","NUMEXPR_NUM_THREADS"):
    os.environ[_v] = "1"
import sys, numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(__file__))
import config as C

RAW = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "raw"))
OUT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "processed"))
os.makedirs(OUT, exist_ok=True)
MISS_CODES = [7, 9, 77, 99, 777, 999, 55, 66, 15, 555, 666]

def load(base, suf):
    f = os.path.join(RAW, f"{base}{suf}.xpt")
    return pd.read_sas(f, format="xport") if os.path.exists(f) else None

def to_nan(s):
    if s is None: return None
    s = pd.to_numeric(s, errors="coerce").copy()
    s[s.isin(MISS_CODES)] = np.nan
    return s

def recode(x, key):
    x = to_nan(x)
    if x is None: return None
    if key == "cont":       return x
    if key == "binary":     return x.map({1:1, 2:0}).astype("float64")
    if key == "binary_01_2to3": return x.map({1:1, 2:1, 3:0}).astype("float64")
    if key in ("cat5", "cat"):  return x
    raise ValueError(key)

def join_col(spine, df_, var, recode_key, name):
    """Left-join a single variable (by SEQN) onto the spine so lengths can't misalign."""
    if df_ is None or var not in df_.columns:
        spine[name] = np.nan; return spine
    col = pd.DataFrame({"seqn": df_["SEQN"].astype("float64"),
                        name: recode(df_[var], recode_key)})
    col = col.drop_duplicates("seqn")
    return spine.merge(col, on="seqn", how="left")

def spec_for(feat, suf):
    spec = C.FEATURE_CODES[feat]
    return spec['*_'] if '*_' in spec else spec[suf]

def build_cycle(suf):
    src = {b: load(b, suf) for b in ["DEMO","MCQ","BMX","BPQ","DIQ","SMQ","ALQ","DPQ"]}
    demo = src["DEMO"]
    d = pd.DataFrame({"seqn": demo["SEQN"].astype("float64")})
    d["cycle"] = suf; d["cycle_label"] = C.CYCLE_LABELS[suf]
    d["weight"] = to_nan(demo.get("WTMEC2YR")); d["psu"] = to_nan(demo.get("SDMVPSU"))
    d["strata"] = to_nan(demo.get("SDMVSTRA"))
    # outcome (join by SEQN)
    d = join_col(d, src["MCQ"], C.OUTCOME["var"], "cont", "_stroke_code")
    d["stroke"] = d["_stroke_code"].map({C.OUTCOME["yes"]:1, C.OUTCOME["no"]:0}).astype("float64")
    # 14 features
    for feat in C.FEATURES:
        file_, var, rk = spec_for(feat, suf)
        d = join_col(d, src[file_], var, rk, feat)
    # structural-missing recodes (see DECISION_LOG):
    #   never-smoker  -> current_smoker = 0  (SMQ040 only asked of ever-smokers)
    #   no regular drinking -> alcohol = 0   (ALQ screener gates the question)
    d.loc[(d["ever_smoker"] == 0) & d["current_smoker"].isna(), "current_smoker"] = 0.0
    d["alcohol"] = d["alcohol"].fillna(0.0)
    # PHQ items (raw; recoded in the association step after code inspection)
    for it in C.PHQ_ITEMS:
        d = join_col(d, src["DPQ"], it, "cont", "phq_"+it)
    return d.drop(columns=["_stroke_code"])

def main():
    df = pd.concat([build_cycle(suf) for suf in C.CYCLES.values()], ignore_index=True)
    df = df[(df["age"] >= C.MIN_AGE) & df["stroke"].isin([0, 1])].copy()
    df.to_csv(os.path.join(OUT, "nhanes_stroke_harmonized.csv"), index=False)

    print("== rows (adults>=20, determinable stroke) ==", len(df), " | unique seqn:", df["seqn"].nunique())
    print("\nN & stroke events by cycle:")
    print(df.groupby("cycle_label").agg(N=("stroke","size"), events=("stroke","sum"),
          prevalence=("stroke","mean")).round(4).to_string())
    print("\nMissing fraction per feature:")
    print(df[C.FEATURES].isna().mean().round(4).to_string())
    print("\nOverall event rate:", round(df["stroke"].mean(),5),
          " EPV (events/feature):", round(df["stroke"].sum()/len(C.FEATURES),1))
    print("\nPHQ item value ranges (for correct recode):")
    for i in C.PHQ_ITEMS:
        u = sorted(pd.unique(df["phq_"+i].dropna()))
        print("  ", i, "->", u)
    print("\nDesign vars present -> psu:", df["psu"].notna().mean().round(3),
          " strata:", df["strata"].notna().mean().round(3),
          " weight:", df["weight"].notna().mean().round(3))
    print("\nsaved:", os.path.join(OUT, "nhanes_stroke_harmonized.csv"))

if __name__ == "__main__":
    main()
