"""Reshape the GATEWAY HARMONISED MHAS release-D gate file (H_MHAS_d.dta) into the SAME
respondent-wave long table that charls_reshape.py produces, so the four-country LOCO
pipeline (modeling.design / run_loco_models) consumes it unchanged.

Mapping was CONFIRMED against the real .dta metadata (results/reports/mhas_metadata_dump.json)
and against the observed value distributions, not assumed. Integrity rule: check, don't assume.

Row structure, established empirically before writing this script:
  * 27,159 rows, `rahhidnp` unique -> one row per person (2001 core respondents and their
    entry spouses), NOT one row per interview.
  * `r{n}VAR` is that person's own data in release n and is populated only where the person
    was actually interviewed (r1agey non-missing = 15,186 = the count of r1iwstat == 1).
  * `s{n}VAR` repeats the same person's SPOUSE data, so appending it would double-count every
    spouse who is also a row in their own right. Only the `r{n}` series is used.
  * releases map to interview years 2001, 2003, 2012-13, 2015, 2018-19, 2021-22 (r{n}iwy).

Harmonisation choices (identical scheme to CHARLS so the cohorts stay directly comparable):
  * unit = person x release; one row per interviewed adult per wave.
  * binary items keep 0/1; the letter-coded specials (.a asked-only-from-50, .d DK, .m missing,
    .p proxy, .r refuse, .s skip, .u unmar, .v spouse-not-reported, .g not-asked-by-gender,
    .n below-screener, .i invalid) become NaN via pd.to_numeric(errors="coerce"). This mirrors
    charls_reshape.py exactly and therefore preserves the already-reported three-country arm;
    the share of rows affected is printed and disclosed rather than silently recoded.
  * sex: ragender 1=man / 2=woman, kept as 1/2 (same as CHARLS and the shared encoding).
  * education: raeducl {1 below upper-secondary, 2 upper-secondary/vocational, 3 tertiary}
    -> the shared 3-level scale (MHAS codes 1/2/3; CHARLS codes 0-3 collapse onto the same).
  * marital: r{n}mstat {1 married, 3 partnered -> 1 partnered; 4 separated, 5 divorced,
    7 widowed, 8 never married -> 2 not partnered} - the source coding is identical to CHARLS.
  * income_pir: household total assets h{n}atotb (MXN, incl. second home) -> log1p of positive
    values -> z-scored WITHIN MHAS, mirroring the CHARLS wealth treatment.
  * bmi: PRIMARY = measured r{n}mbmi only, which exists in releases 1-3 and is non-null for
    just 7-9% of person-rows. Releases 4-6 have no measured exam and the measured value is
    rarely present even in 1-3, so BMI stays missing for ~93% of MX rows and the LOCO imputer
    fills it from the training countries - the same situation the manuscript already discloses
    for KLoSA. Keeping the measured definition is what preserves one shared concept across all
    four cohorts. Pass --bmi selfreport to build the SENSITIVITY variant, which prefers measured
    and backfills self-reported r{n}bmi (non-null 35-56%); that variant changes what BMI *means*
    in Mexico (self-report sits ~0.6 kg/m2 below measured here) and is reported as a sensitivity,
    never as the primary arm.
  * age: rows below 20 are dropped, matching the NHANES >= 20 inclusion rule (7 MX rows).
  * high_cholesterol: ABSENT. The only cholesterol item, r{n}cholst, is "cholesterol checked in
    the last 2 years" - a health-utilisation item, not a diagnosis - so the concept is left NaN,
    exactly as in CHARLS.
  * heart_attack: r{n}hrtatte "ever had a heart attack", present in all six releases. This is
    the SPECIFIC myocardial-infarction item, narrower than the CHARLS proxy (r{n}hearte, "ever
    had heart problems"); the residual definitional difference is disclosed in the manuscript.

Usage: python mhas_reshape.py [dta_path] [out_csv] [--bmi measured|selfreport]
"""
import os, sys, numpy as np, pandas as pd, warnings
warnings.filterwarnings("ignore")

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DTA = os.path.abspath(os.path.join(HERE, "..", "..", "..", "H_MHAS_d.dta"))
DEFAULT_OUT = os.path.abspath(os.path.join(HERE, "..", "..", "..",
                                           "data", "processed", "intl", "std_MHAS.csv"))

COHORT, COUNTRY = "MHAS", "MX"
RELEASES = [1, 2, 3, 4, 5, 6]
PID = "rahhidnp"
MIN_AGE = 20

MAP = {
    "stroke":           ("r{n}stroke",   "bin01"),
    "age":              ("r{n}agey",     "cont"),
    "sex":              ("ragender",     "sex"),
    "education":        ("raeducl",      "edu"),
    "marital":          ("r{n}mstat",    "marr"),
    "income_pir":       ("h{n}atotb",    "wealth"),
    "bmi":              ("r{n}mbmi",     "cont"),
    "ever_smoker":      ("r{n}smokev",   "bin01"),
    "current_smoker":   ("r{n}smoken",   "bin01"),
    "alcohol":          ("r{n}drink",    "bin01"),
    "hypertension":     ("r{n}hibpe",    "bin01"),
    "high_cholesterol": (None,           "absent"),
    "diabetes":         ("r{n}diabe",    "bin01"),
    "heart_attack":     ("r{n}hrtatte",  "bin01"),
}
EDU = {1: 1, 2: 2, 3: 3}
MARR = {1: 1, 3: 1, 4: 2, 5: 2, 7: 2, 8: 2}
FEAT_COLS = list(MAP)

INTERVIEWED = "r{n}iwstat"     # 1 = interviewed this release
MIN_ASK_AGE = 50               # chronic-disease block is asked only from age 50
BMI_MODE = "measured"          # "measured" (primary) or "selfreport" (sensitivity variant)


def apply_recode(vals, kind):
    s = pd.Series(pd.to_numeric(pd.Series(vals), errors="coerce"), dtype="float64")
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
    global BMI_MODE
    args, i, positional = sys.argv[1:], 0, []
    while i < len(args):
        if args[i] == "--bmi":
            BMI_MODE = args[i + 1]; i += 2; continue
        positional.append(args[i]); i += 1
    if BMI_MODE not in ("measured", "selfreport"):
        sys.exit(f"unknown --bmi mode {BMI_MODE!r}")
    dta = positional[0] if positional else DEFAULT_DTA
    # the sensitivity variant goes in a subdirectory: the LOCO runners glob std_*.csv,
    # so a second MX file next to the primary one would silently become a fifth "country".
    out = positional[1] if len(positional) > 1 else (
        DEFAULT_OUT if BMI_MODE == "measured"
        else os.path.join(os.path.dirname(DEFAULT_OUT), "sensitivity", "std_MHAS_selfreport.csv"))
    import pyreadstat
    templates = [t for t, _ in MAP.values() if t]
    need = ([PID, "ragender", "raeducl", "r1wtresp"]
            + [f"r{n}iwy" for n in RELEASES]
            + [INTERVIEWED.format(n=n) for n in RELEASES]
            + [t.format(n=n) for t in templates for n in RELEASES]
            + [f"r{n}bmi" for n in RELEASES])
    need = sorted(set(need))
    df, _ = pyreadstat.read_dta(dta, usecols=[c for c in need])
    missing = [c for c in need if c not in df.columns]
    if missing:
        print(f"  !! columns absent from file: {missing}", file=sys.stderr)
    if PID not in df.columns:
        sys.exit(f"missing person identifier {PID!r} - aborting, not guessing an alternative")

    frames = []
    for n in RELEASES:
        cols = {"cohort": [COHORT] * len(df), "country": [COUNTRY] * len(df),
                "wave": [n] * len(df), "pid": df[PID].values}
        cols["interview_year"] = pd.to_numeric(df.get(f"r{n}iwy"), errors="coerce")
        cols["interviewed"] = pd.to_numeric(df.get(INTERVIEWED.format(n=n)), errors="coerce").eq(1)
        for concept, (tmpl, kind) in MAP.items():
            v = tmpl.format(n=n) if tmpl else None
            if v is None or v not in df.columns:
                if v is not None:
                    print(f"  !! {v} not in file -> {concept}=NaN", file=sys.stderr)
                cols[concept] = np.full(len(df), np.nan)
                continue
            cols[concept] = apply_recode(df[v].values, kind).values
        if BMI_MODE == "selfreport":
            self_bmi = apply_recode(df[f"r{n}bmi"].values, "cont").values
            cols["bmi"] = np.where(np.isnan(cols["bmi"]), self_bmi, cols["bmi"])
        frames.append(pd.DataFrame(cols))
    long = pd.concat(frames, ignore_index=True)

    mu, sd = long["income_pir"].mean(), long["income_pir"].std(ddof=0)
    long["income_pir"] = (long["income_pir"] - mu) / (sd if sd and np.isfinite(sd) else np.nan)

    # keep rows with a person id, adult age and a determinable stroke status (CHARLS rule + >=20)
    long = long[long["pid"].notna() & long["stroke"].isin([0, 1])
                & (long["age"] >= MIN_AGE)].copy()
    std = long[["cohort", "country", "wave", "pid"] + FEAT_COLS].copy()

    os.makedirs(os.path.dirname(out), exist_ok=True)
    std.to_csv(out, index=False)

    # ---- diagnostics: everything below is printed, never fabricated into the manuscript
    iv = pd.concat(frames, ignore_index=True)
    per_wave = iv.groupby("wave").agg(
        interviewed=("interviewed", "sum"),
        n_kept=("stroke", lambda s: int(((s.isin([0, 1])) & iv["interviewed"]).sum())),
        events=("stroke", lambda s: int(s.eq(1).sum())),
        iv_year=("interview_year", "median"),
    )
    per_wave["prev"] = (per_wave["events"] / per_wave["n_kept"]).round(4)
    struct = iv[iv["interviewed"] & iv["age"].notna() & (iv["age"] < MIN_ASK_AGE)]

    print(f"MHAS reshape -> {out}", file=sys.stderr)
    print(f"  respondent-wave rows kept: {len(std)} | unique persons: {std['pid'].nunique()}", file=sys.stderr)
    print(f"  stroke events: {int(std['stroke'].sum())} | prevalence: {std['stroke'].mean():.4f}", file=sys.stderr)
    print("  per-wave:", file=sys.stderr)
    print(per_wave.to_string(), file=sys.stderr)
    print(f"  age range of kept rows: {std['age'].min():.0f}-{std['age'].max():.0f} "
          f"(median {std['age'].median():.0f}); interviewed-but-under-{MIN_ASK_AGE} rows "
          f"dropped for undeterminable stroke: {len(struct)}", file=sys.stderr)
    print("  feature non-null % (of kept rows):", file=sys.stderr)
    print((std[FEAT_COLS].notna().mean() * 100).round(1).to_string(), file=sys.stderr)
    print("  prevalence of binary features:", file=sys.stderr)
    print((std[["stroke", "ever_smoker", "current_smoker", "alcohol", "hypertension",
                "diabetes", "heart_attack"]].mean() * 100).round(1).to_string(), file=sys.stderr)
    print("DECISION NOTES:", file=sys.stderr)
    print("  - r{n} series only; spouse s{n} series not appended (would double-count).", file=sys.stderr)
    print("  - letter-coded specials -> NaN, mirroring charls_reshape.py (no recoding of '.a').", file=sys.stderr)
    print("  - high_cholesterol ABSENT (only a screening-utilisation item exists).", file=sys.stderr)
    print(f"  - bmi = {'MEASURED only (primary)' if BMI_MODE == 'measured' else 'measured, backfilled with self-report (SENSITIVITY)'},"
          f" non-null {100 * std['bmi'].notna().mean():.1f}%.", file=sys.stderr)
    print("  - rows under age 20 dropped.", file=sys.stderr)
    print("  - heart_attack = specific 'ever had heart attack' (narrower than the CHARLS proxy).", file=sys.stderr)
    print(f"  - income_pir = within-MHAS z of log1p(household total assets); log sd = {sd:.4f}", file=sys.stderr)
    print(f"  - wrote {out}", file=sys.stderr)


if __name__ == "__main__":
    main()
