"""Incident-stroke person-period (discrete-time) expansion for the longitudinal arm.

Why this exists
---------------
The prevalent arm scores "has anyone ever reported a stroke", which is not the clinical task a
risk model is asked to solve. This script rebuilds the same harmonised cohorts as a first-event
design: every row is one PERSON x ONE OBSERVATION INTERVAL, the outcome is the first reported
stroke inside that interval, and an interval ends in stroke, death, or censoring.

Sources, and why they are mixed the way they are
------------------------------------------------
* Features come from the ALREADY-AUDITED `corrected/std_<COHORT>.csv` tables (one row per
  respondent x wave, shared coding, plausibility rules applied). Nothing is re-derived here.
* Calendar time and VITAL STATUS come from a separate extract per cohort, because the std tables
  carry a wave LABEL, not a date, and they keep only rows with a determinable stroke answer -
  which is exactly the information needed to say what happened AFTER the last interview:
    CHARLS  r{n}iwy / r{n}iwm, r{n}iwstat, respondent death radyear / radmonth
    MHAS    r{n}iwy / r{n}iwm, r{n}iwstat, respondent death radyear / radmonth
    KLoSA   w0{n}mniw_y / _m / _d and NO vital-status or death field in any of the nine main
            wave workbooks (verified column by column; the only death data sits in the
            w0{2..8}_exit_e exit files, which are not on disk).
    HRS     `hrs_times.csv`, written by intl/hrs_reshape.py from RAND HRS 1992-2022: R{w}IWMID is
            a day-precision interview date, R{w}IWSTAT separates "non-response but alive" from
            "died this wave" / "died previous wave" / "dropped from the sample", and RADDATE is a
            day-precision date of death taken from the Tracker file. HRS is therefore the only
            panel here that does not have to fall back on wave fieldwork windows for a decedent,
            which is also why the US arm is RAND HRS and not the gateway gate file (release D
            carries neither a death date nor an interview-status item).

Why iwstat and not just the death date
--------------------------------------
`radyear` is nearly empty in CHARLS (402 of 25,586 respondents, and it stops at 2014, i.e. two
waves short of the panel's end), so a design censored only on death DATES would silently treat
most Chinese deaths as ordinary attrition. The interview-status item is the field the panels
actually use. CHARLS/MHAS code it 4 = non-response but ALIVE, 5 = died this wave, 6 = died
previous wave, 9 = vital status unknown; RAND HRS codes the same four states as 4, 5, 6 and adds
7 = dropped from the sample, which is neither a death nor follow-up time and credits no exposure.
Death is therefore known even where its date is not, and that knowledge is what makes the
competing risk observable.

Rules, each one checkable in the output
---------------------------------------
1. A person enters follow-up at their FIRST determinable stroke observation; entering with
   stroke == 1 is a PREVALENT case and is excluded, never counted as an event.
2. Intervals run between consecutive determinable observations in DATE order. A person who skips
   a wave contributes one longer interval, flagged with gap_waves > 1.
3. An interval is an event (event=1, end_status="stroke") iff stroke == 1 at its closing
   observation.
4. Both endpoints of a within-panel interval are real interviews, so a stroke answer there is an
   event; a death date earlier than a person's last dated interview is treated as a contradiction
   (counted in the diagnostics, not used), because an answer the respondent gave outweighs a
   person-level date field.
5. Tail censoring after the last determinable observation:
      known death date later than it -> end_status="death_dated", interval ends AT that date
      later record with iwstat 5/6  -> end_status="death_status", interval ends at the MIDPOINT
      between the last date known alive and the date death was found (the full gap would
      over-credit exposure; cutting at the last interview would under-count it)
      iwstat 4 (alive, refused)     -> exposure credited to that date, end_status="alive_nr"
      iwstat 9                      -> end_status="vital_status_unknown"
      nothing later                 -> end_status="administrative_end", no extra interval
   Korea can only ever reach the last branch, and every Korean row carries
   censor_mode="last_interview".
6. Covariates are those of the interval-START wave (lagged, so nothing measured after the event
   can enter a risk set), plus elapsed time since cohort entry.
7. Exposure is elapsed years: date = year + (month - 0.5)/12, mid-year when the month is missing.
   The day field is used for Korea only.

What this design CANNOT fix, and does not claim to
--------------------------------------------------
* Interval censoring: "ever had a stroke" at wave k+1 dates the event only to (k, k+1].
* Fatal stroke: a death from stroke between interviews lands in the death branch, so the incident
  count is a LOWER bound. death-terminated intervals are reported per cohort so the size of that
  bias is visible rather than assumed, and the Korea/China/Mexico asymmetry is disclosed.
* NHANES cannot appear at all: its cycles are independent cross-sectional samples of different
  people, so it has no within-person follow-up and contributes zero intervals. The United States
  in this design is RAND HRS, a genuine 16-wave panel; NHANES stays only as the cross-sectional
  comparator in the supplementary prevalence arm.
"""
import os, sys, json, numpy as np, pandas as pd, warnings
warnings.filterwarnings("ignore")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
STD = os.path.join(ROOT, "data", "processed", "intl", "corrected")
OUTDIR = os.path.join(ROOT, "data", "processed", "intl", "incident")

FEATS = ["stroke", "age", "sex", "education", "marital", "income_pir", "bmi", "ever_smoker",
         "current_smoker", "alcohol", "hypertension", "high_cholesterol", "diabetes",
         "heart_attack"]
DEATH_CODES, ALIVE_NR, DK_STATUS = {5.0, 6.0}, {4.0}, {9.0}
DROPPED_FROM_SAMPLE = {7.0}   # RAND HRS only: out of the study, not a death, earns no exposure

SPECS = {
    "CHARLS": dict(country="CN", dta=os.path.join(ROOT, "data", "raw", "intl", "CHARLS",
                                                  "H_CHARLS_D_Data.dta"),
                  pid="ID", waves=[1, 2, 3, 4], censor="death"),
    "MHAS": dict(country="MX", dta=os.path.join(ROOT, "H_MHAS_d.dta"),
                 pid="rahhidnp", waves=[1, 2, 3, 4, 5, 6], censor="death"),
    "KLoSA": dict(country="KR", dta=None, waves=list(range(1, 10)), censor="last_interview"),
    # RAND HRS is read once by intl/hrs_reshape.py, which writes this small extract; re-scanning
    # a 7.2 GB SAS file for every downstream rerun would be the expensive part, not the design.
    "HRS": dict(country="US", times=os.path.join(OUTDIR, "hrs_times.csv"),
                waves=list(range(1, 17)), censor="death"),
}


def to_num(s):
    return pd.to_numeric(pd.Series(list(s)), errors="coerce").reset_index(drop=True)


def col(df, name):
    """Column if present, else an all-NaN column of the right length: an absent time field must
    become a disclosed missing date, never a zero."""
    if name in df.columns:
        return df[name]
    return pd.Series(np.nan, index=df.index)


def decimal_date(year, month, day=None):
    """Continuous-time year. Mid-month when only year+month exist, mid-year when the month is
    missing, so an unknown month never becomes January (which would shorten every later interval)."""
    y, m = to_num(year), to_num(month)
    m = m.where(m.between(1, 12))
    frac = (m - 0.5) / 12.0
    if day is not None:
        d = to_num(day)
        frac = frac.fillna((((d.where(d.between(1, 31)) - 0.5) / 30.0) / 12.0))
    frac = frac.fillna(6.5 / 12.0)
    return (y + frac).where(y.notna())


# ---------------------------------------------------------------- times + vital status
def times_gate(cohort, spec):
    """CHARLS and MHAS share the harmonised gate layout: r{n}iwy/r{n}iwm/r{n}iwstat +
    respondent death radyear/radmonth."""
    import pyreadstat
    want = [spec["pid"], "radyear", "radmonth"]
    for n in spec["waves"]:
        want += [f"r{n}iwy", f"r{n}iwm", f"r{n}iwstat", f"r{n}wtresp"]
    want = list(dict.fromkeys(want))
    with pd.io.stata.StataReader(spec["dta"]) as r:
        present = set(r.variable_labels())
    absent = [w for w in want if w not in present]
    if absent:
        print(f"  {cohort}: fields absent from gate -> NaN: {absent}", file=sys.stderr)
    df, _ = pyreadstat.read_dta(spec["dta"], usecols=[w for w in want if w in present])
    pid = to_num(col(df, spec["pid"]))
    rows = []
    for n in spec["waves"]:
        rows.append(pd.DataFrame({
            "pid": pid.values, "wave": float(n),
            "t": decimal_date(col(df, f"r{n}iwy"), col(df, f"r{n}iwm")).values,
            "iwstat": to_num(col(df, f"r{n}iwstat")).values,
            "tdeath": decimal_date(col(df, "radyear"), col(df, "radmonth")).values,
            "wt": to_num(col(df, f"r{n}wtresp")).values}))
    out = pd.concat(rows, ignore_index=True)
    out["cohort"] = cohort
    return out


def times_klosa():
    """KLoSA lives in nine original-wave workbooks. Interview date is per respondent; there is
    no vital-status or death field to read, hence iwstat stays NaN."""
    base = os.path.join(ROOT, "data", "raw", "intl", "KLoSA")
    rows = []
    for wv in SPECS["KLoSA"]["waves"]:
        p = f"w{wv:02d}"
        fn = os.path.join(base, f"{p}_e.xlsx")
        if not os.path.exists(fn):
            print(f"  !! missing {fn}", file=sys.stderr); continue
        want = ["pid", f"{p}mniw_y", f"{p}mniw_m", f"{p}mniw_d", f"{p}wgt_p"]
        df = pd.read_excel(fn, engine="calamine", usecols=lambda c: c in want)
        rows.append(pd.DataFrame({
            "cohort": ["KLoSA"] * len(df), "pid": to_num(col(df, "pid")).values,
            "wave": float(wv),
            "t": decimal_date(col(df, f"{p}mniw_y"), col(df, f"{p}mniw_m"),
                              col(df, f"{p}mniw_d")).values,
            "iwstat": np.nan, "tdeath": np.nan,
            "wt": to_num(col(df, f"{p}wgt_p")).values}))
    return pd.concat(rows, ignore_index=True)


def times_extract(spec):
    """A pre-built time/vital-status extract, used for RAND HRS. Dates here are already decimal
    years computed from day-precision SAS dates, so the wave-fieldwork fallback below is a
    backstop for HRS rather than the main route as it is for CHARLS and MHAS."""
    df = pd.read_csv(spec["times"])
    out = df[["cohort", "pid", "wave", "t", "iwstat", "tdeath", "wt"]].copy()
    for c in ("pid", "wave", "t", "iwstat", "tdeath", "wt"):
        out[c] = to_num(out[c])
    return out


# ---------------------------------------------------------------- expansion
def wave_nominal(panel):
    """Median interview date of the DATED records in each wave. Needed because a death-coded record
    (iwstat 5/6) has NO fieldwork date of its own - verified: 0 of 3,581 CHARLS and 0 of 22,036
    MHAS such records carry r{n}iwy - so the wave's own fieldwork window is the only calendar
    information available for it."""
    med = panel[panel["t"].notna()].groupby("wave")["t"].median()
    nominal = {float(w): float(v) for w, v in med.items()}
    return nominal, float(panel["t"].median(skipna=True))


def tail_interval(last, later, censor_mode, nominal, fallback_year):
    """What happens after the last determinable stroke observation. `later` is that person's
    remaining wave records in wave order.

    radyear/radmonth are PERSON-level fields: a decedent carries the same death date on every row,
    so death can be known with a date even where the death wave itself is undated. Where it is not,
    iwstat 5/6 still bounds the death inside (last date known alive, that wave's fieldwork window),
    and the window midpoint is used - the full gap would over-credit exposure, and cutting at the
    last interview would under-count it."""
    dd = last["tdeath"]
    if pd.notna(dd) and dd > last["t"]:
        return dict(t_end=dd, end_status="death_dated"), "death_dated"
    known_alive = last["t"]
    status, end_t = "administrative_end", None
    for _, r in later.iterrows():
        s = r["iwstat"]
        t = r["t"] if pd.notna(r["t"]) else nominal.get(float(r["wave"]), fallback_year)
        if s in DEATH_CODES:
            if pd.isna(t) or t <= known_alive:
                continue
            end_t, status = (known_alive + t) / 2.0, "death_status"
            break
        if s in DK_STATUS:
            # vital status genuinely unknown: no extra exposure may be credited either way
            end_t, status = known_alive, "vital_status_unknown"
            break
        if s in ALIVE_NR:
            if pd.notna(t) and t > known_alive:
                known_alive, end_t, status = t, t, "alive_nr"
            continue
        if s in DROPPED_FROM_SAMPLE:
            # RAND HRS: out of the study, which is neither a death nor follow-up time, so it
            # credits no exposure. The scan still continues - the Tracker file can ascertain a
            # death in a later wave for somebody the core interview stopped following.
            continue
        if censor_mode == "last_interview":
            break
    if end_t is None or end_t <= last["t"]:
        return None, status
    return dict(t_end=end_t, end_status=status), status


def row_from(start, k, t_end, event, status, wave_end, gap_waves, entry_t, cohort, censor_mode):
    r = {"pid": start["pid"], "cohort": cohort, "k": k, "t_start": start["t"], "t_end": t_end,
         "exposure_years": t_end - start["t"], "event": event, "end_status": status,
         "wave_start": start["wave"], "wave_end": wave_end, "gap_waves": gap_waves,
         "t_since_entry_years": start["t"] - entry_t,
         "censor_mode": censor_mode, "wt_start": start["wt"]}
    for f in FEATS:
        if f != "stroke":
            r[f] = start[f]
    return r


def expand(panel, cohort, censor_mode, acc, nominal, fallback_year):
    out = []
    obs = panel[(panel["stroke"].isin([0, 1])) & panel["t"].notna()].sort_values(["t", "wave"])
    if len(obs) == 0:
        acc["no_determinable_stroke"] += 1
        return out
    if obs["stroke"].iloc[0] == 1:
        acc["prevalent_at_entry"] += 1
        return out
    acc["at_risk_persons"] += 1
    entry_t = obs["t"].iloc[0]
    n = len(obs)
    acc["observations_per_at_risk_person"] += n
    if n == 1:
        acc["at_risk_with_single_observation"] += 1
    stopped = False
    for k in range(n - 1):
        a, b = obs.iloc[k], obs.iloc[k + 1]
        # both endpoints are real interviews, so a stroke answer inside the interval is an event;
        # a death date earlier than b is a data inconsistency (counted in the diagnostics), not a
        # reason to discard an answer the respondent actually gave
        end, ev, status = b["t"], int(b["stroke"] == 1), ("stroke" if b["stroke"] == 1 else "continued")
        out.append(row_from(a, k + 1, end, ev, status, int(b["wave"]),
                            int(b["wave"] - a["wave"]), entry_t, cohort, censor_mode))
        if ev:
            stopped = True
            break
    if stopped:
        return out
    last = obs.iloc[-1]
    later = panel[panel["wave"] > last["wave"]].sort_values("wave")
    tail, status = tail_interval(last, later, censor_mode, nominal, fallback_year)
    acc["tail_" + status] = acc.get("tail_" + status, 0) + 1
    if tail:
        out.append(row_from(last, len(out) + 1, tail["t_end"], 0, tail["end_status"],
                            int(last["wave"]), 0, entry_t, cohort, censor_mode))
    return out


def build(cohort):
    spec = SPECS[cohort]
    std = pd.read_csv(os.path.join(STD, f"std_{cohort}.csv"))
    std["pid"], std["wave"] = to_num(std["pid"]), to_num(std["wave"])
    if cohort == "KLoSA":
        tt = times_klosa()
    elif "times" in spec:
        tt = times_extract(spec)
    else:
        tt = times_gate(cohort, spec)
    tt["pid"], tt["wave"] = to_num(tt["pid"]), to_num(tt["wave"])
    n_dup = int(tt.duplicated(["pid", "wave"]).sum())
    tt = tt.drop_duplicates(["pid", "wave"], keep="first")
    keep = std["pid"].dropna().unique()
    tt = tt[tt["pid"].isin(keep)]
    panel = tt.merge(std.drop(columns=["cohort", "country"]), on=["pid", "wave"], how="left")
    panel = panel.sort_values(["pid", "t", "wave"]).reset_index(drop=True)

    acc = {k: 0 for k in ["no_determinable_stroke", "prevalent_at_entry", "at_risk_persons",
                          "at_risk_with_single_observation", "observations_per_at_risk_person",
                          "tail_administrative_end", "tail_death_dated", "tail_death_status",
                          "tail_alive_nr", "tail_vital_status_unknown"]}
    rows, bad_order = [], 0
    nominal, fallback_year = wave_nominal(panel)
    for pid, g in panel.groupby("pid", sort=False):
        gg = g[g["t"].notna()].sort_values(["t", "wave"])
        if (gg["wave"].diff().dropna() < 0).any():
            bad_order += 1
        rows.extend(expand(g, cohort, spec["censor"], acc, nominal, fallback_year))
    pp = pd.DataFrame(rows)
    pp = pp[pp["exposure_years"] > 0].copy() if len(pp) else pp

    # a person-level death date EARLIER than that person's last dated interview is contradictory;
    # it is counted, never silently used, because the interview answer is the stronger evidence
    lt = panel[panel["t"].notna()].groupby("pid")["t"].max()
    dt = panel.groupby("pid")["tdeath"].max()
    both = dt.notna() & lt.reindex(dt.index).notna()
    contradict = int((both & (dt < lt.reindex(dt.index) - 1e-9)).sum())

    diag = {"cohort": cohort, "country": spec["country"], "censor_mode": spec["censor"],
            "wave_records_in_panel": int(len(panel)),
            "duplicate_person_wave_time_rows_dropped": n_dup,
            "persons_ever_interviewed": int(panel["pid"].nunique()),
            "date_coverage_of_wave_records": round(float(panel["t"].notna().mean()), 4),
            "iwstat_coverage_fraction": (round(float(panel["iwstat"].notna().mean()), 4)
                                    if spec["censor"] == "death" else None),
            "death_date_coverage_fraction": (round(float(panel["tdeath"].notna().mean()), 4)
                                         if spec["censor"] == "death" else None),
            "weight_nonnull_pct_of_wave_records": round(float(panel["wt"].notna().mean()), 4),
            "persons_whose_death_precedes_last_dated_interview": contradict,
            "persons_dated_wave_order_disagreeing_with_time_order": bad_order,
            "acc": acc,
            "wave_nominal_dates": {str(int(k)): round(v, 3) for k, v in sorted(nominal.items())},
            "median_waves_per_at_risk_person": round(acc["observations_per_at_risk_person"]
                                                     / max(acc["at_risk_persons"], 1), 3)}
    if len(pp):
        ev, py = pp["event"].sum(), pp["exposure_years"].sum()
        w = pp["wt_start"]; okw = w.notna() & (w > 0)
        diag.update({
            "at_risk_persons_with_intervals": int(pp["pid"].nunique()),
            "intervals": int(len(pp)), "incident_events": int(ev),
            "intervals_ending_in_death": int(pp["end_status"].isin(
                ["death_dated", "death_status"]).sum()),
            "person_years": round(float(py), 1),
            "median_interval_years": round(float(pp["exposure_years"].median()), 3),
            "p95_interval_years": round(float(pp["exposure_years"].quantile(.95)), 3),
            "max_interval_years": round(float(pp["exposure_years"].max()), 3),
            "gap_waves_gt_1_pct": round(float((pp["gap_waves"] > 1).mean()), 4),
            "intervals_with_usable_design_weight_pct": round(float(okw.mean()), 4),
            "intervals_with_zero_design_weight": int((w == 0).sum()),
            "intervals_with_null_design_weight": int(w.isna().sum()),
            "incidence_per_1000py_unweighted": round(1000.0 * ev / py, 2),
            "incidence_per_1000py_design_weighted": (round(
                1000.0 * (pp.loc[okw, "event"] * w[okw]).sum()
                / (pp.loc[okw, "exposure_years"] * w[okw]).sum(), 2)) if okw.any() else None,
            "end_status_counts": pp["end_status"].value_counts().to_dict(),
            "feature_missing_pct": {f: round(float(pp[f].isna().mean()), 4)
                                    for f in FEATS if f != "stroke"},
            "interval_calendar_range": [float(pp["t_start"].min()), float(pp["t_end"].max())],
            "events_by_attained_age_band": pp.assign(
                band=pd.cut(pp["age"] + pp["exposure_years"], [19, 54, 64, 74, 84, 200],
                            labels=["20-54", "55-64", "65-74", "75-84", "85+"])
            ).groupby("band", observed=True)["event"].sum().astype(int).to_dict()})
    os.makedirs(OUTDIR, exist_ok=True)
    pp.to_csv(os.path.join(OUTDIR, f"personperiod_{cohort}.csv"), index=False)
    print(f"  {cohort}: persons={diag.get('at_risk_persons_with_intervals', 0)} "
          f"intervals={len(pp)} events={int(pp['event'].sum()) if len(pp) else 0}", file=sys.stderr)
    return pp, diag


def main():
    only = sys.argv[1:] or list(SPECS)
    os.makedirs(OUTDIR, exist_ok=True)
    dpath = os.path.join(OUTDIR, "personperiod_diagnostics.json")
    diags = {}
    if os.path.exists(dpath):                       # a partial run must not erase the others
        try:
            diags = {d["cohort"]: d for d in json.load(open(dpath, encoding="utf-8"))}
        except Exception:
            diags = {}
    for c in only:
        _, d = build(c)
        diags[c] = d
    parts = [pd.read_csv(os.path.join(OUTDIR, f"personperiod_{c}.csv")) for c in SPECS
             if os.path.exists(os.path.join(OUTDIR, f"personperiod_{c}.csv"))]
    pd.concat(parts, ignore_index=True).to_csv(
        os.path.join(OUTDIR, "personperiod_pooled.csv"), index=False)
    with open(dpath, "w", encoding="utf-8") as f:
        json.dump([diags[c] for c in SPECS if c in diags], f, indent=2, ensure_ascii=False,
                  default=str)
    for c in only:
        print(json.dumps(diags[c], indent=2, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
