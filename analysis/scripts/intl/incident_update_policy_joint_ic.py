"""Round-8 P0-1 (China reconciliation): does the selective-updating POLICY flag China once the observed
outcome is interval-censored instead of midpoint-dated?

Round 7 promoted the joint competing-risks model to the primary arm and ran the deployment decision rule
(`incident_update_policy_joint.py`) on the MIDPOINT four-year outcome `yb = (t_stroke_mid <= H)`. That
produced the "Mexico is the country that needs a local update" story. The interval-censored / flexible-hazard
observed-risk estimator (`incident_cr_interval_eval.py`, `incident_cr_interval_flexhaz.py`) then showed that
China's four-year first-stroke incidence is roughly DOUBLE what midpoint dating reports (0.0216 -> ~0.042),
so the transported prediction looks like a severe UNDER-prediction (frozen P/O ~0.4) rather than the mild
over-prediction (P/O ~0.80) the midpoint frame implies. The eighth-round reviewer asked, concretely, whether
the update rule CORRECTLY identifies China under that midpoint-free outcome, and whether a simple local
intercept repair can close a gap whose origin is the event-time rule rather than the model level.

This script answers both on the SAME experiment as round 7: identical subject-level adaptation/evaluation
splits (disjoint by person_id, asserted per replicate), identical local fractions, identical trigger rules
(|a| > z.SE(a) and, for the magnitude-gated arm, |a| >= min-shift), identical independent evaluation set and
5% net-benefit threshold, identical transported joint linear predictor `pj`/`lp`. The ONLY change is the
observed outcome fed to the calibration-in-the-large and to the decision metrics:

    yb_ic = clip((H - t_stroke_start) / (t_stroke_end - t_stroke_start), 0, 1)  for a reported stroke,
            0 otherwise.

That is the interval-censored EXPECTATION that the true (unobserved) stroke time falls before the horizon -
the midpoint hard 0/1 relaxes to a soft label equal to the fraction of the reporting interval lying before H.
The evaluable frame and IPCW weights are HELD FIXED at the midpoint determination so the comparison isolates
the event-time attribution and nothing else (a deliberate, stated approximation, not a full IC re-derivation).

Both arms (midpoint `yb` and interval-censored `yb_ic`) are run per replicate on identical splits so the
trigger rate can be contrasted without any seed/split confounding. Output suffixed `_joint_ic`:
  incident_update_policy_joint_ic_<rule>.csv
  incident_update_policy_joint_ic_summary_<rule>.csv   (per held, frac, policy: midpoint vs IC trigger rate,
                                                        paired NB vs frozen, residual repaired-over-IC gap)

Usage: python incident_update_policy_joint_ic.py [--reps 200] [--fractions 0.02,0.05,0.10,0.25,0.50]
                                                  [--horizon 4] [--z 1.96] [--min-shift 0.25]
"""
import os, sys, json, numpy as np, pandas as pd, warnings
warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE)); sys.path.insert(0, HERE)
import run_loco_v2 as V2
import run_incident_loco as I
import incident_horizon_recalibration as HR
import incident_update_policy as UP
import incident_cr_joint as J
import incident_cr_primary as P
import incident_cr_joint_primary as JP

OUT = I.OUT
SEED = V2.SEED
POLICIES = UP.POLICIES
sigmoid, logit = UP.sigmoid, HR.logit


def flag(name, default):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default


def metrics_lite_ic(y, p, w, horizon_thr=(0.02, 0.05, 0.10, 0.15)):
    """metrics_lite without the int cast: `y` may be a fractional (interval-censored expectation) outcome.
    Brier = E[w (p - y)^2] and obs_prev = E[w y] are the expected versions, which is the correct level
    summary when y is the probability that the event precedes the horizon rather than a realised 0/1."""
    y = np.asarray(y, float); p = np.asarray(p, float)
    w = np.ones(len(y)) if w is None else np.asarray(w, float)
    s = float(np.sum(w))
    if s <= 0:
        return dict(n_eval_rows=int(len(y)), n_eval_events=0.0, mean_pred=np.nan, obs_prev=np.nan,
                    oe_ratio=np.nan, brier=np.nan, scaled_brier=np.nan)
    b = float(np.sum(w * (p - y) ** 2) / s)
    q = float(np.sum(w * y) / s)
    mp = float(np.sum(w * p) / s)
    out = dict(n_eval_rows=int(len(y)), n_eval_events=float(np.sum(w * y)),
               mean_pred=mp, obs_prev=q, oe_ratio=(mp / q if q > 0 else np.nan),
               brier=b,
               scaled_brier=((q * (1 - q) - b) / (q * (1 - q)) if 0 < q < 1 else np.nan))
    for t in horizon_thr:
        out[f"nb_at_{int(round(t * 100)):02d}"] = I.weighted_net_benefit(y, p, w, t)
        out[f"nb_all_at_{int(round(t * 100)):02d}"] = I.weighted_net_benefit(
            y, np.ones(len(y)), w, t)
    out["flagged_at_05"] = float(np.sum(w * (p >= 0.05)) / s)
    return out


def ic_label(hb, horizon):
    """Interval-censored expectation that the true stroke time < horizon, from the reporting interval."""
    ts = pd.to_numeric(hb["t_stroke_start"], errors="coerce").to_numpy(float)
    te = pd.to_numeric(hb["t_stroke_end"], errors="coerce").to_numpy(float)
    width = te - ts
    frac = (horizon - ts) / np.where(width > 0, width, np.nan)
    y = np.clip(frac, 0.0, 1.0)
    y[~np.isfinite(ts)] = 0.0                      # no reported stroke -> event-before-horizon prob 0
    y[~np.isfinite(y)] = 0.0
    return y


def main():
    reps = int(flag("--reps", "200"))
    fracs = [float(x) for x in flag("--fractions", "0.02,0.05,0.10,0.25,0.50").split(",")]
    horizon = float(flag("--horizon", "4"))
    rule = "cif_mid"          # frame + IPCW held at the midpoint determination (stated approximation)
    zcrit = float(flag("--z", "1.96"))
    min_shift = float(flag("--min-shift", "0.25"))
    time_mode, fset = "linear", "common"

    pp = pd.read_csv(os.path.join(OUT, "personperiod_pooled.csv"))
    pp["country"] = pp["cohort"].map(I.COH2CTRY)
    pp = pp[pp["country"].notna()].reset_index(drop=True)
    X = I.design(pp, fset, time_mode)
    ds = pp["event"].astype(int).values
    dd = pp["end_status"].isin(P.DEATH).astype(int).values
    base, hcount = I.horizon_frame(pp, horizon, rule)
    print(f"JOINT-IC policy | frame=midpoint IPCW outcome=IC-expectation reps={reps} z={zcrit} "
          f"min_shift={min_shift} | {json.dumps(hcount)}", flush=True)

    rows = []
    for held in sorted(set(pp["country"])):
        jf, hb, pj, yb_mid, wb, pid, step, lp = JP.build_joint(
            pp, X, ds, dd, base, held, horizon, time_mode, fset)
        hb = hb.reset_index(drop=True)
        pid = np.asarray(pid)
        yb_mid = np.asarray(yb_mid, float)          # hard midpoint 0/1
        yb_ic = ic_label(hb, horizon)               # soft IC expectation
        wb = np.asarray(wb, float)
        ph = np.asarray(pj, float)
        upid = np.unique(pid)
        cmode = pp.loc[pp["country"].values == held, "censor_mode"].iloc[0]
        print(f"\n=== {held}: rows={len(hb)} persons={len(upid)} "
              f"midpoint obs_prev={np.sum(wb*yb_mid)/np.sum(wb):.5f} "
              f"IC obs_prev={np.sum(wb*yb_ic)/np.sum(wb):.5f} "
              f"ratio={ (np.sum(wb*yb_ic)/np.sum(wb)) / max(1e-12, np.sum(wb*yb_mid)/np.sum(wb)):.3f} "
              f"frozen mean_pred={np.sum(wb*ph)/np.sum(wb):.5f} "
              f"P/O_mid={ (np.sum(wb*ph)/np.sum(wb)) / (np.sum(wb*yb_mid)/np.sum(wb)):.3f} "
              f"P/O_IC={ (np.sum(wb*ph)/np.sum(wb)) / (np.sum(wb*yb_ic)/np.sum(wb)):.3f} "
              f"censor={cmode} step={step}", flush=True)

        for frac in fracs:
            for rep in range(reps):
                rng = np.random.default_rng(SEED + 31000 + 977 * rep + int(10000 * frac))
                take = max(2, int(round(len(upid) * frac)))
                pick = rng.choice(upid, size=take, replace=False)
                loc = np.isin(pid, pick)
                ev = ~loc
                assert not set(pid[loc]) & set(pid[ev]), "adaptation and eval share a person"
                for arm, yv in (("mid", yb_mid), ("ic", yb_ic)):
                    # need >=2 distinct local outcomes for the offset solve (fractional labels always pass
                    # when there is any local event mass, but guard on the sum anyway)
                    if not (0.0 < float(np.sum(wb[loc] * yv[loc])) / float(np.sum(wb[loc])) < 1.0):
                        continue
                    if not (0.0 < float(np.sum(wb[ev] * yv[ev])) / float(np.sum(wb[ev])) < 1.0):
                        continue
                    a, se, q_loc = UP.fit_offset_clustered(lp[loc], yv[loc], wb[loc], pid[loc])
                    if not np.isfinite(se):
                        continue
                    trig = bool(abs(a) > zcrit * se)
                    mag = bool(abs(a) >= min_shift)
                    p_recal = sigmoid(lp[ev] + a)
                    sc = {"always_frozen": ph[ev], "always_recal": p_recal,
                          "selective": p_recal if trig else ph[ev],
                          "selective_magnet": p_recal if (trig and mag) else ph[ev]}
                    mf = metrics_lite_ic(yv[ev], ph[ev], wb[ev])
                    mr = metrics_lite_ic(yv[ev], p_recal, wb[ev])
                    best_oracle = max(mf["nb_at_05"], mr["nb_at_05"])
                    for pol in POLICIES:
                        chosen = (pol == "selective" and trig) or (pol == "selective_magnet" and mag and trig) \
                            or (pol == "always_recal")
                        mm = metrics_lite_ic(yv[ev], sc[pol], wb[ev])
                        rows.append(dict(held=held, arm=arm, policy=pol, frac=frac, rep=rep,
                                         model="joint_cr", censor_mode=cmode,
                                         local_events=float(np.sum(wb[loc] * yv[loc])),
                                         a_hat=a, se_a=se, trigger_95=int(trig), magnitude_met=int(mag),
                                         oracle_nb_at_05=best_oracle, **mm))

    out = pd.DataFrame(rows)
    dest = os.path.join(OUT, f"incident_update_policy_joint_ic_{rule}.csv")
    out.to_csv(dest, index=False)
    print(f"\nwrote {dest} rows={len(out)}")

    summ = []
    for held in sorted(set(out["held"])):
        for frac in fracs:
            for arm in ("mid", "ic"):
                for pol in POLICIES:
                    g = out[(out["held"] == held) & np.isclose(out["frac"].astype(float), frac)
                            & (out["arm"] == arm) & (out["policy"] == pol)]
                    fz = out[(out["held"] == held) & np.isclose(out["frac"].astype(float), frac)
                             & (out["arm"] == arm) & (out["policy"] == "always_frozen")]
                    if g.empty or fz.empty:
                        continue
                    # align frozen by rep
                    d_fz = (g.sort_values("rep")["nb_at_05"].to_numpy()
                            - fz.sort_values("rep")["nb_at_05"].to_numpy()[: len(g)])
                    summ.append(dict(held=held, frac=frac, arm=arm, policy=pol, n_rep=int(len(g)),
                                     a_hat_mean=float(g["a_hat"].mean()),
                                     se_a_mean=float(g["se_a"].mean()),
                                     trigger_rate=float(g["trigger_95"].mean()),
                                     updated_rate=float((g["trigger_95"].astype(bool) if pol.startswith("selective")
                                                         else np.ones(len(g), bool)).astype(float).mean())
                                     if pol != "always_frozen" else 0.0,
                                     oe_eval_mean=float(g["oe_ratio"].mean()),
                                     nb_at_05=float(g["nb_at_05"].mean()),
                                     paired_vs_frozen=float(np.nanmean(d_fz))))
    sm = pd.DataFrame(summ)
    sm.to_csv(os.path.join(OUT, f"incident_update_policy_joint_ic_summary_{rule}.csv"), index=False)

    print("\n########## does the rule find China under interval censoring? (selective arm)")
    for held in sorted(set(sm["held"])):
        for arm in ("mid", "ic"):
            r = sm[(sm["held"] == held) & np.isclose(sm["frac"].astype(float), fracs[0])
                   & (sm["arm"] == arm) & (sm["policy"] == "selective")]
            if not r.empty:
                r = r.iloc[0]
                print(f"  {held} [{arm}] frac={fracs[0]:.2f}: a_hat={r['a_hat_mean']:+.3f} "
                      f"(SE {r['se_a_mean']:.3f}) trigger in {r['trigger_rate']*100:.0f}% of {int(r['n_rep'])} "
                      f"samples | O/E {r['oe_eval_mean']:.2f} | NB@5% {r['nb_at_05']:+.5f} "
                      f"(vs frozen {r['paired_vs_frozen']:+.5f})", flush=True)
    return out


if __name__ == "__main__":
    main()
