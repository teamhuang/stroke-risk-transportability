"""P0-1 resolution: a joint competing-risks likelihood for interval-censored first events.

Where this came from. The review asked whether composing two separately fitted interval event
probabilities as  S = prod(1 - p_s)(1 - p_d)  is a valid competing-events probability, since the
exclusive structure suggests  P(no event) = 1 - p_s - p_d .

Three things are then true at once, and the middle one is the one that decides the design:

 1. The SURVIVAL factor is right. For independent latent event times with cause-specific hazards
    lambda_s, lambda_d, the probability that NEITHER event occurs in a gap of length L is
    exp(-(lambda_s + lambda_d) L) = (1 - p_s)(1 - p_d) exactly, with p_c = 1 - exp(-lambda_c L).
    The complements multiply because the two latent times are independent; `1 - p_s - p_d` would be
    right only if the two marginal event indicators were mutually exclusive, and they are not - a
    stroke and a death can both fall inside one unobserved gap.

 2. The STEP EVENT factor is wrong, as the review suspected. The probability that the FIRST event in
    the step is a stroke is alpha_s = lambda_s/(lambda_s+lambda_d) * (1 - exp(-(lambda_s+lambda_d) L)),
    not p_s. The marginal over-states it by p_s - alpha_s (the death-first-within-step case), which is
    NOT p_s * p_d. The per-step total mass 1 + p_s p_d > 1 arises because the shipped composition summed
    p_s + p_d + (1-p_s)(1-p_d); p_s * p_d is the TOTAL double-count and obeys the exact identity
    p_s * p_d = (p_s - alpha_s) + (p_d - alpha_d). On the real panels that excess is 5.3e-4 to 7.6e-4 per step.

 3. Repairing (2) on top of the SAME marginal fits makes things worse, and `incident_cr_simulation.py`
    shows it. Each cause-specific fit is itself mis-specified for the observed data: it is fitted to an
    EXCLUSIVE first-event category while asserting the marginal event probability, so it returns a
    hazard that is too small, and that deficit almost exactly cancels the over-count in (2). Measured
    total bias against a known truth: shipped composition -0.0% to +4.8%, "exact" composition on the
    same fitted hazards -6.4% to -25.0%. So a numerically exact formula applied to an inconsistent
    estimator is not a better estimator, it is a different error.

The principled object is the joint model fitted here. Per interval of length L, with three mutually
exclusive observed outcomes (stroke-first, death-first, neither):

    P(stroke) = lambda_s/T (1 - E),   P(death) = lambda_d/T (1 - E),   P(neither) = E
    T = lambda_s + lambda_d,          E = exp(-T L),        lambda_c = exp(z_c' beta_c)

which sums to 1 by construction, is fitted by the exact multinomial likelihood of what is actually
observed, and whose cumulative incidence over a horizon is then composed from quantities that are
mutually exclusive at every step - no cancellation, no over-count, no grid dependence.

This module provides:
  JointCrFit           the fitter, with an analytic gradient checked against finite differences at
                       import time (the check aborts the module if it fails by more than 1e-5 relative)
  joint_cif            F_stroke over a horizon from a fitted pair
  run_real()           the four-panel LOCO evaluation under the joint model, alongside the shipped arm

Usage
  python incident_cr_joint.py [--horizon 4] [--reps 40] [--boot 500]
Outputs (data/processed/intl/incident/)
  incident_cr_joint.csv           frozen + repair rows, joint arm beside the shipped arm
  incident_cr_joint_paired.csv    paired repair effects with three-way treat-none counts
  incident_cr_joint_ladder.csv    step ladder: the joint arm must be flat at 1.000
"""
import os, sys, json, warnings
import numpy as np
import pandas as pd
from scipy.optimize import minimize
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler

warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)
import run_incident_loco as I

EXPOSURE = "exposure_years"


def _probs(ls, ld, L):
    """The three exclusive interval probabilities."""
    tot = np.maximum(ls + ld, 1e-12)
    E = np.exp(-tot * L)
    one_minus = -np.expm1(-tot * L)
    ps = ls / tot * one_minus
    pd_ = ld / tot * one_minus
    return ps, pd_, E, tot


class JointCrFit:
    """Cause-specific hazards fitted jointly on the exclusive first-event categories.

    Same preprocessing contract as the published model: median-impute on training rows, drop degenerate
    columns, standardise, log-exposure enters as an offset so the hazard is a rate per year.
    """

    def __init__(self, Xtr, ds, dd, l2=0.0):
        self.cols = list(Xtr.columns)
        self.imp = SimpleImputer(strategy="median").fit(Xtr)
        self.names = list(self.imp.get_feature_names_out())
        A = pd.DataFrame(self.imp.transform(Xtr), columns=self.names, index=Xtr.index)
        keep = [c for c in self.names if A[c].notna().any() and A[c].nunique(dropna=True) > 1]
        self.cov = [c for c in keep if c != EXPOSURE]
        self.sc = StandardScaler().fit(A[self.cov])
        Z = np.column_stack([np.ones(len(A)), self.sc.transform(A[self.cov])])
        self.Zdim = Z.shape[1]
        L = np.clip(pd.to_numeric(A[EXPOSURE], errors="coerce").to_numpy(dtype=float), 1e-6, None)
        ds = np.asarray(ds, dtype=float)
        dd = np.asarray(dd, dtype=float)
        assert np.all(ds + dd <= 1.0), "an interval cannot be both stroke-first and death-first"
        p0 = np.zeros(self.Zdim) - 2.0        # start away from the ridge so both hazards can grow
        x0 = np.concatenate([p0, p0])
        r = minimize(self._obj, x0, args=(Z, L, ds, dd, l2), jac=True, method="L-BFGS-B",
                     options={"maxiter": 4000, "ftol": 1e-13, "gtol": 1e-9})
        self.params = np.asarray(r.x, dtype=float)
        self.nll = float(r.fun)
        self.converged = bool(r.success)
        self.n_iter = int(r.nit)
        self.l2 = l2

    def _rates(self, b, c, Z):
        ls = np.exp(np.clip(Z @ b, -40, 20))
        ld = np.exp(np.clip(Z @ c, -40, 20))
        return ls, ld

    def _obj(self, x, Z, L, ds, dd, l2):
        k = self.Zdim
        b, c = x[:k], x[k:]
        ls, ld = self._rates(b, c, Z)
        ps, pd_, E, tot = _probs(ls, ld, L)
        ps_c = np.clip(ps, 1e-12, 1.0)
        pd_c = np.clip(pd_, 1e-12, 1.0)
        E_c = np.clip(E, 1e-12, 1.0)
        ll = ds * np.log(ps_c) + dd * np.log(pd_c) + (1.0 - ds - dd) * np.log(E_c)
        val = -float(ll.sum())
        # d p_s / d lambda_s ; d p_s / d lambda_d ; etc.
        om = 1.0 - E
        dps_dls = ld / tot ** 2 * om + ls / tot * L * E
        dps_dld = -ls / tot ** 2 * om + ls / tot * L * E
        dpd_dld = ls / tot ** 2 * om + ld / tot * L * E
        dpd_dls = -ld / tot ** 2 * om + ld / tot * L * E
        dE_dls = -L * E
        dE_dld = -L * E
        dll_dls = ds * dps_dls / ps_c + dd * dpd_dls / pd_c + (1.0 - ds - dd) * dE_dls / E_c
        dll_dld = ds * dps_dld / ps_c + dd * dpd_dld / pd_c + (1.0 - ds - dd) * dE_dld / E_c
        # chain rule: d lambda/d beta = lambda * z, and the score sums over rows
        g_b = -(Z.T @ (dll_dls * ls))
        g_c = -(Z.T @ (dll_dld * ld))
        grad = np.concatenate([g_b, g_c])
        if l2:
            val += l2 * float(np.sum(b[1:] ** 2) + np.sum(c[1:] ** 2))
            grad[1:k] += 2.0 * l2 * b[1:]
            grad[k + 1:] += 2.0 * l2 * c[1:]
        return val, grad

    def _ZL(self, F):
        Fi = pd.DataFrame(self.imp.transform(F[self.cols]), columns=self.names, index=F.index)
        L = np.clip(pd.to_numeric(Fi[EXPOSURE], errors="coerce").to_numpy(dtype=float), 1e-6, None)
        Z = np.column_stack([np.ones(len(Fi)), self.sc.transform(Fi[self.cov])])
        return Z, L

    def rates(self, F):
        Z, L = self._ZL(F)
        k = self.Zdim
        return self._rates(self.params[:k], self.params[k:], Z)

    def predict_interval(self, F):
        """P(first event in this interval is a stroke) - the exclusive quantity."""
        ls, ld = self.rates(F)
        Z, L = self._ZL(F)
        ps, _, _, _ = _probs(ls, ld, L)
        return ps

    @property
    def term_names(self):
        return ["const_s"] + [f"b_s[{c}]" for c in self.cov] + ["const_d"] + \
            [f"b_d[{c}]" for c in self.cov]


def _mass_dev(jf, F, step, fset="common", time_mode="linear"):
    """Largest deviation from 1 of the three exclusive interval probabilities - the conservation check."""
    Dm = I.design(F.assign(exposure_years=step), fset, time_mode).reindex(columns=jf.cols)
    ps, pd_, E, _ = _probs(*jf.rates(Dm), np.full(len(F), float(step)))
    return float(np.max(np.abs(ps + pd_ + E - 1.0)))


def joint_cif(jf, base, horizon, time_mode, step, fset="common", advance=True):
    """F_stroke(horizon) from the joint fit, stepping by `step`.

    The step terms are mutually exclusive by construction (alpha + beta + E = 1), so the composition
    is exactly the horizon CIF for piecewise-constant hazards at ANY step size; the ladder in main()
    checks that numerically. As in incident_cr_primary.compose_two the covariates are advanced on the
    RAW frame and then re-expanded into the one-hot design matrix the model was fitted on - jf.rates
    expects those design columns, not the raw questionnaire fields."""
    n_steps = max(1, int(round(horizon / step)))
    surv = np.ones(len(base))
    acc = np.zeros(len(base))
    Dlen = np.full(len(base), float(step))
    for j in range(n_steps):
        frame = base.copy()
        if advance:
            frame["age"] = pd.to_numeric(base["age"], errors="coerce").values + j * step
            if time_mode == "linear":
                frame["t_since_entry_years"] = j * step
        frame[EXPOSURE] = step
        Dm = I.design(frame, fset, time_mode).reindex(columns=jf.cols)
        ls, ld = jf.rates(Dm)
        ps, _, E, _ = _probs(ls, ld, Dlen)
        acc = acc + surv * ps
        surv = surv * E
    return acc


def selftest_gradient():
    """Analytic gradient vs central finite differences; aborts the module if they disagree.

    WHERE it checks matters. The original guard compared the two at `jf.params`, the L-BFGS
    converged point, where the true gradient is ~0. There both the analytic gradient and the finite
    differences are dominated by floating-point noise (~1e-8 in the objective), so their ratio -
    which is what a relative test reads - was arbitrary (~1.08) and the assert false-failed on a
    gradient that is in fact exact to 3.5e-10 at realistic hazards. A converged optimum is the worst
    possible place to verify a gradient. This now checks at a non-degenerate PROBE point: both
    intercepts at log 0.05/yr and slopes at 0.4, so the per-year hazards stay small (no `np.clip`
    on the linear predictor, no underflow of `exp(-(lambda_s+lambda_d)L)` to the 1e-12 floor - the
    two places where the objective is deliberately clamped and a finite difference of the clamped
    surrogate would legitimately differ from the gradient of the true likelihood), while the
    gradient is clearly nonzero. Real fits sit in this same unclipped regime."""
    rng = np.random.default_rng(7)
    n = 400
    F = pd.DataFrame({"x": rng.standard_normal(n), "exposure_years": rng.uniform(0.5, 4.0, n)})
    ds = (rng.random(n) < 0.05).astype(float)
    dd = ((rng.random(n) < 0.20) & (ds == 0)).astype(float)
    jf = JointCrFit(F, ds, dd)
    Z, L = jf._ZL(F)
    probe = np.full_like(jf.params, 0.4)
    probe[0] = probe[jf.Zdim] = -3.0            # both intercepts -> hazard ~0.05/yr, slopes modest
    _, g = jf._obj(probe, Z, L, ds, dd, 0.0)
    h = 1e-6
    fd = np.zeros_like(g)
    for i in range(len(g)):
        xp = probe.copy(); xp[i] += h
        xm = probe.copy(); xm[i] -= h
        fd[i] = (jf._obj(xp, Z, L, ds, dd, 0.0)[0] - jf._obj(xm, Z, L, ds, dd, 0.0)[0]) / (2 * h)
    assert float(np.max(np.abs(g))) > 1e-6, "probe gradient is degenerate - the check tests nothing"
    rel = float(np.max(np.abs(g - fd)) / max(np.max(np.abs(fd)), 1e-12))
    assert rel < 1e-5, f"analytic gradient disagrees with finite differences, rel {rel:.2e}"
    ps, pd_, E, _ = _probs(*jf.rates(F), L)
    mass = float(np.max(np.abs(ps + pd_ + E - 1.0)))
    assert mass < 1e-12, f"joint interval probabilities do not sum to 1, max deviation {mass:.2e}"
    return rel, mass


GRAD_REL, MASS_DEV = selftest_gradient()


def main():
    horizon = float(flag("--horizon", "4"))
    reps = int(flag("--reps", "40"))
    B = int(flag("--boot", "500"))
    fracs = [float(x) for x in flag("--fractions", "0.02,0.05,0.10,0.25,0.50").split(",")]
    rules = flag("--rules", "cif_mid,cif_start,cif_end").split(",")
    fset, time_mode = "common", "linear"

    import run_incident_loco as I
    import incident_cr_primary as P
    import incident_ic_grid as IC
    import incident_cr_exact as EX

    OUT = P.OUT
    SEED = P.SEED
    print(f"module self-test: gradient rel error {GRAD_REL:.2e}, interval-probability mass deviation "
          f"{MASS_DEV:.2e}", flush=True)

    pp = pd.read_csv(os.path.join(OUT, "personperiod_pooled.csv"))
    pp["country"] = pp["cohort"].map(I.COH2CTRY)
    pp = pp[pp["country"].notna()].reset_index(drop=True)
    panels = sorted(set(pp["country"]))
    X = I.design(pp, fset, time_mode)
    ds = pp["event"].astype(int).values
    dd = pp["end_status"].isin(P.DEATH).astype(int).values
    assert np.all(ds + dd <= 1), "a real interval was labelled both stroke-first and death-first"
    n_both = int(((ds == 1) & (dd == 1)).sum())
    print(f"rows where both flags are set: {n_both} (must be 0)", flush=True)

    JOINT, MARG = {}, {}
    for held in panels:
        tr = (pp["country"].values != held)
        JOINT[held] = JointCrFit(X.loc[tr], ds[tr], dd[tr])
        MARG[held] = (IC.IcFit(X.loc[tr], ds[tr], "cloglog", "offset", 1.0),
                      IC.IcFit(X.loc[tr], dd[tr], "cloglog", "offset", 1.0))
        jf = JOINT[held]
        print(f"  {held}: joint conv={jf.converged} it={jf.n_iter} nll={jf.nll:.2f}", flush=True)

    rows, paired, ladder, audit = [], [], [], []
    diag = {}
    for rule in rules:
        base_frame, hcounts = I.horizon_frame(pp, horizon, rule)
        print(f"\n########## timing convention: {rule}", flush=True)
        for held in panels:
            tr = (pp["country"].values != held)
            step_L = round(float(np.median(pp.loc[tr, "exposure_years"])) * 4) / 4
            step = horizon / max(1, int(round(horizon / step_L)))
            hb = base_frame[base_frame["country"] == held].reset_index(drop=True)
            yb = hb["label"].astype(int).values
            wb = pd.to_numeric(hb["ipcw"], errors="coerce").fillna(1.0).to_numpy(dtype=float)
            pid = hb["pid"].values
            upid = np.unique(pid)
            jf = JOINT[held]
            pj = joint_cif(jf, hb, horizon, time_mode, step, fset)
            ms, md = MARG[held]
            p4 = P.compose_two(ms, md, hb, horizon, time_mode, fset, step, True)
            mj = P.metrics(yb, pj, wb, full=True)
            m4 = P.metrics(yb, p4, wb, full=True)
            rng = np.random.default_rng(SEED + 9000)
            cj = P.boot_ci(yb, pj, wb, pid, B, rng) if rule == rules[0] else {}
            rng2 = np.random.default_rng(SEED + 9001)
            c4 = P.boot_ci(yb, p4, wb, pid, B, rng2) if rule == rules[0] else {}
            for tag, mm, ci in (("joint_multinomial", mj, cj), ("shipped_product", m4, c4)):
                rows.append(dict(horizon_rule=rule, held=held, composition_arm=tag,
                                 strategy="frozen_all", frac=0.0, rep=0, step_years=step,
                                 local_persons=0, **mm,
                                 ci_auroc_lo=ci.get("auroc", [np.nan, np.nan])[0],
                                 ci_auroc_hi=ci.get("auroc", [np.nan, np.nan])[1],
                                 ci_po_lo=ci.get("pred_over_obs", [np.nan, np.nan])[0],
                                 ci_po_hi=ci.get("pred_over_obs", [np.nan, np.nan])[1],
                                 ci_nb_lo=ci.get("nb_at_05", [np.nan, np.nan])[0],
                                 ci_nb_hi=ci.get("nb_at_05", [np.nan, np.nan])[1]))
            # ladder for the joint arm: must be exactly flat, since the step terms are exclusive
            idx = np.random.default_rng(SEED + 11).choice(len(hb), size=min(3000, len(hb)),
                                                           replace=False)
            sub = hb.iloc[idx]
            vals = {n: float(joint_cif(jf, sub, horizon, time_mode, horizon / n, fset,
                                       advance=False).mean()) for n in (1, 2, 4, 8)}
            one = joint_cif(jf, sub, horizon, time_mode, horizon, fset, advance=False)
            ana = None
            for n in (1, 2, 4, 8):
                ladder.append(dict(horizon_rule=rule, held=held, composition_arm="joint_multinomial",
                                   n_steps=n, step_years=horizon / n, mean_risk=vals[n],
                                   ratio_over_1=vals[n] / max(vals[1], 1e-12)))
            diag[f"{rule}|{held}"] = {
                "joint_converged": bool(jf.converged), "joint_n_iter": int(jf.n_iter),
                "joint_mean_pred": round(mj["mean_pred"], 6),
                "shipped_mean_pred": round(m4["mean_pred"], 6),
                "rel_change_pct": round(100 * (mj["mean_pred"] / m4["mean_pred"] - 1), 3),
                "joint_pred_over_obs": round(mj["pred_over_obs"], 4),
                "shipped_pred_over_obs": round(m4["pred_over_obs"], 4),
                "ladder_ratio_8_over_1": round(vals[8] / max(vals[1], 1e-12), 12),
                "interval_prob_mass_max_dev": _mass_dev(jf, sub, step, fset, time_mode)}
            print(f"  {held}: joint P/O {mj['pred_over_obs']:.4f} [{diag[f'{rule}|{held}']['ladder_ratio_8_over_1']:.12f}"
                  f" ladder] vs shipped {m4['pred_over_obs']:.4f} "
                  f"({100*(mj['mean_pred']/m4['mean_pred']-1):+.2f}% predicted mass)", flush=True)

            for frac in fracs:
                gains, repl, rep_po = [], [], []
                for rep_i in range(reps):
                    rng3 = np.random.default_rng(SEED + 7000 + 1000 * rep_i + int(100 * frac))
                    take = max(2, int(round(len(upid) * frac)))
                    pick = rng3.choice(upid, size=take, replace=False)
                    locm, evm = np.isin(pid, pick), ~np.isin(pid, pick)
                    assert not set(pid[locm]) & set(pid[evm]), "local and eval share a person"
                    audit.append(dict(rule=rule, held=held, frac=frac, rep=rep_i,
                                      overlap=int(len(set(pid[locm]) & set(pid[evm])))))
                    if len(np.unique(yb[locm])) < 2 or len(np.unique(yb[evm])) < 2:
                        continue
                    a = IC.fit_offset_space(pj[locm], yb[locm], "logit")
                    lo = np.log(np.clip(pj[evm], 1e-12, 1 - 1e-12) /
                                (1 - np.clip(pj[evm], 1e-12, 1 - 1e-12)))
                    pr = np.clip(1.0 / (1.0 + np.exp(-(lo + a))), 0.0, 1.0)
                    for strat, pv, sh in (("frozen_sub", pj[evm], 0.0), ("offset_logit", pr, a)):
                        mm = P.metrics(yb[evm], pv, wb[evm])
                        rows.append(dict(horizon_rule=rule, held=held,
                                         composition_arm="joint_multinomial", strategy=strat,
                                         frac=frac, rep=rep_i, step_years=step,
                                         local_persons=int(locm.sum()), mean_repair_shift=sh, **mm,
                                         ci_auroc_lo=np.nan, ci_auroc_hi=np.nan, ci_po_lo=np.nan,
                                         ci_po_hi=np.nan, ci_nb_lo=np.nan, ci_nb_hi=np.nan))
                        if strat == "offset_logit":
                            mf = P.metrics(yb[evm], pj[evm], wb[evm])
                            gains.append(mm["nb_at_05"] - mf["nb_at_05"])
                            repl.append(mm["nb_at_05"]); rep_po.append(mm["pred_over_obs"])
                g, r, rp = np.asarray(gains), np.asarray(repl), np.asarray(rep_po)
                if not len(g):
                    continue
                paired.append(dict(horizon_rule=rule, held=held, frac=frac,
                                   composition_arm="joint_multinomial", n_complete_reps=int(len(g)),
                                   mean_gain_nb_at_05=float(g.mean()),
                                   sd_gain_nb_at_05=float(g.std(ddof=1)) if len(g) > 1 else 0.0,
                                   lo_gain_nb_at_05=float(np.percentile(g, 2.5)),
                                   hi_gain_nb_at_05=float(np.percentile(g, 97.5)),
                                   n_gain_positive=int((g > 0).sum()),
                                   n_repaired_nb_above_treat_none=int((r > 0).sum()),
                                   n_repaired_nb_tied_treat_none=int((r == 0).sum()),
                                   n_repaired_nb_below_treat_none=int((r < 0).sum()),
                                   max_nb_above_treat_none=float(r.max()),
                                   mean_repaired_pred_over_obs=float(rp.mean()),
                                   sd_repaired_pred_over_obs=float(rp.std(ddof=1))))

    R = pd.DataFrame(rows); R.to_csv(os.path.join(OUT, "incident_cr_joint.csv"), index=False)
    PA = pd.DataFrame(paired); PA.to_csv(os.path.join(OUT, "incident_cr_joint_paired.csv"), index=False)
    LA = pd.DataFrame(ladder); LA.to_csv(os.path.join(OUT, "incident_cr_joint_ladder.csv"), index=False)
    ov = pd.DataFrame(audit)
    coef = {}
    for held in panels:
        jf = JOINT[held]
        coef[held] = {"converged": bool(jf.converged), "n_iter": int(jf.n_iter),
                      "terms": jf.term_names,
                      "params": [round(float(v), 6) for v in jf.params]}
    report = {"generated_from": "incident_cr_joint.py", "horizon_years": horizon, "reps": reps,
              "boot": B, "rules": rules, "fractions": fracs,
              "selftest": {"gradient_relative_error": GRAD_REL,
                           "interval_probability_mass_deviation": MASS_DEV},
              "overlap_total": int(ov.overlap.sum()), "audit_rows": int(len(ov)),
              "coefficients": coef, "diagnostics": diag}
    with open(os.path.join(OUT, "incident_cr_joint_diagnostics.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=float)
    print(f"\nwrote {len(R)} rows, {len(PA)} paired, {len(LA)} ladder rows; "
          f"overlap={int(ov.overlap.sum())}", flush=True)


def flag(name, default):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default


if __name__ == "__main__":
    main()
