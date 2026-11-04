"""KLoSA respondent-wave table, v2 - rebuilds the five features that v1 (klosa_reshape.py)
miscoded, each fix traced to the official Gateway creation code or to the wave files.

WHY v2 EXISTS (measured on the data, not assumed). In v1's std_KLoSA.csv:
  * education  85.5% "tertiary"; waves 3-9 were 100% category 3. Real cause: `w{v}A003` is
    only filled in wave 1 (w3-w7 non-null count = 0, w8/w9 column absent), and v1's
    `s.where(...).map(lambda v: ...)` passes NaN *through the lambda*, where `NaN <= 4` is
    False, so every missing value became "3 = tertiary". The Gateway's own raeducl is built
    from the wave-1 A003 (lines 1376-1384 of `KLoSA Stata Creation Code.do`) and is
    time-invariant, so the fix is to read wave 1 and carry it forward by pid.
    Wave-1 A003 truth: {1-4} 62.4%, {5} 26.4%, {6-9} 11.2% - which is what Korean 45+ should look like.
  * alcohol    99.9%. v1 used `w{v}C119`, which the creation code defines as
    "R # cigarettes/day" (line 7043) - the wrong question entirely - and the same NaN-through-lambda
    bug turned every missing value into 1. The drinking item is `w{v}C122` ("drinks now", 1/5),
    present in all nine waves at 35-40% yes, plus `C111a` for wave 1 exactly as the Gateway combines them.
  * marital    wave 1 was 100% "not partnered" for the same reason: `w01marital` does not exist.
  * current_smoker  23.4% but ever_smoker 15.1%, with 823 impossible rows. C117 is asked only of
    ever-smokers in waves 1-4 and of everyone from wave 5; the Gateway closes the gap with the
    structural rule `smoken = 0 if C116 == 5` (line 7024), which v1 did not apply.
  * bmi        v1 set it NaN claiming no clean source. `w{v}C105` (weight, kg) and `w{v}C107`
    (height, cm) are present and fully non-null in ALL nine waves, and the Gateway computes
    r{wv}bmi from exactly those two (line 6739) with the plausibility window 20-140 kg / 100-200 cm.

Still NaN, now for a documented reason rather than an untested claim:
  * high_cholesterol - no cholesterol-diagnosis item is harmonised for KLoSA (CHARLS and MHAS
    are also NaN, so only NHANES observes this feature).
  * income_pir - `r{wv}itot` is the sum of six components (itearn + icap + ipena + igxfr +
    itothr + ipubpen), each rebuilt from bracketed income items with midpoint imputation and
    `_I` flags (`H_KLoSA_imputflag`). Reproducing that faithfully is a separate task, not a
    one-line lookup, so Korea's economic axis stays unobserved and is median-imputed from the
    training countries during LOCO - disclosed, not fabricated.

All recodes use dict/value maps, never a callable through Series.map(), so a missing value can
no longer be converted into a real category.

Unit = respondent x wave, as in v1. Usage: python klosa_reshape_v2.py [out_csv]
"""
import os, sys, numpy as np, pandas as pd, warnings
warnings.filterwarnings("ignore")

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.abspath(os.path.join(HERE, "..", "..", "..", "data", "raw", "intl", "KLoSA"))
OUT = os.path.abspath(os.path.join(HERE, "..", "..", "..",
                                   "data", "processed", "intl", "corrected", "std_KLoSA.csv"))
COHORT, COUNTRY = "KLoSA", "KR"
WAVES = list(range(1, 10))

YESNO = {1: 1.0, 5: 0.0}
SEX = {1: 1.0, 5: 2.0}
EDU = {1: 1.0, 2: 1.0, 3: 1.0, 4: 1.0, 5: 2.0, 6: 3.0, 7: 3.0, 8: 3.0, 9: 3.0}
MARR = {1: 1.0, 2: 2.0, 3: 2.0, 4: 2.0, 5: 2.0}
FEATS = ["stroke", "age", "sex", "education", "marital", "income_pir", "bmi", "ever_smoker",
         "current_smoker", "alcohol", "hypertension", "high_cholesterol", "diabetes",
         "heart_attack"]


def coded(s, mapping):
    """Numeric coercion + dict recode. Dict lookup returns NaN for NaN input, which is the
    whole point: a missing answer must never become a category."""
    s = pd.to_numeric(pd.Series(s), errors="coerce")
    return s.map(mapping)


def main():
    frames = []
    for wv in WAVES:
        p = f"w{wv:02d}"
        fn = os.path.join(BASE, f"w{wv:02d}_e.xlsx")
        if not os.path.exists(fn):
            print(f"  !! missing {fn}", file=sys.stderr); continue
        want = ["pid", f"{p}A003", f"{p}C105", f"{p}C107", f"{p}C111a", f"{p}C116", f"{p}C117",
                f"{p}C122", f"{p}marital", f"{p}gender1", f"{p}A001_age", f"{p}A002_age",
                f"{p}C006", f"{p}C011", f"{p}C033", f"{p}C038"]
        df = pd.read_excel(fn, engine="calamine",
                           usecols=lambda c: c in want)
        have = set(df.columns)
        missing_cols = [c for c in want if c not in have]
        if missing_cols:
            print(f"  w{wv:02d} absent columns (-> NaN, disclosed): {missing_cols}", file=sys.stderr)

        def col(name):
            return df[name] if name in df.columns else pd.Series(np.nan, index=df.index)

        agecol = f"{p}A001_age" if f"{p}A001_age" in have else f"{p}A002_age"
        c116, c117 = col(f"{p}C116"), col(f"{p}C117")
        c122, c111a = col(f"{p}C122"), col(f"{p}C111a")
        wt = pd.to_numeric(col(f"{p}C105"), errors="coerce")
        ht = pd.to_numeric(col(f"{p}C107"), errors="coerce")
        # Gateway plausibility window, then BMI = kg / m^2
        ok = wt.between(20, 140) & ht.between(100, 200)
        bmi = ((wt / (ht / 100.0) ** 2)).where(ok)

        # alcohol exactly as the Gateway combines the two items (the yes-rule is applied last)
        a, d = pd.to_numeric(c111a, errors="coerce"), pd.to_numeric(c122, errors="coerce")
        drink = pd.Series(np.nan, index=df.index)
        drink = drink.mask((a == 5) | (d == 5), 0.0)
        drink = drink.mask((a == 1) | (d == 1), 1.0)

        # current smoker: the item itself, then the structural 0 for never-smokers (Gateway rule)
        e, n = pd.to_numeric(c116, errors="coerce"), pd.to_numeric(c117, errors="coerce")
        smoken = coded(c117, YESNO).mask(e == 5, 0.0)

        row = {
            "cohort": [COHORT] * len(df), "country": [COUNTRY] * len(df),
            "wave": [wv] * len(df),
            "pid": pd.to_numeric(col("pid"), errors="coerce").values,
            "stroke": coded(col(f"{p}C038"), YESNO).values,
            "age": pd.to_numeric(col(agecol), errors="coerce").values,
            "sex": coded(col(f"{p}gender1"), SEX).values,
            "education": coded(col(f"{p}A003"), EDU).values,   # only wave 1 carries it; merged below
            "marital": coded(col(f"{p}marital"), MARR).values,
            "income_pir": np.full(len(df), np.nan),
            "bmi": bmi.values,
            "ever_smoker": coded(c116, YESNO).values,
            "current_smoker": smoken.values,
            "alcohol": drink.values,
            "hypertension": coded(col(f"{p}C006"), YESNO).values,
            "high_cholesterol": np.full(len(df), np.nan),
            "diabetes": coded(col(f"{p}C011"), YESNO).values,
            "heart_attack": coded(col(f"{p}C033"), YESNO).values,
        }
        frames.append(pd.DataFrame(row))
    long = pd.concat(frames, ignore_index=True)

    # education is a baseline, time-invariant attribute: carry the wave-1 value to every wave,
    # and fall back to a later wave's own value only for people absent from wave 1
    edu1 = (long.loc[long["wave"] == 1, ["pid", "education"]]
            .dropna(subset=["pid"]).drop_duplicates("pid").set_index("pid")["education"])
    long["education"] = long["pid"].map(edu1).fillna(long["education"])

    long = long[long["pid"].notna() & long["stroke"].isin([0, 1])].copy()
    std = long[["cohort", "country", "wave", "pid"] + FEATS].copy()
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    std.to_csv(OUT, index=False)

    print(f"KLoSA v2 reshape -> {OUT}", file=sys.stderr)
    print(f"  rows {len(std)} | persons {std['pid'].nunique()} | strokes {int(std.stroke.sum())} "
          f"(prev {std.stroke.mean():.4f})", file=sys.stderr)
    print("  education distribution:", std["education"].value_counts(dropna=False).sort_index().to_dict(), file=sys.stderr)
    print("  logical check current>ever rows:", int(((std.current_smoker == 1) & (std.ever_smoker == 0)).sum()), file=sys.stderr)
    print((std[FEATS].notna().mean() * 100).round(1).to_string(), file=sys.stderr)
    print("  prevalence of observed binaries:", file=sys.stderr)
    print((std[["alcohol", "ever_smoker", "current_smoker", "hypertension", "diabetes",
                "heart_attack"]].mean() * 100).round(1).to_string(), file=sys.stderr)
    print("  bmi mean (sd):", round(std.bmi.mean(), 2), round(std.bmi.std(), 2), file=sys.stderr)


if __name__ == "__main__":
    main()
