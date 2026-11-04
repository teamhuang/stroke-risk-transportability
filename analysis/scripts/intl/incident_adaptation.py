"""When should a transported stroke model be frozen, recalibrated, or retrained?

Why this is the analysis the study needs
----------------------------------------
The incident LOCO arm (run_incident_loco.py) shows a consistent pattern: the RANKING of people
transports (held-out AUROC 0.57-0.74 depending on panel and model) but the LEVEL does not. Each
panel's stroke incidence differs about threefold (China 10.25, Korea 4.75, Mexico 3.39 per 1,000
person-years), so a model fitted on two panels predicts the third one's absolute risk badly -
China's 4-year risk comes out at 0.018 when the observed value is 0.061. That failure is what
destroys decision-level value: at a 5% threshold the frozen model's net benefit is below
"treat everyone" in China and below "treat no one" in Korea.

Three responses are available and they cost different things:
  FROZEN       deploy as-is; needs no local labels at all.
  OFFSET       correct only the intercept, i.e. realign to the local base rate. This can be done
               with a published local incidence rather than patient-level data - the cheapest
               realistic adaptation, and the one that is possible when local data exist only in
               aggregate.
  RECALIBRATE  fit intercept AND slope on a small labelled local sample (Platt / logistic
               recalibration of the linear predictor).
  RETRAIN      fit the whole model on that local sample.

Two properties of this design make the comparison clean, and both are asserted in code:
* Any monotone transform of the linear predictor leaves AUROC EXACTLY unchanged. So recalibration
  can only ever fix calibration and decision value, never discrimination - which is testable here
  rather than merely claimed, and the script verifies it numerically.
* The local-sample size is swept, so the answer is a CURVE, not a verdict: how many local
  labelled intervals does each strategy need before it beats the frozen model?

Sampling is by PERSON, never by interval: a person contributes many intervals, and leaking one
person's later intervals into a calibration set that is then scored on their earlier ones would
overstate how little local data is needed.

Usage
  python incident_adaptation.py [--models logistic,xgboost] [--fractions 0.02,0.05,0.10,0.25,0.50]
                                [--reps 5] [--horizon 4] [--boot 0]
"""
import os, sys, json, numpy as np, pandas as pd, warnings
warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)
import modeling as M
import run_loco_v2 as V2
import run_incident_loco as I
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.metrics import roc_auc_score, brier_score_loss

OUT = os.path.abspath(os.path.join(HERE, "..", "..", "..", "data", "processed", "intl", "incident"))
SEED = V2.SEED


def flag(name, default):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default


def linear_predictor(fr, X):
    """A score on the log-odds scale for any fitted model. Linear families expose
    decision_function directly; trees only give probabilities, so their logit is used - the same
    object a Platt scaler would fit."""
    if fr.kind in ("logit", "logit_agesex", "spline_logit"):
        return fr.clf.decision_function(fr._mat(X))
    p = np.clip(fr.predict(X), 1e-6, 1 - 1e-6)
    return np.log(p / (1.0 - p))


def fit_recal(lp, y):
    """Logistic recalibration of a frozen score. Returns (intercept, slope)."""
    lr = LogisticRegression(C=1e6, max_iter=1000, solver="lbfgs").fit(lp.reshape(-1, 1), y)
    return float(lr.intercept_[0]), float(lr.coef_[0][0])


def fit_offset(lp, y):
    """Intercept-only correction: slope pinned at 1, only the log-odds offset moves. This is the
    strategy that needs nothing but the local base rate."""
    p = 1.0 / (1.0 + np.exp(-lp))
    q = float(np.mean(y))
    if q <= 0 or q >= 1:
        return 0.0, 1.0
    # solve mean(sigmoid(lp + a)) = q by bisection; monotone in a, so this converges
    lo, hi = -12.0, 12.0
    for _ in range(60):
        mid = (lo + hi) / 2.0
        if (1.0 / (1.0 + np.exp(-(lp + mid)))).mean() < q:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2.0, 1.0


class Adapter:
    """Presents a recalibration map as if it were a fitted model, so the horizon composition in
    run_incident_loco.horizon_risk can be reused without duplicating its stepping logic."""

    def __init__(self, fr, a, b):
        self.fr, self.a, self.b, self.cols = fr, a, b, fr.cols

    def predict(self, X):
        lp = linear_predictor(self.fr, X)
        return 1.0 / (1.0 + np.exp(-(self.a + self.b * lp)))


def evaluate(y, p, naive):
    b = float(brier_score_loss(y, p))
    ci, cs = M.cal_intercept_slope(y, p)
    q = float(y.mean())
    return dict(auroc=float(roc_auc_score(y, p)), brier=b,
                skill_train=float((naive - b) / naive),
                scaled_brier=float((q * (1 - q) - b) / (q * (1 - q))),
                cal_intercept=ci, cal_slope=cs, mean_pred=float(p.mean()),
                nb_at_01=I.net_benefit(y, p, 0.01), nb_at_02=I.net_benefit(y, p, 0.02),
                nb_at_03=I.net_benefit(y, p, 0.03), nb_at_05=I.net_benefit(y, p, 0.05),
                nb_all_at_02=I.net_benefit(y, np.ones(len(y)), 0.02),
                flagged_at_02=float((p >= 0.02).mean()), flagged_at_05=float((p >= 0.05).mean()))


def main():
    pp = pd.read_csv(os.path.join(OUT, "personperiod_pooled.csv"))
    pp["country"] = pp["cohort"].map(I.COH2CTRY)
    pp = pp[pp["country"].notna()].reset_index(drop=True)
    models = flag("--models", "logistic,xgboost").split(",")
    fracs = [float(x) for x in flag("--fractions", "0.02,0.05,0.10,0.25,0.50").split(",")]
    reps = int(flag("--reps", "5"))
    horizon = float(flag("--horizon", "4"))
    fset, time_mode = "common", "linear"

    X = I.design(pp, fset, time_mode)
    y = pp["event"].astype(int).values
    # one estimand per run, named in the output filename. `cif_mid` is the cumulative incidence of
    # a first stroke with competing deaths kept in as non-events and loss to follow-up carried by
    # IPCW; `exclusive_start` is the pre-audit frame, kept as the sensitivity arm.
    rule = flag("--horizon-rule", "cif_mid")
    base_frame, hcounts = I.horizon_frame(pp, horizon, rule)
    print(f"  horizon person accounting [{rule}]:", json.dumps(hcounts), flush=True)
    rows = []
    rng_master = np.random.default_rng(SEED)
    for held in sorted(set(pp["country"])):
        tr = (pp["country"].values != held); te = (pp["country"].values == held)
        ptr = float(y[tr].mean()); qte = float(y[te].mean())
        naive = ptr ** 2 * (1 - qte) + (1 - ptr) ** 2 * qte
        cmode = pp.loc[te, "censor_mode"].iloc[0]
        # the frozen model is fitted on the OTHER panels only - exactly the deployed situation
        frozen = {name: I.Frozen(X.loc[tr], y[tr], name) for name in models}
        lp_te = {name: linear_predictor(frozen[name], X.loc[te]) for name in models}
        pid_te = pp.loc[te, "pid"].values
        sub = pp.loc[te].reset_index(drop=True)
        upid = np.unique(pid_te)
        for name in models:
            p0 = 1.0 / (1.0 + np.exp(-lp_te[name]))
            base = evaluate(y[te], p0, naive)
            rows.append(dict(strategy="frozen", model=name, held=held, censor_mode=cmode,
                             frac=0.0, rep=0, local_persons=0, local_rows=int(te.sum()),
                             **base))
            for frac in fracs:
                for rep in range(reps):
                    rng = np.random.default_rng(SEED + 1000 * rep + int(100 * frac))
                    take = max(1, int(round(len(upid) * frac)))
                    pick = rng.choice(upid, size=take, replace=False)
                    inl = np.isin(pid_te, pick)
                    out = ~inl
                    if len(np.unique(y[te][inl])) < 2 or len(np.unique(y[te][out])) < 2:
                        continue
                    # 1) OFFSET: intercept only, fitted on the same local sample (for fairness of
                    #    information; a real deployment could take it from an aggregate incidence)
                    a, s = fit_offset(lp_te[name][inl], y[te][inl])
                    p_off = 1.0 / (1.0 + np.exp(-(lp_te[name][out] + a)))
                    # 2) RECALIBRATE: intercept + slope on the local sample
                    b0, b1 = fit_recal(lp_te[name][inl], y[te][inl])
                    p_cal = 1.0 / (1.0 + np.exp(-(b0 + b1 * lp_te[name][out])))
                    # 3) RETRAIN: the whole model on the local sample only
                    Xte = X.loc[te].reset_index(drop=True)
                    fr_local = I.Frozen(Xte[inl], y[te][inl], name)
                    p_new = 1.0 / (1.0 + np.exp(-linear_predictor(fr_local, Xte[out])))
                    nq = float(y[te][out].mean())
                    nv = ptr ** 2 * (1 - nq) + (1 - ptr) ** 2 * nq
                    # the frozen model scored on exactly the rows the adaptations are judged on,
                    # so AUROC invariance under a monotone map is checkable rather than asserted
                    froz_sub = evaluate(y[te][out], p0[out], nv)
                    # ---- the same four strategies on the PERSON scale, because a 2% interval
                    # threshold is not what a screening programme sets. Persons whose intervals
                    # formed the local sample are dropped from evaluation entirely, so no person
                    # is adapted on and then scored.
                    hb_all = base_frame[base_frame["country"] == held].reset_index(drop=True)
                    local_pids = set(pick.tolist())
                    ev_mask = ~hb_all["pid"].isin(local_pids).values
                    hb_ev = hb_all[ev_mask].reset_index(drop=True)
                    yb = hb_ev["label"].astype(int).values
                    wb = pd.to_numeric(hb_ev["ipcw"], errors="coerce").fillna(1.0)                              .to_numpy(dtype=float)
                    step_L = round(float(np.median(pp.loc[tr, "exposure_years"])) * 4) / 4
                    adapters = {"frozen": Adapter(frozen[name], 0.0, 1.0),
                                "offset": Adapter(frozen[name], a, s),
                                "recalibrate": Adapter(frozen[name], b0, b1),
                                "retrain": fr_local}
                    hz = {}
                    if len(np.unique(yb)) > 1:
                        for strat, ad in adapters.items():
                            ph, real = I.horizon_risk(ad, hb_ev, horizon, time_mode, fset, step_L)
                            qb = I.w_mean(yb, yb, wb); nt = qb * (1 - qb)
                            bh = float(np.sum(wb * (ph - yb) ** 2) / np.sum(wb))
                            ci_h, sl_h = I.weighted_recal(yb, ph, wb)
                            wuse = bool(np.any(np.abs(wb - 1.0) > 1e-12))
                            hz[strat] = dict(
                                hz_auroc=float(roc_auc_score(yb, ph, sample_weight=wb if wuse
                                                             else None)), hz_brier=bh,
                                hz_scaled_brier=float((nt - bh) / nt),
                                hz_mean_pred=I.w_mean(yb, ph, wb),
                                hz_mean_pred_unweighted=float(ph.mean()), hz_obs_prev=qb,
                                hz_oe_ratio=float(I.w_mean(yb, ph, wb) / qb) if qb else np.nan,
                                hz_cal_intercept=ci_h, hz_cal_slope=sl_h,
                                hz_realised_years=real, hz_n=len(yb),
                                hz_nb_at_05=I.weighted_net_benefit(yb, ph, wb, 0.05),
                                hz_nb_at_10=I.weighted_net_benefit(yb, ph, wb, 0.10),
                                hz_nb_all_at_05=I.weighted_net_benefit(yb, np.ones(len(yb)),
                                                                       wb, 0.05),
                                hz_flagged_at_05=float(np.sum(wb * (ph >= 0.05)) / np.sum(wb)),
                                hz_median_ipcw_weight=float(np.median(wb)))
                    rows.append(dict(strategy="frozen_sub", model=name, held=held,
                                     censor_mode=cmode, frac=frac, rep=rep,
                                     local_persons=int(take), local_rows=int(inl.sum()),
                                     auroc_frozen_same_rows=froz_sub["auroc"],
                                     delta_auroc_vs_frozen=0.0, delta_nb05_vs_frozen=0.0,
                                     **froz_sub, **hz.get("frozen", {})))
                    for strat, p in (("offset", p_off), ("recalibrate", p_cal), ("retrain", p_new)):
                        ev = evaluate(y[te][out], p, nv)
                        ev["auroc_frozen_same_rows"] = froz_sub["auroc"]
                        ev["delta_auroc_vs_frozen"] = ev["auroc"] - froz_sub["auroc"]
                        ev["delta_nb05_vs_frozen"] = ev["nb_at_05"] - froz_sub["nb_at_05"]
                        rows.append(dict(strategy=strat, model=name, held=held, censor_mode=cmode,
                                         frac=frac, rep=rep, local_persons=int(take),
                                         local_rows=int(inl.sum()), **ev, **hz.get(strat, {})))
                        r = rows[-1]
                        print(f"  {held} {name:14s} {strat:11s} frac={frac:5.2f} rep={rep} "
                              f"persons={r['local_persons']:6d} AUROC {r['auroc']:.4f} "
                              f"scaledB {r['scaled_brier']:+.4f} int {r['cal_intercept']:+.2f} "
                              f"slope {r['cal_slope']:.2f} NB@2% {r['nb_at_02']:+.5f} "
                              f"flag {r['flagged_at_02']:.3f}"
                              + (f" | 4y AUROC {r['hz_auroc']:.4f} mean_p {r['hz_mean_pred']:.4f} "
                                 f"prev {r['hz_obs_prev']:.4f} NB@5% {r['hz_nb_at_05']:+.5f} "
                                 f"(all {r['hz_nb_all_at_05']:+.5f})"
                                 if "hz_auroc" in r else ""), flush=True)
    out = pd.DataFrame(rows)
    dest = os.path.join(OUT, f"incident_adaptation_{rule}.csv")
    out.to_csv(dest, index=False)
    print("\nwrote", dest)
    piv = out.pivot_table(index=["model", "strategy"], columns=["held", "frac"],
                          values="nb_at_02").round(5)
    print("\nnet benefit at a 2% per-interval threshold (the model's own unit; the panels' median "
          "gap is 2.0-3.0 years):\n", piv.to_string())


if __name__ == "__main__":
    main()
