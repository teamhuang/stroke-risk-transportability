"""Round-9: is the estimand-matched midpoint-free result an artefact of the UNIFORM-within-interval assumption?

Round 8's Table 19 relaxed the hard midpoint by allocating a straddling event in proportion to the fraction of
its reporting interval lying before the horizon, clip((H - t_start)/(t_end - t_start), 0, 1). The ninth-round
reviewer correctly noted that that is a UNIFORM-within-interval allocation assumption, not the general
interval-censored conditional event-time probability, and recommended re-running the check with the conditional
distribution implied by the fitted joint model to confirm the "only Mexico moves materially" conclusion is not a
uniform-allocation artefact.

We therefore compute a third observed-risk estimator alongside midpoint and uniform, on the identical cif_mid
evaluable frame and IPCW weights:

  * midpoint:                y = 1[t_stroke_mid <= H]                                   (hard date)
  * uniform allocation:      y = clip((H - t_start)/(t_end - t_start), 0, 1)             (this paper's round-8 check)
  * model-based conditional: for a stroke reported in (t_start, t_end] with the person event-free at t_start and
    fitted total hazard lam_tot = lam_s + lam_d at that row, the conditional probability the true first-stroke time
    precedes H given the event lies in the interval is the truncated-exponential
         y = (1 - exp(-lam_tot (H - t_start))) / (1 - exp(-lam_tot (t_end - t_start))),
    = 1 if t_end <= H, = 0 if t_start >= H, and -> uniform as lam_tot -> 0.  Because within-interval survival is
    decreasing, this pulls event mass EARLIER than uniform (y_model >= y_uniform for a straddling interval), which
    is exactly the sensitivity the reviewer asked us to check.

lam_s, lam_d are the transported joint model's fitted per-row cause-specific hazards (jf.rates on the horizon
frame), so this is 'the conditional event-time distribution derived from the joint model', not a new fit. Output
data/processed/intl/incident/incident_cr_alloc_variants_cif_mid.csv, one row per held country, with each observed
risk, its P/O against the shipped transported mean prediction, and the ratio to the midpoint value.

Usage: python incident_cr_alloc_variants.py [--horizon 4]
"""
import os, sys, warnings
import numpy as np, pandas as pd
warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE)); sys.path.insert(0, HERE)
import run_loco_v2 as V2
import run_incident_loco as I
import incident_cr_primary as P
import incident_cr_joint_primary as JP

OUT = I.OUT
ORDER = ["CN", "KR", "MX", "US"]


def flag(name, default):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default


def main():
    H = float(flag("--horizon", "4"))
    rule, time_mode, fset = "cif_mid", "linear", "common"
    pp = pd.read_csv(os.path.join(OUT, "personperiod_pooled.csv"))
    pp["country"] = pp["cohort"].map(I.COH2CTRY); pp = pp[pp["country"].notna()].reset_index(drop=True)
    X = I.design(pp, fset, time_mode)
    ds = pp["event"].astype(int).values; dd = pp["end_status"].isin(P.DEATH).astype(int).values
    base, hc = I.horizon_frame(pp, H, rule)

    rows = []
    for held in ORDER:
        jf, hb, pj, yb, wb, pid, step, lp = JP.build_joint(pp, X, ds, dd, base, held, H, time_mode, fset)
        hb = hb.reset_index(drop=True); wb = np.asarray(wb, float); yb = np.asarray(yb, float)
        ph = np.asarray(pj, float)
        a = pd.to_numeric(hb["t_stroke_start"], errors="coerce").to_numpy(float)   # reporting-interval start
        b = pd.to_numeric(hb["t_stroke_end"], errors="coerce").to_numpy(float)     # reporting-interval end
        width = b - a
        # fitted per-row cause-specific hazards, evaluated when the person entered the event interval
        # (non-stroke rows have weight 0 regardless, so a 0 fallback there is harmless)
        teval = np.nan_to_num(a, nan=0.0)
        Dm = I.design(hb.assign(t_since_entry_years=teval, exposure_years=np.full(len(hb), step)),
                      fset, time_mode).reindex(columns=jf.cols)
        ls, ld = jf.rates(Dm)
        lam_tot = np.clip(np.asarray(ls, float) + np.asarray(ld, float), 0.0, None)
        # uniform allocation
        y_unif = np.clip((H - a) / np.where(width > 0, width, np.nan), 0.0, 1.0)
        y_unif[~np.isfinite(a)] = 0.0; y_unif[~np.isfinite(y_unif)] = 0.0
        # model-based conditional allocation (truncated exponential in the total hazard, survival from t_start)
        num = -np.expm1(-lam_tot * np.clip(H - a, 0, None))          # 1 - exp(-lam*(H-a)), >=0
        den = -np.expm1(-lam_tot * np.clip(width, 0, None))          # 1 - exp(-lam*(b-a))
        y_model = np.where(den > 1e-12, num / np.where(den > 1e-12, den, 1.0), y_unif)
        y_model = np.where(b <= H, 1.0, np.where(a >= H, 0.0, y_model))
        y_model[~np.isfinite(a)] = 0.0; y_model[~np.isfinite(y_model)] = 0.0
        sw = float(np.sum(wb))
        obs_mid = float(np.sum(wb * yb) / sw)
        obs_unif = float(np.sum(wb * y_unif) / sw)
        obs_model = float(np.sum(wb * y_model) / sw)
        mp = float(np.sum(wb * ph) / sw)
        rows.append(dict(held=held, model_mean_pred=mp,
                         obs_mid=obs_mid, obs_uniform=obs_unif, obs_model=obs_model,
                         ratio_unif_over_mid=obs_unif / obs_mid if obs_mid else np.nan,
                         ratio_model_over_mid=obs_model / obs_mid if obs_mid else np.nan,
                         ratio_model_over_unif=obs_model / obs_unif if obs_unif else np.nan,
                         PO_mid=mp / obs_mid if obs_mid else np.nan,
                         PO_uniform=mp / obs_unif if obs_unif else np.nan,
                         PO_model=mp / obs_model if obs_model else np.nan))
    D = pd.DataFrame(rows)
    dest = os.path.join(OUT, "incident_cr_alloc_variants_cif_mid.csv")
    D.to_csv(dest, index=False)
    pd.set_option("display.width", 200)
    print(D.to_string(index=False, float_format=lambda v: f"{v:.5f}"))
    print(f"\nwrote {dest}")
    print("\n=== does 'only Mexico moves materially' survive dropping the uniform assumption? ===")
    for _, r in D.iterrows():
        print(f"  {r['held']}: P/O  mid {r['PO_mid']:.2f} -> uniform {r['PO_uniform']:.2f}"
              f" -> model-based {r['PO_model']:.2f}  (model/uniform ratio {r['ratio_model_over_unif']:.3f})")
    return D


if __name__ == "__main__":
    main()
