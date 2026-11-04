"""P1-2: a deployable DECISION RULE for whether a new country should recalibrate.

The manuscript can already show, after the fact, that Mexico's frozen model over-predicts about
threefold and that a one-parameter intercept repair fitted on a small local sample pays, while the
same repair costs money in the United States. That is a retrospective finding: at deployment nobody
knows which country they are in. The reviewer's objection is exactly this:

  "真实部署时，我们不知道哪个国家将来会出现较大校准误差 ... 不能简单根据完整目标国家的数据选择策略,
   因为这会使用未来部署时不可获得的信息。"

So this script prespecifies three policies and evaluates all three on persons who never touched the
update, with the decision made from ADAPTATION-set information only:

  always_frozen     never move the model
  always_recal      fit the intercept on the local sample and apply it, whatever it says
  selective         update only if the local evidence is strong:  |a| > z * SE(a)
  selective_magnet  ... AND practically large:  |a| >= --min-shift log-odds as well

Nothing else is allowed to see the evaluation set. The intercept `a` is solved on the adaptation
persons' linear predictors against their own IPCW-weighted event fraction; SE(a) is a person-clustered
sandwich estimator of the same weighted estimating equation, computed from adaptation rows only; the
trigger is a function of (a, SE) alone. The evaluation set is the complementary persons of the same
country, disjoint by person_id, asserted per replicate.

Why this is the translational result rather than another metric: it converts "Mexico needs
recalibration" into "here is how an organisation that has just licensed this model decides, with 2-5%
local data and no oracle knowledge, whether to move it" — including how often that rule is wrong and
how much each wrong turn costs.

Two honesty items are printed rather than hidden:

 * regret. The per-replicate best of {frozen, recal} evaluated on the eval set is an ORACLE: it used
   evaluation outcomes. The gap between the selective policy and that oracle is the price of deciding
   without the answer, and it is reported as such.
 * the paired intervals are over random adaptation/evaluation splits, so they describe the variability
   of the DEPLOYMENT PROCEDURE (how much local data, which people were sampled), not a confidence
   interval for a fixed model's performance on a fixed population. Person-clustered bootstrap
   intervals for the absolute levels come from intl/incident_cr_primary.py.

Usage
  python incident_update_policy.py [--reps 200] [--fractions 0.02,0.05,0.10,0.25,0.50]
                                   [--horizon 4] [--horizon-rule cif_mid] [--z 1.96]
                                   [--min-shift 0.25] [--model logistic] [--pp personperiod_pooled.csv]
"""
import os, sys, json, numpy as np, pandas as pd, warnings
warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)
import run_loco_v2 as V2
import run_incident_loco as I
import incident_horizon_recalibration as HR

OUT = I.OUT
SEED = V2.SEED
POLICIES = ("always_frozen", "always_recal", "selective", "selective_magnet")


def flag(name, default):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default


sigmoid, logit = HR.sigmoid, HR.logit


def fit_offset_clustered(lp, y, w, ids):
    """Calibration-in-the-large on the adaptation set, with a person-clustered SE.

    Solves  sum_i w_i [sigmoid(lp_i + a) - y_i] = 0  by bisection (the equation HR.fit_offset_weighted
    uses), then takes Var(a) = meat / (dU/da)^2 with
        meat    = sum_g ( sum_{i in g} w_i (p_i(a) - y_i) )^2      (independent clusters of people)
        dU/da   = sum_i w_i p_i(a) (1 - p_i(a))
    so the interval on `a` respects the fact that one person contributes several horizon rows only
    where the horizon frame itself does.
    """
    s = float(np.sum(w))
    if s <= 0:
        return 0.0, np.nan, np.nan
    q = float(np.sum(w * y) / s)
    if not (0.0 < q < 1.0):
        return 0.0, np.nan, q
    lo, hi = -12.0, 12.0
    for _ in range(80):
        mid = (lo + hi) / 2.0
        if float(np.sum(w * sigmoid(lp + mid)) / s) < q:
            lo = mid
        else:
            hi = mid
    a = (lo + hi) / 2.0
    p = sigmoid(lp + a)
    denom = float(np.sum(w * p * (1.0 - p)))
    _, inv = np.unique(np.asarray(ids), return_inverse=True)
    score = w * (p - np.asarray(y, dtype=float))
    per = np.bincount(inv, weights=score)
    meat = float(np.sum(per ** 2))
    se = float(np.sqrt(meat) / denom) if denom > 0 else np.nan
    return a, se, q


def metrics_lite(y, p, w, horizon_thr=(0.02, 0.05, 0.10, 0.15)):
    """The decision-and-level fields. AUROC is deliberately absent: a constant shift of the linear
    predictor is a monotone map, so the ranking is identical for frozen and repaired rows and
    repeating it per policy would only inflate the row count."""
    y = np.asarray(y).astype(int); p = np.asarray(p, float)
    w = np.ones(len(y)) if w is None else np.asarray(w, float)
    b = float(np.sum(w * (p - y) ** 2) / np.sum(w))
    q = float(np.sum(w * y) / np.sum(w))
    mp = float(np.sum(w * p) / np.sum(w))
    out = dict(n_eval_rows=int(len(y)), n_eval_events=int(np.sum(y)),
               mean_pred=mp, obs_prev=q, oe_ratio=(mp / q if q > 0 else np.nan),
               brier=b,
               scaled_brier=((q * (1 - q) - b) / (q * (1 - q)) if 0 < q < 1 else np.nan))
    for t in horizon_thr:
        out[f"nb_at_{int(round(t * 100)):02d}"] = I.weighted_net_benefit(y, p, w, t)
        out[f"nb_all_at_{int(round(t * 100)):02d}"] = I.weighted_net_benefit(
            y, np.ones(len(y)), w, t)
    out["flagged_at_05"] = float(np.sum(w * (p >= 0.05)) / np.sum(w))
    return out


def main():
    reps = int(flag("--reps", "200"))
    fracs = [float(x) for x in flag("--fractions", "0.02,0.05,0.10,0.25,0.50").split(",")]
    horizon = float(flag("--horizon", "4"))
    rule = flag("--horizon-rule", "cif_mid")
    zcrit = float(flag("--z", "1.96"))
    min_shift = float(flag("--min-shift", "0.25"))
    model = flag("--model", "logistic")
    frame_file = flag("--pp", "personperiod_pooled.csv")

    pp = pd.read_csv(os.path.join(OUT, frame_file))
    pp["country"] = pp["cohort"].map(I.COH2CTRY)
    pp = pp[pp["country"].notna()].reset_index(drop=True)
    X = I.design(pp, "common", "linear")
    y = pp["event"].astype(int).values
    base_frame, hcounts = I.horizon_frame(pp, horizon, rule)
    print(f"policy arm | rule={rule} model={model} reps={reps} z={zcrit} "
          f"min_shift={min_shift} | {json.dumps(hcounts)}", flush=True)

    rows, decisions = [], []
    for held in sorted(set(pp["country"])):
        tr = (pp["country"].values != held)
        cmode = pp.loc[pp["country"].values == held, "censor_mode"].iloc[0]
        step_L = round(float(np.median(pp.loc[tr, "exposure_years"])) * 4) / 4
        hb = base_frame[base_frame["country"] == held].reset_index(drop=True)
        yb = hb["label"].astype(int).values
        wb = pd.to_numeric(hb["ipcw"], errors="coerce").fillna(1.0).to_numpy(float)
        pid = hb["pid"].values
        frozen = I.Frozen(X.loc[tr], y[tr], model)
        ph_all, realised = I.horizon_risk(frozen, hb, horizon, "linear", "common", step=step_L)
        lp_all = logit(ph_all)
        upid = np.unique(pid)
        print(f"\n=== {held}: rows={len(hb)} persons={len(upid)} events={int(yb.sum())} "
              f"frozen unweighted mean_pred/obs={ph_all.mean() / yb.mean():.3f} "
              f"ipcw O/E={np.sum(wb * ph_all) / np.sum(wb * yb):.3f} censor={cmode} "
              f"step={step_L} realised={realised:.2f}y", flush=True)

        # the no-local-data reference: the whole held-out country scored by the frozen model
        rows.append(dict(held=held, policy="frozen_no_local_data", frac=0.0, rep=-1,
                         censor_mode=cmode, realised_horizon_years=realised,
                         local_persons=0, local_events=0, a_hat=0.0, se_a=np.nan,
                         a_lo=np.nan, a_hi=np.nan, updated=False, trigger_95=False,
                         **metrics_lite(yb, ph_all, wb)))

        for frac in fracs:
            for rep in range(reps):
                rng = np.random.default_rng(SEED + 31000 + 977 * rep + int(10000 * frac))
                take = max(2, int(round(len(upid) * frac)))
                pick = rng.choice(upid, size=take, replace=False)
                loc = np.isin(pid, pick)
                ev = ~loc
                assert not set(pid[loc]) & set(pid[ev]), "adaptation and eval share a person"
                if len(np.unique(yb[loc])) < 2 or len(np.unique(yb[ev])) < 2:
                    continue
                a, se, q_loc = fit_offset_clustered(lp_all[loc], yb[loc], wb[loc], pid[loc])
                if not np.isfinite(se):
                    continue
                a_lo, a_hi = a - zcrit * se, a + zcrit * se
                trig = bool(abs(a) > zcrit * se)
                mag = bool(abs(a) >= min_shift)
                p_recal = sigmoid(lp_all[ev] + a)
                sc = {"always_frozen": ph_all[ev], "always_recal": p_recal,
                      "selective": p_recal if trig else ph_all[ev],
                      "selective_magnet": p_recal if (trig and mag) else ph_all[ev]}
                best_oracle = max(I.weighted_net_benefit(yb[ev], ph_all[ev], wb[ev], 0.05),
                                  I.weighted_net_benefit(yb[ev], p_recal, wb[ev], 0.05))
                for pol in POLICIES:
                    chosen = (pol == "selective" and trig) or (pol == "selective_magnet" and mag and trig) \
                        or (pol == "always_recal")
                    rows.append(dict(held=held, policy=pol, frac=frac, rep=rep,
                                     censor_mode=cmode, realised_horizon_years=realised,
                                     local_persons=int(loc.sum()),
                                     local_events=int(np.sum(yb[loc])),
                                     local_event_fraction=q_loc, a_hat=a, se_a=se,
                                     a_lo=a_lo, a_hi=a_hi, updated=bool(chosen),
                                     trigger_95=trig, magnitude_met=mag,
                                     oracle_nb_at_05=best_oracle,
                                     **metrics_lite(yb[ev], sc[pol], wb[ev])))
                decisions.append(dict(held=held, frac=frac, rep=rep, a_hat=a, se_a=se,
                                      trigger_95=int(trig), magnitude_met=int(mag),
                                      local_events=int(np.sum(wb[loc] * yb[loc])),
                                      frozen_oe_local=float(np.sum(wb[loc] * ph_all[loc]) /
                                                            max(1e-12, np.sum(wb[loc] * yb[loc]))),
                                      nb_frozen_eval=I.weighted_net_benefit(yb[ev], ph_all[ev],
                                                                            wb[ev], 0.05),
                                      nb_recal_eval=I.weighted_net_benefit(yb[ev], p_recal, wb[ev],
                                                                           0.05)))

    out = pd.DataFrame(rows)
    dest = os.path.join(OUT, f"incident_update_policy_{rule}.csv")
    out.to_csv(dest, index=False)
    dec = pd.DataFrame(decisions)
    dec.to_csv(os.path.join(OUT, f"incident_update_policy_decisions_{rule}.csv"), index=False)
    print(f"\nwrote {dest} rows={len(out)} | decisions={len(dec)}")

    # ---------------------------------------------------------------- per-country summary
    summ = []
    for held in sorted(set(out["held"])):
        sub = out[(out["held"] == held) & (out["policy"] != "frozen_no_local_data")]
        for frac in fracs:
            g = sub[np.isclose(sub["frac"].astype(float), frac)]
            if g.empty:
                continue
            fz = g[g["policy"] == "always_frozen"].sort_values("rep")
            rc = g[g["policy"] == "always_recal"].sort_values("rep")
            for pol in POLICIES:
                p = g[g["policy"] == pol].sort_values("rep")
                nb = p["nb_at_05"].to_numpy()
                d_frozen = (p["nb_at_05"].to_numpy() - fz["nb_at_05"].to_numpy())
                d_recal = (p["nb_at_05"].to_numpy() - rc["nb_at_05"].to_numpy())
                regret = (p["oracle_nb_at_05"].to_numpy() - nb)
                r0 = dict(held=held, frac=frac, policy=pol, n_rep=int(len(p)),
                          local_events_median=float(p["local_events"].median()),
                          a_hat_mean=float(p["a_hat"].mean()), se_a_mean=float(p["se_a"].mean()),
                          updated_rate=float(p["updated"].astype(float).mean()),
                          oe_eval_mean=float(p["oe_ratio"].mean()),
                          nb_at_02=float(p["nb_at_02"].mean()), nb_at_05=float(nb.mean()),
                          nb_at_10=float(p["nb_at_10"].mean()), nb_at_15=float(p["nb_at_15"].mean()),
                          nb_all_at_05=float(p["nb_all_at_05"].mean()),
                          brier=float(p["brier"].mean()),
                          paired_vs_frozen=float(d_frozen.mean()),
                          paired_vs_frozen_lo=float(np.percentile(d_frozen, 2.5)),
                          paired_vs_frozen_hi=float(np.percentile(d_frozen, 97.5)),
                          beats_frozen_rate=float(np.mean(d_frozen > 0)),
                          paired_vs_always_recal=float(d_recal.mean()),
                          beats_always_recal_rate=float(np.mean(d_recal > 0)),
                          regret_vs_oracle=float(regret.mean()),
                          worse_than_treat_none_rate=float(np.mean(nb < 0.0)))
                summ.append(r0)
    sm = pd.DataFrame(summ)
    sm.to_csv(os.path.join(OUT, f"incident_update_policy_summary_{rule}.csv"), index=False)

    print("\n########## the decision rule, per country and local sample size")
    for held in sorted(set(sm["held"])):
        for frac in fracs:
            line = f"  {held} frac={frac:5.2f} |"
            for pol in POLICIES:
                r = sm[(sm["held"] == held) & np.isclose(sm["frac"].astype(float), frac)
                       & (sm["policy"] == pol)]
                if r.empty:
                    continue
                r = r.iloc[0]
                line += (f" {pol.replace('selective_', 'sel_'):14s}"
                         f" upd={r['updated_rate']:.2f} NB={r['nb_at_05']:+.5f}"
                         f" (vs fz {r['paired_vs_frozen']:+.5f})")
            print(line, flush=True)
    print("\n########## does the rule find the country that needs it, without the oracle?")
    for held in sorted(set(sm["held"])):
        r = sm[(sm["held"] == held) & np.isclose(sm["frac"].astype(float), fracs[0])
               & (sm["policy"] == "selective")]
        if not r.empty:
            r = r.iloc[0]
            print(f"  {held}: a_hat={r['a_hat_mean']:+.3f} (SE {r['se_a_mean']:.3f}) "
                  f"update triggered in {r['updated_rate'] * 100:.0f}% of {int(r['n_rep'])} local "
                  f"samples | local events median {r['local_events_median']:.0f} | regret vs the "
                  f"oracle {r['regret_vs_oracle']:+.5f}", flush=True)
    return out


if __name__ == "__main__":
    main()
