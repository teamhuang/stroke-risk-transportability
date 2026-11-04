"""Round-8 P0-3: a two-dimensional sensitivity to unreported pre-fatal stroke.

Round 7's `incident_cr_unreported_stroke_sim.py` swept ONE knob (the fraction pi of a panel's died-first pool
that was really an unreported fatal stroke) and reported only two corners - uniform ascertainment (every panel
misses the same pi, which cancels in the ratio) and one differential corner (a fully-ascertained source against
a target that misses pi). The eighth-round reviewer asked for the full two-parameter surface: let the source
panel's under-report fraction pi_source and the target panel's pi_target vary INDEPENDENTLY, then read off what
happens to the clinical P/O, and in particular under which (pi_source, pi_target) the Mexican over-prediction
weakens or disappears.

Mechanism, entirely analytic (nothing fitted on synthetic labels; pi are hypothetical sensitivity parameters,
never an adjustment applied to the shipped headline):

  * The model is trained on the SOURCE ascertained rate and transported to the target, so it predicts the
    target's ASCERTAINED risk `mp`.
  * If the source under-reports pi_source of its died-first pool, its clinical rate is
        q_clin_s = q_asc_s + pi_source * d_df_s,
    and a model that was calibrated to the source ascertained level, reinterpreted as a CLINICAL predictor,
    carries the same ascertained->clinical inflation factor
        kappa(pi_source) = q_clin_s / q_asc_s = 1 + pi_source * d_df_s / q_asc_s.
  * The target's clinical observed rate is q_clin_t = q_asc_t + pi_target * d_df_t.
  * Clinical P/O on the target = mp * kappa(pi_source) / q_clin_t(pi_target).

Uniform ascertainment is the diagonal pi_source = pi_target (cancels); maximal differential is the corner
pi_source = 0 (perfectly-ascertained source) with pi_target large (target hides many pre-fatal strokes), which
is the scenario that could most turn a real over-prediction into a reporting artefact. We report, per panel,
the whole grid and the crossing points where P/O reaches 2.0 and 1.0.

Output: data/processed/intl/incident/incident_cr_unreported_stroke_2d.csv (long) plus the same to stdout.

Usage: python incident_cr_unreported_stroke_2d.py [--horizon 4] [--grid 0,0.1,0.2,0.3,0.4,0.5]
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
SEED = V2.SEED
ORDER = ["CN", "KR", "MX", "US"]


def flag(name, default):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default


def asc_and_df(base_df, held_mask):
    s = base_df[held_mask]
    y = s["label"].astype(int).to_numpy(float)
    ddf = (s["horizon_status"].to_numpy() == "died_first_within_horizon").astype(float)
    w = pd.to_numeric(s["ipcw"], errors="coerce").fillna(1.0).to_numpy(float)
    sw = float(np.sum(w))
    return (float(np.sum(w * y) / sw) if sw else np.nan,
            float(np.sum(w * ddf) / sw) if sw else np.nan)


def main():
    horizon = float(flag("--horizon", "4"))
    grid = [float(x) for x in flag("--grid", "0,0.1,0.2,0.3,0.4,0.5").split(",")]
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
        q_asc_t, d_df_t = asc_and_df(base, (base["country"] == held).to_numpy())
        q_asc_s, d_df_s = asc_and_df(base, (base["country"] != held).to_numpy())
        po_reported = mp / q_asc_t if q_asc_t else np.nan
        for pi_s in grid:
            kappa = (q_asc_s + pi_s * d_df_s) / q_asc_s if q_asc_s else np.nan
            for pi_t in grid:
                q_clin_t = q_asc_t + pi_t * d_df_t
                po = mp * kappa / q_clin_t if q_clin_t else np.nan
                rows.append(dict(held=held, pi_source=pi_s, pi_target=pi_t,
                                 model_mean_pred=mp, q_asc_target=q_asc_t, d_df_target=d_df_t,
                                 q_asc_source=q_asc_s, d_df_source=d_df_s,
                                 kappa_source=kappa, q_clinical_target=q_clin_t,
                                 PO_reported_ascertained=po_reported, PO_clinical=po))
    D = pd.DataFrame(rows)
    dest = os.path.join(OUT, "incident_cr_unreported_stroke_2d.csv")
    D.to_csv(dest, index=False)

    print(f"wrote {dest} rows={len(D)}")
    for held in ORDER:
        sub = D[D["held"] == held]
        po_rep = float(sub["PO_reported_ascertained"].iloc[0])
        # pivot PO_clinical: rows = pi_source, cols = pi_target
        piv = sub.pivot(index="pi_source", columns="pi_target", values="PO_clinical")
        # most-differential corner that could erase the over-prediction: pi_source=0 (best source), pi_target=max
        worst_source0 = float(piv.loc[0.0].min())                       # best source, target hides a lot
        diag = float(np.mean([piv.loc[v, v] for v in grid]))             # uniform, near-reported
        # for an over-predicted panel: smallest pi_target (with pi_source=0) that brings clinical P/O <= 2.0 and <=1.0
        def crossing(level):
            for pt in grid:
                if piv.loc[0.0, pt] <= level:
                    return pt
            return np.nan
        x2 = crossing(2.0); x1 = crossing(1.0)
        print(f"\n=== {held}: reported ascertained P/O = {po_rep:.3f} ===")
        print(piv.to_string(float_format=lambda v: f"{v:.3f}"))
        print(f"  uniform-diagonal mean P/O {diag:.3f} | best-source worst-target P/O {worst_source0:.3f} "
              f"| pi_target reaching P/O<=2.0 (pi_src=0): {x2 if not np.isnan(x2) else 'never in grid'} "
              f"| <=1.0: {x1 if not np.isnan(x1) else 'never in grid'}")
    return D


if __name__ == "__main__":
    main()
