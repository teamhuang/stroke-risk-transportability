"""Does the four-year frame count people as observed who were merely alive?

The published horizon frames judge coverage from `t_cens` = the end of a person's last interval, and
an interval may be terminated by `alive_nr` - a later wave record in which the respondent is *known
alive but was not interviewed*. On that row the outcome item was never asked, so the person's last
real answer is older than their coverage date. RAND HRS carries 9,325 such intervals and MHAS 1,166,
and because those panels' gaps are long, some respondents contribute a 20- or 26-year interval whose
exposure is credited to a non-interview. Under `P(first stroke within 4 years)` those people are not
"observed at least to H and stroke-free"; they are censored at their last answer and leave the frame.

This script rebuilds the frame with a strict coverage date (`t_ask` = the last wave at which the
stroke item was answerable) and reports what moves: persons in the frame, observed incidence, the IPCW
weight, and the observed-to-expected ratio of the frozen model. Mexico is the case that matters,
because the audit's headline is that Mexico is where a single local intercept pays (O/E 3.2) - and
Mexico is also the panel with 19% of intervals longer than the horizon.

Self-check, run before anything is printed: with `cover_col="t_cens"` the local rebuild must reproduce
`run_incident_loco.horizon_frame` exactly. If it does not, this script's numbers are meaningless.

    python intl/incident_ascertainment_sensitivity.py [--horizon 4] [--models logistic,random_forest]
"""
import os
import sys
import json
import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)
import run_incident_loco as I                                    # noqa: E402

OUT = I.OUT
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
ANSWERED_END = ("stroke", "continued")   # the interval ends at an interview that asked the item


def flag(name, default):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default


def logit(p):
    p = np.clip(np.asarray(p, dtype=float), 1e-9, 1 - 1e-9)
    return np.log(p / (1.0 - p))


def expit(z):
    return 1.0 / (1.0 + np.exp(-z))


def weighted_offset(lp, y, w):
    """IPCW-weighted version of incident_adaptation.fit_offset: the single log-odds shift that makes
    the weighted mean prediction equal the weighted observed prevalence."""
    q = float(np.sum(w * y) / np.sum(w))
    if not 0.0 < q < 1.0:
        return 0.0
    lo, hi = -12.0, 12.0
    for _ in range(60):
        mid = (lo + hi) / 2.0
        if np.sum(w * expit(lp + mid)) / np.sum(w) < q:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2.0


def ask_time(pp):
    """Last time each person's stroke item was answerable, in years since their own entry.

    A row contributes its END only if an interview actually happened there; otherwise its START, which
    is always an answer by construction (the expander builds intervals only from determinable rows)."""
    e = pp[["cohort", "pid", "t_since_entry_years", "exposure_years", "end_status"]].copy()
    e["end_offset"] = e["t_since_entry_years"] + e["exposure_years"]
    e["a"] = np.where(e["end_status"].isin(ANSWERED_END), e["end_offset"], e["t_since_entry_years"])
    return e.groupby(["cohort", "pid"])["a"].max()


def frame_from_clock(pc, horizon, cover_col):
    """Mirror of run_incident_loco.horizon_frame's cif_mid arm, with the coverage column named."""
    t_s = pc["t_stroke_mid"].to_numpy(dtype=float)
    t_d = pc["t_death"].to_numpy(dtype=float)
    t_c = pc[cover_col].to_numpy(dtype=float)
    stroke = np.isfinite(t_s) & (t_s <= horizon)
    died_first = np.isfinite(t_d) & (t_d <= horizon) & ~stroke
    determined = stroke | died_first | (t_c >= horizon - 1e-9)
    tau = np.where(stroke, np.fmin(t_s, horizon),
                   np.where(died_first, np.fmin(t_d, horizon), np.fmin(t_c, horizon)))
    obs = np.where(determined, tau, t_c)
    steps = I.censoring_survival(determined, obs, horizon)
    keys = np.array(sorted(steps), dtype=float)
    pos = np.searchsorted(keys, np.round(tau, 6) - 1e-9, side="right") - 1
    gval = np.array([1.0 if p < 0 else steps[keys[p]] for p in pos])
    weight = np.where(determined, 1.0 / np.maximum(gval, 1e-6), 0.0)
    out = pc[determined].copy()
    out["label"] = stroke[determined].astype(int)
    out["ipcw"] = weight[determined]
    out["horizon_status"] = np.where(stroke[determined], "stroke_within_horizon",
                                     np.where(died_first[determined], "died_first_within_horizon",
                                              "stroke_free_through_horizon"))
    out["coverage_years"] = t_c[determined]
    return out, {"evaluable": int(determined.sum()),
                 "events": int(stroke[determined].sum()),
                 "deaths_as_non_event": int((died_first & determined).sum()),
                 "excluded": int((~determined).sum()),
                 "prevalence": float(stroke[determined].mean()) if determined.any() else float("nan")}


def main():
    horizon = float(flag("--horizon", "4"))
    fset = flag("--features", "common")
    time_mode = flag("--time", "linear")
    models = flag("--models", "logistic").split(",")
    pp = pd.read_csv(os.path.join(OUT, "personperiod_pooled.csv"))
    pp["country"] = pp["cohort"].map(I.COH2CTRY)
    pp = pp[pp["country"].notna()].reset_index(drop=True)
    X = I.design(pp, fset, time_mode)
    y = pp["event"].astype(int).values

    # ---- self-check: the local rebuild must equal the published frame -------------------------
    pc = I.person_clock(pp)
    pc["t_ask"] = ask_time(pp).reindex(
        pd.MultiIndex.from_arrays([pc["cohort"], pc["pid"]])).to_numpy()
    pub, pub_counts = I.horizon_frame(pp, horizon, "cif_mid")
    chk, chk_counts = frame_from_clock(pc, horizon, "t_cens")
    for loc, pub_k in (("evaluable", "evaluable"), ("events", "event_within_horizon"),
                       ("excluded", "lost_before_horizon_excluded"),
                       ("deaths_as_non_event", "death_counted_as_non_event")):
        if chk_counts[loc] != pub_counts[pub_k]:
            raise AssertionError(f"rebuild disagrees with horizon_frame on {loc}: "
                                 f"{chk_counts[loc]} vs {pub_counts[pub_k]}")
    dp = abs(pub_counts["observed_prevalence_unweighted"] - chk_counts["prevalence"])
    if dp > 1e-12:
        raise AssertionError(f"rebuild prevalence off by {dp:.3g}")
    print(f"self-check ok: the rebuild reproduces the published cif_mid frame "
          f"({chk_counts['evaluable']} evaluable, prevalence {chk_counts['prevalence']:.6f})",
          flush=True)

    strict, strict_counts = frame_from_clock(pc, horizon, "t_ask")
    kpub = set(map(tuple, pub[["cohort", "pid"]].to_numpy()))
    kstr = set(map(tuple, strict[["cohort", "pid"]].to_numpy()))
    left = [k for k in kpub if k not in kstr]
    last_status = (pp.sort_values(["cohort", "pid", "k"]).groupby(["cohort", "pid"])
                   ["end_status"].last().rename("last_end_status"))
    lf = (pd.DataFrame(left, columns=["cohort", "pid"])
          .join(last_status, on=["cohort", "pid"])
          .join(pc.set_index(["cohort", "pid"])[["t_cens", "t_ask", "country"]],
                on=["cohort", "pid"]))
    lf["unobserved_years"] = lf["t_cens"] - lf["t_ask"]

    rows = []
    for held in sorted(set(pp["country"])):
        tr = (pp["country"].values != held)
        step_L = round(float(np.median(pp.loc[tr, "exposure_years"])) * 4) / 4
        ptr = float(y[tr].mean())
        for name in models:
            fr = I.Frozen(X.loc[tr], y[tr], name)
            for rule, frame in (("published_t_cens", pub), ("strict_t_ask", strict)):
                hb = frame[frame["country"] == held].reset_index(drop=True)
                yb = hb["label"].astype(int).to_numpy()
                wb = pd.to_numeric(hb["ipcw"], errors="coerce").fillna(1.0).to_numpy(dtype=float)
                ph, real = I.horizon_risk(fr, hb, horizon, time_mode, fset, step=step_L)
                prev_u = float(yb.mean())
                prev_w = float(I.w_mean(yb, yb, wb))
                mean_p = float(ph.mean())
                mean_p_w = float(I.w_mean(yb, ph, wb))
                nb = float(I.weighted_net_benefit(yb, ph, wb, 0.05))
                nb_all = float(I.weighted_net_benefit(yb, np.ones_like(ph), wb, 0.05))
                # one local parameter, fitted on this very frame: the headline the audit put on the
                # table is that this is what pays, so it has to be re-priced under each coverage rule
                lp = logit(ph)
                a = weighted_offset(lp, yb, wb)
                nb_off = float(I.weighted_net_benefit(yb, expit(lp + a), wb, 0.05))
                weighted = bool(np.any(np.abs(wb - 1.0) > 1e-12))
                auc = (float(roc_auc_score(yb, ph, sample_weight=wb if weighted else None))
                       if len(np.unique(yb)) > 1 else float("nan"))
                rows.append(dict(
                    held=held, model=name, coverage_rule=rule, horizon_years=round(float(real), 3),
                    step_years=step_L, evaluable=len(hb), events=int(yb.sum()),
                    deaths_as_non_event=int((hb["horizon_status"]
                                             == "died_first_within_horizon").sum()),
                    prevalence_unweighted=round(prev_u, 6),
                    prevalence_ipcw=round(prev_w, 6),
                    median_ipcw=round(float(np.median(wb)), 4),
                    mean_predicted=round(mean_p, 6),
                    mean_predicted_ipcw=round(mean_p_w, 6),
                    pred_over_obs_ipcw=round(mean_p_w / prev_w, 4) if prev_w else None,
                    obs_over_pred_ipcw=round(prev_w / mean_p_w, 4) if mean_p_w else None,
                    net_benefit_5pct=round(nb, 6),
                    net_benefit_offset_5pct=round(nb_off, 6),
                    net_benefit_gain_from_offset=round(nb_off - nb, 6),
                    offset_log_odds_shift=round(float(a), 4),
                    net_benefit_treat_all=round(nb_all, 6),
                    horizon_auroc=round(auc, 4),
                    train_prevalence_interval=round(ptr, 6)))
        d = pd.DataFrame(rows)
        print(d.to_string(index=False), flush=True)

    d.to_csv(os.path.join(OUT, "incident_ascertainment_sensitivity.csv"), index=False)
    summary = dict(
        horizon=horizon, models=models, self_check="exact",
        persons_published_frame=len(kpub), persons_strict_frame=len(kstr),
        persons_leaving=len(left),
        leaving_by_country=lf.groupby("country").size().to_dict(),
        leaving_share_by_country=round_series(
            lf.groupby("country").size() / pub.groupby("country").size()),
        leaving_by_last_end_status={f"{k[0]}|{k[1]}": int(v) for k, v in
                                    lf.groupby(["country", "last_end_status"]).size().items()},
        median_unobserved_years_by_country={str(k): round(float(v), 3) for k, v in
                                            lf.groupby("country")["unobserved_years"]
                                            .median().items()},
        published_counts=pub_counts, strict_counts=strict_counts)
    sp = os.path.join(ROOT, "results", "reports", "incident_ascertainment_summary.json")
    json.dump(summary, open(sp, "w", encoding="utf-8"), indent=1, default=float)
    print(json.dumps(summary, indent=1, ensure_ascii=False), flush=True)
    print("-> " + os.path.join(OUT, "incident_ascertainment_sensitivity.csv"))


def round_series(s):
    return {str(k): round(float(v), 4) for k, v in s.items()}


if __name__ == "__main__":
    main()
