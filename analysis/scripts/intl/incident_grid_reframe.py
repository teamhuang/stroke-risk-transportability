"""Re-frame the person-interval file on a FIXED interval grid, for the link-function arm.

The reviewer's structural worry, verbatim:

  "不同国家随访间隔差异很大" - the panels do not share a follow-up grid (median interval 2.00 yr
  in KLoSA and HRS, 2.08 in CHARLS, 3.00 in MHAS, with tails out to 16-21 yr), and the primary
  model puts `exposure_years` in as a covariate with a logistic link. A discrete-time model fitted
  that way is not guaranteed to answer the same question as the same model fitted on a finer grid,
  so the four-year risk could in principle be an artefact of how each panel happens to slice
  follow-up rather than of what the panels contain.

Each natural interval of length L is cut into n = ceil(L / delta) equal sub-intervals of length
L / n, so every row the model then sees is at most `delta` years long and every panel is written on
the SAME grid.

WHERE THE EVENT GOES IS THE WHOLE POINT, AND IT IS NOW AN EXPLICIT, VARIED DIMENSION. An earlier
version of this script put the interval-censored stroke on the parent's LAST sub-interval and
defended it on the grounds that the unsplit discrete-time likelihood already behaves that way. That
defence is withdrawn: the raw data says only "stroke between the two interviews", so asserting the
last piece asserts "event-free through the first n-1 pieces, stroke in the last one" - timing the
panel does not report. A grid arm built that way changes the event-time model at the same moment as
the grid, and its numbers cannot be read as a grid sensitivity check. Three allocations are
therefore produced, and the arm is only interpretable if its conclusions hold under all three:

  uniform   every sub-interval of the parent window carries fractional event weight 1/n, so the
            likelihood states "stroke somewhere in this window, uniformly" and invents no date. This
            is the uniform-within-interval assumption the `cif_mid` estimand already declares,
            written into the likelihood instead of into an assumed event day, and it is the PRIMARY
            allocation of this arm.
  last      the event on the parent's last sub-interval. This is the convention the UNSPLIT
            discrete-time likelihood implies, so it is the like-for-like grid comparison - and the
            one that assumes more than the data supports. Kept precisely so that "refined the grid"
            and "changed the event-time model" can be told apart rather than conflated.
  midcell   the event in the single sub-interval containing the parent midpoint, with the pieces
            after it dropped because a person is not at risk after their own stroke. The closest
            discrete-time reading of the declared midpoint DATE, at the cost of shortening follow-up
            for exactly the stroke-terminated persons - by how much is reported, not hidden.

Deaths and non-response tails are NOT interval-censored in these files: the person-period builder
puts `t_end` at the death date or at the last contact, so their terminal status legitimately stays on
the parent's last sub-interval under every allocation.

Covariates are the parent interval's start covariates, carried onto every sub-row, so the model never
sees a value that was not available at the parent's start. A fractional outcome is emitted in the
equivalent weighted 0/1 form - an event row of weight 1/n beside a non-event row of weight 1 - 1/n -
so no estimator has to understand non-integer labels and `row_weight` is just a sample weight.

The estimation target is unchanged and evaluation always uses the horizon frame built from the
ORIGINAL person-period file (`incident_cloglog.py --frame-pp`), so the arms are scored on identical
persons with identical labels and identical IPCW weights. A grid file must never be used to build a
horizon frame: its interval midpoints are finer-grained than the parent's, so `person_clock` would
date a stroke up to half a grid step away from where the primary frame dates it.

Self-checks, all hard assertions (the script dies rather than write a bad file): the number of
persons and the TOTAL EVENT WEIGHT are preserved exactly; no window carries more than one unit of
event; every dated death / non-response tail keeps its terminal status on exactly one row; no
sub-interval exceeds delta and none is non-positive; no row weight is zero or negative; under
`uniform` and `last` total person-time, per-person follow-up and per-person last observed date are
preserved; under `midcell` follow-up may only shorten; and the persons carrying a stroke are the same
persons in every allocation.

Usage
  python incident_grid_reframe.py [--delta 1] [--alloc uniform|last|midcell]
                                  [--pp personperiod_pooled.csv]
"""
import os, sys, json, numpy as np, pandas as pd, warnings
warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)
import run_incident_loco as I

OUT = I.OUT
REP = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results", "reports"))
ALLOCS = ("uniform", "last", "midcell")
DATED_TERMINAL = ("death_dated", "death_status", "alive_nr", "vital_status_unknown")


def flag(name, default):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default


def pw(f, w):
    """Weighted person-time per person, for the assertions below."""
    return f.assign(pw=f["exposure_years"].to_numpy(dtype=float) * w).groupby(
        ["cohort", "pid"])["pw"].sum()


def split(d, delta, alloc):
    """Interval -> sub-interval expansion under one stated event-time allocation.

    Returns (rows carrying a row_weight column, sub-counts, total event weight, dropped person-years).
    """
    L = pd.to_numeric(d["exposure_years"], errors="coerce").to_numpy(dtype=float)
    s = pd.to_numeric(d["t_since_entry_years"], errors="coerce").to_numpy(dtype=float)
    t0 = pd.to_numeric(d["t_start"], errors="coerce").to_numpy(dtype=float)
    ev = d["event"].to_numpy(dtype=int)
    st = d["end_status"].to_numpy()
    entry = t0 - s
    if not np.all(np.isfinite(L)) or np.any(L <= 0):
        raise AssertionError("every interval needs a finite positive exposure before splitting")
    if bool(((st == "stroke") != (ev == 1)).any()):
        raise AssertionError("the event flag and end_status='stroke' disagree")
    n = np.maximum(1, np.ceil(L / float(delta)).astype(np.int64))
    j_mid = n // 2                                   # the piece containing the parent midpoint
    keep_n = np.where((ev == 1) & (alloc == "midcell"), j_mid + 1, n)
    total = int(keep_n.sum())
    grp = np.repeat(np.arange(len(d)), keep_n)
    first = np.concatenate(([0], np.cumsum(keep_n)[:-1]))
    j = np.arange(total, dtype=np.int64) - np.repeat(first, keep_n)
    sub = L[grp] / n[grp]
    last_kept = (j == keep_n[grp] - 1)
    parent_ev = ev[grp] == 1
    if alloc == "last":
        q = np.where(parent_ev & last_kept, 1.0, 0.0)
    elif alloc == "uniform":
        q = np.where(parent_ev, 1.0 / n[grp], 0.0)
    elif alloc == "midcell":
        q = np.where(parent_ev & last_kept, 1.0, 0.0)
    else:
        raise ValueError(f"unknown allocation {alloc!r}, expected one of {ALLOCS}")
    base = d.iloc[grp].reset_index(drop=True).copy()
    s_new = s[grp] + j * sub
    e_new = entry[grp] + s_new
    base["t_since_entry_years"] = s_new
    base["t_start"] = e_new
    base["exposure_years"] = sub
    base["t_end"] = e_new + sub
    # every cell is emitted twice when it carries part of an event: a non-event row of weight 1-q and
    # an event row of weight q. A cell with q=1 is simply an event row, and q=0 simply a risk-set row.
    base["end_status"] = np.where(parent_ev | ~last_kept, "continued", st[grp])
    base["event"] = 0
    base["row_weight"] = 1.0 - q
    base = base.loc[base["row_weight"] > 0].reset_index(drop=True)
    kq = q > 0
    ev_rows = d.iloc[grp[kq]].reset_index(drop=True).copy()
    ev_rows["t_since_entry_years"] = s_new[kq]
    ev_rows["t_start"] = e_new[kq]
    ev_rows["exposure_years"] = sub[kq]
    ev_rows["t_end"] = (e_new + sub)[kq]
    ev_rows["end_status"] = "stroke"
    ev_rows["event"] = 1
    ev_rows["row_weight"] = q[kq]
    out = pd.concat([base, ev_rows], ignore_index=True)
    out = out.sort_values(["cohort", "pid", "t_since_entry_years", "t_end", "event"],
                          kind="stable").reset_index(drop=True)
    out["k"] = out.groupby(["cohort", "pid"], sort=False).cumcount().add(1)
    dropped = float(np.sum((n - keep_n) * (L / n)))
    return out, n, float(q.sum()), dropped


def main():
    delta = float(flag("--delta", "1"))
    alloc = flag("--alloc", "uniform")
    src = flag("--pp", "personperiod_pooled.csv")
    d = pd.read_csv(os.path.join(OUT, src))
    d = d.sort_values(["cohort", "pid", "k"]).reset_index(drop=True)

    # the split clock is only a person clock if entry_t is a person constant
    chk = d.assign(entry=d["t_start"] - d["t_since_entry_years"])
    spread = chk.groupby(["cohort", "pid"])["entry"].agg(lambda v: float(np.ptp(v.to_numpy())))
    assert float(spread.max()) < 1e-9, "t_start - t_since_entry_years is not constant within a person"

    def tally(f, w=None):
        w = np.ones(len(f)) if w is None else np.asarray(w, dtype=float)
        e = (f["event"] == 1).to_numpy()
        return {"rows": int(len(f)),
                "persons": int(f[["cohort", "pid"]].drop_duplicates().shape[0]),
                "event_rows": int(e.sum()),
                "stroke_persons": int(f.loc[e, ["cohort", "pid"]].drop_duplicates().shape[0]),
                "event_weight": round(float(w[e].sum()), 4),
                "person_years": round(float((f["exposure_years"].to_numpy(dtype=float) * w).sum()), 1),
                "median_interval_years": round(float(f["exposure_years"].median()), 3),
                "max_interval_years": round(float(f["exposure_years"].max()), 3),
                "dated_terminal_counts": {str(a): int(b) for a, b in
                                          f[f["end_status"].isin(DATED_TERMINAL)]
                                          ["end_status"].value_counts().items()}}
    before = tally(d)
    out, n_sub, ev_w, dropped = split(d, delta, alloc)
    w = out["row_weight"].to_numpy(dtype=float)
    after = tally(out, w)
    assert after["persons"] == before["persons"], "splitting changed the set of persons"
    assert abs(after["event_weight"] - before["event_weight"]) < 1e-4, \
        "the total event weight changed: an event was created or destroyed"
    assert after["stroke_persons"] == before["stroke_persons"], "a stroke moved between persons"
    assert after["dated_terminal_counts"] == before["dated_terminal_counts"], \
        f"a dated terminal status moved: {before['dated_terminal_counts']} -> " \
        f"{after['dated_terminal_counts']}"
    assert float(out["exposure_years"].max()) <= delta + 1e-9, "a sub-interval exceeds the grid"
    assert float(out["exposure_years"].min()) > 0, "a sub-interval has non-positive length"
    assert float(out["row_weight"].min()) > 0, "a zero or negative row weight was emitted"
    per_window = out[out["event"] == 1].groupby(["cohort", "pid", "wave_end"])["row_weight"].sum()
    assert float(per_window.max()) <= 1.0 + 1e-9, "a window carries more than one event"
    if alloc != "midcell":
        assert abs(after["person_years"] - before["person_years"]) < 0.05, \
            "the allocation lost or invented person-time"
        pa = d.groupby(["cohort", "pid"])["exposure_years"].sum()
        assert float((pw(out, w) - pa).abs().max()) < 1e-4, "a person's total follow-up changed"
        eb = out.assign(e=out["t_since_entry_years"] + out["exposure_years"]).groupby(
            ["cohort", "pid"])["e"].max()
        ea = d.assign(e=d["t_since_entry_years"] + d["exposure_years"]).groupby(
            ["cohort", "pid"])["e"].max()
        assert float((eb - ea).abs().max()) < 1e-6, "a person's last observed date changed"
    else:
        pa = d.groupby(["cohort", "pid"])["exposure_years"].sum()
        assert float((pw(out, w) - pa).max()) < 1e-9, "the midcell allocation extended follow-up"

    fshort = f"_grid{delta:g}_{alloc}"
    dest = os.path.join(OUT, f"personperiod{fshort}.csv")
    out.to_csv(dest, index=False)
    doc = {"delta_years": delta, "alloc": alloc, "source_file": src,
           "before": before, "after": after,
           "rows_added": after["rows"] - before["rows"],
           "sub_intervals_per_parent_row_mean": round(float(n_sub.mean()), 3),
           "person_years_dropped_after_the_event_cell": round(dropped, 1),
           "event_time_meaning": {
               "uniform": "each piece of the parent window carries 1/n of the event: 'stroke somewhere "
                          "in this window, uniformly', which is the assumption cif_mid already "
                          "declares, with no invented date (PRIMARY allocation of this arm)",
               "last": "the event in the parent's LAST piece - the convention the unsplit "
                       "discrete-time likelihood implies, kept so the grid effect and the event-time "
                       "effect can be told apart",
               "midcell": "the event in the piece containing the parent midpoint, later pieces dropped: "
                          "the closest discrete-time reading of the declared midpoint date"},
           "note": ("each interval cut into ceil(L/delta) equal sub-intervals carrying the parent's "
                    "start covariates; deaths and non-response tails keep their terminal status on the "
                    "parent's last sub-interval because their t_end IS that date; a fractional event is "
                    "emitted as a weighted 0/1 row pair in column row_weight"),
           "checks": ["persons", "total_event_weight", "stroke_persons", "dated_terminal_counts",
                      "grid_max", "positive_lengths", "positive_row_weights",
                      "at_most_one_event_per_window", "person_time_identity_when_not_midcell",
                      "per_person_last_date"]}
    os.makedirs(REP, exist_ok=True)
    with open(os.path.join(REP, f"incident_grid_reframe{fshort}.json"), "w",
              encoding="utf-8") as f:
        json.dump(doc, f, indent=2, ensure_ascii=False)
    print(json.dumps(doc, indent=2, ensure_ascii=False))
    print(f"\nwrote {dest}  rows={after['rows']}")


if __name__ == "__main__":
    main()
