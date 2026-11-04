"""Round-8 P0-1 / Finding C: is the interval-censored observed risk a constant-hazard artefact?

Round-7's midpoint-free observed risk (`incident_cr_interval_eval.py`) was a two-parameter CONSTANT-hazard
joint competing-risks MLE. The eighth-round reviewer correctly noted that this is a parametric model, not a
nonparametric one, and that the striking new result it produced - China under-predicted to P/O 0.43 while
Mexico's over-prediction softened to 2.10 - could in principle be an artefact of forcing hazards to be
time-invariant. This script refits the observed-risk estimator with FLEXIBLE time-varying baseline hazards and
asks whether the country conclusions survive.

It reuses the published, gradient-self-tested joint machinery (`incident_cr_joint.JointCrFit`) rather than a
bespoke likelihood, so convergence is the same tested path as the primary model. Time variation is introduced
as a covariate on time-since-entry:

  * piecewise-constant: hazards constant within K bands of time-since-entry (K = 3 by default: [0,2), [2,4), [4,+)).
  * linear: log hazard linear in time-since-entry (a smooth decay or rise).

For each shape the marginal baseline-to-4-year cumulative incidence of first stroke is obtained by evaluating
the fitted hazards on a fine time grid and integrating the exclusive competing-risks CIF

    CIF_s(4) = int_0^4 lambda_s(u) exp(-(Lambda_s(u) + Lambda_d(u))) du,

which makes no midpoint assignment. The transported frozen prediction `pj` (unchanged primary model) gives
P/O_frozen = mean(pj) / CIF_s(4); the 5% local-intercept repair is scored the same way. A person-clustered
bootstrap gives intervals. If China's 0.43 moves back toward the midpoint 0.80 under flexible hazards the
constant-hazard assumption was driving it; if it stays near 0.43 the under-prediction is a genuine feature.

Usage: python incident_cr_interval_flexhaz.py [--horizon 4] [--bands 3] [--boot 300] [--dt 0.05]
"""
import os, sys, warnings
import numpy as np, pandas as pd
warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE)); sys.path.insert(0, HERE)
import run_loco_v2 as V2
import run_incident_loco as I
import incident_cr_primary as P
import incident_cr_joint as J
import incident_cr_joint_primary as JP
import incident_update_policy as UP
import incident_horizon_recalibration as HR

OUT = I.OUT
SEED = V2.SEED
ORDER = ["CN", "KR", "MX", "US"]
logit, expit = HR.logit, UP.sigmoid
EXPOSURE = "exposure_years"


def flag(name, default):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default


def time_design(tstart, L, kind, edges):
    """Build the interval frame for JointCrFit with time-since-entry encoded as covariates."""
    df = pd.DataFrame({EXPOSURE: np.asarray(L, float)})
    if kind == "linear":
        df["t_since_entry_years"] = np.asarray(tstart, float)
    else:  # piecewise-constant: band index of t_start
        idx = np.clip(np.searchsorted(edges, np.asarray(tstart, float), side="right") - 1, 0, len(edges) - 2)
        df["band"] = idx.astype(float)
    return df


def hazards_on_grid(jf, kind, edges, grid, dt):
    """Evaluate the fitted hazards (lambda_s, lambda_d) at each grid time."""
    g = pd.DataFrame({EXPOSURE: np.full(len(grid), dt)})
    if kind == "linear":
        g["t_since_entry_years"] = grid
    else:
        idx = np.clip(np.searchsorted(edges, grid, side="right") - 1, 0, len(edges) - 2)
        g["band"] = idx.astype(float)
    ls, ld = jf.rates(g)
    return np.asarray(ls, float), np.asarray(ld, float)


def cif_from_hazards(lam_s, lam_d, dt, horizon):
    """Marginal baseline-to-horizon CIF of first stroke under time-varying hazards (grid integration)."""
    lam_tot = np.clip(lam_s + lam_d, 1e-12, None)
    Lam = np.concatenate([[0.0], np.cumsum(lam_tot) * dt])
    surv_start = np.exp(-Lam[:-1])
    A = np.concatenate([[0.0], np.cumsum(lam_s * surv_start) * dt])
    ih = int(round(horizon / dt))
    return float(A[min(ih, len(A) - 1)])


def fit_country(iv, kind, edges, dt):
    """Fit JointCrFit on the country's own intervals with time-varying hazards; return CIF_s(4)."""
    tstart = iv["t_since_entry_years"].to_numpy(float)
    L = iv["exposure_years"].to_numpy(float)
    ds = iv["event"].astype(int).to_numpy(float)
    dd = iv["end_status"].isin(P.DEATH).astype(int).to_numpy(float)
    Xd = time_design(tstart, L, kind, edges)
    jf = J.JointCrFit(Xd, ds, dd, l2=1e-4)
    grid = np.arange(0, edges[-1] + dt, dt)
    lam_s, lam_d = hazards_on_grid(jf, kind, edges, grid, dt)
    return cif_from_hazards(lam_s, lam_d, dt, 4.0), jf


def main():
    horizon = float(flag("--horizon", "4"))
    K_bands = int(flag("--bands", "3"))
    boot = int(flag("--boot", "300"))
    dt = float(flag("--dt", "0.05"))
    rule, time_mode, fset = "cif_mid", "linear", "common"

    pp = pd.read_csv(os.path.join(OUT, "personperiod_pooled.csv"))
    pp["country"] = pp["cohort"].map(I.COH2CTRY); pp = pp[pp["country"].notna()].reset_index(drop=True)
    X = I.design(pp, fset, time_mode)
    ds_all = pp["event"].astype(int).values
    dd_all = pp["end_status"].isin(P.DEATH).astype(int).values
    base, hc = I.horizon_frame(pp, horizon, rule)

    rows = []
    for held in ORDER:
        jf, hb, pj, yb, wb, pid, step, lp = JP.build_joint(
            pp, X, ds_all, dd_all, base, held, horizon, time_mode, fset)
        mp = float(np.sum(wb * pj) / np.sum(wb))
        o_mid = float(np.sum(wb * yb) / np.sum(wb))
        a_bar = JP.mean_offset(lp, yb.astype(int), wb, pid, 0.05, 120, SEED + 61000)
        p_rep = expit(lp + a_bar); mp_rep = float(np.sum(wb * p_rep) / np.sum(wb))

        iv = pp[pp["country"] == held].reset_index(drop=True)
        tmax = float(max(np.nanmax(iv["t_since_entry_years"] + iv["exposure_years"]), horizon))
        edges = np.linspace(0, tmax, K_bands + 1)

        cif_pw, _ = fit_country(iv, "pw", edges, dt)
        cif_ln, _ = fit_country(iv, "linear", edges, dt)

        # person-clustered bootstrap of the two flexible observed risks
        rng = np.random.default_rng(SEED + 1234)
        pid_iv = iv["pid"].to_numpy(); codes = pd.factorize(pid_iv)[0]; upid = np.unique(codes)
        b_pw, b_ln = [], []
        for _ in range(boot):
            take = rng.integers(0, len(upid), size=len(upid))
            rep = np.bincount(take, minlength=len(upid))[codes]
            sel = np.repeat(np.arange(len(codes)), rep)
            sub = iv.iloc[sel]
            if sub["event"].sum() + sub["end_status"].isin(P.DEATH).sum() < 5:
                continue
            try:
                c1, _ = fit_country(sub, "pw", edges, dt); b_pw.append(c1)
                c2, _ = fit_country(sub, "linear", edges, dt); b_ln.append(c2)
            except Exception:
                pass
        lo_pw = float(np.nanpercentile(b_pw, 2.5)) if len(b_pw) >= 20 else np.nan
        hi_pw = float(np.nanpercentile(b_pw, 97.5)) if len(b_pw) >= 20 else np.nan
        lo_ln = float(np.nanpercentile(b_ln, 2.5)) if len(b_ln) >= 20 else np.nan
        hi_ln = float(np.nanpercentile(b_ln, 97.5)) if len(b_ln) >= 20 else np.nan

        rows.append(dict(held=held, model_mean_pred=mp, obs_midpoint=o_mid,
                         cif_pw=cif_pw, cif_pw_lo=lo_pw, cif_pw_hi=hi_pw,
                         cif_linear=cif_ln, cif_linear_lo=lo_ln, cif_linear_hi=hi_ln,
                         PO_frozen_over_mid=mp / o_mid if o_mid else np.nan,
                         PO_frozen_over_pw=mp / cif_pw if cif_pw else np.nan,
                         PO_frozen_over_linear=mp / cif_ln if cif_ln else np.nan,
                         PO_repaired_over_pw=mp_rep / cif_pw if cif_pw else np.nan,
                         PO_repaired_over_linear=mp_rep / cif_ln if cif_ln else np.nan,
                         n_boot_pw=len(b_pw), n_boot_linear=len(b_ln),
                         horizon_years=horizon, bands=K_bands, dt=dt))
    D = pd.DataFrame(rows)
    dest = os.path.join(OUT, "incident_cr_interval_flexhaz_cif_mid.csv")
    D.to_csv(dest, index=False)
    pd.set_option("display.width", 240)
    print(D.to_string(index=False, float_format=lambda v: f"{v:.5f}"))
    print(f"\nwrote {dest}")
    for _, r in D.iterrows():
        print(f"  {r['held']}: frozen P/O  midpoint {r['PO_frozen_over_mid']:.2f} -> "
              f"piecewise-const {r['PO_frozen_over_pw']:.2f} [{r['cif_pw_lo']:.5f},{r['cif_pw_hi']:.5f}] -> "
              f"linear {r['PO_frozen_over_linear']:.2f} [{r['cif_linear_lo']:.5f},{r['cif_linear_hi']:.5f}]")
    return D


if __name__ == "__main__":
    main()
