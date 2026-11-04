"""Refit the whole LOCO design under strict outcome ascertainment, so the training target and the
evaluation frame agree. This is the arm the coverage objection requires.

The objection: the published frame judges four-year coverage from `t_cens`, the end of a person's last
interval, and an interval can be terminated by `alive_nr` - a wave in which the respondent is known
alive but the stroke item was never asked. Those people are scored stroke-free through four years on
evidence that only says they were alive. `incident_ascertainment_sensitivity.py` re-labelled the
evaluation frame at `t_ask` (the last wave where the item was answerable) but left the models fitted on
the permissive risk set, and the manuscript defended that as matching the label to the target the model
was asked to estimate. The defence identified the right invariant and drew the wrong conclusion: the fix
is to change the training target too.

Doing that exposes a structural fact about interval-censored survey panels, which this script prints
before anything else. In all four cohorts a death is recorded on the interval that BEGINS at the last
answered interview. So truncating risk time at `t_ask` deletes every competing death as well
(21,591 dated + 1,756 status-coded): full strictness and competing-risk adjustment are mutually
exclusive here, and a fully truncated frame estimates "detected stroke among those still interviewed",
which is not the estimand anyone wants to deploy.

Three coherent conventions, therefore, and this script runs the middle one:

  permissive        coverage from interval end; alive-but-uninterviewed tails credit stroke-free time
  partial-strict    coverage from t_ask; an alive_nr or vital_status_unknown tail contributes NO risk
                    time and its person leaves the frame unless they answered past the horizon, while a
                    death - which is a real observation, made at the same wave that ends ascertainment -
                    stays a determined non-event
  full-strict       everything, including death observation, ends at t_ask; zero competing mortality

Training rows for partial-strict = pooled rows minus the non-interview tails. Evaluation frame =
`t_ask` coverage on the untruncated person clock, which is exactly the published strict arm, so the
self-check is a person-for-person equality test against
`incident_ascertainment_sensitivity.csv` before any model is fitted.

    python intl/incident_strict_refit.py [--models logistic,elasticnet,xgboost] [--reps 20]
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
import incident_adaptation as A                                  # noqa: E402
from incident_ascertainment_sensitivity import frame_from_clock   # noqa: E402

OUT = I.OUT
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
NON_INTERVIEW_TAIL = ("alive_nr", "vital_status_unknown")
SEED = I.SEED


def flag(name, default):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default


def logit(p):
    p = np.clip(np.asarray(p, dtype=float), 1e-9, 1 - 1e-9)
    return np.log(p / (1.0 - p))


def expit(z):
    return 1.0 / (1.0 + np.exp(-z))


def main():
    horizon = float(flag("--horizon", "4"))
    reps = int(flag("--reps", "20"))
    fracs = [float(x) for x in flag("--fractions", "0.02,0.05,0.10,0.25,0.50").split(",")]
    models = flag("--models", "logistic,elasticnet,xgboost").split(",")
    fset, time_mode, rule = "common", "linear", "cif_mid"

    pp = pd.read_csv(os.path.join(OUT, "personperiod_pooled.csv"))
    pp["country"] = pp["cohort"].map(I.COH2CTRY)
    pp = pp[pp["country"].notna()].reset_index(drop=True)

    # ---- the structural fact, stated before it is used ----------------------------------
    tail = pp[pp["end_status"].isin(NON_INTERVIEW_TAIL)]
    last_k = pp.groupby(["cohort", "pid"])["k"].transform("max")
    if not (tail["k"].values == last_k[tail.index].values).all():
        raise SystemExit("a non-interview tail is not the last interval for some person; the "
                         "partial-strict row rule would silently delete mid-study exposure")
    keep_rows = pp[~pp["end_status"].isin(NON_INTERVIEW_TAIL)].copy()
    print(f"pooled intervals {len(pp):,}; non-interview tails {len(tail):,} "
          f"({tail.end_status.value_counts().to_dict()}); partial-strict training rows "
          f"{len(keep_rows):,}; deaths retained "
          f"{int(keep_rows.end_status.str.startswith('death').sum()):,}", flush=True)

    # ---- evaluation frame: t_ask coverage on the untruncated clock ----------------------
    pc = I.person_clock(pp)
    from incident_ascertainment_sensitivity import ask_time
    pc["t_ask"] = ask_time(pp).reindex(
        pd.MultiIndex.from_arrays([pc["cohort"], pc["pid"]])).to_numpy()
    frame, counts = frame_from_clock(pc, horizon, "t_ask")
    print(f"partial-strict frame: {json.dumps(counts)}", flush=True)

    pub = pd.read_csv(os.path.join(OUT, "incident_ascertainment_sensitivity.csv"))
    pub = pub[(pub.model == "logistic") & (pub.coverage_rule == "strict_t_ask")].set_index("held")
    got = frame.groupby("country").agg(n=("label", "size"), ev=("label", "sum"))
    for h in sorted(got.index):
        if int(got.loc[h, "n"]) != int(pub.loc[h, "evaluable"]) or \
           int(got.loc[h, "ev"]) != int(pub.loc[h, "events"]):
            raise SystemExit(f"frame mismatch {h}: {int(got.loc[h,'n'])}/{int(got.loc[h,'ev'])} vs "
                             f"published {int(pub.loc[h,'evaluable'])}/{int(pub.loc[h,'events'])}")
    print("  frame reproduces the published strict arm exactly, panel by panel", flush=True)

    X = I.design(keep_rows, fset, time_mode)
    y = keep_rows["event"].astype(int).values
    rows, summary = [], {}
    for held in sorted(set(keep_rows["country"])):
        tr = (keep_rows["country"].values != held)
        step_L = round(float(np.median(keep_rows.loc[tr, "exposure_years"])) * 4) / 4
        hb = frame[frame["country"] == held].reset_index(drop=True)
        yb = hb["label"].astype(int).to_numpy()
        wb = pd.to_numeric(hb["ipcw"], errors="coerce").fillna(1.0).to_numpy(dtype=float)
        pid = hb["pid"].to_numpy()
        for name in models:
            fr = I.Frozen(X.loc[tr], y[tr], name)
            ph, real = I.horizon_risk(fr, hb, horizon, time_mode, fset, step=step_L)
            lp = logit(ph)
            frozen_nb = I.weighted_net_benefit(yb, ph, wb, 0.05)
            rows.append(dict(held=held, model=name, strategy="frozen", frac=0.0, rep=0,
                             censor_mode=hb["censor_mode"].iloc[0] if "censor_mode" in hb else "",
                             realised_horizon_years=round(float(real), 3), step_years=step_L,
                             n_eval=len(yb), auroc=float(roc_auc_score(yb, ph, sample_weight=wb)),
                             mean_pred=float(np.sum(wb * ph) / wb.sum()),
                             obs_prev=float(np.sum(wb * yb) / wb.sum()),
                             nb_at_05=frozen_nb))
            summary.setdefault(held, {})["frozen_auroc"] = float(roc_auc_score(yb, ph, sample_weight=wb))
            summary[held]["frozen_pred_over_obs"] = float(np.sum(wb * ph) / np.sum(wb * yb))
            summary[held]["frozen_nb"] = float(frozen_nb)
            for frac in fracs:
                for rep in range(reps):
                    rng = np.random.default_rng(SEED + 7000 + 1000 * rep + int(100 * frac))
                    upid = np.unique(pid)
                    pick = rng.choice(upid, size=max(2, int(round(len(upid) * frac))), replace=False)
                    loc = np.isin(pid, pick)
                    ev = ~loc
                    # Regression guard for the adaptation/evaluation independence the manuscript claims.
                    # ev is the complement of loc, so this cannot fire unless a future edit splits by row
                    # instead of by person; incident_adaptation_leakage_audit.py measures it empirically.
                    assert not (set(pid[loc]) & set(pid[ev])), "local-adaptation and evaluation persons overlap"
                    if len(np.unique(yb[loc])) < 2 or len(np.unique(yb[ev])) < 2:
                        continue
                    a_h, _ = A.fit_offset(lp[loc], yb[loc])
                    p_off = expit(lp[ev] + a_h)
                    y_e, w_e = yb[ev], wb[ev]
                    nb_f = I.weighted_net_benefit(y_e, ph[ev], w_e, 0.05)
                    nb_o = I.weighted_net_benefit(y_e, p_off, w_e, 0.05)
                    rows.append(dict(held=held, model=name, strategy="offset_horizon", frac=frac,
                                     rep=rep, fitted_intercept=float(a_h),
                                     local_persons=int(loc.sum()),
                                     local_events=int(yb[loc].sum()),
                                     n_eval=int(ev.sum()),
                                     censor_mode=hb["censor_mode"].iloc[0] if "censor_mode" in hb else "",
                                     realised_horizon_years=round(float(real), 3), step_years=step_L,
                                     auroc=float(roc_auc_score(y_e, p_off, sample_weight=w_e)),
                                     mean_pred=float(np.sum(w_e * p_off) / w_e.sum()),
                                     obs_prev=float(np.sum(w_e * y_e) / w_e.sum()),
                                     nb_at_05=nb_o, nb_frozen_same_rows=nb_f,
                                     nb_gain=nb_o - nb_f,
                                     nb_all_at_05=I.weighted_net_benefit(y_e, np.ones(len(y_e)), w_e, 0.05),
                                     flagged_at_05=float(np.sum(w_e * (p_off >= 0.05)) / w_e.sum())))
    out = pd.DataFrame(rows)
    dest = os.path.join(OUT, "incident_strict_refit.csv")
    out.to_csv(dest, index=False)

    lg = out[(out.model == "logistic")]
    print("\n=== partial-strict refit, logistic: does the Mexico repair survive? ===", flush=True)
    for h in sorted(lg.held.unique()):
        s = lg[lg.held == h]
        f = s[s.strategy == "frozen"].iloc[0]
        g = s[s.strategy == "offset_horizon"]
        for frac in sorted(g.frac.unique()):
            gf = g[g.frac == frac]
            gain = gf.nb_gain.to_numpy()
            print(f"  {h} frac={frac:.2f} local={int(gf.local_persons.max()):,} "
                  f"(median {int(np.median(gf.local_events))} local events): frozen NB {gf.nb_frozen_same_rows.mean():+.5f} "
                  f"-> offset {gf.nb_at_05.mean():+.5f}, paired gain {gain.mean():+.6f} "
                  f"(SD {gain.std():.6f}, beats frozen {int((gain > 0).sum())}/{len(gain)}), "
                  f"pred/obs {f.mean_pred:.4f}/{f.obs_prev:.4f}={f.mean_pred / f.obs_prev:.2f} -> "
                  f"{gf.mean_pred.mean():.2f}, intercept {gf.fitted_intercept.mean():+.3f} "
                  f"(SD {gf.fitted_intercept.std():.3f})", flush=True)
        fr0 = s[s.strategy == "frozen"].iloc[0]
        print(f"  {h}: strict-refit frozen AUROC {fr0.auroc:.4f}, predicted {fr0.mean_pred:.4f} "
              f"vs observed {fr0.obs_prev:.4f}, NB {fr0.nb_at_05:+.5f}", flush=True)
    summary["_refit_frozen"] = {h: {"auroc": float(lg[lg.held == h][lg.strategy == 'frozen'].auroc.iloc[0]),
                                    "pred_over_obs": float(lg[lg.held == h][lg.strategy == 'frozen'].mean_pred.iloc[0] /
                                                            lg[lg.held == h][lg.strategy == 'frozen'].obs_prev.iloc[0]),
                                    "nb": float(lg[lg.held == h][lg.strategy == 'frozen'].nb_at_05.iloc[0])}
                                for h in sorted(lg.held.unique())}
    with open(os.path.join(ROOT, "results", "reports", "incident_strict_refit.json"), "w",
              encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2)
    print("\nwrote", dest)


if __name__ == "__main__":
    main()
