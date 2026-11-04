"""Incident-stroke LOCO: discrete-time hazards fitted on two panels, validated on the third.

The outcome here is a FIRST reported stroke inside an observation interval, not "has anyone ever
reported a stroke", so the target is the one a clinician could act on.

Reuses, unchanged, the audited machinery of run_loco_v2.py - the frozen estimators, the imputer
with its degenerate-column guard, the fitted-transform `prep`, and the person-clustered bootstrap
- so the prevalent and incident arms differ only in the outcome, never in the pipeline.

Design
------
* Unit = person x interval (personperiod_pooled.csv). Covariates are those of the interval START
  wave, so nothing measured after the event can enter a risk set.
* Time enters as `t_since_entry_years` (--time linear|none). Without a time term a discrete-time
  model asserts a constant hazard across a panel whose intervals run from 2 to 20 years.
* NHANES contributes no interval: its cycles resample different people, so the incident arm is a
  THREE-panel leave-one-country-out test (CN, KR, MX) and is described as one.
* Korea carries censor_mode="last_interview" because the nine KLoSA main wave workbooks have no
  vital-status or death field (verified column by column; the death data sits in the
  w0{2..8}_exit_e exit files, which are not on disk). China and Mexico censor on death. The
  asymmetry is carried into every row of every table rather than averaged away.
* Two evaluation levels, because an interval hazard is the likelihood unit but nobody screens on
  it:
    interval level - all intervals of the held-out panel.
    horizon level  - one row per person, asked as a SINGLE interval of length H (baseline
      covariates, exposure_years = H): the estimand "probability of a first stroke within H
      years", with no assumption about the shape of the hazard inside the interval. It never
      consults whether the person was in fact followed to H, so it cannot leak the label.
      Labels: 1 = stroke within H; 0 = observed at least to H and stroke-free; a person who dies
      or vanishes before H without a stroke is EXCLUDED and the counts are reported - folding
      competing deaths into the negatives would invent a result.
* Decision-curve net benefit is reported at thresholds a screening programme would consider,
  against treat-all and treat-none, because AUROC says nothing about whether a model is usable.

Usage
  python run_incident_loco.py [--features common|extended] [--time linear|none]
                              [--horizon 4] [--boot 2000] [--weights]
"""
import os, sys, json, numpy as np, pandas as pd, warnings
warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))          # modeling.py lives in analysis/scripts
sys.path.insert(0, HERE)
import modeling as M
import run_loco_v2 as V2
from sklearn.impute import SimpleImputer
from sklearn.metrics import roc_auc_score, brier_score_loss, average_precision_score

OUT = os.path.abspath(os.path.join(HERE, "..", "..", "..", "data", "processed", "intl", "incident"))
SEED = V2.SEED
BASE = ["logistic", "elasticnet", "agesex_logistic", "spline_logistic", "random_forest",
        "random_forest_balanced", "xgboost", "gradient_boosting", "lightgbm"]
COH2CTRY = {"CHARLS": "CN", "KLoSA": "KR", "MHAS": "MX", "HRS": "US"}
THRESHOLDS = (0.02, 0.05, 0.10, 0.15)


def flag(name, default):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default


# Definitional-ablation feature sets (review item P1-5). The primary "common" set is already the
# intersection of what every panel ASKS; these sets additionally drop the concepts whose QUESTION
# differs between panels, which no amount of recoding can fix, and whose measured availability is
# in `incident_cr_definition.py`'s report:
#   heart_attack - "ever had heart problems" (US, CN) vs a specific heart-attack/MI item (KR, MX)
#   alcohol      - "ever drinks any alcohol" (US) vs a last-year item (CN)
# The stricter tier adds the items whose AVAILABILITY rather than meaning differs:
#   hypertension - 29.1% of Korean interval rows missing (0.0-1.0% in the other three panels)
#   marital      - 16.1% Korean, 0.1% US, 0.0% CN/MX
DEFINITION_DROPS = {"core": ["heart_attack", "alcohol"],
                    "core_strict": ["heart_attack", "alcohol", "hypertension", "marital"]}


def design(df, fset, time_mode):
    """Interval-row features: the shared one-hot/numeric encoding plus the time term. Identifiers
    and the outcome are never features (modeling.encode only takes its own column lists).

    `exposure_years` IS a feature, and it has to be: without it the model is asked to predict the
    probability of an event in an interval while being shown nothing that says how long that
    interval is, and the panels mix 2-year and 20-year gaps. It is known at prediction time
    because the analyst chooses it, and the horizon prediction chooses it to be the horizon.

    `fset` also accepts the two definitional-ablation names in DEFINITION_DROPS, which subtract
    from "common" rather than adding to it, so the ablated arms are nested inside the primary arm."""
    X = M.encode(df)
    if fset == "common":
        X = X.drop(columns=[c for c in V2.EXTRA if c in X.columns])
    if fset in DEFINITION_DROPS:
        X = X.drop(columns=[c for c in V2.EXTRA if c in X.columns])
        gone = [c for c in X.columns
                if any(c == d or c.startswith(d + "_") for d in DEFINITION_DROPS[fset])]
        assert gone, f"ablation fset {fset!r} dropped nothing - column names changed"
        X = X.drop(columns=gone)
    X["exposure_years"] = pd.to_numeric(df["exposure_years"], errors="coerce")
    if time_mode == "linear":
        X["t_since_entry_years"] = pd.to_numeric(df["t_since_entry_years"], errors="coerce")
    return X


class Frozen:
    """One fitted model plus every preprocessing artefact needed to apply it to brand-new rows.
    The horizon stepping re-uses `apply`, so the transform it scores is the one it was trained
    under - not a refitted approximation of it."""

    def __init__(self, Xtr, ytr, name, sample_weight=None):
        self.name = name
        self.kind, clf = V2.estimator(name)
        self.cols = list(Xtr.columns)
        self.imp = SimpleImputer(strategy="median").fit(Xtr)
        self.names = list(self.imp.get_feature_names_out())
        A = pd.DataFrame(self.imp.transform(Xtr), columns=self.names, index=Xtr.index)
        self.keep = [c for c in self.names if A[c].notna().any() and A[c].nunique(dropna=True) > 1]
        mat, self.apply, self.out_cols = V2.prep(A[self.keep], self.kind, self.keep)
        self.clf = V2.clone(clf)
        try:
            self.clf = self.clf.fit(mat, ytr, sample_weight=sample_weight) \
                if sample_weight is not None else self.clf.fit(mat, ytr)
        except TypeError:
            self.clf = V2.clone(clf).fit(mat, ytr)

    def _mat(self, F):
        Fi = pd.DataFrame(self.imp.transform(F[self.cols]), columns=self.names, index=F.index)
        return self.apply(Fi[self.keep])

    def predict(self, F):
        return self.clf.predict_proba(self._mat(F))[:, 1]


DEATH_STATUS = ["death_dated", "death_status"]
HORIZON_RULES = ("cif_mid", "exclusive_start")


def person_clock(pp):
    """One row per person with every time an incidence estimand can ask for, plus their baseline
    covariates (first interval), so a prediction and a label come from the same person frame.

    A stroke is only known to have happened BETWEEN two interviews. The discrete-time model
    composes hazards across that interval, which is an implicit uniform-within-interval assumption,
    so the empirical date that MATCHES the model is the interval midpoint. The interval start is
    what the earlier frame used, and it counts a stroke whose interval straddles the horizon as
    "within the horizon" - which is not the estimand anyone would state to a clinician. Both are
    carried, so the choice is visible in the output instead of buried in a helper."""
    pp = pp.copy()
    pp["end_offset"] = pp["t_since_entry_years"] + pp["exposure_years"]
    pp["mid_offset"] = pp["t_since_entry_years"] + pp["exposure_years"] / 2.0
    g = pp.sort_values(["cohort", "pid", "k"]).groupby(["cohort", "pid"], sort=False)
    out = g.first().reset_index()
    for nm, sel, col in (("t_stroke_mid", pp["event"] == 1, "mid_offset"),
                         ("t_stroke_start", pp["event"] == 1, "t_since_entry_years"),
                         ("t_stroke_end", pp["event"] == 1, "end_offset"),
                         ("t_death", pp["end_status"].isin(DEATH_STATUS), "end_offset"),
                         ("t_death_start", pp["end_status"].isin(DEATH_STATUS),
                          "t_since_entry_years")):
        out = out.merge(pp[sel].groupby(["cohort", "pid"])[col].min().rename(nm),
                        on=["cohort", "pid"], how="left")
    out["t_cens"] = g["end_offset"].max().to_numpy()
    out["n_intervals"] = g.size().to_numpy()
    for c in ("t_stroke_mid", "t_stroke_start", "t_stroke_end", "t_death", "t_death_start",
              "t_cens"):
        out[c] = pd.to_numeric(out[c], errors="coerce").astype(float)
    # t_since_entry_years is 0 at a person's first interval by construction, so the largest
    # interval-end offset IS their total observed follow-up.
    out["follow_years"] = out["t_cens"]
    return out


def censoring_survival(uncensored, times, horizon):
    """G(t) = P(still in follow-up at t), Kaplan-Meier with LOSS TO FOLLOW-UP as the only failure
    being measured. A competing death is an outcome, never a censoring event, so it enters as a
    truncation time and cannot depress G."""
    keys = np.unique(np.round(np.asarray(times, dtype=float), 6))
    keys = keys[keys <= horizon]
    order = np.argsort(times, kind="stable")
    t, d = np.asarray(times, dtype=float)[order], np.asarray(uncensored, dtype=bool)[order]
    n = len(t)
    surv, i, steps = 1.0, 0, {}
    for gt in keys:
        while i < n and t[i] <= gt:
            j = i
            while j < n and t[j] == t[i]:
                j += 1
            at_risk = n - i
            dd = int((~d[i:j]).sum())          # a loss to follow-up is a failure of G
            if dd and at_risk > 0:
                surv *= (1.0 - dd / at_risk)
            i = j
        steps[round(float(gt), 6)] = surv
    return steps


def horizon_frame(pp, horizon, rule="cif_mid", cover_slack=0.5):
    """One row per person who has a determinable four-year endpoint, on ONE stated estimand, with
    the IPCW weight that endpoint needs.

      cif_mid          - the cumulative incidence of a first stroke within H, competing death kept
                         in. A person who dies inside the window without a stroke is a NON-EVENT,
                         not missing data: they did not have a stroke within four years. Someone
                         lost to follow-up before their endpoint is determined is excluded, and the
                         people who remain carry 1/G(tau-) so that exclusion does not bias the
                         level. This is the estimand the manuscript should be judged on.
      exclusive_start  - the frame the analysis used before the estimand was audited: strokes dated
                         at the interval START, pre-horizon deaths dropped entirely, coverage
                         judged from the interval END. Kept so the before/after is a published
                         sensitivity arm rather than a quiet edit.
    """
    pc = person_clock(pp)
    if rule == "exclusive_start":
        col = "t_stroke_start"
    elif rule in ("cif_mid", "cif_start", "cif_end"):
        col = {"cif_mid": "t_stroke_mid", "cif_start": "t_stroke_start",
               "cif_end": "t_stroke_end"}[rule]
    else:
        raise ValueError(f"unknown horizon rule {rule!r}")
    t_s = pc[col].to_numpy(dtype=float)
    # the pre-audit frame dated a death at its interval START too, so reproducing it means using
    # the same offset here rather than the (better) end offset - the point of the sensitivity arm
    # is that it is the old number, not a new number that looks like the old one.
    t_d = pc["t_death_start" if rule == "exclusive_start" else "t_death"].to_numpy(dtype=float)
    t_c = pc["t_cens"].to_numpy(dtype=float)
    stroke = np.isfinite(t_s) & (t_s <= horizon)
    died_first = np.isfinite(t_d) & (t_d <= horizon) & ~stroke
    if rule == "exclusive_start":
        determined = stroke | (~stroke & ~died_first & (t_c >= horizon - cover_slack))
        weight = np.ones(len(pc))
    else:
        determined = stroke | died_first | (t_c >= horizon - 1e-9)
        tau = np.where(stroke, np.fmin(t_s, horizon),
                       np.where(died_first, np.fmin(t_d, horizon), np.fmin(t_c, horizon)))
        obs = np.where(determined, tau, t_c)
        steps = censoring_survival(determined, obs, horizon)
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
    out["horizon_rule"] = rule
    counts = {"horizon_rule": rule, "persons_total": int(len(pc)),
              "event_within_horizon": int(stroke.sum()),
              "death_within_horizon_no_stroke": int(died_first.sum()),
              "death_counted_as_non_event": int((determined & died_first).sum()),
              "death_excluded_from_frame": int((~determined & died_first).sum()),
              "lost_before_horizon_excluded": int((~determined).sum()),
              "stroke_free_through_horizon": int((determined & ~stroke & ~died_first).sum()),
              "evaluable": int(determined.sum()),
              "observed_prevalence_unweighted": float(stroke[determined].mean())
              if determined.any() else np.nan,
              "observed_prevalence_ipcw": float(np.sum(weight[determined] * stroke[determined])
                                                / np.sum(weight[determined]))
              if determined.any() else np.nan,
              "median_ipcw_weight": float(np.median(weight[determined]))
              if determined.any() else np.nan,
              "max_ipcw_weight": float(np.max(weight[determined])) if determined.any() else np.nan}
    return out, counts


def person_baseline(pp, horizon, cover_slack=0.5):
    """Back-compatibility wrapper: the pre-audit frame. New code should call `horizon_frame` and
    name the estimand out loud."""
    return horizon_frame(pp, horizon, "exclusive_start", cover_slack)


def horizon_risk(fr, base, horizon, time_mode, fset, step=None):
    """Risk of a first stroke within `horizon` years.

    Two ways of getting it, and the difference is not cosmetic:
      step=None  - one interval of length H. Exactly the estimand, no within-interval assumption,
                   but H must be a length the model actually saw. China's and Korea's panels have
                   median gaps of 2.08 and 2.00 years with a 95th percentile of 3.08 and 2.17, so a
                   4-year interval is an extrapolation for them and the trees respond by flattening.
      step=L     - compose ceil(H/L) hazards at the panel's own typical interval length L,
                   advancing age between steps. Every prediction then sits inside the training
                   distribution of `exposure_years`, which is the point of a discrete-time model.
                   The realised horizon is n_steps*L and is returned so the caller cannot pretend
                   it is exactly H."""
    n = len(base)
    if step is None:
        frame = base.copy()
        frame["exposure_years"] = horizon
        if time_mode == "linear":
            frame["t_since_entry_years"] = 0.0
        return fr.predict(design(frame, fset, time_mode).reindex(columns=fr.cols)), horizon

    n_steps = max(1, int(round(horizon / step)))
    realised = n_steps * step
    surv = np.ones(n)
    for j in range(n_steps):
        frame = base.copy()
        frame["age"] = pd.to_numeric(base["age"], errors="coerce").values + j * step
        frame["exposure_years"] = step
        if time_mode == "linear":
            frame["t_since_entry_years"] = j * step
        h = fr.predict(design(frame, fset, time_mode).reindex(columns=fr.cols))
        surv *= (1.0 - h)
    return 1.0 - surv, realised


def exposure_support(tr_exp, horizon):
    """How much of the TRAINING panel's interval lengths can actually inform a horizon-length
    prediction: the share within a factor of two of it, plus the observed range."""
    a = np.asarray(tr_exp, dtype=float)
    a = a[np.isfinite(a)]
    return {"train_interval_years_min": round(float(a.min()), 3),
            "train_interval_years_median": round(float(np.median(a)), 3),
            "train_interval_years_max": round(float(a.max()), 3),
            "train_within_factor2_of_horizon_pct": round(float(((a >= horizon / 2)
                                                               & (a <= horizon * 2)).mean()), 4)}


def net_benefit(y, p, thr):
    tp = float(((p >= thr) & (y == 1)).sum()); fp = float(((p >= thr) & (y == 0)).sum())
    return tp / len(y) - fp / len(y) * (thr / (1.0 - thr))


def iid_boot_auroc(y, p, n, seed, w=None):
    """Person-level (one row per person here) bootstrap AUROC, replicate by replicate. Seeded per
    replicate so every fitted model sees the same resamples and nothing is stored: a
    (n x rows) index matrix is 0.5 GB for the US panel and is thrown away after one statistic."""
    from sklearn.metrics import roc_auc_score as _r
    use_w = w is not None and np.any(np.abs(np.asarray(w) - 1.0) > 1e-12)
    out = []
    for j in range(n):
        ii = np.random.default_rng([seed, j]).integers(0, len(y), len(y))
        if len(np.unique(y[ii])) > 1:
            out.append(_r(y[ii], p[ii], sample_weight=w[ii] if use_w else None))
    return np.asarray(out, dtype=float)


def w_mean(y, p, w):
    s = float(np.sum(w))
    if s <= 0:
        return np.nan
    return float(np.sum(w * p) / s)


def weighted_recal(y, p, w):
    """Calibration intercept and slope with IPCW weights, same joint fit as cal_intercept_slope."""
    from sklearn.linear_model import LogisticRegression
    lp = np.log(np.clip(p, 1e-9, 1 - 1e-9) / (1 - np.clip(p, 1e-9, 1 - 1e-9)))
    lr = LogisticRegression(C=1e6, max_iter=1000, solver="lbfgs")
    lr.fit(lp.reshape(-1, 1), y, sample_weight=w)
    return float(lr.intercept_[0]), float(lr.coef_[0][0])


def weighted_net_benefit(y, p, w, thr):
    f_ = p >= thr
    s = float(np.sum(w))
    if s <= 0:
        return np.nan
    tp = float(np.sum(w[f_] * y[f_]))
    fp = float(np.sum(w[f_] * (1 - y[f_])))
    return tp / s - fp / s * (thr / (1.0 - thr))


def main():
    # --pp selects the coverage frame the model is TRAINED on, not just the frame it is scored on:
    # personperiod_strict.csv truncates every interval at the last wave where the stroke item was
    # actually answerable, so the risk set, the labels and the horizon frame all agree with each other.
    frame_file = flag("--pp", "personperiod_pooled.csv")
    pp = pd.read_csv(os.path.join(OUT, frame_file))
    fset = flag("--features", "common")
    time_mode = flag("--time", "linear")
    horizon = float(flag("--horizon", "4"))
    rules = flag("--horizon-rules", ",".join(HORIZON_RULES)).split(",")
    n_boot = int(flag("--boot", "2000"))
    use_w = "--weights" in sys.argv
    pp["country"] = pp["cohort"].map(COH2CTRY)
    pp = pp[pp["country"].notna()].reset_index(drop=True)
    X = design(pp, fset, time_mode)
    y = pp["event"].astype(int).values
    grp = (pp["cohort"].astype(str) + "|" + pp["pid"].astype(str)).values
    wt = pd.to_numeric(pp["wt_start"], errors="coerce").fillna(1.0).values
    # The estimand is named, not assumed. `cif_mid` is the cumulative incidence of a first stroke
    # within H with competing deaths kept in as non-events and loss to follow-up carried by IPCW;
    # `exclusive_start` is the pre-audit frame, run alongside so the reader can see which number
    # the choice of convention is responsible for.
    frames = {r: horizon_frame(pp, horizon, r) for r in rules}
    print(f"incident intervals={len(pp)} persons={len(set(grp))} events={int(pp.event.sum())} "
          f"cohorts={sorted(set(pp.country))} features={fset} time={time_mode} weights={use_w} "
          f"horizon={horizon}y rules={rules}", flush=True)
    for r, (_, c) in frames.items():
        print(f"  horizon accounting [{r}]: {json.dumps(c)}", flush=True)
    rows = []
    for held in sorted(set(pp["country"])):
        tr = (pp["country"].values != held); te = (pp["country"].values == held)
        yt = y[te]; qte = float(yt.mean()); ptr = float(y[tr].mean())
        naive_train = ptr ** 2 * (1 - qte) + (1 - ptr) ** 2 * qte
        naive_oracle = qte * (1 - qte)
        cmode = pp.loc[te, "censor_mode"].iloc[0]
        fitted = {}
        for name in BASE:
            fitted[name] = Frozen(X.loc[tr], y[tr], name,
                                  sample_weight=(wt[tr] if use_w else None))
        support = exposure_support(pp.loc[tr, "exposure_years"], horizon)
        # the composed horizon steps over the interval length the TRAINING panels actually use
        step_L = round(float(np.median(pp.loc[tr, "exposure_years"])) * 4) / 4
        for name in BASE:
            fr = fitted[name]
            p = fr.predict(X.loc[te])
            auc = float(roc_auc_score(yt, p)); br = float(brier_score_loss(yt, p))
            ci_a, cs = M.cal_intercept_slope(yt, p)
            bd = np.full(n_boot, np.nan)
            for i, idx in enumerate(V2.bootstrap_seeded_draws(grp[te], n_boot, SEED)):
                yy = yt[idx]
                if yy.min() != yy.max():
                    bd[i] = roc_auc_score(yy, p[idx])
            for rule in rules:
                base_frame, _ = frames[rule]
                hb = base_frame[base_frame["country"] == held].reset_index(drop=True)
                yb = hb["label"].astype(int).values
                wb = pd.to_numeric(hb["ipcw"], errors="coerce").fillna(1.0).to_numpy(dtype=float)
                weighted = bool(np.any(np.abs(wb - 1.0) > 1e-12))
                qb = w_mean(yb, yb, wb)
                nt_h = ptr ** 2 * (1 - qb) + (1 - ptr) ** 2 * qb
                ph_c, real_c = horizon_risk(fr, hb, horizon, time_mode, fset, step=step_L)
                ph_s, real_s = horizon_risk(fr, hb, horizon, time_mode, fset, step=None)
                for lvl, ph, real in ((f"horizon_{int(horizon)}y_composed", ph_c, real_c),
                                      (f"horizon_{int(horizon)}y_single_interval", ph_s, real_s)):
                    if len(np.unique(yb)) < 2:
                        break
                    auc_h = float(roc_auc_score(yb, ph, sample_weight=wb if weighted else None))
                    br_h = float(np.sum(wb * (ph - yb) ** 2) / np.sum(wb))
                    ci_h, sl_h = weighted_recal(yb, ph, wb)
                    bd_h = iid_boot_auroc(yb, ph, n_boot, SEED + 13, wb)
                    row = dict(level=lvl, horizon_rule=rule, feature_set=fset, time=time_mode,
                           weights=use_w,
                           model=name, held=held, censor_mode=cmode, realised_horizon_years=real,
                           n=len(yb), events=int(yb.sum()), events_weighted=float(np.sum(wb * yb)),
                           persons=len(yb), obs_prev=qb,
                           obs_prev_unweighted=float(yb.mean()),
                           prev_train=ptr, brier_naive_train=nt_h,
                           brier_naive_oracle=qb * (1 - qb),
                           mean_pred=w_mean(yb, ph, wb), mean_pred_unweighted=float(ph.mean()),
                           oe_ratio=float(w_mean(yb, ph, wb) / qb) if qb else np.nan,
                           median_ipcw_weight=float(np.median(wb)),
                           auroc=auc_h, auroc_lo=float(np.percentile(bd_h, 2.5)),
                           auroc_hi=float(np.percentile(bd_h, 97.5)),
                           auprc=float(average_precision_score(yb, ph)), brier=br_h,
                           skill_train=float((nt_h - br_h) / nt_h),
                           scaled_brier=float((qb * (1 - qb) - br_h) / (qb * (1 - qb))),
                           cal_intercept=ci_h, cal_slope=sl_h, n_features=len(fr.out_cols),
                           horizon_events=int(yb.sum()), horizon_auroc=auc_h, **support)
                    for thr in THRESHOLDS:
                        row[f"nb_at_{thr:g}"] = weighted_net_benefit(yb, ph, wb, thr)
                        row[f"nb_all_at_{thr:g}"] = weighted_net_benefit(yb, np.ones(len(yb)),
                                                                        wb, thr)
                    rows.append(row)
            row = dict(level="interval", horizon_rule="n/a", feature_set=fset, time=time_mode,
                       weights=use_w,
                       model=name, held=held, censor_mode=cmode, n=int(te.sum()),
                       events=int(yt.sum()), persons=int(pd.Series(grp[te]).nunique()),
                       obs_prev=qte, prev_train=ptr, brier_naive_train=naive_train,
                       brier_naive_oracle=naive_oracle, mean_pred=float(p.mean()), auroc=auc,
                       auroc_lo=float(np.nanpercentile(bd, 2.5)),
                       auroc_hi=float(np.nanpercentile(bd, 97.5)),
                       auprc=float(average_precision_score(yt, p)), brier=br,
                       skill_train=float((naive_train - br) / naive_train),
                       scaled_brier=float((naive_oracle - br) / naive_oracle),
                       cal_intercept=ci_a, cal_slope=cs, n_features=len(fr.out_cols),
                       horizon_events=np.nan, horizon_auroc=np.nan, **support)
            rows.append(row)
            primary = rules[0]
            rh = [x for x in rows if x["model"] == name and x["held"] == held
                  and x["level"].endswith("composed") and x["horizon_rule"] == primary][0]
            r = row
            print(f"  {held} {name:22s} [{cmode:15s}] interval AUROC {r['auroc']:.4f} "
                  f"[{r['auroc_lo']:.4f},{r['auroc_hi']:.4f}] skill {r['skill_train']:+.4f} | "
                  f"{primary} horizon AUROC {rh['auroc']:.4f} mean_p {rh['mean_pred']:.4f} "
                  f"prev {rh['obs_prev']:.4f} O/E {rh['oe_ratio']:.3f} "
                  f"slope {rh['cal_slope']:.3f} int {rh['cal_intercept']:+.2f} "
                  f"NB@5% {rh.get('nb_at_0.05', float('nan')):+.5f} "
                  f"(all {rh.get('nb_all_at_0.05', float('nan')):+.5f})", flush=True)

    out = pd.DataFrame(rows)
    tag = "w" if use_w else "uw"
    # a strict-coverage run must not overwrite the permissive one; the frame is part of the name and
    # part of the accounting key, exactly the defect (last-writer-wins) that keyed the horizon rules.
    fshort = "" if frame_file == "personperiod_pooled.csv" else \
        "_" + os.path.splitext(frame_file)[0].replace("personperiod_", "")
    dest = os.path.join(OUT, f"incident_loco_{fset}_{time_mode}_H{int(horizon)}_{tag}{fshort}.csv")
    out.to_csv(dest, index=False)
    # keyed by horizon AND estimand: a single filename overwritten by whichever arm ran last used
    # to publish the H=6 accounting as though it were the primary H=4 one.
    cpath = os.path.join(OUT, "incident_horizon_counts.json")
    counts_by_key = {}
    if os.path.exists(cpath):
        try:
            counts_by_key = json.load(open(cpath, encoding="utf-8"))
        except Exception:
            counts_by_key = {}
    for r, (_, c) in frames.items():
        counts_by_key[f"H{int(horizon)}_{r}_{fset}_{time_mode}{fshort}"] = c
    with open(cpath, "w", encoding="utf-8") as f:
        json.dump(counts_by_key, f, indent=2)
    print("\nwrote", dest)


if __name__ == "__main__":
    main()
