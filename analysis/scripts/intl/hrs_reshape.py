"""Reshape RAND HRS 1992-2022 (v1, SAS release) into the shared international tables.

    python intl/hrs_reshape.py [--bmi measured|selfreport]

Two outputs, one pass over the 7.2 GB source:
  * `data/processed/intl/corrected/std_HRS.csv`  - respondent x wave, the 14 canonical features,
    shared coding, identical in shape to std_CHARLS / std_KLoSA / std_MHAS.
  * `data/processed/intl/incident/hrs_times.csv` - respondent x wave CALENDAR TIME + VITAL STATUS
    (pid, wave, t, iwstat, tdeath, wt), which is what `incident_personperiod.py` needs and which
    the std table deliberately does not carry. Reading the small extract instead of the SAS file
    keeps every downstream rerun cheap.

Why RAND HRS and not the harmonised gate
----------------------------------------
`data/raw/intl/HRS/H_HRS_d.dta` (gateway release D) has stroke and interview years but NO death
dates and no interview-status field, so a US person who stopped being seen could only ever be
censored at their last interview. RAND HRS carries `RADDATE` (date of death, from the Tracker
file) and `R{w}IWSTAT` (which explicitly separates "non-response but alive" from "died this wave"
and "died previous wave"). Those two fields are what make the US arm a real competing-risk panel
rather than an attrition panel, and they are the reason this file is worth a 7 GB read.

Metadata: what was checked, and how
-----------------------------------
The SAS header in this release is unreliable: `metadataonly` returns 13,262 label entries for
19,880 columns, so name and label arrays are index-shifted (R1IWMID is "labelled" SMOKEV,
R1WTRESP is labelled PRCHMEMRY). The PDF codebook's descriptive-statistics block is a broken
multi-column layout. So EVERY value code used here was established by reading the codebook's
"Variable Category Codes" frequency tables AND cross-checking them against the observed counts in
the data file itself. The two agreed exactly on every variable checked, e.g.:

  R1MSTAT  observed {1:9837, 2:57, 3:385, 4:310, 5:1080, 7:621, 8:362}
           codebook 1=Married 9837, 2=Married spouse absent 57, 3=Partnered 385,
                     4=Separated 310, 5=Divorced 1080, 7=Widowed 621, 8=Never married 362
  R5HIBP   observed {0:9604, 1:9663, 3:7, 4:291}
           codebook 0=No 9604, 1=Yes 9663, 3=Disp prev record and has 7,
                    4=Disp prev record and no 291
  R1STROKE observed {0:12316, 1:336} = codebook w1 0=No 12316, 1=Yes 336

The machine-readable record of that check is `results/reports/hrs_metadata_probe.json`
(`intl/hrs_metadata_probe.py`). Never edit a code in this file without re-running it.

Harmonisation choices (one concept, one definition, across four panels)
----------------------------------------------------------------------
  * unit = respondent x wave, keeping rows where the respondent was interviewed (iwstat 1),
    aged >= 20 and with a determinable 0/1 stroke answer - the CHARLS/MHAS rule.
  * `R{w}STROKE` is "ever had stroke" (0/1, clean in all 16 waves), so the first 0 -> 1
    transition is the incident event, exactly as in the other three panels. TIA is folded into
    "yes" by RAND's own derivation of RwSTROKE; disclosed, not silently accepted.
  * hypertension/diabetes/heart_attack = the "EVER" items (`HIBPE`/`DIABE`/`HEARTE`), which are
    clean 0/1 in every wave. The "this wave" items (`HIBP`/`DIAB`/`HEART`) additionally carry
    codes 3-6 = record-discrepancy flags (7 to 508 rows per wave) and are not used.
    `HEARTE` = "ever had heart problems", the SAME broad proxy CHARLS uses; MHAS's narrower
    myocardial-infarction item is the one known asymmetry, already disclosed in the manuscript.
  * ever_smoker / current_smoker = `SMOKEV` / `SMOKEN` (0/1, "smoke ever" / "smokes now").
  * alcohol = `DRINK` = "ever drinks any alcohol" (0/1). Slightly broader than the CHARLS
    last-year item; the residual difference is disclosed rather than papered over.
  * marital: HRS MSTAT is NOT the CHARLS/MHAS coding. 1=Married, 2=Married-spouse-absent and
    3=Partnered are partnered; 4=Separated, 5=Divorced, 6=Separated/divorced (wave 3 only),
    7=Widowed, 8=Never married are not. Reusing the CHARLS dictionary here would have put
    "separated" on the partnered side of the variable.
  * education: RAEDUC 1=Less than high school, 2=GED, 3=High-school graduate, 4=Some college,
    5=College and above -> the shared 3-level scale as {1->1, 2->2, 3->2, 4->3, 5->3}. GED joins
    high-school completion because that is how the NHANES bridge in build_nhanes_std.py treats it
    (DMDEDUC2 code 3 = "high school graduate OR GED"), so the two US sources stay comparable.
  * sex: RAGENDER 1=male / 2=female, kept as-is (shared encoding).
  * age: `R{w}AGEY_M` = age in YEARS at the mid-month of the interview (the "_M" is mid, not
    months - verified against the codebook long name and the observed 23-85 range at wave 1).
  * income_pir: household total assets `H{w}ATOTB` ("Total of all Assets - Cross-wave", USD),
    log1p of positive values, z-scored WITHIN HRS. This is the same asset concept CHARLS
    (`hh{w}atotb`) and MHAS (`h{w}atotb`) use, not the income concept NHANES uses. HRS reports
    NEGATIVE assets for indebted households; the shared log1p rule cannot take them, so they stay
    missing and the count is printed.
  * bmi: PRIMARY = `R{w}PMBMI`, the physical-measurement-based BMI, which is non-null only in the
    waves the diagnostic counts as carrying it (8-14 and 16; zero rows in 1-7 and in 15) and covers
    ~35-40% of those interviews. `R{w}BMI` is
    SELF-REPORTED (built from `R{w}HEIGHT`/`R{w}WEIGHT`, both labelled self-reported) and is used
    only in the --bmi selfreport sensitivity variant, mirroring the MHAS decision to keep one BMI
    definition across cohorts rather than mix measured and reported.
  * high_cholesterol: ABSENT. The only cholesterol item in this release is `R{w}CHOLST` =
    "Prev Cholesterol", drawn from the section on preventative tests and procedures ("a blood
    test for cholesterol, a flu shot, monthly self-checks") - screening utilisation, not a
    diagnosis. This is the same reason MHAS's cholst was rejected, and it keeps HRS aligned with
    CHARLS and KLoSA, which have no such item either.
  * calendar time: `R{w}IWMID` is a SAS date (days since 1960-01-01), converted to an exact
    decimal year. Wave 1 spans 1992-03-20 to 1993-04-28, which is why wave LABELS were never
    good enough for a four-year risk horizon.
  * vital status: `R{w}IWSTAT` 1=respondent alive, 4=non-response alive, 5=died this wave,
    6=died previous wave, 7=dropped from the sample, 0=inapplicable (not in that wave's sample).
    5 and 6 are deaths; 4 is alive-but-refused; 7 is neither a death nor exposure.

Usage: python hrs_reshape.py [--bmi measured|selfreport]
"""
import os, sys, json, warnings
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
SRC = os.path.join(ROOT, "data", "raw", "intl", "HRS", "randhrs", "randhrs1992_2022v1.sas7bdat")
STD_DIR = os.path.join(ROOT, "data", "processed", "intl", "corrected")
INC_DIR = os.path.join(ROOT, "data", "processed", "intl", "incident")
DIAG = os.path.join(ROOT, "results", "reports", "hrs_reshape_diagnostics.json")

COHORT, COUNTRY = "HRS", "US"
WAVES = list(range(1, 17))
PID = "HHIDPN"
MIN_AGE = 20
SAS_EPOCH = pd.Timestamp("1960-01-01")

# concept -> (column template, recode). {w} is the wave number.
MAP = {
    "stroke":           ("R{w}STROKE",  "bin01"),
    "age":              ("R{w}AGEY_M",  "cont"),
    "sex":              ("RAGENDER",    "sex"),
    "education":        ("RAEDUC",      "edu"),
    "marital":          ("R{w}MSTAT",   "marr"),
    "income_pir":       ("H{w}ATOTB",   "wealth"),
    "bmi":              ("R{w}PMBMI",   "cont"),
    "ever_smoker":      ("R{w}SMOKEV",  "bin01"),
    "current_smoker":   ("R{w}SMOKEN",  "bin01"),
    "alcohol":          ("R{w}DRINK",   "bin01"),
    "hypertension":     ("R{w}HIBPE",   "bin01"),
    "high_cholesterol": (None,          "absent"),
    "diabetes":         ("R{w}DIABE",   "bin01"),
    "heart_attack":     ("R{w}HEARTE",  "bin01"),
}
EDU = {1: 1, 2: 2, 3: 2, 4: 3, 5: 3}
MARR = {1: 1, 2: 1, 3: 1, 4: 2, 5: 2, 6: 2, 7: 2, 8: 2}
FEATS = list(MAP)
BMI_SELFREPORT = "R{w}BMI"


def needed_columns():
    cols = [PID, "RAGENDER", "RAEDUC", "RABYEAR", "RADDATE"]
    for w in WAVES:
        cols += [f"R{w}IWSTAT", f"R{w}IWMID", f"R{w}WTRESP"]
        for tmpl, _ in MAP.values():
            if tmpl:
                cols.append(tmpl.format(w=w))
        cols.append(BMI_SELFREPORT.format(w=w))
    return sorted(set(cols))


def to_num(s):
    return pd.to_numeric(pd.Series(list(s)), errors="coerce").reset_index(drop=True)


def decimal_year(vals):
    """SAS date numbers (days since 1960-01-01), or datetimes if the reader converted them,
    to an exact decimal calendar year. A day-precision date is the whole point of using RAND
    HRS instead of the gate file, so nothing here falls back to a month midpoint."""
    s = pd.Series(list(vals)) if not isinstance(vals, pd.Series) else vals
    if np.issubdtype(s.dtype, np.datetime64):
        d = pd.to_datetime(s)
    else:
        d = SAS_EPOCH + pd.to_timedelta(pd.to_numeric(s, errors="coerce"), unit="D")
    yr = d.dt.year.astype("float64")
    doy = d.dt.dayofyear.astype("float64")
    span = np.where(d.dt.is_leap_year, 366.0, 365.0)
    return np.where(yr.notna(), yr + (doy - 0.5) / span, np.nan)


def apply_recode(vals, kind):
    s = to_num(vals).astype("float64")
    if kind == "cont":
        return s
    if kind == "bin01":
        return s.where(s.isin([0, 1]))
    if kind == "sex":
        return s.where(s.isin([1, 2]))
    if kind == "edu":
        return s.map(EDU)
    if kind == "marr":
        return s.map(MARR)
    if kind == "wealth":
        return np.log1p(s.where(s > 0))
    if kind == "absent":
        return pd.Series(np.nan, index=s.index)
    raise ValueError(kind)


def main():
    bmi_mode = "measured"
    if "--bmi" in sys.argv:
        bmi_mode = sys.argv[sys.argv.index("--bmi") + 1]
    if bmi_mode not in ("measured", "selfreport"):
        sys.exit(f"unknown --bmi mode {bmi_mode!r}")

    want = needed_columns()
    print(f"reading {len(want)} columns from {os.path.basename(SRC)} ...", flush=True)
    import pyreadstat
    raw, meta = pyreadstat.read_sas7bdat(SRC, usecols=want, formats_as_category=False)
    absent = [c for c in want if c not in raw.columns]
    if absent:
        print(f"  !! absent from file ({len(absent)}): {absent[:20]}", file=sys.stderr)
    if PID not in raw.columns:
        sys.exit(f"missing person identifier {PID!r} - aborting, not guessing an alternative")
    print(f"  rows={len(raw)}  persons(unique {PID})={raw[PID].nunique()}", flush=True)

    raw["__pid"] = to_num(raw[PID])
    raw["__tdeath"] = decimal_year(raw["RADDATE"].values)

    def g(name):
        """Column if the file has it, else all-NaN - an absent item must become a disclosed gap,
        never a zero and never a silently skipped concept."""
        return raw[name] if name in raw.columns else pd.Series(np.full(len(raw), np.nan))

    feats, times = [], []
    for w in WAVES:
        iw = to_num(g(f"R{w}IWSTAT"))
        row = {"cohort": [COHORT] * len(raw), "country": [COUNTRY] * len(raw),
               "wave": float(w), "pid": raw["__pid"].values,
               "iwstat": iw.values,
               "interviewed": (iw == 1).values}
        for concept, (tmpl, kind) in MAP.items():
            col = tmpl.format(w=w) if tmpl else None
            row[concept] = apply_recode(g(col) if col else [np.nan] * len(raw), kind).values
            if col and col not in raw.columns:
                print(f"  !! {col} absent -> {concept}=NaN", file=sys.stderr)
        self_bmi = apply_recode(g(BMI_SELFREPORT.format(w=w)), "cont")
        row["bmi_selfreport"] = self_bmi.values
        if bmi_mode == "selfreport":
            row["bmi"] = np.where(pd.isna(row["bmi"]), self_bmi.values, row["bmi"])
        row["assets_raw"] = g(f"H{w}ATOTB").values
        feats.append(pd.DataFrame(row))

        times.append(pd.DataFrame({
            "cohort": COHORT, "pid": raw["__pid"].values, "wave": float(w),
            "t": decimal_year(g(f"R{w}IWMID").values), "iwstat": iw.values,
            "tdeath": raw["__tdeath"].values,
            "wt": to_num(g(f"R{w}WTRESP")).values}))

    iv = pd.concat(feats, ignore_index=True)
    tt = pd.concat(times, ignore_index=True)

    # shared plausibility rules, identical to clean_intl_std.py / klosa_reshape_v2.py
    log = {}
    keep = iv["interviewed"] & iv["pid"].notna() & iv["stroke"].isin([0, 1])
    log["rows_interviewed_with_determinable_stroke"] = int(keep.sum())
    std = iv[keep].copy()
    n0 = len(std)
    std = std[std["age"] >= MIN_AGE]
    log["rows_dropped_under_age_20"] = n0 - len(std)
    b = std["bmi"]
    bad = b.notna() & ~b.between(12, 70)
    log["bmi_impossible_to_nan"] = int(bad.sum())
    log["bmi_max_before"] = float(b.max()) if b.notna().any() else None
    std.loc[bad, "bmi"] = np.nan
    mis = (std["ever_smoker"] == 0) & (std["current_smoker"] == 1)
    log["current_smoker_structural_zero"] = int(mis.sum())
    std.loc[mis, "current_smoker"] = 0.0

    mu, sd = std["income_pir"].mean(), std["income_pir"].std(ddof=0)
    std["income_pir"] = (std["income_pir"] - mu) / (sd if sd and np.isfinite(sd) else np.nan)
    log["income_pir_log_sd"] = float(sd) if sd and np.isfinite(sd) else None

    out_std = os.path.join(STD_DIR, "std_HRS.csv") if bmi_mode == "measured" else os.path.join(
        STD_DIR, "sensitivity", "std_HRS_selfreport.csv")
    os.makedirs(os.path.dirname(out_std), exist_ok=True)
    std[["cohort", "country", "wave", "pid"] + FEATS].to_csv(out_std, index=False)

    # iwstat 0 means "not in this wave's sample at all" - no interview, no vital status, nothing a
    # censoring rule can use - so those rows stay out of the time extract.
    tt_all = tt.copy()
    tt = tt[tt["iwstat"].notna() & (tt["iwstat"] != 0)].copy()
    out_times = os.path.join(INC_DIR, "hrs_times.csv")
    os.makedirs(INC_DIR, exist_ok=True)
    tt.to_csv(out_times, index=False)

    # ---------------------------------------------------------------- diagnostics
    med_date = tt[tt["iwstat"] == 1].groupby("wave")["t"].median()
    st = std.groupby("wave").agg(n=("stroke", "size"), events=("stroke", "sum"))
    st["prev"] = (st["events"] / st["n"]).round(4)
    st["median_interview_date"] = med_date.round(3)
    iw_by_wave = tt.groupby("wave")["iwstat"].value_counts().unstack().sort_index(axis=1)
    per_wave_assets = iv.groupby("wave").agg(
        rows_in_sample=("iwstat", lambda s: int((s.notna() & (s != 0)).sum())),
        assets_nonnull=("assets_raw", lambda s: int(s.notna().sum())),
        assets_le0=("assets_raw", lambda s: int((s <= 0).sum())),
        pmbmi_nonnull=("bmi", lambda s: int(s.notna().sum())),
        selfbmi_nonnull=("bmi_selfreport", lambda s: int(s.notna().sum())))
    diag = {
        "source": os.path.relpath(SRC, ROOT), "bmi_mode": bmi_mode,
        "sas_rows": int(len(raw)), "sas_persons": int(raw["__pid"].nunique()),
        "std_rows": int(len(std)), "std_persons": int(std["pid"].nunique()),
        "std_events": int(std["stroke"].sum()), "std_prevalence": float(std["stroke"].mean()),
        "death_date_coverage_persons": int((raw["__tdeath"].notna()).sum()),
        "times_extract_rows": int(len(tt)),
        "interview_date_coverage_of_extract": float(tt["t"].notna().mean()),
        "iwstat_counts_by_wave": {str(int(k)): {str(int(c)): int(v) for c, v in row.items()
                                                if pd.notna(v)}
                                  for k, row in iw_by_wave.iterrows()},
        "per_wave": st.fillna("").to_dict("index"),
        "assets_and_bmi_by_wave": per_wave_assets.to_dict("index"),
        "feature_nonnull_pct": (std[FEATS].notna().mean() * 100).round(2).to_dict(),
        "binary_feature_prevalence_pct": (std[["stroke", "ever_smoker", "current_smoker", "alcohol",
                                               "hypertension", "diabetes", "heart_attack"]].mean() * 100
                                          ).round(2).to_dict(),
        "rules_applied": log,
    }
    os.makedirs(os.path.dirname(DIAG), exist_ok=True)
    with open(DIAG, "w", encoding="utf-8") as f:
        json.dump(diag, f, indent=1, ensure_ascii=False, default=float)

    print(f"\nHRS reshape -> {out_std}", file=sys.stderr)
    print(f"  rows={len(std)} persons={std['pid'].nunique()} events={int(std['stroke'].sum())} "
          f"prevalence={std['stroke'].mean():.4f}", file=sys.stderr)
    print(f"  times extract -> {out_times}  rows={len(tt)} of {len(tt_all)}  "
          f"persons with a death date={diag['death_date_coverage_persons']}  "
          f"interview-date coverage of extract={diag['interview_date_coverage_of_extract']:.4f}",
          file=sys.stderr)
    print("  per wave (n / events / prevalence / median interview date):", file=sys.stderr)
    print(st.to_string(), file=sys.stderr)
    print("  iwstat by wave (1=interviewed 4=NR alive 5=died this wv 6=died prev wv "
          "7=dropped 0=inapplicable):", file=sys.stderr)
    print(iw_by_wave.fillna(0).astype(int).to_string(), file=sys.stderr)
    print("  assets / BMI availability by wave:", file=sys.stderr)
    print(per_wave_assets.to_string(), file=sys.stderr)
    print("  feature non-null % of kept rows:", file=sys.stderr)
    print((std[FEATS].notna().mean() * 100).round(1).to_string(), file=sys.stderr)
    print("  rules:", json.dumps(log), file=sys.stderr)
    print(f"  wrote {out_std}\n  wrote {out_times}\n  wrote {DIAG}", file=sys.stderr)


if __name__ == "__main__":
    main()
