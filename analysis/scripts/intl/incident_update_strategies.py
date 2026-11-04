"""P1: fairer local-update baselines, so "recalibration beats retraining" is not a straw man.

Why this exists
---------------
The adaptation experiment compares ONE parameter against a de novo refit on the same local rows. A
reviewer is entitled to say that is a comparison designed to be won, because the middle of the
model-update spectrum was never populated. This script fills it in and evaluates every strategy on
identical held-out persons under the same local sample and the same estimand.

Strategies, ordered by how much of the original model they throw away:

  frozen                    deploy as-is. Zero local labels.
  offset_horizon            calibration-in-the-large: the intercept that makes the mean composed
                            four-year risk equal the observed four-year incidence. ONE parameter,
                            and it can in principle come from a published local incidence rather
                            than patient-level data.
  recalibrate_horizon       intercept AND slope on the composed four-year risk (Platt scaling of
                            the frozen score). TWO parameters.
  revise                    penalised model revision: refit the coefficients with a ridge penalty
                            toward the FROZEN coefficients (Gudmundsson-style model revision; the
                            Bayesian reading is the same objective with a Gaussian prior centred on
                            the original model). A free tuning parameter lambda spans the whole gap
                            between recalibration and refitting, which is exactly the point the
                            reviewer can make against a two-arm comparison. Intercept unpenalised,
                            because the level is what transport breaks. Regression families only.
  time_only                 refit the intercept and the two time terms (exposure, time since
                            entry) and freeze every clinical coefficient. Tests whether what needs
                            repairing is the hazard model's time scale rather than its risk factors.
  pooled                    Riley-style pooled updating: fit the whole model on the original
                            training panels PLUS the local rows. Uses the most information, so it
                            should be the strongest arm, and it costs a full refit.
  refit_local               de novo on the local rows alone. The weakest use of data, kept as the
                            published baseline.

Every arm is scored on the SAME evaluation persons - people who were not in the local sample, under
the named estimand (`cif_mid` by default: Aalen-Johansen cumulative incidence, competing deaths as
non-events, IPCW for loss to follow-up) - so differences are paired within replicate and a strategy
cannot win by being judged on an easier subset.

Usage
  python incident_update_strategies.py [--models logistic,elasticnet,spline_logistic]
                                       [--fractions 0.02,0.05,0.10,0.25,0.50] [--reps 20]
                                       [--horizon 4] [--horizon-rule cif_mid]
                                       [--lambdas 0.003,0.03,0.3,3]
"""
import os, sys, json, numpy as np, pandas as pd, warnings
warnings.filterwarnings("ignore")
from scipy.optimize import minimize
from sklearn.metrics import roc_auc_score, brier_score_loss

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)
import modeling as M
import run_loco_v2 as V2
import run_incident_loco as I
import incident_adaptation as A

OUT = I.OUT
SEED = V2.SEED
LINEAR = ("logit", "logit_agesex", "spline_logit", "elasticnet")


def flag(name, default):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default


def logit(p):
    p = np.clip(np.asarray(p, dtype=float), 1e-9, 1 - 1e-9)
    return np.log(p / (1.0 - p))


def sigmoid(z):
    return 1.0 / (1.0 + np.exp(-z))


class Revised:
    """A frozen linear model whose coefficients have been revised under a ridge penalty toward
    their original values. Presents the `predict` / `cols` interface `horizon_risk` expects."""

    def __init__(self, fr, a, b):
        self.fr, self.a, self.b, self.cols = fr, float(a), np.asarray(b, dtype=float), fr.cols

    def predict(self, X):
        return sigmoid(self.a + self.fr._mat(X) @ self.b)


def revise_coefficients(fr, Z, y, lam):
    """argmin_theta  deviance(theta) + (lam/2) * ||beta - beta_frozen||^2, intercept free.
    Started at the frozen coefficients, so lambda -> inf returns the frozen model itself and
    lambda -> 0 returns a de novo refit on these rows: the whole spectrum in one objective."""
    b0 = np.asarray(fr.clf.coef_[0], dtype=float)
    a0 = float(fr.clf.intercept_[0])
    Z = np.asarray(Z, dtype=float)
    y = np.asarray(y, dtype=float)
    n, p = Z.shape

    def obj(theta):
        a, b = theta[0], theta[1:]
        z = a + Z @ b
        # numerically stable logistic deviance
        dev = float(np.sum(np.logaddexp(0.0, z) - y * z))
        g_a = float(np.sum(sigmoid(z) - y))
        g_b = Z.T @ (sigmoid(z) - y)
        pen = 0.5 * lam * float(np.sum((b - b0) ** 2))
        g_pen = lam * (b - b0)
        return dev + pen, np.concatenate([[g_a], g_b + g_pen])

    res = minimize(obj, np.concatenate([[a0], b0]), jac=True, method="L-BFGS-B",
                   options={"maxiter": 500, "ftol": 1e-12, "gtol": 1e-10})
    return float(res.x[0]), res.x[1:], int(res.nit)


def time_only_revision(fr, Z, y, time_idx):
    """Refit only the intercept and the time terms; freeze every clinical coefficient at its
    transported value. `time_idx` are the columns of Z that carry time."""
    b0 = np.asarray(fr.clf.coef_[0], dtype=float).copy()
    a0 = float(fr.clf.intercept_[0])
    Z = np.asarray(Z, dtype=float); y = np.asarray(y, dtype=float)
    free = list(time_idx)
    offset = Z[:, [j for j in range(Z.shape[1]) if j not in free]] @ b0[
        [j for j in range(Z.shape[1]) if j not in free]]

    def obj(theta):
        z = theta[0] + offset + Z[:, free] @ theta[1:]
        dev = float(np.sum(np.logaddexp(0.0, z) - y * z))
        g_a = float(np.sum(sigmoid(z) - y))
        g_f = Z[:, free].T @ (sigmoid(z) - y)
        return dev, np.concatenate([[g_a], g_f])

    start = np.concatenate([[a0], b0[free]])
    res = minimize(obj, start, jac=True, method="L-BFGS-B",
                   options={"maxiter": 500, "ftol": 1e-12, "gtol": 1e-10})
    b = b0.copy()
    b[free] = res.x[1:]
    return float(res.x[0]), b, int(res.nit)


def score(y, p, w, **kw):
    y = np.asarray(y).astype(int); p = np.asarray(p, dtype=float)
    w = np.ones(len(y)) if w is None else np.asarray(w, dtype=float)
    weighted = bool(np.any(np.abs(w - 1.0) > 1e-12))
    q = I.w_mean(y, y, w)
    b = float(np.sum(w * (p - y) ** 2) / np.sum(w))
    mp = I.w_mean(y, p, w)
    ri, rs = I.weighted_recal(y, p, w)
    return dict(**kw, n=int(len(y)), prevalence=q, mean_pred=mp,
                oe_ratio=float(mp / q) if q else np.nan, brier=b,
                scaled_brier=float((q * (1 - q) - b) / (q * (1 - q))) if 0 < q < 1 else np.nan,
                recal_intercept=ri, recal_slope=rs,
                auroc=float(roc_auc_score(y, p, sample_weight=w if weighted else None)),
                nb_at_05=I.weighted_net_benefit(y, p, w, 0.05),
                nb_at_10=I.weighted_net_benefit(y, p, w, 0.10),
                nb_all_at_05=I.weighted_net_benefit(y, np.ones(len(y)), w, 0.05),
                flagged_at_05=float(np.sum(w * (p >= 0.05)) / np.sum(w)))


def main():
    models = flag("--models", "logistic,elasticnet,spline_logistic").split(",")
    fracs = [float(x) for x in flag("--fractions", "0.02,0.05,0.10,0.25,0.50").split(",")]
    reps = int(flag("--reps", "20"))
    horizon = float(flag("--horizon", "4"))
    rule = flag("--horizon-rule", "cif_mid")
    lambdas = [float(x) for x in flag("--lambdas", "0.003,0.03,0.3,3").split(",")]
    fset, time_mode = "common", "linear"

    pp = pd.read_csv(os.path.join(OUT, "personperiod_pooled.csv"))
    pp["country"] = pp["cohort"].map(I.COH2CTRY)
    pp = pp[pp["country"].notna()].reset_index(drop=True)
    X = I.design(pp, fset, time_mode)
    y = pp["event"].astype(int).values
    frame, counts = I.horizon_frame(pp, horizon, rule)
    print(f"horizon accounting [{rule}]: {json.dumps(counts)}", flush=True)
    def time_columns(fr):
        """Indices of the two time terms inside the FROZEN model's own coefficient vector. Not the
        design's: SimpleImputer drops all-NaN concepts (high_cholesterol in three of four panels),
        so the model's column space is narrower than X and the offsets are different."""
        return [j for j, c in enumerate(list(fr.out_cols))
                if str(c).startswith("exposure_years") or str(c).startswith("t_since_entry_years")]
    rows = []
    for held in sorted(set(pp["country"])):
        tr = (pp["country"].values != held)
        g = frame[frame["country"] == held].reset_index(drop=True)
        yb = g["label"].astype(int).to_numpy()
        wb = pd.to_numeric(g["ipcw"], errors="coerce").fillna(1.0).to_numpy(dtype=float)
        pid = g["pid"].to_numpy()
        step_L = round(float(np.median(pp.loc[tr, "exposure_years"])) * 4) / 4
        print(f"\n=== {held}: {len(g)} evaluable persons, {int(yb.sum())} events, "
              f"step {step_L}y", flush=True)
        for name in models:
            fr = I.Frozen(X.loc[tr], y[tr], name)
            ph0, realised = I.horizon_risk(A.Adapter(fr, 0.0, 1.0), g, horizon, time_mode, fset,
                                          step=step_L)
            lp0 = logit(ph0)
            # coefficient-space strategies exist only for the linear families, and the family is a
            # property of the FITTED object (logistic, elasticnet and agesex all come back as
            # "logit"), not of the model's display name.
            is_linear = fr.kind in LINEAR
            time_idx = time_columns(fr)
            base = dict(held=held, model=name, kind=fr.kind, horizon_rule=rule,
                        realised_years=realised, step_years=step_L,
                        censor_mode=g["censor_mode"].iloc[0], is_linear=is_linear)
            rows.append(dict(**base, strategy="frozen", frac=0.0, rep=0, local_persons=0,
                             **score(yb, ph0, wb)))
            for frac in fracs:
                for rep in range(reps):
                    rng = np.random.default_rng(SEED + 31000 + 1000 * rep + int(100 * frac))
                    up = np.unique(pid)
                    take = max(2, int(round(len(up) * frac)))
                    pick = rng.choice(up, size=take, replace=False)
                    loc = np.isin(pid, pick)
                    ev = ~loc
                    # Regression guard for the adaptation/evaluation independence the manuscript claims.
                    # ev is the complement of loc, so this cannot fire unless a future edit splits by row
                    # instead of by person; incident_adaptation_leakage_audit.py measures it empirically.
                    assert not (set(pid[loc]) & set(pid[ev])), "local-adaptation and evaluation persons overlap"
                    if yb[loc].sum() < 1 or len(np.unique(yb[ev])) < 2:
                        continue
                    # the local labelled sample comes from the HELD-OUT panel: that is the whole
                    # deployment scenario. Indexing the training rows here would silently give the
                    # updating arms the answer key.
                    inl = np.isin(pp.loc[~tr, "pid"].to_numpy(), pick)
                    Xl, yl = X.loc[~tr][inl], y[~tr][inl]
                    if len(np.unique(yl)) < 2:
                        continue
                    common = dict(**base, frac=frac, rep=rep, local_persons=int(loc.sum()),
                                  local_rows=int(inl.sum()), n_eval=int(ev.sum()))
                    out = {}

                    # --- one-parameter and two-parameter recalibration, on the risk scale
                    a_off, _ = A.fit_offset(lp0[loc], yb[loc])
                    out["offset_horizon"] = (sigmoid(lp0[ev] + a_off), 1)
                    b0_h, b1_h = A.fit_recal(lp0[loc], yb[loc])
                    out["recalibrate_horizon"] = (sigmoid(b0_h + b1_h * lp0[ev]), 2)

                    if is_linear:
                        Zl = fr._mat(Xl)
                        for lam in lambdas:
                            a_r, b_r, nit = revise_coefficients(fr, Zl, yl, lam)
                            rv = Revised(fr, a_r, b_r)
                            ph_r, _ = I.horizon_risk(rv, g[ev].reset_index(drop=True), horizon,
                                                     time_mode, fset, step=step_L)
                            out[f"revise_lam{lam:g}"] = (ph_r, 1 + len(b_r))
                        if time_idx:
                            a_t, b_t, nit = time_only_revision(fr, Zl, yl, time_idx)
                            rv = Revised(fr, a_t, b_t)
                            ph_t, _ = I.horizon_risk(rv, g[ev].reset_index(drop=True), horizon,
                                                     time_mode, fset, step=step_L)
                            out["time_only"] = (ph_t, 1 + len(time_idx))

                    # --- pooled updating: original training rows plus the local rows
                    Xp = pd.concat([X.loc[tr], Xl], ignore_index=True)
                    yp = np.concatenate([y[tr], yl])
                    fr_pool = I.Frozen(Xp, yp, name)
                    ph_p, _ = I.horizon_risk(fr_pool, g[ev].reset_index(drop=True), horizon,
                                             time_mode, fset, step=step_L)
                    out["pooled"] = (ph_p, np.nan)

                    # --- de novo on the local rows only
                    fr_new = I.Frozen(Xl, yl, name)
                    ph_n, _ = I.horizon_risk(fr_new, g[ev].reset_index(drop=True), horizon,
                                             time_mode, fset, step=step_L)
                    out["refit_local"] = (ph_n, np.nan)

                    frozen_here = score(yb[ev], ph0[ev], wb[ev])
                    rows.append(dict(**common, strategy="frozen_same_rows", n_params=np.nan,
                                     **frozen_here))
                    scored_here = {}
                    for strat, (p_, npar) in out.items():
                        r = dict(**common, strategy=strat, n_params=npar,
                                 **score(yb[ev], p_, wb[ev]))
                        rows.append(r)
                        scored_here[strat] = r
                    if rep == reps - 1:
                        brief = ("offset_horizon", "recalibrate_horizon", "pooled", "refit_local")
                        print(f"  {held} {name:16s} frac={frac:5.2f} local={int(loc.sum()):6d} "
                              f"frozen={frozen_here['nb_at_05']:+.5f} | "
                              + " ".join(f"{s}={scored_here[s]['nb_at_05']:+.5f}"
                                         for s in brief if s in scored_here), flush=True)

    df = pd.DataFrame(rows)
    dest = os.path.join(OUT, "incident_update_strategies.csv")
    df.to_csv(dest, index=False)
    # paired against the frozen model on the identical evaluation rows and replicate
    k = ["held", "model", "frac", "rep", "local_persons"]
    fz = df[df["strategy"] == "frozen_same_rows"][k + ["nb_at_05", "oe_ratio", "auroc"]].rename(
        columns={"nb_at_05": "nb_frozen", "oe_ratio": "oe_frozen", "auroc": "auroc_frozen"})
    d = df[df["strategy"] != "frozen_same_rows"].drop_duplicates(subset=k + ["strategy"])
    d = d.merge(fz, on=k, how="left", validate="many_to_one")
    d["nb_gain"] = d["nb_at_05"] - d["nb_frozen"]
    d.to_csv(os.path.join(OUT, "incident_update_strategies_paired.csv"), index=False)
    print(f"\nwrote {dest}  rows={len(df)}")
    print("=== mean net benefit at a 5% threshold, by strategy (paired gain in brackets)")
    pv = d.pivot_table(index="strategy", columns=["held", "frac"], values="nb_gain",
                       aggfunc="mean")
    print(pv.round(5).to_string())
    print("\n=== O/E before and after each strategy (mean over replicates)")
    print(d.pivot_table(index="strategy", columns="held", values=["oe_frozen", "oe_ratio"],
                        aggfunc="mean").round(3).to_string())
    print("\n=== fraction of replicate cells where the strategy beat the frozen model")
    print(d[d["strategy"] != "frozen"].assign(win=lambda x: (x["nb_gain"] > 0).astype(float))
          .pivot_table(index="strategy", columns="held", values="win", aggfunc="mean").round(3)
          .to_string())
    return df, d


if __name__ == "__main__":
    main()
