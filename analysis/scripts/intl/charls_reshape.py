"""Reshape the HARMONISED CHARLS release-D gate file (wide-by-release, r{n}VAR) into a
respondent-wave long table with the SAME 14 canonical features + stroke that the
synthetic-validated LOCO pipeline (modeling.encode / loco_multicohort.loco) consumes.

Variable mapping was CONFIRMED against the real .dta via pyreadstat labels (integrity
rule: check, don't assume). See DECISION notes printed to stderr.

Key harmonisation choices (all logged):
  * unit = respondent x wave (one row per interviewed adult per release r1..r4),
    mirroring NHANES "one row per participant per cycle".
  * binary health vars (stroke/hypertension/diabetes/heart/smoking/drinking): CHARLS
    codes 0=No / 1=Yes with letter-coded special missing (d/m/p/r/s/u/v/x); we keep
    0/1 and coerce everything else to NaN via pd.to_numeric(errors='coerce').
  * sex: ragender 1=man / 2=woman -> kept as 1/2 (encode ref=1).
  * education: raeducl {0 none,1 <lower-sec,2 upper-sec&voc,3 tertiary} mapped onto a
    SHARED 3-level scale {0,1->1 low, 2->2 upper-secondary, 3->3 tertiary} (identical
    scheme applied to NHANES so the two cohorts are directly comparable under LOCO).
  * marital: r{n}mstat {1 married,3 partnered,4 separated,5 divorced,7 widowed,8 never}
    mapped onto a SHARED 2-level scale {1,3->1 partnered; 4,5,7,8->2 not partnered}.
  * income_pir: household total wealth hh{n}atotb (CNY) -> log1p of positive values,
    then z-scored WITHIN CHARLS so the economic axis is on a comparable scale to the
    other cohorts' standardised income (raw CNY would otherwise dominate LOCO).
  * bmi: r{n}mbmi (measured, kg/m^2) continuous, comparable across cohorts.
  * high_cholesterol: genuinely ABSENT from the CHARLS harmonised gate -> NaN (reported,
    not fabricated).
  * heart_attack: closest available is r{n}hearte "ever had heart problem" (broader than
    MI) -> used, flagged in DECISION notes.

Usage: python charls_reshape.py [dta_path] [out_csv]
"""
import os, sys, numpy as np, pandas as pd, warnings
warnings.filterwarnings("ignore")

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DTA = os.path.abspath(os.path.join(HERE, "..", "..", "..",
                                           "data", "raw", "intl", "CHARLS", "H_CHARLS_D_Data.dta"))
DEFAULT_OUT = os.path.abspath(os.path.join(HERE, "..", "..", "..",
                                           "data", "processed", "intl", "std_CHARLS.csv"))

COHORT, COUNTRY = "CHARLS", "CN"
RELEASES = [1, 2, 3, 4]

# canonical concept -> (column template per release {n}, recode kind)
MAP = {
    "stroke":           ("r{n}stroke",  "bin01"),
    "age":              ("r{n}agey",    "cont"),
    "sex":              ("ragender",    "sex"),
    "education":        ("raeducl",     "edu"),
    "marital":          ("r{n}mstat",   "marr"),
    # wealth column name differs by release: w1/w2 = hh{n}atotb (household), w3/w4 = h{n}atotb (r+s)
    "income_pir":       ({1: "hh1atotb", 2: "hh2atotb", 3: "h3atotb", 4: "h4atotb"}, "wealth"),
    "bmi":              ("r{n}mbmi",    "cont"),
    "ever_smoker":      ("r{n}smokev",  "bin01"),
    "current_smoker":   ("r{n}smoken",  "bin01"),
    "alcohol":          ("r{n}drinkl",  "bin01"),
    "hypertension":     ("r{n}hibpe",   "bin01"),
    "high_cholesterol": (None,          "absent"),
    "diabetes":         ("r{n}diabe",   "bin01"),
    "heart_attack":     ("r{n}hearte",  "bin01"),
}
EDU = {0: 1, 1: 1, 2: 2, 3: 3}          # shared 3-level: low / upper-sec / tertiary
MARR = {1: 1, 3: 1, 4: 2, 5: 2, 7: 2, 8: 2}   # shared 2-level: partnered / not


def apply_recode(vals, kind):
    s = pd.Series(pd.to_numeric(pd.Series(vals), errors="coerce"), dtype="float64")
    if kind == "cont":
        return s
    if kind == "bin01":                       # 0/1 kept, letters already NaN
        return s.where(s.isin([0, 1]))
    if kind == "sex":                          # 1 man / 2 woman
        return s.where(s.isin([1, 2]))
    if kind == "edu":
        return s.map(EDU)
    if kind == "marr":
        return s.map(MARR)
    if kind == "wealth":                       # log1p of positive, else NaN
        s = np.log1p(s.where(s > 0))
        return s
    if kind == "absent":
        return pd.Series(np.nan, index=s.index)
    raise ValueError(kind)


def main():
    dta = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_DTA
    out = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_OUT
    import pyreadstat
    df, _ = pyreadstat.read_dta(dta)
    df["ID"] = pd.to_numeric(df["ID"], errors="coerce") if df["ID"].dtype != object else df["ID"]
    frames = []
    for n in RELEASES:
        cols = {"cohort": [COHORT] * len(df), "country": [COUNTRY] * len(df),
                "wave": [n] * len(df), "pid": df["ID"].values}
        for concept, (tmpl, kind) in MAP.items():
            if tmpl is None:
                cols[concept] = np.full(len(df), np.nan); continue
            v = tmpl[n] if isinstance(tmpl, dict) else tmpl.format(n=n)
            if v not in df.columns:
                print(f"  !! {v} not in file -> {concept}=NaN", file=sys.stderr)
                cols[concept] = np.full(len(df), np.nan); continue
            cols[concept] = apply_recode(df[v].values, kind).values
        frames.append(pd.DataFrame(cols))
    long = pd.concat(frames, ignore_index=True)

    # z-score income WITHIN cohort on the pooled respondent-wave wealth (comparable axis)
    mu, sd = long["income_pir"].mean(), long["income_pir"].std(ddof=0)
    long["income_pir"] = (long["income_pir"] - mu) / (sd if sd and np.isfinite(sd) else np.nan)

    # keep rows with a person id and a determinable stroke status
    long = long[long["pid"].notna() & long["stroke"].isin([0, 1])].copy()
    feat_cols = ["stroke", "age", "sex", "education", "marital", "income_pir", "bmi",
                 "ever_smoker", "current_smoker", "alcohol", "hypertension",
                 "high_cholesterol", "diabetes", "heart_attack"]
    std = long[["cohort", "country", "wave", "pid"] + feat_cols].copy()

    os.makedirs(os.path.dirname(out), exist_ok=True)
    std.to_csv(out, index=False)

    print(f"CHARLS reshape -> {out}", file=sys.stderr)
    print(f"  respondent-wave rows: {len(std)} | unique persons: {std['pid'].nunique()}", file=sys.stderr)
    print(f"  stroke events: {int(std['stroke'].sum())} | prevalence: {std['stroke'].mean():.3f}", file=sys.stderr)
    print("  per-wave n / events:", file=sys.stderr)
    print(std.groupby("wave").agg(n=("stroke", "size"), ev=("stroke", "sum")).to_string(), file=sys.stderr)
    print("  feature non-null %:", file=sys.stderr)
    print((std[feat_cols].notna().mean() * 100).round(1).to_string(), file=sys.stderr)
    print("DECISION NOTES:", file=sys.stderr)
    print("  - high_cholesterol ABSENT in CHARLS harmonised gate (NaN).", file=sys.stderr)
    print("  - heart_attack proxied by 'ever had heart problem' (r{n}hearte).", file=sys.stderr)
    print("  - income = within-cohort z of log1p(household total wealth).", file=sys.stderr)
    print(f"  - wealth log1p sd used for z: {sd:.4f}", file=sys.stderr)


if __name__ == "__main__":
    main()
