"""Publish the incident-stroke arm's tables into results/tables with dated names.

The working files live under data/processed/intl/incident/ and are overwritten on every rerun.
These copies are the deliverables that the manuscript and the reports cite, so they carry a date
and a short provenance header row set (cohort, software, seed) that makes a figure traceable to
the run that produced it.

Usage: python publish_incident_tables.py
"""
import os, sys, shutil, json, datetime as dt

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
SRC = os.path.join(ROOT, "data", "processed", "intl", "incident")
DST = os.path.join(ROOT, "results", "tables")
TODAY = "2026-11-03"

FILES = {
    "personperiod_pooled.csv": f"incident_personperiod_pooled_{TODAY}.csv",
    "personperiod_diagnostics.json": f"incident_personperiod_diagnostics_{TODAY}.json",
    # keyed by H{horizon}_{estimand}_{features}_{time} now, so no arm can overwrite another
    "incident_horizon_counts.json": f"incident_horizon_accounting_{TODAY}.json",
    # primary run, four countries, BOTH estimands in one table (column `horizon_rule`)
    "incident_loco_common_linear_H4_uw.csv": f"incident_loco_common_H4_{TODAY}.csv",
    # the P0 audits
    "incident_competing_risks_cif.csv": f"incident_competing_risks_cif_{TODAY}.csv",
    "incident_competing_risks_estimands.csv": f"incident_competing_risks_estimands_{TODAY}.csv",
    "incident_competing_risks_estimands_paired.csv":
        f"incident_competing_risks_estimands_paired_{TODAY}.csv",
    "incident_horizon_recalibration_cif_mid.csv": f"incident_horizon_recal_{TODAY}.csv",
    "incident_horizon_recalibration_exclusive_start.csv":
        f"incident_horizon_recal_preaudit_frame_{TODAY}.csv",
    "incident_horizon_calibration_curves_cif_mid.csv":
        f"incident_horizon_calibration_curves_{TODAY}.csv",
    # the P1 arm: pooled / revised / time-only / de novo, all on identical evaluation persons
    "incident_update_strategies.csv": f"incident_update_strategies_{TODAY}.csv",
    "incident_update_strategies_paired.csv": f"incident_update_strategies_paired_{TODAY}.csv",
    # adaptation curves under the reported estimand and under the pre-audit one
    "incident_adaptation_cif_mid.csv": f"incident_adaptation_{TODAY}.csv",
    "incident_adaptation_exclusive_start.csv": f"incident_adaptation_preaudit_frame_{TODAY}.csv",
    "incident_shap.csv": f"incident_shap_{TODAY}.csv",
    # the declared sensitivity arms, published side by side with the primary run
    "incident_internal_common_linear_interval.csv": f"incident_internal_clustered_{TODAY}.csv",
    "incident_loco_common_none_H4_uw.csv": f"incident_loco_common_none_H4_{TODAY}.csv",
    "incident_loco_extended_linear_H4_uw.csv": f"incident_loco_extended_linear_H4_{TODAY}.csv",
    "incident_loco_common_linear_H6_uw.csv": f"incident_loco_common_linear_H6_{TODAY}.csv",
    "incident_loco_common_linear_H4_w.csv": f"incident_loco_common_linear_H4_weighted_{TODAY}.csv",
    # does the horizon frame count people as observed who were only alive?
    "incident_ascertainment_sensitivity.csv": f"incident_ascertainment_sensitivity_{TODAY}.csv",
    # who the transported model is right for: baseline strata on the reported estimand
    "incident_subgroups.csv": f"incident_subgroups_{TODAY}.csv",
    # the arm the coverage objection requires: refit under strict ascertainment, train and test agree
    "incident_strict_refit.csv": f"incident_strict_refit_{TODAY}.csv",
    # the arm the link objection requires: logit vs cloglog vs cloglog-with-log-exposure-offset,
    # and the same three arms refitted on a common sub-year interval grid
    "incident_cloglog_cif_mid.csv": f"incident_cloglog_{TODAY}.csv",
    "incident_cloglog_paired_cif_mid.csv": f"incident_cloglog_paired_{TODAY}.csv",
    "incident_cloglog_cif_mid_grid1_last.csv": f"incident_cloglog_grid1_last_{TODAY}.csv",
    "incident_cloglog_paired_cif_mid_grid1_last.csv":
        f"incident_cloglog_paired_grid1_last_{TODAY}.csv",
    # the same grid refitted under the two event-time allocations that do NOT assert the stroke
    # happened at the end of its interview gap: `uniform` (the primary one, fractional event weight)
    # and `midcell` (the declared midpoint date)
    "incident_cloglog_cif_mid_grid1_uniform.csv": f"incident_cloglog_grid1_uniform_{TODAY}.csv",
    "incident_cloglog_paired_cif_mid_grid1_uniform.csv":
        f"incident_cloglog_paired_grid1_uniform_{TODAY}.csv",
    "incident_cloglog_cif_mid_grid1_midcell.csv": f"incident_cloglog_grid1_midcell_{TODAY}.csv",
    "incident_cloglog_paired_cif_mid_grid1_midcell.csv":
        f"incident_cloglog_paired_grid1_midcell_{TODAY}.csv",
    # the arm the second-round objection requires: the ACTUAL interval-censored likelihood
    # (1 - prod_j(1 - p_j) over an interval's pieces) instead of a fractional-event re-weighting,
    # fitted unsplit and on a 1-year piece grid
    "incident_ic_likelihood_cif_mid.csv": f"incident_ic_likelihood_{TODAY}.csv",
    "incident_ic_likelihood_paired_cif_mid.csv": f"incident_ic_likelihood_paired_{TODAY}.csv",
    # the arm the third-round review requires: two cause-specific interval-censored hazards (stroke,
    # death) composed into an Aalen-Johansen CIF, duration-consistent and not duration-consistent
    # alike, with person-clustered intervals and the local repair scored on disjoint persons
    "incident_cr_primary.csv": f"incident_cr_primary_{TODAY}.csv",
    "incident_cr_primary_paired.csv": f"incident_cr_primary_paired_{TODAY}.csv",
    # P1-2: the prespecified freeze / recalibrate / selectively-recalibrate decision policies
    "incident_update_policy_cif_mid.csv": f"incident_update_policy_{TODAY}.csv",
    "incident_update_policy_summary_cif_mid.csv": f"incident_update_policy_summary_{TODAY}.csv",
    "incident_update_policy_decisions_cif_mid.csv": f"incident_update_policy_decisions_{TODAY}.csv",
    # P0-3: the machine-checked adaptation/evaluation independence audit, one row per reviewer question
    "incident_adaptation_leakage_audit_cif_mid.csv":
        f"incident_adaptation_leakage_audit_{TODAY}.csv",
    "incident_adaptation_leakage_audit_cif_mid.json":
        f"incident_adaptation_leakage_audit_{TODAY}.json",
    # P1-1: decile calibration with person-clustered intervals, frozen vs locally repaired
    "incident_calibration_curves_cif_mid.csv": f"incident_calibration_curves_{TODAY}.csv",
    # P1-5: the definitional-ablation arm - the same two cause-specific hazards refitted from scratch
    # with the concepts whose QUESTION differs between panels removed, plus the missingness table that
    # justifies each tier
    "incident_cr_definition.csv": f"incident_cr_definition_{TODAY}.csv",
    "incident_cr_definition_paired.csv": f"incident_cr_definition_paired_{TODAY}.csv",
    "incident_cr_definition_missingness.csv": f"incident_cr_definition_missingness_{TODAY}.csv",
    # writing-fix 8: one per-country flow table, so the flow figure and Table 1 cannot disagree
    "incident_sample_flow_cif_mid.csv": f"incident_sample_flow_{TODAY}.csv",
    "personperiod_strict.csv": None,               # intermediate risk set, not a reported table
    "personperiod_grid1_last.csv": None,           # the re-framed risk sets the link arm fits on
    "personperiod_grid1_uniform.csv": None,
    "personperiod_grid1_midcell.csv": None,
    # the pre-allocation version of the grid (event forced into the last sub-interval) lives in
    # results/superseded/2026-11-03_last-piece-grid/ and is deliberately not published: an unlabeled
    # `personperiod_grid1.csv` / `incident_cloglog_grid1_*.csv` is one default glob away from being
    # read as the honest arm.
    "incident_feasibility_tally.csv": None,          # superseded by the built design
}
# provenance records that live outside the incident folder but are cited by the same tables
EXTRA = {
    os.path.join(ROOT, "data", "processed", "intl", "corrected", "rf_ablation_common.csv"):
        f"rf_probability_ablation_common_{TODAY}.csv",
    os.path.join(ROOT, "data", "processed", "intl", "corrected", "rf_ablation_extended.csv"):
        f"rf_probability_ablation_extended_{TODAY}.csv",
    os.path.join(ROOT, "results", "reports", "hrs_reshape_diagnostics.json"):
        f"hrs_reshape_diagnostics_{TODAY}.json",
    os.path.join(ROOT, "results", "reports", "hrs_metadata_probe.json"):
        f"hrs_metadata_probe_{TODAY}.json",
    # link/offset coefficients, convergence and the duration-consistency diagnostic; and the
    # assertions that each re-framed grid preserved persons, total event weight, the dated terminal
    # statuses and (except under midcell) all person-time
    os.path.join(ROOT, "results", "reports", "incident_cloglog_cif_mid.json"):
        f"incident_cloglog_diagnostics_{TODAY}.json",
    **{os.path.join(ROOT, "results", "reports", f"incident_cloglog_cif_mid_grid1_{a}.json"):
       f"incident_cloglog_grid1_{a}_diagnostics_{TODAY}.json" for a in ("last", "uniform", "midcell")},
    **{os.path.join(ROOT, "results", "reports", f"incident_grid_reframe_grid1_{a}.json"):
       f"incident_grid_reframe_{a}_{TODAY}.json" for a in ("last", "uniform", "midcell")},
    # the interval-censored-likelihood arm: coefficients per delta, the analytic grid-invariance check
    # for the offset arm, and the published row's optimiser-tolerance gap
    os.path.join(ROOT, "results", "reports", "incident_ic_likelihood_cif_mid.json"):
        f"incident_ic_likelihood_diagnostics_{TODAY}.json",
    # the competing-risks primary arm: per-variant convergence, the duration-consistency ratio
    # (risk composed from eight half-year pieces over risk composed from one four-year piece), the
    # closed-form CIF cross-check and the horizon accounting per timing rule
    os.path.join(ROOT, "results", "reports", "incident_cr_primary.json"):
        f"incident_cr_primary_diagnostics_{TODAY}.json",
    # the definitional-ablation arm: which columns each tier actually fits, the replication check that
    # the "common" tier reproduces the published primary rows, and per-cell convergence
    os.path.join(ROOT, "data", "processed", "intl", "incident",
                 "incident_cr_definition_diagnostics.json"):
        f"incident_cr_definition_diagnostics_{TODAY}.json",
}


def main():
    os.makedirs(DST, exist_ok=True)
    missing = []
    for src, dst in FILES.items():
        if dst is None:
            continue
        a, b = os.path.join(SRC, src), os.path.join(DST, dst)
        if not os.path.exists(a):
            missing.append(src); continue
        if src.endswith(".csv"):
            publish_csv(a, b, dst)
        elif src == "incident_horizon_counts.json":
            publish_accounting(a, b, dst)
        elif src.endswith(".json"):
            publish_json(a, b, dst)
        else:
            shutil.copyfile(a, b)
            print(f"  {src} -> results/tables/{dst}")
    for a, dst in EXTRA.items():
        if not os.path.exists(a):
            missing.append(os.path.basename(a)); continue
        if a.endswith(".csv"):
            publish_csv(a, os.path.join(DST, dst), dst)
        else:
            shutil.copyfile(a, os.path.join(DST, dst))
            print(f"  {os.path.basename(a)} -> results/tables/{dst}")
    tally = os.path.join(ROOT, "results", "reports", "incident_feasibility_tally.csv")
    if os.path.exists(tally):
        shutil.copyfile(tally, os.path.join(DST, f"incident_feasibility_tally_{TODAY}.csv"))
        print("  incident_feasibility_tally.csv -> results/tables/ (pre-design ceiling, kept)")
    if missing:
        print("  MISSING (run the builders first):", missing); sys.exit(1)


def publish_csv(a, b, dst):
    """Copy a working table, correcting one column name that is wrong in the producer.

    `oe_ratio` in the LOCO and adaptation tables is `mean_pred / obs_prev` - predicted over observed,
    an *expected-to-observed* ratio - but its name and the console line invite the reader to take it as
    observed-to-expected. The first draft of the manuscript did exactly that and wrote "O/E 3.2, so the
    model under-predicts Mexico" from a run whose own columns say mean predicted 0.0306 against 0.0095
    observed, i.e. the model OVER-predicts Mexico threefold. The publisher is the single normalisation
    point: the working files stay byte-identical copies of what the run produced, while every published
    table names the direction and carries both orientations, so nobody has to infer one from a name.
    Renaming in the producer instead would desynchronise the arms mid-flight, because the run in
    progress imported the old module.
    """
    import pandas as pd
    d = pd.read_csv(a)
    renamed = []
    for c in [x for x in d.columns if x.endswith("oe_ratio")]:
        base = c[: -len("oe_ratio")].rstrip("_")
        new = f"{base}_pred_over_obs" if base else "pred_over_obs"
        inv = f"{base}_obs_over_pred" if base else "obs_over_pred"
        d = d.rename(columns={c: new})
        if c.startswith("delta_"):        # a difference of ratios has no meaningful reciprocal
            renamed.append(f"{c}={new}")
            continue
        d[inv] = (1.0 / d[new]).round(6)
        renamed.append(f"{c}={new}")
    if renamed:
        print(f"  {os.path.basename(a)} -> results/tables/{dst} [" + ", ".join(renamed) +
              " (=mean_pred/obs_prev), + reciprocals]")
    else:
        print(f"  {os.path.basename(a)} -> results/tables/{dst}")
    d.to_csv(b, index=False)


JSON_KEY_FIXES = {
    # notna().mean() rounded to four places: a fraction, printed under a name that reads as a percent.
    # Quoting `death_date_coverage_pct = 0.0152` as "0.015%" is a hundredfold error, and defect 11
    # already caught one statistic of exactly this shape. The producer now emits *_fraction; this map
    # repairs the already-published copy without re-running the expander.
    "death_date_coverage_pct": "death_date_coverage_fraction",
    "iwstat_coverage_pct": "iwstat_coverage_fraction",
}


def publish_json(a, b, dst):
    """Copy a provenance JSON, renaming keys whose name asserts a unit the value does not carry."""
    with open(a, encoding="utf-8") as fh:
        raw = json.load(fh)

    hits = []

    def walk(x):
        if isinstance(x, dict):
            out = {}
            for k, v in x.items():
                if k in JSON_KEY_FIXES:
                    hits.append(k)
                    out[JSON_KEY_FIXES[k]] = walk(v)
                else:
                    out[k] = walk(v)
            return out
        if isinstance(x, list):
            return [walk(v) for v in x]
        return x

    doc = walk(raw)
    with open(b, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=1)
    note = f" [{', '.join(sorted(set(hits)))} -> *_fraction]" if hits else ""
    print(f"  {os.path.basename(a)} -> results/tables/{dst}{note}")


def publish_accounting(a, b, dst):
    """Separate the keyed per-arm accounting from the unkeyed top level before publishing.

    `incident_horizon_counts.json` carries one block per arm (`H4_cif_mid_common_linear`, ...) and, at
    the top level, a bare set of scalars that some older writer left behind - the last arm to touch the
    file, not the primary one. Defect 9 (docs/SELF_AUDIT.md) is exactly that trap: an H=6 count shipped
    under an H=4 label. The keyed blocks are the deliverable, so the published copy states which one the
    design uses and demotes the loose scalars to a labelled legacy block instead of deleting them.
    """
    with open(a, encoding="utf-8") as fh:
        raw = json.load(fh)
    keyed = {k: v for k, v in raw.items() if isinstance(v, dict)}
    loose = {k: v for k, v in raw.items() if k not in keyed}
    primary = "H4_cif_mid_common_linear"
    out = {"primary_estimand_key": primary if primary in keyed else None,
           "warning_unkeyed_top_level": ("These scalars are the last arm that wrote the working file, "
                                         "which is not necessarily the primary design. Read the keyed "
                                         "blocks below."),
           "keyed_accounting_by_arm": keyed,
           "unkeyed_top_level_verbatim": loose}
    with open(b, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1)
    print(f"  {os.path.basename(a)} -> results/tables/{dst} "
          f"[{len(keyed)} keyed arms kept; unkeyed top level moved to "
          f"'unkeyed_top_level_verbatim'; primary = {primary}]")


if __name__ == "__main__":
    main()
