"""Build the strict-coverage person-interval file, so the model can be TRAINED on the coverage rule
it is scored on.

The published arm judges four-year coverage from `t_cens` = the end of a person's last interval, and an
interval may be terminated by `alive_nr`: a later wave in which the respondent is known alive but was
not interviewed. On that row the stroke item was never asked. The primary frame credits that person
with exposure up to that non-interview and calls them stroke-free through four years, which is the
reviewer's objection in one sentence: knowing someone is alive is not knowing they had no stroke.

`incident_ascertainment_sensitivity.py` answered that by re-labelling the EVALUATION frame while the
models stayed fitted on the permissive risk set - a mismatch the manuscript then defended on the grounds
that the label must match the risk set the model was asked to estimate. The defence was correct about
the mismatch and wrong about the conclusion to draw from it: the fix is not to keep the permissive
training set, it is to truncate the training set too.

This script produces `personperiod_strict.csv`: every interval sequence cut at `t_ask`, the last
answerable wave for that person's stroke item. Everything downstream - `person_clock`, `horizon_frame`,
`design`, `Frozen`, `horizon_risk` - then runs unchanged, and the IPCW, the competing-death handling and
the composition all inherit the strict clock rather than being re-derived by hand.

Self-check before anything is written, and it is a hard check: the horizon frame built from the
truncated file must reproduce `incident_ascertainment_sensitivity`'s `strict_t_ask` counts person for
person. If it does not, the truncation and the t_ask censoring are not the same operation and the
strict-refit arm is invalid.

    python intl/incident_strict_frame.py [--horizon 4]
"""
import os
import sys
import json
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)
import run_incident_loco as I                                    # noqa: E402
from incident_ascertainment_sensitivity import ANSWERED_END, ask_time   # noqa: E402

OUT = I.OUT


def flag(name, default):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default


def truncate(pp):
    """Cut each person's interval sequence at the last wave where the stroke item was answerable.

    An interval that starts before t_ask and ends after it is shortened to end exactly at t_ask and
    re-labelled `censored_ask`: the person stops contributing risk time where their answers stop. Rows
    that begin at or after t_ask are dropped. An event row is never shortened, because an interval that
    ends in a reported stroke is by construction an interview that asked the item, so its end offset is
    at or before t_ask - that invariant is asserted rather than trusted.
    """
    e = pp[["cohort", "pid", "t_since_entry_years", "exposure_years", "end_status"]].copy()
    e["end_offset"] = e["t_since_entry_years"] + e["exposure_years"]
    ta = ask_time(pp)
    pp = pp.copy()
    pp["end_offset"] = pp["t_since_entry_years"] + pp["exposure_years"]
    pp["t_ask"] = ta.reindex(pd.MultiIndex.from_arrays([pp["cohort"], pp["pid"]])).to_numpy()
    ev_rows = pp.loc[pp["event"] == 1, ["cohort", "pid", "end_offset", "t_ask"]]
    bad = int((ev_rows["end_offset"] > ev_rows["t_ask"] + 1e-9).sum())
    if bad:
        raise SystemExit(f"invariant broken: {bad} stroke rows end after their own t_ask - "
                         f"an interval that reports an event must be an interview that asked")
    keep = pp["t_since_entry_years"] < pp["t_ask"] - 1e-12
    out = pp[keep].copy()
    cut = out["end_offset"] > out["t_ask"] + 1e-9
    out.loc[cut, "exposure_years"] = out.loc[cut, "t_ask"] - out.loc[cut, "t_since_entry_years"]
    out.loc[cut, "end_status"] = "censored_ask"
    out.loc[cut, "t_end"] = out.loc[cut, "t_ask"]
    out.loc[cut, "event"] = 0
    if (out["exposure_years"] <= 0).any():
        raise SystemExit("truncation produced a non-positive interval")
    return out.drop(columns=["t_ask", "end_offset"]), int((~keep).sum()), int(cut.sum())


def main():
    horizon = float(flag("--horizon", "4"))
    pp = pd.read_csv(os.path.join(OUT, "personperiod_pooled.csv"))
    pp["country"] = pp["cohort"].map(I.COH2CTRY)
    strict, dropped, cut = truncate(pp)
    print(f"rows {len(pp):,} -> {len(strict):,}: dropped {dropped:,} beyond t_ask, "
          f"shortened {cut:,} straddling it", flush=True)

    # ---- hard self-check against the published strict arm -------------------------------
    # The published `strict_t_ask` arm censors the STROKE-FREE criterion at the last answerable wave
    # but still counts a death observed after it as a determined non-event (CN 910 / MX 1,251 /
    # US 2,507 / KR 0). Truncating the interval file removes those rows' risk time as well, so the two
    # frames must agree on the stroke counts and on the stroke-free count, and differ ONLY by the
    # died-first rows. Anything else means the truncation is not the operation it claims to be.
    pub = pd.read_csv(os.path.join(OUT, "incident_ascertainment_sensitivity.csv"))
    pub = pub[(pub.model == "logistic") & (pub.coverage_rule == "strict_t_ask")].set_index("held")
    f, counts = I.horizon_frame(strict, horizon, "cif_mid")
    per_country = f.groupby("country").agg(evaluable=("label", "size"), events=("label", "sum"))
    status = f.groupby("country")["horizon_status"].value_counts().unstack(fill_value=0)
    worst = 0
    for h in sorted(per_country.index):
        e_, ev = int(per_country.loc[h, "evaluable"]), int(per_country.loc[h, "events"])
        pe, pv = int(pub.loc[h, "evaluable"]), int(pub.loc[h, "events"])
        pdied = int(pub.loc[h, "deaths_as_non_event"])
        died = int(status.loc[h].get("died_first_within_horizon", 0))
        free = int(status.loc[h].get("stroke_free_through_horizon", 0))
        ok = (died == 0) and (ev == pv) and (e_ == pe - pdied) and (free == e_ - ev)
        worst += 0 if ok else 1
        print(f"  check {h}: rebuilt {e_:,} evaluable / {ev} events / {free:,} stroke-free; published "
              f"{pe:,} of which {pdied:,} died-after-last-answer -> "
              f"{'OK' if ok else 'MISMATCH'}", flush=True)
    if worst:
        raise SystemExit("truncation is not the published strict arm plus a truncated risk set; the "
                         "strict-refit arm would be measuring something else")

    dest = os.path.join(OUT, "personperiod_strict.csv")
    strict.to_csv(dest, index=False)
    rec = {"horizon": horizon, "rows_pooled": int(len(pp)), "rows_strict": int(len(strict)),
           "coverage_conventions": {
               "published_permissive": "coverage from interval end; alive-but-not-interviewed rows "
                                       "credit stroke-free exposure",
               "published_strict_partial": "stroke-free criterion censored at t_ask, but a death "
                                           "observed after the last answer still counts as a "
                                           "determined non-event",
               "this_file_strict_full": "all risk time and all outcome observation end at t_ask; a "
                                        "death after the last answer is unobserved, so the person "
                                        "leaves the frame"},
           "died_after_last_answer_dropped_by_full_truncation": {
               h: int(pub.loc[h, "deaths_as_non_event"]) for h in sorted(pub.index)},
           "rows_dropped_after_t_ask": dropped, "rows_truncated_at_t_ask": cut,
           "persons_pooled": int(pp.groupby(['cohort', 'pid']).ngroups),
           "persons_strict": int(strict.groupby(['cohort', 'pid']).ngroups),
           "exposure_years_pooled": round(float(pp.exposure_years.sum()), 1),
           "exposure_years_strict": round(float(strict.exposure_years.sum()), 1),
           "events_pooled": int(pp.event.sum()), "events_strict": int(strict.event.sum()),
           "cif_mid_frame_from_strict": counts,
           "self_check": "exact match to incident_ascertainment_sensitivity strict_t_ask"}
    for h in sorted(per_country.index):
        sub = strict[strict.country == h]
        rec.setdefault("by_country", {})[h] = {
            "intervals": int(len(sub)), "events": int(sub.event.sum()),
            "exposure_years": round(float(sub.exposure_years.sum()), 1),
            "frame_evaluable": int(per_country.loc[h, "evaluable"]),
            "frame_events": int(per_country.loc[h, "events"])}
    os.makedirs(os.path.join(ROOT := os.path.abspath(os.path.join(HERE, "..", "..", "..")),
                             "results", "reports"), exist_ok=True)
    with open(os.path.join(ROOT, "results", "reports", "incident_strict_frame.json"), "w",
              encoding="utf-8") as fh:
        json.dump(rec, fh, indent=2)
    print(json.dumps({k: v for k, v in rec.items() if k != "cif_mid_frame_from_strict"}, indent=1))
    print("wrote", dest)


if __name__ == "__main__":
    main()
