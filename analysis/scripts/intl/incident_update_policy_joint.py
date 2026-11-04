"""Round-7 P0-6: the selective-updating DECISION POLICY re-run on the JOINT competing-risks model.

The sixth round promoted the joint multinomial likelihood on the three mutually exclusive interval
outcomes (stroke-first / death-first / neither) to the PRIMARY absolute-risk arm everywhere - the four-
year risk, the four-country calibration, the age-band heterogeneity, the decision curves. But the deploy-
ment decision rule (`incident_update_policy.py`) was still evaluated with the frozen logistic predictor
feeding its linear-predictor scale, which means the manuscript could not say "the primary model's selec-
tive-updating policy has been validated" - only that an earlier specification's policy had been. The
seventh-round reviewer named this exact split (P0-6).

This script closes it. It re-runs the SAME prespecified policy experiment - identical subject-level adap-
tation/evaluation splits (disjoint by person_id, asserted per replicate), identical local-sample fractions,
identical trigger rules (|a| > z.SE(a) and, for the magnitude-gated arm, |a| >= min-shift), identical
independent evaluation set and 5% net-benefit threshold - with ONLY the underlying risk model changed: the
frozen per-person probability is now the joint horizon CIF `pj` from `incident_cr_joint_primary.build_joint`
(the very same quantity that reproduces the Mexico 2.975 headline), so the linear-predictor offset is solved
on logit(pj) rather than logit of a logistic cloglog prediction.

Everything is imported so a joint policy number is comparable by construction to the joint calibration and
net-benefit tables already in the manuscript. The logistic arm is left byte-identical on disk
(`incident_update_policy_cif_mid.csv`) as a labelled sensitivity analysis; nothing here overwrites it.

Outputs (data/processed/intl/incident/), all suffixed `_joint`:
  incident_update_policy_joint_<rule>.csv          one row per (held, policy, frac, rep)
  incident_update_policy_joint_decisions_<rule>.csv  per-replicate trigger bookkeeping
  incident_update_policy_joint_summary_<rule>.csv    per (held, frac, policy) means, paired gains, regret

Usage:
  python incident_update_policy_joint.py [--reps 200] [--fractions 0.02,0.05,0.10,0.25,0.50]
                                         [--horizon 4] [--horizon-rule cif_mid] [--z 1.96] [--min-shift 0.25]
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


def main():
    reps = int(flag("--reps", "200"))
    fracs = [float(x) for x in flag("--fractions", "0.02,0.05,0.10,0.25,0.50").split(",")]
    horizon = float(flag("--horizon", "4"))
    rule = flag("--horizon-rule", "cif_mid")
    zcrit = float(flag("--z", "1.96"))
    min_shift = float(flag("--min-shift", "0.25"))
    time_mode, fset = "linear", "common"

    pp = pd.read_csv(os.path.join(OUT, "personperiod_pooled.csv"))
    pp["country"] = pp["cohort"].map(I.COH2CTRY)
    pp = pp[pp["country"].notna()].reset_index(drop=True)
    X = I.design(pp, fset, time_mode)
    ds = pp["event"].astype(int).values
    dd = pp["end_status"].isin(P.DEATH).astype(int).values
    base_frame, hcount = I.horizon_frame(pp, horizon, rule)
    print(f"JOINT policy arm | rule={rule} model=joint_cr reps={reps} z={zcrit} "
          f"min_shift={min_shift} | {json.dumps(hcount)}", flush=True)

    rows, decisions = [], []
    for held in sorted(set(pp["country"])):
        # the frozen per-person JOINT horizon CIF and its linear-predictor scale, identical to the
        # promoted primary calibration/DCA tables
        jf, hb, pj, yb, wb, pid, step, lp_all = JP.build_joint(
            pp, X, ds, dd, base_frame, held, horizon, time_mode, fset)
        hb = hb.reset_index(drop=True)
        realised = step * round(horizon / step)
        upid = np.unique(pid)
        ph_all = np.asarray(pj, float)
        yb = yb.astype(int)
        cmode = pp.loc[pp["country"].values == held, "censor_mode"].iloc[0]
        print(f"\n=== {held}: rows={len(hb)} persons={len(upid)} events={int(yb.sum())} "
              f"frozen joint unweighted mean_pred/obs={ph_all.mean() / yb.mean():.3f} "
              f"ipcw O/E={np.sum(wb * ph_all) / np.sum(wb * yb):.3f} censor={cmode} "
              f"step={step} realised={realised:.2f}y", flush=True)

        rows.append(dict(held=held, policy="frozen_no_local_data", frac=0.0, rep=-1,
                         model="joint_cr", censor_mode=cmode, realised_horizon_years=realised,
                         local_persons=0, local_events=0, a_hat=0.0, se_a=np.nan,
                         a_lo=np.nan, a_hi=np.nan, updated=False, trigger_95=False,
                         **UP.metrics_lite(yb, ph_all, wb)))

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
                a, se, q_loc = UP.fit_offset_clustered(lp_all[loc], yb[loc], wb[loc], pid[loc])
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
                    rows.append(dict(held=held, policy=pol, frac=frac, rep=rep, model="joint_cr",
                                     censor_mode=cmode, realised_horizon_years=realised,
                                     local_persons=int(loc.sum()), local_events=int(np.sum(yb[loc])),
                                     local_event_fraction=q_loc, a_hat=a, se_a=se, a_lo=a_lo, a_hi=a_hi,
                                     updated=bool(chosen), trigger_95=trig, magnitude_met=mag,
                                     oracle_nb_at_05=best_oracle,
                                     **UP.metrics_lite(yb[ev], sc[pol], wb[ev])))
                decisions.append(dict(held=held, frac=frac, rep=rep, model="joint_cr", a_hat=a, se_a=se,
                                      trigger_95=int(trig), magnitude_met=int(mag),
                                      local_events=int(np.sum(wb[loc] * yb[loc])),
                                      frozen_oe_local=float(np.sum(wb[loc] * ph_all[loc]) /
                                                            max(1e-12, np.sum(wb[loc] * yb[loc]))),
                                      nb_frozen_eval=I.weighted_net_benefit(yb[ev], ph_all[ev], wb[ev], 0.05),
                                      nb_recal_eval=I.weighted_net_benefit(yb[ev], p_recal, wb[ev], 0.05)))

    out = pd.DataFrame(rows)
    dest = os.path.join(OUT, f"incident_update_policy_joint_{rule}.csv")
    out.to_csv(dest, index=False)
    pd.DataFrame(decisions).to_csv(
        os.path.join(OUT, f"incident_update_policy_joint_decisions_{rule}.csv"), index=False)
    print(f"\nwrote {dest} rows={len(out)} | decisions={len(decisions)}")

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
                summ.append(dict(held=held, frac=frac, policy=pol, model="joint_cr", n_rep=int(len(p)),
                                 local_events_median=float(p["local_events"].median()),
                                 a_hat_mean=float(p["a_hat"].mean()), se_a_mean=float(p["se_a"].mean()),
                                 updated_rate=float(p["updated"].astype(float).mean()),
                                 oe_eval_mean=float(p["oe_ratio"].mean()),
                                 nb_at_02=float(p["nb_at_02"].mean()), nb_at_05=float(nb.mean()),
                                 nb_at_10=float(p["nb_at_10"].mean()), nb_at_15=float(p["nb_at_15"].mean()),
                                 nb_all_at_05=float(p["nb_all_at_05"].mean()), brier=float(p["brier"].mean()),
                                 paired_vs_frozen=float(d_frozen.mean()),
                                 paired_vs_frozen_lo=float(np.percentile(d_frozen, 2.5)),
                                 paired_vs_frozen_hi=float(np.percentile(d_frozen, 97.5)),
                                 beats_frozen_rate=float(np.mean(d_frozen > 0)),
                                 paired_vs_always_recal=float(d_recal.mean()),
                                 beats_always_recal_rate=float(np.mean(d_recal > 0)),
                                 regret_vs_oracle=float(regret.mean()),
                                 worse_than_treat_none_rate=float(np.mean(nb < 0.0))))
    sm = pd.DataFrame(summ)
    sm.to_csv(os.path.join(OUT, f"incident_update_policy_joint_summary_{rule}.csv"), index=False)

    print("\n########## JOINT-arm decision rule, per country and local sample size")
    for held in sorted(set(sm["held"])):
        for frac in fracs:
            line = f"  {held} frac={frac:5.2f} |"
            for pol in POLICIES:
                r = sm[(sm["held"] == held) & np.isclose(sm["frac"].astype(float), frac) & (sm["policy"] == pol)]
                if r.empty:
                    continue
                r = r.iloc[0]
                line += (f" {pol.replace('selective_', 'sel_'):14s}"
                         f" upd={r['updated_rate']:.2f} NB={r['nb_at_05']:+.5f}"
                         f" (vs fz {r['paired_vs_frozen']:+.5f})")
            print(line, flush=True)
    print("\n########## JOINT arm: does the rule find the country that needs it, without the oracle?")
    for held in sorted(set(sm["held"])):
        r = sm[(sm["held"] == held) & np.isclose(sm["frac"].astype(float), fracs[0]) & (sm["policy"] == "selective")]
        if not r.empty:
            r = r.iloc[0]
            print(f"  {held}: a_hat={r['a_hat_mean']:+.3f} (SE {r['se_a_mean']:.3f}) update triggered in "
                  f"{r['updated_rate'] * 100:.0f}% of {int(r['n_rep'])} local samples | local events median "
                  f"{r['local_events_median']:.0f} | regret vs the oracle {r['regret_vs_oracle']:+.5f}", flush=True)
    return out


if __name__ == "__main__":
    main()
