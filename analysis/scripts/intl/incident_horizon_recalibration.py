"""P0 audit: does the intercept-repair result survive when it is fitted ON THE HORIZON SCALE?

The reviewer's decisive question, verbatim:

  "如果在完全一致的四年风险尺度上重新进行局部截距校准，中国队列的 net benefit 是否仍然从约
   0.0022 提升至 0.0167，同时墨西哥队列不再出现异常的风险下降？"

What the published adaptation arm (incident_adaptation.py) actually does is fit the correction on
the INTERVAL-scale linear predictor and then run the corrected hazard through the composition.
That is a legitimate estimator of a different estimand, but it is not "recalibrate the four-year
risk", and the two are numerically different: shifting every step's log-odds by `a` and then
multiplying survivals compounds `a` over steps, and a slope b<1 shrinks each step toward the
baseline hazard rather than toward the baseline four-year risk. So the headline could in principle
be an artefact of correcting the wrong scale.

This script fits BOTH and reports them side by side on identical evaluation persons:

  scale=interval  a and b fitted on the local sample's per-interval log-odds, applied inside the
                  four-year composition   (the published estimator)
  scale=horizon   a and b fitted on the local sample's composed four-year risk, applied directly
                  to the evaluation persons' composed four-year risk (the honest estimator)

and it separates the three quantities the manuscript previously ran together:

  calibration-in-the-large  intercept only, slope pinned at 1  -> `cil_intercept`
  logistic recalibration    intercept and slope jointly        -> `recal_intercept`, `recal_slope`
  observed/expected         mean(predicted) / mean(observed)   -> `oe_ratio`

Only persons with a determinable four-year label enter at all: a local sample for horizon-scale
calibration means local people who were actually followed for four years, which is a deployment
requirement this script states in its output rather than assumes.

Everything is evaluated on persons NOT in the local sample, so no person is adapted on and then
scored, and every strategy is scored on the same rows in the same replicate, so the reported
gains are paired.

Usage
  python incident_horizon_recalibration.py [--models logistic,elasticnet,xgboost]
                                           [--fractions 0.02,0.05,0.10,0.25,0.50]
                                           [--reps 20] [--horizon 4] [--horizon-rule cif_mid]
"""
import os, sys, json, numpy as np, pandas as pd, warnings
warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)
import modeling as M
import run_loco_v2 as V2
import run_incident_loco as I
import incident_adaptation as A
from sklearn.metrics import roc_auc_score, brier_score_loss

OUT = I.OUT
SEED = V2.SEED
STRATS = ("offset_interval", "recalibrate_interval", "retrain_local",
          "offset_horizon", "recalibrate_horizon")


def flag(name, default):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default


def logit(p):
    p = np.clip(np.asarray(p, dtype=float), 1e-9, 1 - 1e-9)
    return np.log(p / (1.0 - p))


def sigmoid(z):
    return 1.0 / (1.0 + np.exp(-z))


def fit_offset_weighted(lp, y, w):
    """Calibration-in-the-large with IPCW weights: the single intercept that makes the weighted
    mean predicted risk equal the weighted observed risk. The bisection in incident_adaptation is
    unweighted, so the weighted target needs its own."""
    s = float(np.sum(w))
    if s <= 0 or not (0 < float(np.sum(w * y) / s) < 1):
        return 0.0
    q = float(np.sum(w * y) / s)
    lo, hi = -12.0, 12.0
    for _ in range(80):
        mid = (lo + hi) / 2.0
        if float(np.sum(w * sigmoid(lp + mid)) / s) < q:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2.0


def metrics(yb, ph, w=None):
    """The calibration trio kept apart by name, plus decision-curve net benefit. `yb` and `ph`
    must already be the evaluation-person rows only. Weights are the estimand's IPCW weights."""
    yb = np.asarray(yb).astype(int); ph = np.asarray(ph, dtype=float)
    w = np.ones(len(yb)) if w is None else np.asarray(w, dtype=float)
    weighted = bool(np.any(np.abs(w - 1.0) > 1e-12))
    b = I.w_mean(yb, (ph - yb) ** 2, w)
    q = I.w_mean(yb, yb, w)
    mp = I.w_mean(yb, ph, w)
    ri, rs = I.weighted_recal(yb, ph, w)            # intercept AND slope, jointly estimated
    cil = fit_offset_weighted(logit(ph), yb, w)     # slope pinned at 1 = calibration-in-the-large
    return dict(auroc=float(roc_auc_score(yb, ph, sample_weight=w if weighted else None)),
                brier=b,
                scaled_brier=float((q * (1 - q) - b) / (q * (1 - q))) if 0 < q < 1 else np.nan,
                mean_pred=mp, obs_prev=q, obs_prev_unweighted=float(yb.mean()),
                mean_pred_unweighted=float(ph.mean()),
                oe_ratio=float(mp / q) if q > 0 else np.nan,
                cil_intercept=float(cil), recal_intercept=float(ri), recal_slope=float(rs),
                nb_at_02=I.weighted_net_benefit(yb, ph, w, 0.02),
                nb_at_05=I.weighted_net_benefit(yb, ph, w, 0.05),
                nb_at_10=I.weighted_net_benefit(yb, ph, w, 0.10),
                nb_all_at_05=I.weighted_net_benefit(yb, np.ones(len(yb)), w, 0.05),
                flagged_at_05=float(np.sum(w * (ph >= 0.05)) / np.sum(w)))


def main():
    models = flag("--models", "logistic,elasticnet,xgboost").split(",")
    fracs = [float(x) for x in flag("--fractions", "0.02,0.05,0.10,0.25,0.50").split(",")]
    reps = int(flag("--reps", "20"))
    horizon = float(flag("--horizon", "4"))
    fset, time_mode = "common", "linear"

    rule = flag("--horizon-rule", "cif_mid")
    frame_file = flag("--pp", "personperiod_pooled.csv")
    pp = pd.read_csv(os.path.join(OUT, frame_file))
    pp["country"] = pp["cohort"].map(I.COH2CTRY)
    pp = pp[pp["country"].notna()].reset_index(drop=True)
    X = I.design(pp, fset, time_mode)
    y = pp["event"].astype(int).values
    # one estimand per process: run the script twice, once per rule, and the filenames carry which.
    base_frame, hcounts = I.horizon_frame(pp, horizon, rule)
    print(f"horizon person accounting [{rule}]: {json.dumps(hcounts)}", flush=True)

    rows, curves = [], []
    for held in sorted(set(pp["country"])):
        tr = (pp["country"].values != held); te = (pp["country"].values == held)
        cmode = pp.loc[te, "censor_mode"].iloc[0]
        step_L = round(float(np.median(pp.loc[tr, "exposure_years"])) * 4) / 4
        hb = base_frame[base_frame["country"] == held].reset_index(drop=True)
        yb_all = hb["label"].astype(int).values
        wb_all = pd.to_numeric(hb["ipcw"], errors="coerce").fillna(1.0).to_numpy(dtype=float)
        pid_all = hb["pid"].values
        qb = float(yb_all.mean())
        sub_te = pp.loc[te].reset_index(drop=True)
        X_te = X.loc[te].reset_index(drop=True)
        y_te = y[te]
        print(f"\n=== {held}: horizon-evaluable persons={len(hb)} events={int(yb_all.sum())} "
              f"prevalence={qb:.4f} censor={cmode} step={step_L}", flush=True)
        for name in models:
            frozen = I.Frozen(X.loc[tr], y[tr], name)
            ph_all, realised = I.horizon_risk(A.Adapter(frozen, 0.0, 1.0), hb, horizon,
                                             time_mode, fset, step=step_L)
            lp_all = logit(ph_all)
            lp_int = A.linear_predictor(frozen, X_te)

            # frozen with NO local data: every horizon-evaluable person of the held-out country
            rows.append(dict(held=held, model=name, strategy="frozen_all", scale="horizon",
                             frac=0.0, rep=0, censor_mode=cmode,
                             realised_horizon_years=realised, local_persons=0,
                             local_interval_rows=0, n_eval_persons=int(len(hb)),
                             fitted_intercept=0.0, fitted_slope=1.0,
                             **metrics(yb_all, ph_all, wb_all)))

            for frac in fracs:
                for rep in range(reps):
                    rng = np.random.default_rng(SEED + 7000 + 1000 * rep + int(100 * frac))
                    upid = np.unique(pid_all)
                    take = max(2, int(round(len(upid) * frac)))
                    pick = rng.choice(upid, size=take, replace=False)
                    loc = np.isin(pid_all, pick)
                    ev = ~loc
                    # Regression guard for the adaptation/evaluation independence the manuscript claims.
                    # ev is the complement of loc, so this cannot fire unless a future edit splits by row
                    # instead of by person; incident_adaptation_leakage_audit.py measures it empirically.
                    assert not (set(pid_all[loc]) & set(pid_all[ev])), "local-adaptation and evaluation persons overlap"
                    if len(np.unique(yb_all[loc])) < 2 or len(np.unique(yb_all[ev])) < 2:
                        continue
                    inl = np.isin(sub_te["pid"].values, pick)
                    if len(np.unique(y_te[inl])) < 2:
                        continue
                    hb_ev = hb[ev].reset_index(drop=True)
                    y_e = hb_ev["label"].astype(int).values
                    w_e = wb_all[ev]

                    # --- horizon scale: fit on the local persons' COMPOSED four-year risk
                    a_h, _ = A.fit_offset(lp_all[loc], yb_all[loc])
                    b0_h, b1_h = A.fit_recal(lp_all[loc], yb_all[loc])

                    # --- interval scale: fit on the local persons' INTERVAL rows, then run the
                    #     corrected hazard back through the same four-year composition
                    a_i, s_i = A.fit_offset(lp_int[inl], y_te[inl])
                    b0_i, b1_i = A.fit_recal(lp_int[inl], y_te[inl])
                    ph_off_i, _ = I.horizon_risk(A.Adapter(frozen, a_i, s_i), hb_ev, horizon,
                                                 time_mode, fset, step=step_L)
                    ph_cal_i, _ = I.horizon_risk(A.Adapter(frozen, b0_i, b1_i), hb_ev, horizon,
                                                 time_mode, fset, step=step_L)
                    fr_local = I.Frozen(X_te[inl], y_te[inl], name)
                    ph_new, _ = I.horizon_risk(fr_local, hb_ev, horizon, time_mode, fset,
                                               step=step_L)

                    common = dict(held=held, model=name, frac=frac, rep=rep, censor_mode=cmode,
                                  realised_horizon_years=realised, local_persons=int(loc.sum()),
                                  local_interval_rows=int(inl.sum()),
                                  n_eval_persons=int(len(y_e)))
                    scored = (("frozen_sub", "both", 0.0, 1.0, ph_all[ev]),
                              ("offset_interval", "interval", a_i, s_i, ph_off_i),
                              ("recalibrate_interval", "interval", b0_i, b1_i, ph_cal_i),
                              ("retrain_local", "interval", np.nan, np.nan, ph_new),
                              ("offset_horizon", "horizon", a_h, 1.0, sigmoid(lp_all[ev] + a_h)),
                              ("recalibrate_horizon", "horizon", b0_h, b1_h,
                               sigmoid(b0_h + b1_h * lp_all[ev])))
                    last = {}
                    for strat, scale, ai, bi, ph in scored:
                        r = dict(**common, strategy=strat, scale=scale,
                                 fitted_intercept=float(ai), fitted_slope=float(bi),
                                 **metrics(y_e, ph, w_e))
                        rows.append(r)
                        last[strat] = r

                    # decile calibration curve on the two scales that matter, first replicate only
                    if rep == 0:
                        for strat, ph in (("frozen", ph_all[ev]),
                                          ("offset_interval", ph_off_i),
                                          ("offset_horizon", sigmoid(lp_all[ev] + a_h))):
                            d = pd.qcut(ph, 10, labels=False, duplicates="drop")
                            for dec, g in pd.DataFrame({"d": d, "p": ph, "y": y_e}).groupby("d"):
                                curves.append(dict(held=held, model=name, strategy=strat,
                                                   frac=frac, decile=int(dec), n=len(g),
                                                   mean_pred=float(g["p"].mean()),
                                                   observed=float(g["y"].mean())))
                    if rep == reps - 1:
                        fz, oh = last["frozen_sub"], last["offset_horizon"]
                        print(f"  {held} {name:11s} frac={frac:5.2f} "
                              f"local_persons={int(loc.sum()):6d} | frozen mean_p "
                              f"{fz['mean_pred']:.4f} NB@5% {fz['nb_at_05']:+.5f} | "
                              f"offset-horizon mean_p {oh['mean_pred']:.4f} NB@5% "
                              f"{oh['nb_at_05']:+.5f} (all {oh['nb_all_at_05']:+.5f})", flush=True)

    out = pd.DataFrame(rows)
    fshort = "" if frame_file == "personperiod_pooled.csv" else \
        "_" + os.path.splitext(frame_file)[0].replace("personperiod_", "")
    dest = os.path.join(OUT, f"incident_horizon_recalibration_{rule}{fshort}.csv")
    out.to_csv(dest, index=False)
    pd.DataFrame(curves).to_csv(
        os.path.join(OUT, f"incident_horizon_calibration_curves_{rule}{fshort}.csv"), index=False)
    print(f"\nwrote {dest}  rows={len(out)}")

    # Paired deltas. Every strategy and the frozen model are scored on the SAME persons in the
    # SAME replicate, so the difference is a paired quantity and its spread over replicates is an
    # honest interval for the GAIN, not for the level.
    for held in sorted(set(out["held"])):
        for name in models:
            fz = out[(out["held"] == held) & (out["model"] == name)
                     & (out["strategy"] == "frozen_sub")].pivot_table(index="frac", columns="rep",
                                                                     values="nb_at_05")
            for strat in STRATS:
                s = out[(out["held"] == held) & (out["model"] == name)
                        & (out["strategy"] == strat)].pivot_table(index="frac", columns="rep",
                                                                 values="nb_at_05")
                for frac in s.index:
                    a, b = s.loc[frac].dropna(), fz.loc[frac].dropna()
                    common_rep = a.index.intersection(b.index)
                    if len(common_rep) < 3:
                        continue
                    d = (a.loc[common_rep] - b.loc[common_rep]).to_numpy()
                    g = out[(out["held"] == held) & (out["model"] == name)
                            & (out["strategy"] == strat) & (out["frac"] == frac)]
                    print(f"  {held} {name:11s} {strat:20s} frac={frac:5.2f} "
                          f"mean_pred {g['mean_pred'].mean():.4f} vs observed "
                          f"{g['obs_prev'].mean():.4f} O/E {g['oe_ratio'].mean():.3f} "
                          f"CIL {g['cil_intercept'].mean():+.3f} slope {g['recal_slope'].mean():.3f} "
                          f"NB@5% {g['nb_at_05'].mean():+.5f} paired gain {np.mean(d):+.5f} "
                          f"[{np.percentile(d, 2.5):+.5f}, {np.percentile(d, 97.5):+.5f}] "
                          f"beat frozen in {int((d > 0).sum())}/{d.size} replicates")
    return out


if __name__ == "__main__":
    main()
