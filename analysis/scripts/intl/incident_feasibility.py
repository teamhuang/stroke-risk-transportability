"""Feasibility diagnostic for an INCIDENT-stroke (longitudinal) arm.

Read-only: it consumes the existing std_<COHORT>.csv tables and reports what a
first-event design would actually have to work with. It changes no analysis input and
writes no std file; output is a tally for results/reports/.

Definition used for the tally (deliberately simple, so the ceiling is what is measured):
  * a person enters follow-up at their FIRST wave with a determinable stroke status;
  * person is at risk if that entry status is 0 (no reported stroke yet);
  * an incident case = the first later wave with stroke == 1 for an at-risk person;
  * person-time proxy = number of wave-intervals observed before the event or exit.

Caveats quantified rather than assumed:
  * entries whose status was NOT determinable at any earlier wave are counted separately,
    because the chronic-disease block is asked only above an age threshold (CHARLS 45,
    MHAS 50), so a first determinable "yes" may be a prevalent case, not an incident one;
  * mortality is not in these tables, so a competing-risk denominator cannot be built here.
"""
import os, sys, glob, numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
D = os.path.abspath(os.path.join(HERE, "..", "..", "..", "data", "processed", "intl"))
OUT = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results", "reports"))


def tally(df):
    # wave is an ordinal label; NHANES stores cycle codes (_I/_J/_L) rather than integers
    if not pd.api.types.is_numeric_dtype(df["wave"]):
        order = {w: i for i, w in enumerate(sorted(df["wave"].unique()))}
        df["wave"] = df["wave"].map(order)
    df = df.sort_values(["pid", "wave"]).copy()
    n_waves = df.groupby("pid", sort=False)["wave"].size()
    # status at entry wave
    entry = df.drop_duplicates("pid", keep="first").set_index("pid")
    at_risk = entry[entry["stroke"] == 0]
    ev_rows = []
    for pid, sub in df.groupby("pid", sort=False):
        s = sub["stroke"].values
        w = sub["wave"].values
        nz = np.flatnonzero(s == 1)
        if s[0] != 0:
            continue
        if len(nz) == 0:
            ev_rows.append((pid, 0, w[-1] - w[0], np.nan))
        else:
            k = nz[0]
            ev_rows.append((pid, 1, w[k] - w[0], w[k]))
    ev = pd.DataFrame(ev_rows, columns=["pid", "incident", "follow_waves", "event_wave"])
    per_wave_first = df.drop_duplicates("pid", keep="first")["wave"].value_counts().sort_index()
    return {
        "persons": int(df["pid"].nunique()),
        "person_waves": int(len(df)),
        "waves_observed": f"{int(df.wave.min())}-{int(df.wave.max())}",
        "at_entry_stroke0": int(len(at_risk)),
        "at_entry_stroke1": int((entry["stroke"] == 1).sum()),
        "incident_cases": int(ev["incident"].sum()),
        "incident_rate_per_person": round(float(ev["incident"].mean()), 4),
        "median_follow_waves_at_risk": float(ev.loc[ev.follow_waves > 0, "follow_waves"].median()),
        "max_follow_waves": int(ev["follow_waves"].max()),
        "persons_2plus_waves": int((n_waves >= 2).sum()),
        "incidence_per_1000_wave_yrs": round(
            1000 * ev["incident"].sum() / max(ev["follow_waves"].sum(), 1), 1),
        "entry_by_wave": {int(k): int(v) for k, v in per_wave_first.items()},
    }


def main():
    os.makedirs(OUT, exist_ok=True)
    if len(sys.argv) > 1:
        globals()["D"] = os.path.abspath(sys.argv[1])
    files = sorted(glob.glob(os.path.join(D, "std_*.csv")))
    print("pool:", D)
    rows = []
    for f in files:
        coh = os.path.basename(f)[4:-4]
        df = pd.read_csv(f, usecols=["pid", "wave", "stroke"])
        t = tally(df)
        t["cohort"] = coh
        rows.append(t)
        print(f"\n=== {coh} ===")
        for k, v in t.items():
            if k != "cohort":
                print(f"  {k:28s} {v}")
    out = pd.DataFrame(rows)[["cohort", "persons", "person_waves", "waves_observed",
                              "at_entry_stroke0", "at_entry_stroke1", "incident_cases",
                              "incident_rate_per_person", "incidence_per_1000_wave_yrs",
                              "median_follow_waves_at_risk", "max_follow_waves",
                              "persons_2plus_waves", "entry_by_wave"]]
    out.to_csv(os.path.join(OUT, "incident_feasibility_tally.csv"), index=False)
    print("\nwrote", os.path.join(OUT, "incident_feasibility_tally.csv"))
    # pooled view: 14 features -> events-per-variable ceiling for a Cox / logistic-incident model
    tot = out["incident_cases"].sum()
    print(f"\npooled incident events across cohorts = {tot} -> EPV on 14 features = {tot/14:.1f}")


if __name__ == "__main__":
    main()
