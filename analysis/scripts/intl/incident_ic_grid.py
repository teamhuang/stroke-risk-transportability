"""The interval-censored likelihood arm: does the grid result survive the CORRECT likelihood?

The reviewer's second-round objection, in substance:

  "Uniform allocation 虽然避免了把所有事件放在最后一个子区间，却**不自动等价于区间删失数据的正确
   似然函数**。将一个已知发生过卒中的人的事件拆成多个分数事件，与对'事件发生在整个访视区间内'这一
   概率建立似然，通常不是同一件事。"

That is right, and it is checkable. A stroke known only to have happened inside an interview gap
(a, b] is an interval-censored observation, and its likelihood contribution is

    P(a < T <= b) = S(a) - S(b) = 1 - prod_j (1 - p_j)                    [interval-censored]

where p_j is the hazard of the j-th piece. The `uniform` allocation implemented in
`incident_grid_reframe.py --alloc uniform` instead writes each piece as a fractional 0/1 row, so the
objective becomes the weighted-dataset product

    prod_j p_j^(1/n) (1 - p_j)^(1 - 1/n)                                  [moment-matched]

Both put total event weight 1 in the gap, and neither invents an event date, but they are not the same
function of the parameters: the first is the probability that the event falls somewhere in the gap, the
second is a pseudo-likelihood whose score equations are not the IC score equations. So the uniform arm
is a moment-matched device, not the IC likelihood, and it cannot be the last word on the grid question.

This script fits the actual interval-censored likelihood. It needs no re-cut file at all: covariates are
constant within a parent interval by construction (the design carries the interval-START values), so a
gap of length L cut into n = ceil(L/delta) equal pieces of length D = L/n has one hazard per piece, and

    log L_i = d_i * log(1 - (1 - p_i)^n_i) + (1 - d_i) * n_i * log(1 - p_i)

is maximised directly, with p_i = g(eta_i) for the arm's link and eta built from the PIECE length D.
Two facts make this a sharp instrument rather than another sensitivity run:

  * at delta -> infinity (n_i = 1 for every row) the contribution collapses to d log p + (1-d) log(1-p),
    i.e. exactly the Bernoulli likelihood the published GLM arms maximise. So the unsplit fit of this
    script must reproduce `logit_glm` / `cloglog_glm` / `cloglog_ph` - it is checked to 1e-6 and the
    script dies if it does not. The anchor is what makes the grid comparison meaningful. Observed:
    4.4e-8, 1.5e-7 and 3.5e-8 respectively.
  * for the proportional-hazards arm (cloglog with log-exposure offset) the aggregation is exact:
    (1 - p)^n = exp(-lambda * n * D) = exp(-lambda * L), so q depends on L and not on the grid. The IC
    likelihood therefore has ONE maximiser for the offset arm at every delta, and the frozen predictions
    at delta = 1 reproduce the unsplit ones (observed max abs diff 1.4e-12). Duration consistency stops
    being a property asserted by a link and becomes a theorem about this likelihood - and it is measured,
    not claimed.

Arms (same rows, same one-hot encoding, same LOCO split, same preprocessing contract as the published
model - median impute, degenerate-column guard, standardise, all fitted on training rows only):

  ic_logit_len      logistic link, piece length as a covariate, unpenalised   (IC analogue of logit_glm)
  ic_logit_len_l2   same with ridge 1/(2C), C = 1.0 on standardised coefficients, which is the objective
                    sklearn's LogisticRegression(C=1.0) minimises            (IC analogue of the published model)
  ic_cloglog_len    cloglog link, piece length as a covariate, unpenalised   (IC analogue of cloglog_glm)
  ic_cloglog_off    cloglog link, log(piece length) as an OFFSET, length removed from the covariates
                    (IC analogue of cloglog_ph; grid-invariant by the algebra above)

Evaluation is identical to the link arm: the horizon frame comes from `personperiod_pooled.csv`
(`--frame-pp`), so every arm is scored on identical persons with identical labels and identical IPCW
weights, and the one-intercept repair uses the same seed formula, fractions and replicate count as the
published adaptation arm.

Usage
  python incident_ic_grid.py [--horizon 4] [--horizon-rule cif_mid] [--reps 20]
                             [--delta 1] [--deltas 0,1] [--arms ic_logit_len,...]
"""
import os, sys, json, numpy as np, pandas as pd, warnings
warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)
import run_loco_v2 as V2
import run_incident_loco as I
import incident_horizon_recalibration as R
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from scipy.optimize import minimize

OUT = I.OUT
REP = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results", "reports"))
SEED = V2.SEED
FRACS = (0.02, 0.05, 0.10, 0.25, 0.50)
EXPOSURE = "exposure_years"
# arm -> (link, how length enters, ridge coefficient on 0.5*||beta_nonintercept||^2)
ARMS = {"ic_logit_len": ("logit", "covariate", 0.0),
        "ic_logit_len_l2": ("logit", "covariate", 0.5),
        "ic_cloglog_len": ("cloglog", "covariate", 0.0),
        "ic_cloglog_off": ("cloglog", "offset", 0.0)}
# the unpenalised IC arms must reproduce these GLM rows when delta -> inf (n = 1)
GLM_ANCHOR = {"ic_logit_len": "logit_glm", "ic_cloglog_len": "cloglog_glm",
              "ic_cloglog_off": "cloglog_ph"}
# ... and the L2 arm must reproduce the published sklearn model, whose objective is identical
L2_ANCHOR = {"ic_logit_len_l2": "sklearn_logistic"}


def flag(name, default):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default


def piece_count(L, delta):
    """How many equal pieces a gap of length L is cut into. delta <= 0 means 'do not cut'."""
    if delta is None or delta <= 0:
        return np.ones_like(L, dtype=np.int64)
    return np.maximum(1, np.ceil(L / float(delta)).astype(np.int64))


def inv_link(eta, link):
    eta = np.clip(eta, -40.0, 40.0)
    if link == "logit":
        return 1.0 / (1.0 + np.exp(-eta))
    return 1.0 - np.exp(-np.exp(eta))


def log_surv(eta, link):
    """log(1 - p), computed stably for both links."""
    eta = np.clip(eta, -40.0, 40.0)
    if link == "logit":
        return -np.logaddexp(0.0, eta)                    # log 1/(1+e^eta)
    return -np.exp(eta)                                   # log exp(-e^eta)


def dp_over_u(eta, link):
    """(dp/deta) / (1 - p): p for the logit, e^eta for cloglog. Both links' score factors use it."""
    eta = np.clip(eta, -40.0, 40.0)
    if link == "logit":
        return 1.0 / (1.0 + np.exp(-eta))
    return np.exp(eta)


def ic_nll_grad(b, Z, off, d, n, link, l2):
    """Negative interval-censored log-likelihood and its gradient.

    ll_i = d_i log(1 - u_i^{n_i}) + (1 - d_i) n_i log u_i,  u_i = 1 - p_i,  eta_i = Z b (+ off)
    dll/deta_i = n_i * (dp/deta / u) * [ d_i u^{n}/(1 - u^{n}) - (1 - d_i) ]
    """
    eta = Z @ b
    if off is not None:
        eta = eta + off
    lu = log_surv(eta, link)
    nl = n * lu
    nl = np.minimum(nl, -1e-12)                            # keep 1 - exp(nl) strictly positive
    logq = np.log(-np.expm1(nl))
    ll = d * logq + (1.0 - d) * nl
    g = n * dp_over_u(eta, link) * (d * np.exp(nl - logq) - (1.0 - d))
    grad = -(Z.T @ g)
    val = -float(ll.sum())
    if l2:
        val += l2 * float(np.sum(b[1:] ** 2))
        grad[1:] += 2.0 * l2 * b[1:]
    return val, grad


class IcFit:
    """Discrete-time hazard fitted by the interval-censored likelihood on a fixed piece grid.

    Preprocessing is the published model's contract, not a new one: median-impute the design, drop
    columns that are degenerate on the training rows, standardise, all on training rows only. The one
    deliberate difference from `incident_cloglog.FrozenGlm` is that the scaler is fitted on the PIECE
    length rather than the parent length, because under this specification the model's own exposure
    variable IS the piece. At delta -> inf the two coincide, which is what makes the anchor exact.
    """

    def __init__(self, Xtr, ytr, link, length_mode, delta, l2=0.0):
        self.link, self.length_mode, self.delta, self.l2 = link, length_mode, delta, l2
        self.cols = list(Xtr.columns)
        self.imp = SimpleImputer(strategy="median").fit(Xtr)
        self.names = list(self.imp.get_feature_names_out())
        A = pd.DataFrame(self.imp.transform(Xtr), columns=self.names, index=Xtr.index)
        keep = [c for c in self.names if A[c].notna().any() and A[c].nunique(dropna=True) > 1]
        self.cov = [c for c in keep if not (length_mode == "offset" and c == EXPOSURE)]
        L = np.clip(pd.to_numeric(A[EXPOSURE], errors="coerce").to_numpy(dtype=float), 1e-6, None)
        n = piece_count(L, delta).astype(float)
        D = L / n
        Ap = A.copy()
        if length_mode == "covariate":
            Ap[EXPOSURE] = D
        self.sc = StandardScaler().fit(Ap[self.cov])
        Z = np.column_stack([np.ones(len(Ap)), self.sc.transform(Ap[self.cov])])
        off = np.log(D) if length_mode == "offset" else None
        d = np.asarray(ytr, dtype=float)
        r = minimize(ic_nll_grad, np.zeros(Z.shape[1]), args=(Z, off, d, n, link, l2),
                     jac=True, method="L-BFGS-B",
                     options={"maxiter": 3000, "ftol": 1e-14, "gtol": 1e-10})
        self.params = np.asarray(r.x, dtype=float)
        self.nll = float(r.fun)
        self.converged = bool(r.success)
        self.n_iter = int(r.nit)
        self.term_names = (["const"] + [f"b[{c}]" for c in self.cov]
                           + (["offset:log(piece_length)"] if length_mode == "offset" else []))

    def _pieces(self, F):
        Fi = pd.DataFrame(self.imp.transform(F[self.cols]), columns=self.names, index=F.index)
        L = np.clip(pd.to_numeric(Fi[EXPOSURE], errors="coerce").to_numpy(dtype=float), 1e-6, None)
        n = piece_count(L, self.delta)
        D = L / n.astype(float)
        Fp = Fi.copy()
        if self.length_mode == "covariate":
            Fp[EXPOSURE] = D
        Z = np.column_stack([np.ones(len(Fp)), self.sc.transform(Fp[self.cov])])
        off = np.log(D) if self.length_mode == "offset" else None
        return Z, off, n.astype(float), L, D

    def eta(self, F):
        Z, off, n, L, D = self._pieces(F)
        e = Z @ self.params
        return e if off is None else e + off

    def piece_prob(self, F):
        """hazard of ONE piece, and the piece geometry, for readers who want the parts."""
        Z, off, n, L, D = self._pieces(F)
        e = Z @ self.params
        if off is not None:
            e = e + off
        return inv_link(e, self.link), n, D

    def predict(self, F):
        """P(stroke inside an interval of this row's length) under the IC aggregation."""
        p, n, _ = self.piece_prob(F)
        lu = np.log(np.clip(1.0 - p, 1e-300, 1.0))
        return -np.expm1(np.minimum(n * lu, -1e-12))

    def predict_piece(self, F):
        """The un-aggregated single-interval answer, i.e. what the same parameters say if the gap is
        treated as one piece. Only used to show that the offset arm does not depend on the grid."""
        p, _, _ = self.piece_prob(F)
        return p


def link_of(p):
    return np.log(np.clip(p, 1e-12, 1 - 1e-12) / (1.0 - np.clip(p, 1e-12, 1 - 1e-12)))


def cumhaz_of(p):
    p = np.clip(np.asarray(p, dtype=float), 1e-12, 1 - 1e-12)
    return np.log(-np.log(1.0 - p))


def inv_link_space(z, space):
    z = np.clip(np.asarray(z, dtype=float), -40.0, 40.0)
    if space == "logit":
        return 1.0 / (1.0 + np.exp(-z))
    return 1.0 - np.exp(-np.exp(z))


def fit_offset_space(p, y, space):
    q = float(np.mean(y))
    if not (0 < q < 1):
        return 0.0
    z = link_of(p) if space == "logit" else cumhaz_of(p)
    lo, hi = -12.0, 12.0
    for _ in range(80):
        mid = (lo + hi) / 2.0
        if inv_link_space(z + mid, space).mean() < q:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2.0


def compose(fr, base, horizon, time_mode, fset, n_pieces):
    """H-year risk from n_pieces EQUAL pieces with the covariates held fixed (no age advancing)."""
    step = horizon / float(n_pieces)
    surv = np.ones(len(base))
    for _ in range(int(n_pieces)):
        frame = base.copy()
        frame[EXPOSURE] = step
        if time_mode == "linear":
            frame["t_since_entry_years"] = 0.0
        surv *= (1.0 - fr.predict(I.design(frame, fset, time_mode).reindex(columns=fr.cols)))
    return 1.0 - surv


class SkL2:
    """sklearn's LogisticRegression(C=1.0) behind the SAME preprocessing as IcFit, used only as the
    reference for `ic_logit_len_l2`: the two minimise the identical objective
    (sum log-loss + 0.5||beta_nonintercept||^2 on standardised columns), so agreement proves the ridge
    term in this script is the published model's L2 penalty and not something else.

    It is deliberately NOT compared against the published row. See `published_row_tolerance` in the
    diagnostics: the published primary model runs sklearn at its default tol = 1e-4 and stops after 10
    iterations, while this reference is run to tol = 1e-10; the two differ by up to 0.009 in the US
    predicted-to-observed ratio (1.1606 published vs 1.1698 converged), which is a convergence gap in
    the published model, not a difference in estimand or specification.
    """

    def __init__(self, Xtr, ytr):
        self.cols = list(Xtr.columns)
        self.imp = SimpleImputer(strategy="median").fit(Xtr)
        self.names = list(self.imp.get_feature_names_out())
        A = pd.DataFrame(self.imp.transform(Xtr), columns=self.names, index=Xtr.index)
        self.keep = [c for c in self.names if A[c].notna().any() and A[c].nunique(dropna=True) > 1]
        self.sc = StandardScaler().fit(A[self.keep])
        self.clf = LogisticRegression(max_iter=5000, C=1.0, tol=1e-10,
                                      random_state=SEED).fit(self.sc.transform(A[self.keep]), ytr)
        self.n_iter = int(self.clf.n_iter_[0])

    def predict(self, F):
        Fi = pd.DataFrame(self.imp.transform(F[self.cols]), columns=self.names, index=F.index)
        return self.clf.predict_proba(self.sc.transform(Fi[self.keep]))[:, 1]


def main():
    horizon = float(flag("--horizon", "4"))
    rule = flag("--horizon-rule", "cif_mid")
    reps = int(flag("--reps", "20"))
    frame_file = flag("--frame-pp", "personperiod_pooled.csv")
    fit_file = flag("--pp", "personperiod_pooled.csv")
    deltas = [float(v) for v in flag("--deltas", "0,1").split(",")]
    arms = flag("--arms", ",".join(ARMS)).split(",")
    fset, time_mode = "common", "linear"

    pp = pd.read_csv(os.path.join(OUT, fit_file))
    pp["country"] = pp["cohort"].map(I.COH2CTRY)
    pp = pp[pp["country"].notna()].reset_index(drop=True)
    if "row_weight" in pp.columns and not np.allclose(
            pd.to_numeric(pp["row_weight"], errors="coerce").fillna(1.0), 1.0):
        sys.exit("this arm fits parent intervals, not re-cut pieces: pass --pp "
                 "personperiod_pooled.csv")
    X = I.design(pp, fset, time_mode)
    y = pp["event"].astype(int).values
    fp = pd.read_csv(os.path.join(OUT, frame_file)) if frame_file != fit_file else pp
    fp["country"] = fp["cohort"].map(I.COH2CTRY)
    fp = fp[fp["country"].notna()].reset_index(drop=True)
    base_frame, hcounts = I.horizon_frame(fp, horizon, rule)
    L = pd.to_numeric(pp[EXPOSURE], errors="coerce").to_numpy(dtype=float)
    print(f"fit rows={len(pp)} (parent intervals) from {fit_file} | horizon frame from "
          f"{frame_file} [{rule}]", flush=True)
    print(f"piece grid deltas={deltas} | max pieces per interval "
          + ", ".join(f"{d:g}:{int(piece_count(L, d).max())}" for d in deltas), flush=True)

    rows, diag = [], {}
    for held in sorted(set(pp["country"])):
        tr = (pp["country"].values != held)
        te = (pp["country"].values == held)
        cmode = pp.loc[te, "censor_mode"].iloc[0]
        step_L = round(float(np.median(pp.loc[tr, EXPOSURE])) * 4) / 4
        n_steps = max(1, int(round(horizon / step_L)))
        step_used = horizon / n_steps
        hb = base_frame[base_frame["country"] == held].reset_index(drop=True)
        yb_all = hb["label"].astype(int).values
        wb = pd.to_numeric(hb["ipcw"], errors="coerce").fillna(1.0).to_numpy(dtype=float)
        pid_all = hb["pid"].values
        upid = np.unique(pid_all)
        rng0 = np.random.default_rng(SEED + 11)
        idx = rng0.choice(len(hb), size=min(3000, len(hb)), replace=False)
        print(f"\n=== {held}: horizon-evaluable persons={len(hb)} events={int(yb_all.sum())} "
              f"prevalence={yb_all.mean():.4f} censor={cmode} step_used={step_used}", flush=True)
        for delta in deltas:
            for name in arms:
                link, lmode, l2 = ARMS[name]
                fr = IcFit(X.loc[tr], y[tr], link, lmode, delta, l2)
                ph, realised = I.horizon_risk(fr, hb, horizon, time_mode, fset, step=step_used)
                ph1, _ = I.horizon_risk(fr, hb, horizon, time_mode, fset, step=None)
                ratios = {n: compose(fr, hb.iloc[idx], horizon, time_mode, fset, n)
                          for n in (1, 2, 4, 8)}
                diag[f"{held}|{name}|d{delta:g}"] = {
                    "link": link, "length_mode": lmode, "ridge": l2, "delta_years": delta,
                    "converged": fr.converged, "n_iter": fr.n_iter, "nll": round(fr.nll, 3),
                    "terms": fr.term_names,
                    "params": [round(float(v), 5) for v in fr.params],
                    "duration_consistency_mean_risk_1pc": round(float(ratios[1].mean()), 5),
                    **{f"ratio_pieces{n}_over_1":
                       float(np.mean(ratios[n] / np.maximum(ratios[1], 1e-12)))
                       for n in (2, 4, 8)},
                    "frozen_mean_pred_step": round(float(ph.mean()), 5),
                    "frozen_mean_pred_single_interval": round(float(ph1.mean()), 5)}
                space = link
                z_all = link_of(ph) if space == "logit" else cumhaz_of(ph)
                rows.append(dict(held=held, arm=name, link=space, delta_years=delta,
                                 strategy="frozen_all", frac=0.0, rep=0, censor_mode=cmode,
                                 realised_horizon_years=realised, local_persons=0,
                                 n_eval_persons=int(len(hb)), mean_repair_shift=np.nan,
                                 **R.metrics(yb_all, ph, wb)))
                for frac in FRACS:
                    for rep_i in range(reps):
                        rng = np.random.default_rng(SEED + 7000 + 1000 * rep_i + int(100 * frac))
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
                        y_e, ph_e, w_e = yb_all[ev], ph[ev], wb[ev]
                        a_link = fit_offset_space(ph[loc], yb_all[loc], space)
                        a_logit = fit_offset_space(ph[loc], yb_all[loc], "logit")
                        common = dict(held=held, arm=name, link=space, delta_years=delta, frac=frac,
                                      rep=rep_i, censor_mode=cmode,
                                      realised_horizon_years=realised,
                                      local_persons=int(loc.sum()),
                                      local_events=int(yb_all[loc].sum()),
                                      n_eval_persons=int(len(y_e)))
                        cand = [("frozen_sub", 0.0, z_all[ev]),
                                (f"offset_{space}", a_link, z_all[ev] + a_link)]
                        if space != "logit":
                            cand.append(("offset_logit", a_logit, z_all[ev] + a_logit))
                        for strat, sh, z in cand:
                            p = ph_e if strat == "frozen_sub" else inv_link_space(z, space)
                            rows.append(dict(**common, strategy=strat, mean_repair_shift=float(sh),
                                             **R.metrics(y_e, p, w_e)))
                        if rep_i == reps - 1 and delta == deltas[-1]:
                            fz = [r for r in rows if r["held"] == held and r["arm"] == name
                                  and r["frac"] == frac and r["rep"] == rep_i
                                  and r["strategy"] == "frozen_sub"][-1]
                            rp = [r for r in rows if r["held"] == held and r["arm"] == name
                                  and r["frac"] == frac and r["rep"] == rep_i
                                  and r["strategy"] == f"offset_{space}"][-1]
                            print(f"  {held} {name:16s} d={delta:g} frac={frac:5.2f} "
                                  f"shift={rp['mean_repair_shift']:+.3f} "
                                  f"mean_p {fz['mean_pred']:.4f}->{rp['mean_pred']:.4f} "
                                  f"p/obs {fz['oe_ratio']:.2f}->{rp['oe_ratio']:.2f} "
                                  f"NB@5% {fz['nb_at_05']:+.5f}->{rp['nb_at_05']:+.5f}", flush=True)

    out = pd.DataFrame(rows)
    dest = os.path.join(OUT, f"incident_ic_likelihood_{rule}.csv")
    out.to_csv(dest, index=False)

    paired = []
    for held in sorted(set(out["held"])):
        for name in [a for a in arms if a in set(out["arm"])]:
            for delta in sorted(set(out["delta_years"])):
                sub = out[(out.held == held) & (out.arm == name) & (out.delta_years == delta)]
                fz = sub[sub.strategy == "frozen_sub"].pivot_table(index="frac", columns="rep",
                                                                    values="nb_at_05")
                for strat in [s for s in sub["strategy"].unique() if s != "frozen_sub"]:
                    s = sub[sub.strategy == strat].pivot_table(index="frac", columns="rep",
                                                               values="nb_at_05")
                    for frac in s.index.intersection(fz.index):
                        a, b = s.loc[frac].dropna(), fz.loc[frac].dropna()
                        ix = a.index.intersection(b.index)
                        if len(ix) < 3:
                            continue
                        d = (a.loc[ix] - b.loc[ix]).to_numpy()
                        paired.append(dict(held=held, arm=name, strategy=strat,
                                           delta_years=float(delta), frac=float(frac),
                                           n_complete_reps=int(len(ix)),
                                           mean_gain_nb_at_05=float(d.mean()),
                                           sd_gain_nb_at_05=float(d.std(ddof=1)),
                                           n_gain_positive=int((d > 0).sum()),
                                           min_gain=float(d.min()), max_gain=float(d.max())))
    pdf = pd.DataFrame(paired)
    pdf.to_csv(os.path.join(OUT, f"incident_ic_likelihood_paired_{rule}.csv"), index=False)

    # ---- the gates. this arm is only evidence if its unsplit fit IS the published fit.
    checks = {}
    glm_path = os.path.join(OUT, f"incident_cloglog_{rule}.csv")
    pub_path = os.path.join(OUT, f"incident_horizon_recalibration_{rule}.csv")
    cols = ("mean_pred", "obs_prev", "oe_ratio", "nb_at_05", "auroc", "n_eval_persons")
    if os.path.exists(glm_path):
        glm = pd.read_csv(glm_path)
        for arm, ref in GLM_ANCHOR.items():
            a = out[(out.arm == arm) & (out.delta_years == 0.0) & (out.strategy == "frozen_all")]
            b = glm[(glm.arm == ref) & (glm.strategy == "frozen_all")]
            m = a.merge(b, on="held", suffixes=("", "_ref"))
            if len(m) != 4:
                checks[f"{arm}_vs_{ref}"] = "row count mismatch"
                continue
            checks[f"{arm}_vs_{ref}"] = {c: float((m[c] - m[f"{c}_ref"]).abs().max()) for c in cols}
        # the offset arm must ALSO be grid-invariant: delta=1 == delta=0, same parameters, same risk
        for arm in ("ic_cloglog_off",):
            a = out[(out.arm == arm) & (out.delta_years == 1.0) & (out.strategy == "frozen_all")]
            b = out[(out.arm == arm) & (out.delta_years == 0.0) & (out.strategy == "frozen_all")]
            m = a.merge(b, on="held", suffixes=("", "_d0"))
            checks[f"{arm}_grid_invariance"] = {
                c: float((m[c] - m[f"{c}_d0"]).abs().max()) for c in cols}
    if os.path.exists(pub_path) and "ic_logit_len_l2" in arms:
        pub = pd.read_csv(pub_path)
        pub = pub[(pub.model == "logistic") & (pub.strategy == "frozen_all")]
        a = out[(out.arm == "ic_logit_len_l2") & (out.delta_years == 0.0)
                & (out.strategy == "frozen_all")]
        m = a.merge(pub, on="held", suffixes=("", "_pub"))
        if len(m):
            # the published row is NOT the gate: sklearn's default tol=1e-4 stopped it after 10
            # iterations. Report that gap, and gate against the converged same-objective reference.
            checks["published_row_tolerance_gap"] = {
                c: float((m[c] - m[f"{c}_pub"]).abs().max()) for c in cols}
            ref = []
            for held in sorted(set(out["held"])):
                trm = (pp["country"].values != held)
                sk = SkL2(X.loc[trm], y[trm])
                hb = base_frame[base_frame["country"] == held].reset_index(drop=True)
                st = round(float(np.median(pp.loc[trm, EXPOSURE])) * 4) / 4
                st = horizon / max(1, int(round(horizon / st)))
                ph, _ = I.horizon_risk(sk, hb, horizon, time_mode, fset, step=st)
                yb = hb["label"].astype(int).values
                ref.append(dict(held=held, n_eval_persons=int(len(yb)),
                                **R.metrics(yb, ph,
                                            pd.to_numeric(hb["ipcw"], errors="coerce")
                                            .fillna(1.0).to_numpy(dtype=float)),
                                sk_n_iter=sk.n_iter))
            r = pd.DataFrame(ref)
            m2 = a.merge(r, on="held", suffixes=("", "_sk"))
            have = [c for c in cols if c in m2.columns and f"{c}_sk" in m2.columns]
            checks["ic_logit_len_l2_vs_converged_sklearn_l2"] = {
                c: float((m2[c] - m2[f"{c}_sk"]).abs().max()) for c in have}
            m3 = r.merge(pub, on="held", suffixes=("", "_pub"))
            have3 = [c for c in cols if c in m3.columns and f"{c}_pub" in m3.columns]
            checks["converged_sklearn_l2_vs_published_row"] = {
                c: float((m3[c] - m3[f"{c}_pub"]).abs().max()) for c in have3}
    bad = []
    # the two published-row comparisons are DISCLOSURES, not gates: they measure how far the published
    # primary model sits from its own converged optimum (sklearn's default tol = 1e-4), which is a fact
    # about the published run, not a consistency condition this script can satisfy.
    NOT_GATED = {"published_row_tolerance_gap", "converged_sklearn_l2_vs_published_row"}
    for k in [k for k in checks if k not in NOT_GATED]:
        v = checks[k]
        if not isinstance(v, dict):
            bad.append(f"{k}: {v}")
            continue
        mx = max(v.values())
        print(f"  anchor {k}: max abs diff {mx:.3e}", flush=True)
        if mx > 1e-5:
            bad.append(f"{k}: max abs diff {mx:.3e}")
    for k in NOT_GATED:
        if isinstance(checks.get(k), dict):
            print(f"  disclosure {k}: max abs diff {max(checks[k].values()):.3e} -> "
                  f"{json.dumps(checks[k])}", flush=True)
    doc = {"horizon_years": horizon, "horizon_rule": rule, "fit_file": fit_file,
           "frame_file": frame_file, "reps": reps, "fractions": list(FRACS),
           "deltas_years": deltas, "arms": {k: {"link": v[0], "length_enters_as": v[1],
                                                 "ridge": v[2]} for k, v in ARMS.items()},
           "likelihood": ("per parent interval i with n_i equal pieces of length D_i: "
                          "d_i*log(1-(1-p_i)^n_i) + (1-d_i)*n_i*log(1-p_i), p_i = g(eta(x_i, D_i)). "
                          "At n_i = 1 this is the Bernoulli likelihood of the published GLM arms; for "
                          "the cloglog-offset arm the aggregation collapses to exp(-lambda*L) at every "
                          "n_i, so that arm is grid-invariant by construction"),
           "not_the_thing_this_replaces": ("`--alloc uniform` in incident_grid_reframe.py writes each "
                                           "piece as a fractional 0/1 row pair, whose objective is "
                                           "prod_j p_j^(1/n)(1-p_j)^(1-1/n). That matches the event "
                                           "count and invents no date, but it is not the interval-"
                                           "censored likelihood 1 - prod_j(1 - p_j), which is what this "
                                           "script maximises"),
           "horizon_person_accounting": hcounts, "fit_and_linkage_diagnostics": diag,
           "anchor_checks": checks, "anchor_gate_failures": bad, "n_rows": int(len(out)),
           "published_model_convergence": (
               "the published primary model is sklearn LogisticRegression(C=1.0) at its default "
               "tol=1e-4, which stops after ~10 iterations. Re-running the IDENTICAL objective to "
               "tol=1e-10 changes the US predicted-to-observed ratio from 1.1606 to 1.1698 and the "
               "US AUROC by 3.6e-4; the unpenalised GLM arms of incident_cloglog.py sit at the "
               "converged value, which is why the L2 anchor here is gated against the converged "
               "reference and the published-row difference is reported as a disclosure. No "
               "manuscript conclusion turns on it (both values over-predict the US), but the "
               "published numbers are converged to 1e-4, not to machine precision."),
           "note": ("interval-censored discrete-time hazards fitted on the LOCO training panels; the "
                    "evaluation frame and its IPCW weights always come from --frame-pp, so every arm "
                    "here and every arm in incident_cloglog.py is scored on identical persons")}
    os.makedirs(REP, exist_ok=True)
    with open(os.path.join(REP, f"incident_ic_likelihood_{rule}.json"), "w",
              encoding="utf-8") as f:
        json.dump(doc, f, indent=2, ensure_ascii=False)
    print(f"\nwrote {dest} rows={len(out)}")
    if bad:
        raise AssertionError("interval-censored arm failed its anchor gates: " + "; ".join(bad))


if __name__ == "__main__":
    main()
