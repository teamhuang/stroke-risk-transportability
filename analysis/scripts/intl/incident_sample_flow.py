"""Per-country sample flow, published as a table so the figure and the text cannot disagree.

Writing-fix 8 of the pre-submission review asks for a standardised flow diagram, per country, showing
initial subjects, prevalent exclusions, persons contributing analysable intervals, the four-year
evaluation set, and what terminated the follow-up. Those numbers exist - they are printed across
Table 1, the horizon accounting JSON and the horizon-frame counts - but they are spread over three
files with different scopes (Table 1 is per-cohort person-interval assembly; the accounting JSON is
POOLED, not per country). A figure drawn from three scopes is a figure with a hidden inconsistency, so
this script puts them in one table, computed the same way every other four-year number in the paper is
computed.

One subtlety worth stating in the output: `at_risk_persons` from the person-period diagnostics counts
everyone who entered the risk set, while the horizon frame counts only those with a determinable
four-year endpoint. The difference is attrition *plus* the persons whose entire follow-up is shorter
than the horizon, and it is per-country, so it is the row that explains why Mexico's four-year analysis
sits on 19,808 of 26,525 at-risk adults while Korea's sits on 8,770 of 10,792.

Usage: python incident_sample_flow.py [--horizon 4] [--rule cif_mid]
"""
import os, sys, json, numpy as np, pandas as pd, warnings
warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)
import run_incident_loco as I

OUT = I.OUT
COH2CTRY = I.COH2CTRY


def flag(name, default):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default


def main():
    horizon = float(flag("--horizon", "4"))
    rule = flag("--rule", "cif_mid")

    pp = pd.read_csv(os.path.join(OUT, "personperiod_pooled.csv"))
    pp["country"] = pp["cohort"].map(COH2CTRY)
    pp = pp[pp["country"].notna()].reset_index(drop=True)
    diag_path = os.path.join(OUT, "personperiod_diagnostics.json")
    with open(diag_path, encoding="utf-8") as fh:
        diag = {d["country"]: d for d in json.load(fh)}
    base, pooled = I.horizon_frame(pp, horizon, rule)

    rows = []
    for held in sorted(set(pp["country"])):
        d = diag[held]
        acc = d["acc"]
        hb = base[base["country"] == held]
        hs = hb["horizon_status"].value_counts()
        n_ev = int(hs.get("stroke_within_horizon", 0))
        n_dead = int(hs.get("died_first_within_horizon", 0))
        n_free = int(hs.get("stroke_free_through_horizon", 0))
        ipcw = pd.to_numeric(hb["ipcw"], errors="coerce").fillna(1.0).to_numpy(float)
        lab = hb["label"].astype(float).to_numpy()
        rows.append(dict(
            country=held, cohort=d["cohort"], censor_mode=d["censor_mode"],
            adults_ever_interviewed=int(d["persons_ever_interviewed"]),
            prevalent_at_entry_excluded=int(acc["prevalent_at_entry"]),
            no_determinable_stroke=int(acc["no_determinable_stroke"]),
            at_risk_persons=int(acc["at_risk_persons"]),
            at_risk_without_analysable_interval=int(acc["at_risk_persons"]
                                                    - d["at_risk_persons_with_intervals"]),
            persons_with_intervals=int(d["at_risk_persons_with_intervals"]),
            person_intervals=int(d["intervals"]),
            incident_strokes_over_whole_panel=int(d["incident_events"]),
            intervals_terminated_by_death=int(d["intervals_ending_in_death"]),
            person_years=round(float(d["person_years"]), 1),
            horizon_evaluable_persons=int(len(hb)),
            horizon_events=int(n_ev),
            horizon_died_first_as_non_event=int(n_dead),
            horizon_stroke_free=int(n_free),
            horizon_persons_lost_or_shorter_than_horizon=int(
                int(d["at_risk_persons_with_intervals"]) - len(hb)),
            observed_incidence_unweighted=round(float(lab.mean()), 6) if len(hb) else np.nan,
            observed_incidence_ipcw=round(float(np.sum(ipcw * lab) / np.sum(ipcw)), 6)
            if len(hb) else np.nan,
            horizon_years=horizon, horizon_rule=rule))
    out = pd.DataFrame(rows)
    dest = os.path.join(OUT, f"incident_sample_flow_{rule}.csv")
    out.to_csv(dest, index=False)
    tot = dict(country="POOLED", cohort="all four", censor_mode="mixed",
               adults_ever_interviewed=int(out.adults_ever_interviewed.sum()),
               prevalent_at_entry_excluded=int(out.prevalent_at_entry_excluded.sum()),
               no_determinable_stroke=int(out.no_determinable_stroke.sum()),
               at_risk_persons=int(out.at_risk_persons.sum()),
               at_risk_without_analysable_interval=int(out.at_risk_without_analysable_interval.sum()),
               persons_with_intervals=int(out.persons_with_intervals.sum()),
               person_intervals=int(out.person_intervals.sum()),
               incident_strokes_over_whole_panel=int(out.incident_strokes_over_whole_panel.sum()),
               intervals_terminated_by_death=int(out.intervals_terminated_by_death.sum()),
               person_years=round(float(out.person_years.sum()), 1),
               horizon_evaluable_persons=int(out.horizon_evaluable_persons.sum()),
               horizon_events=int(out.horizon_events.sum()),
               horizon_died_first_as_non_event=int(out.horizon_died_first_as_non_event.sum()),
               horizon_stroke_free=int(out.horizon_stroke_free.sum()),
               horizon_persons_lost_or_shorter_than_horizon=int(
                   out.horizon_persons_lost_or_shorter_than_horizon.sum()),
               observed_incidence_unweighted=round(float(pooled["observed_prevalence_unweighted"]), 6),
               observed_incidence_ipcw=round(pooled["observed_prevalence_ipcw"], 6),
               horizon_years=horizon, horizon_rule=rule)
    out = pd.concat([out, pd.DataFrame([tot])], ignore_index=True)
    out.to_csv(dest, index=False)
    print(out.to_string(index=False, max_colwidth=18))
    print(f"\nwrote {dest}")
    rep = os.path.join(ROOT, "results", "reports")
    os.makedirs(rep, exist_ok=True)
    with open(os.path.join(rep, f"incident_sample_flow_{rule}.json"), "w", encoding="utf-8") as fh:
        json.dump({"horizon_years": horizon, "horizon_rule": rule,
                   "pooled_accounting_from_horizon_frame": pooled,
                   "note": ("`horizon_persons_lost_or_shorter_than_horizon` is persons-with-intervals minus "
                            "horizon-evaluable, so it mixes death/attrition before four years with "
                            "follow-up shorter than the horizon; the horizon frame's own counts are "
                            "given separately in pooled_accounting_from_horizon_frame."),
                   "per_country": rows}, fh, indent=1)
    return out


if __name__ == "__main__":
    main()
