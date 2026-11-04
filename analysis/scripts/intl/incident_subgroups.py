"""Who the transported model is right for: horizon performance inside baseline subgroups.

A single held-out AUROC per country hides the question a deploying service asks first: does the model
work equally well for the people it will actually be pointed at. For each held-out panel this fits the
frozen model on the other three countries, composes the four-year risk on the primary `cif_mid` frame,
and repeats the whole evaluation inside strata defined at the person's BASELINE interview (the
interval's starting wave, so nothing measured after the event can enter a cell): age band, sex,
hypertension, education, and the two structural strata the panels differ on - whether the respondent
is still working-age at entry, and how long their intervals are.

Confidence intervals are person-level bootstrap (the horizon frame is one row per person, so a row
resample IS a person resample) and are reported per cell, not as a difference: cells are disjoint, and
a paired-difference interval across disjoint groups resamples two independent populations, which would
be a different statistic from the one worth reporting.

    python intl/incident_subgroups.py [--horizon 4] [--boot 500] [--models logistic,random_forest]
                                      [--features common] [--time linear] [--rule cif_mid]
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
import modeling as M                                             # noqa: E402

OUT = I.OUT
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
THRESHOLD = 0.05


def flag(name, default):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default


def logit(p):
    p = np.clip(np.asarray(p, dtype=float), 1e-9, 1 - 1e-9)
    return np.log(p / (1.0 - p))


def expit(z):
    return 1.0 / (1.0 + np.exp(-z))


def weighted_offset(lp, y, w):
    """The one-parameter repair, IPCW-weighted: the log-odds shift that makes the weighted mean
    prediction equal the weighted observed prevalence on the whole held-out country frame."""
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


def strata(pc, pp):
    """Baseline strata, keyed on the person. Computed from the frame's own baseline covariates plus
    two structural descriptors that are properties of the panel rather than of the person."""
    s = pd.DataFrame({"cohort": pc["cohort"], "pid": pc["pid"], "country": pc["country"]})
    age = pd.to_numeric(pc["age"], errors="coerce")
    s["age_band"] = labelled(age, pd.cut(age, [19, 59, 69, 79, 200],
                                         labels=["20-59", "60-69", "70-79", "80+"]))
    s["sex"] = np.where(pd.to_numeric(pc["sex"], errors="coerce").values == 1, "male", "female")
    hyp = pd.to_numeric(pc["hypertension"], errors="coerce")
    s["hypertension"] = np.where(hyp.isna(), "unknown",
                                 np.where(hyp.values == 1, "hypertensive", "not hypertensive"))
    edu = pd.to_numeric(pc["education"], errors="coerce")
    s["education"] = labelled(edu, pd.cut(edu, [0.5, 1.5, 2.5, 3.5],
                                          labels=["low", "middle", "high"]))
    # structural: the person's own median interval length, because a model that composes hazards over
    # intervals has to be judged against people whose intervals it was never shown
    med = pp.groupby(["cohort", "pid"])["exposure_years"].median().rename("med_interval")
    j = s.merge(med, on=["cohort", "pid"], how="left")
    s["interval_length"] = labelled(j["med_interval"], pd.cut(
        j["med_interval"], [0, 2.5, 5.0, 100.0], labels=["<=2.5y", "2.5-5y", ">5y"]))
    s["band_entry"] = labelled(age, pd.Series(np.where(age.values < 45, "entered pre-60",
                                                       "entered 45+"), index=age.index))
    return s


def labelled(src, cut):
    """Keep unmeasured baseline cells visible instead of dropping them from a subgroup table."""
    return cut.astype("object").where(~src.isna(), "unknown")


def cell_row(y, p, w, seed, n_boot, p_off=None):
    """One subgroup: size, events, level, discrimination with a person-bootstrap interval, net
    benefit and its treat-all comparator, the calibration joint fit - and, when supplied, the same
    decision-curve numbers after the ONE parameter a local deployment would fit. A single intercept
    is only a repair if it works inside the strata as well as on the pooled country frame."""
    prev = float(I.w_mean(y, y, w))
    mp = float(I.w_mean(y, p, w))
    weighted = bool(np.any(np.abs(np.asarray(w) - 1.0) > 1e-12))
    if len(np.unique(y)) > 1:
        auc = float(roc_auc_score(y, p, sample_weight=w if weighted else None))
        bd = I.iid_boot_auroc(y, p, n_boot, seed, w=w if weighted else None)
        lo, hi = (float(np.percentile(bd, 2.5)), float(np.percentile(bd, 97.5))) if len(bd) else \
            (float("nan"), float("nan"))
    else:
        auc = lo = hi = float("nan")          # a single-class cell has no discrimination to report
    ci, cs = M.cal_intercept_slope(y, p)
    nb = float(I.weighted_net_benefit(y, p, w, THRESHOLD))
    all_nb = float(I.weighted_net_benefit(y, np.ones_like(p), w, THRESHOLD))
    out = dict(n=int(len(y)), events=int(np.sum(y)), events_weighted=round(float(np.sum(w * y)), 1),
               prevalence_ipcw=round(prev, 6), mean_predicted_ipcw=round(mp, 6),
               pred_over_obs=round(mp / prev, 4) if prev else None,
               auroc=round(auc, 4) if auc == auc else None,
               auroc_lo=round(lo, 4) if lo == lo else None,
               auroc_hi=round(hi, 4) if hi == hi else None,
               cal_slope=round(float(cs), 4), cal_intercept=round(float(ci), 4),
               net_benefit_5pct=round(nb, 6), net_benefit_treat_all=round(all_nb, 6),
               net_benefit_gain_over_best_default=round(nb - max(0.0, all_nb), 6),
               # an AUROC from a cell with one or two events is arithmetic, not evidence
               interpretable=bool(int(np.sum(y)) >= 10 and len(y) >= 100))
    if p_off is not None:
        nb_off = float(I.weighted_net_benefit(y, p_off, w, THRESHOLD))
        out["net_benefit_offset_5pct"] = round(nb_off, 6)
        out["net_benefit_offset_gain"] = round(nb_off - nb, 6)
        out["pred_over_obs_offset"] = (round(float(I.w_mean(y, p_off, w)) / prev, 4)
                                       if prev else None)
    return out


def main():
    horizon = float(flag("--horizon", "4"))
    fset = flag("--features", "common")
    time_mode = flag("--time", "linear")
    rule = flag("--rule", "cif_mid")
    n_boot = int(flag("--boot", "500"))
    models = flag("--models", "logistic,random_forest").split(",")
    pp = pd.read_csv(os.path.join(OUT, "personperiod_pooled.csv"))
    pp["country"] = pp["cohort"].map(I.COH2CTRY)
    pp = pp[pp["country"].notna()].reset_index(drop=True)
    X = I.design(pp, fset, time_mode)
    y = pp["event"].astype(int).values
    frame, counts = I.horizon_frame(pp, horizon, rule)
    pc = I.person_clock(pp)
    pc["country"] = pc["cohort"].map(I.COH2CTRY)
    st = strata(pc, pp).set_index(["cohort", "pid"])
    print(f"incident subgroups horizon={horizon} rule={rule} features={fset} time={time_mode} "
          f"frame_evaluable={counts['evaluable']} boot={n_boot} models={models}", flush=True)

    rows = []
    skipped = []
    for held in sorted(set(pp["country"])):
        tr = (pp["country"].values != held)
        step_L = round(float(np.median(pp.loc[tr, "exposure_years"])) * 4) / 4
        for name in models:
            fr = I.Frozen(X.loc[tr], y[tr], name)
            hb = frame[frame["country"] == held].reset_index(drop=True)
            ph, real = I.horizon_risk(fr, hb, horizon, time_mode, fset, step=step_L)
            key = list(zip(hb["cohort"], hb["pid"]))
            hh = st.loc[key].reset_index()
            for c in hh.columns:
                hb[c] = hh[c].values
            yb = hb["label"].astype(int).to_numpy()
            wb = pd.to_numeric(hb["ipcw"], errors="coerce").fillna(1.0).to_numpy(dtype=float)
            pb = np.asarray(ph, dtype=float)
            lp = logit(pb)
            a = weighted_offset(lp, yb, wb)
            pob = expit(lp + a)
            hb = hb.assign(p=pb, p_off=pob)
            base = dict(held=held, model=name, horizon_rule=rule, offset_log_odds_shift=round(a, 4),
                        realised_horizon_years=round(float(real), 3), step_years=step_L)
            rows.append({**base, "stratum": "ALL", "level": "all held-out persons",
                         **cell_row(yb, pb, wb, I.SEED, n_boot, p_off=pob)})
            for var in ("age_band", "sex", "hypertension", "education", "interval_length",
                        "band_entry"):
                for lv, g in hb.groupby(var, observed=True):
                    if len(g) < 50:
                        skipped.append(dict(held=held, model=name, stratum=var, level=str(lv),
                                            n=len(g)))
                        continue
                    rows.append({**base, "stratum": var, "level": str(lv),
                                 **cell_row(g["label"].astype(int).to_numpy(),
                                            g["p"].to_numpy(dtype=float),
                                            pd.to_numeric(g["ipcw"], errors="coerce")
                                            .fillna(1.0).to_numpy(dtype=float),
                                            I.SEED, n_boot, p_off=g["p_off"].to_numpy(dtype=float))})
        print(f"  {held} done, {sum(r['stratum'] == 'ALL' for r in rows)} ALL-cells so far",
              flush=True)

    d = pd.DataFrame(rows)
    d.to_csv(os.path.join(OUT, "incident_subgroups.csv"), index=False)
    # smallest cell that still produced a two-class AUROC, so the reader can see where these
    # intervals are honest and where they are decorative
    ok = d[d["auroc"].notna()]
    interp = d[d["interpretable"]]
    summary = dict(horizon=horizon, horizon_rule=rule, features=fset, time_mode=time_mode,
                   n_boot=n_boot, models=models, cells=len(d),
                   cells_interpretable=int(len(interp)),
                   interpretable_rule="events >= 10 and n >= 100",
                   cells_skipped_below_50=len(skipped),
                   skipped_detail=skipped[:40],
                   cells_without_discrimination=int(len(d) - len(ok)),
                   min_cell_events_for_auroc=int(ok["events"].min()),
                   min_cell_n_for_auroc=int(ok["n"].min()),
                   frame_counts={k: counts[k] for k in ("evaluable", "event_within_horizon",
                                                        "stroke_free_through_horizon",
                                                        "lost_before_horizon_excluded")})
    json.dump(summary, open(os.path.join(ROOT, "results", "reports",
                                         "incident_subgroups_summary.json"), "w", encoding="utf-8"),
              indent=1, default=float)
    show = ["held", "model", "stratum", "level", "n", "events", "prevalence_ipcw",
            "mean_predicted_ipcw", "pred_over_obs", "auroc", "auroc_lo", "auroc_hi",
            "net_benefit_5pct", "net_benefit_treat_all", "net_benefit_offset_5pct",
            "net_benefit_offset_gain", "interpretable"]
    with pd.option_context("display.width", 260, "display.max_rows", 400):
        print(d[show].to_string(index=False), flush=True)
    print(json.dumps(summary, indent=1), "->", os.path.join(OUT, "incident_subgroups.csv"))


if __name__ == "__main__":
    main()
