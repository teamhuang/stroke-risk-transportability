"""Round-7 P0-3: does the four-year headline depend on the midpoint allocation of event times?

The joint competing-risks likelihood integrates the unobserved event time over each interview interval,
so the MODEL side (the per-person horizon CIF `pj`) never assumes a specific event date. But the primary
four-year EVALUATION compares that prediction against an observed label that IS dated - `cif_mid` places a
stroke at the midpoint of the interval in which it was first reported. The reviewer's P0-3 point is the
asymmetry: numerator interval-censored-consistent, denominator midpoint-assigned. The manuscript must not
describe the Mexico 2.98 as assumption-free, because the observed side does carry a within-interval
allocation assumption.

This script adds a genuinely midpoint-free evaluation of the OBSERVED four-year cumulative incidence and
places it beside the shipped midpoint rule and the interval-start / interval-end brackets:

  * observed interval-censored CIF - a two-parameter intercept-only joint competing-risks MLE fitted to the
    country's own intervals (constant hazards). This is a constant-hazard PARAMETRIC model - the simplest
    member of the published joint likelihood family - NOT a fully nonparametric estimator: it uses the fact
    that an event lies somewhere inside [t_start, t_end], never a midpoint, but still assumes time-invariant
    within-interval hazards (a flexible time-varying-hazard version: incident_cr_interval_flexhaz.py). The
    4-year first-stroke cumulative incidence has the closed form alpha_s*(1-exp(-(lam_s+lam_d)*H)) with
    alpha_s = lam_s/(lam_s+lam_d). A person-clustered bootstrap gives its interval.
  * observed ascertained incidence under cif_mid / cif_start / cif_end - the midpoint and its two bracketing
    dating rules (start = earliest possible, end = latest possible), IPCW-weighted.

The reported P/O is the transported model prediction `pj` (midpoint-free by construction) over each observed
estimate, so the difference between P/O_mid and P/O_IC isolates exactly how much the headline rides on the
event-time allocation. It is reported, not smoothed over.

Usage: python incident_cr_interval_eval.py [--horizon 4] [--boot 500]
"""
import os, sys, json, warnings
import numpy as np, pandas as pd
from scipy.optimize import minimize
warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE)); sys.path.insert(0, HERE)
import run_loco_v2 as V2
import run_incident_loco as I
import incident_cr_primary as P
import incident_cr_joint as J
import incident_cr_joint_primary as JP

OUT = I.OUT
SEED = V2.SEED
ORDER = ["CN", "KR", "MX", "US"]
HORIZON_DEFAULT = 4.0


def flag(name, default):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default


def ic_cif_hazard(L, ds, dd, H):
    """Intercept-only joint competing-risks MLE (constant hazards) -> 4-year CIF of first stroke.

    Negative log-likelihood is the published exclusive-outcome multinomial `_probs`, reduced to two free
    parameters (log lam_s, log lam_d). A stroke/death is credited to the interval it was reported in; a
    person event-free through their last interval contributes exp(-(lam_s+lam_d)*L) over that exposure. No
    midpoint is used anywhere.
    """
    L = np.clip(np.asarray(L, float), 1e-6, None)
    ds = np.asarray(ds, float); dd = np.asarray(dd, float)
    tot = ds + dd

    def nll(x):
        ls, ld = np.exp(np.clip(x[0], -20, 5)), np.exp(np.clip(x[1], -20, 5))
        tt = ls + ld
        E = np.exp(-tt * L)
        one_minus = -np.expm1(-tt * L)
        ps = ls / tt * one_minus; pd_ = ld / tt * one_minus
        ll = ds * np.log(np.clip(ps, 1e-15, 1)) + dd * np.log(np.clip(pd_, 1e-15, 1)) \
            + (1.0 - tot) * np.log(np.clip(E, 1e-15, 1))
        return -float(ll.sum())

    r = minimize(nll, [np.log(0.02), np.log(0.05)], method="L-BFGS-B",
                 bounds=[(-20, 5), (-20, 5)])
    ls, ld = float(np.exp(r.x[0])), float(np.exp(r.x[1]))
    tt = ls + ld
    alpha_s = ls / tt
    cif4 = alpha_s * (1.0 - np.exp(-tt * H))
    return cif4, alpha_s, ls, ld


def weighted_rate(mask_vals, weight, target_mask):
    s = float(np.sum(weight[target_mask]))
    return float(np.sum(weight[target_mask] * mask_vals[target_mask]) / s) if s > 0 else np.nan


def main():
    horizon = float(flag("--horizon", "4"))
    boot = int(flag("--boot", "500"))
    rule, time_mode, fset = "cif_mid", "linear", "common"

    pp = pd.read_csv(os.path.join(OUT, "personperiod_pooled.csv"))
    pp["country"] = pp["cohort"].map(I.COH2CTRY); pp = pp[pp["country"].notna()].reset_index(drop=True)
    X = I.design(pp, fset, time_mode)
    ds_all = pp["event"].astype(int).values
    dd_all = pp["end_status"].isin(P.DEATH).astype(int).values
    base_mid, hc_mid = I.horizon_frame(pp, horizon, "cif_mid")
    base_start, _ = I.horizon_frame(pp, horizon, "cif_start")
    base_end, _ = I.horizon_frame(pp, horizon, "cif_end")

    rows = []
    for held in ORDER:
        jf, hb, pj, yb, wb, pid, step, lp = JP.build_joint(
            pp, X, ds_all, dd_all, base_mid, held, horizon, time_mode, fset)
        mp = float(np.sum(wb * pj) / np.sum(wb))            # transported model mean prediction (midpoint-free)
        # observed ascertained incidence under the three dating rules (same persons differ by frame; each
        # rule has its own IPCW weights)
        def obs_rate(base_df):
            s = base_df[base_df["country"] == held]
            y = s["label"].astype(int).to_numpy(float)
            w = pd.to_numeric(s["ipcw"], errors="coerce").fillna(1.0).to_numpy(float)
            return float(np.sum(w * y) / np.sum(w))
        o_mid, o_start, o_end = obs_rate(base_mid), obs_rate(base_start), obs_rate(base_end)

        # observed interval-censored CIF from the country's OWN intervals (no transport, no midpoint)
        iv = pp[pp["country"] == held].reset_index(drop=True)
        L = iv["exposure_years"].to_numpy(float)
        ds_iv = iv["event"].astype(int).to_numpy(float)
        dd_iv = iv["end_status"].isin(P.DEATH).astype(int).to_numpy(float)
        cif_ic, alpha_s, ls, ld = ic_cif_hazard(L, ds_iv, dd_iv, horizon)
        # person-clustered bootstrap of the interval-censored observed CIF
        rng = np.random.default_rng(SEED + 909)
        pid_iv = iv["pid"].to_numpy(); codes = pd.factorize(pid_iv)[0]; upid = np.unique(codes)
        boots = []
        for _ in range(boot):
            take = rng.integers(0, len(upid), size=len(upid))
            rep = np.bincount(take, minlength=len(upid))[codes]
            sel_idx = np.repeat(np.arange(len(codes)), rep)
            if len(sel_idx) < 10 or ds_iv[sel_idx].sum() + dd_iv[sel_idx].sum() < 5:
                continue
            try:
                c4, _, _, _ = ic_cif_hazard(L[sel_idx], ds_iv[sel_idx], dd_iv[sel_idx], horizon)
                boots.append(c4)
            except Exception:
                pass
        lo = float(np.nanpercentile(boots, 2.5)) if len(boots) >= 20 else np.nan
        hi = float(np.nanpercentile(boots, 97.5)) if len(boots) >= 20 else np.nan

        rows.append(dict(held=held, model_mean_pred=mp,
                         obs_ascertained_mid=o_mid, obs_ascertained_start=o_start, obs_ascertained_end=o_end,
                         obs_interval_censored_IC=cif_ic, ic_lo=lo, ic_hi=hi,
                         ic_alpha_s=alpha_s, ic_lam_s=ls, ic_lam_d=ld,
                         PO_model_over_mid=mp / o_mid if o_mid else np.nan,
                         PO_model_over_IC=mp / cif_ic if cif_ic else np.nan,
                         PO_model_over_start=mp / o_start if o_start else np.nan,
                         PO_model_over_end=mp / o_end if o_end else np.nan,
                         n_intervals=int(len(iv)), n_persons=int(len(np.unique(pid_iv))),
                         horizon_years=horizon, n_boot_valid=len(boots)))
    D = pd.DataFrame(rows)
    dest = os.path.join(OUT, "incident_cr_interval_eval_cif_mid.csv")
    D.to_csv(dest, index=False)
    print(D.to_string(index=False, float_format=lambda v: f"{v:.5f}"))
    print(f"\nwrote {dest}")
    for _, r in D.iterrows():
        print(f"  {r['held']}: model {r['model_mean_pred']:.5f} | midpoint-obs {r['obs_ascertained_mid']:.5f} "
              f"(start {r['obs_ascertained_start']:.5f} / end {r['obs_ascertained_end']:.5f}) -> "
              f"P/O_mid {r['PO_model_over_mid']:.2f}; interval-censored-obs {r['obs_interval_censored_IC']:.5f} "
              f"[{r['ic_lo']:.5f},{r['ic_hi']:.5f}] -> P/O_IC {r['PO_model_over_IC']:.2f}")
    return D


if __name__ == "__main__":
    main()
