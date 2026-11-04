"""Round-8 clinical-value 3: is the complex cross-national model worth it over a simple clinical baseline?

The reviewer's strongest clinical suggestion: an editor will ask whether a ten-concept cross-national model
beats a simple, transparent, easily-rebuilt clinical risk model. This script fits a LOW-COMPLEXITY baseline -
age, sex, hypertension, diabetes and current smoking (a Framingham-style minimum), plus the exposure/time terms
the discrete-time hazard needs - as a joint competing-risks model under the SAME leave-one-country-out design,
the SAME four-year exclusive-first-stroke estimand, the SAME IPCW weights and the SAME evaluation persons as the
full primary model. Nothing about the estimand changes between the two arms, so the comparison is clean.

For each held country it reports AUROC, mean predicted 4-year risk, observed risk, predicted/observed and net
benefit at 5%, for the simple baseline against the full model, and the difference. If the simple model matches
the complex one on transportable discrimination but both fail equally on absolute-risk calibration, the paper's
thesis is strengthened: the failure is the estimand transport, not the algorithm's complexity.

Usage: python incident_cr_clinical_baseline.py [--horizon 4] [--rule cif_mid] [--frac 0.05] [--splits 120]
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
import incident_horizon_recalibration as HR
from sklearn.metrics import roc_auc_score

OUT = I.OUT
SEED = V2.SEED
ORDER = ["CN", "KR", "MX", "US"]
logit, expit = HR.logit, J.__dict__.get("sigmoid", None) or (lambda z: 1.0 / (1.0 + np.exp(-z)))
SIMPLE = ["age", "sex_2", "hypertension", "diabetes", "current_smoker"]


def flag(name, default):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default


def main():
    horizon = float(flag("--horizon", "4"))
    rule = flag("--rule", "cif_mid")
    frac = float(flag("--frac", "0.05"))
    splits = int(flag("--splits", "120"))
    time_mode, fset = "linear", "common"

    pp = pd.read_csv(os.path.join(OUT, "personperiod_pooled.csv"))
    pp["country"] = pp["cohort"].map(I.COH2CTRY); pp = pp[pp["country"].notna()].reset_index(drop=True)
    Xfull = I.design(pp, fset, time_mode)
    keep = SIMPLE + ["exposure_years", "t_since_entry_years"]
    Xsimple = Xfull[[c for c in keep if c in Xfull.columns]]
    ds_all = pp["event"].astype(int).values
    dd_all = pp["end_status"].isin(P.DEATH).astype(int).values
    base, hc = I.horizon_frame(pp, horizon, rule)

    rows = []
    for held in ORDER:
        tr = (pp["country"].values != held)
        # full primary model (transported)
        jf, hb, pj, yb, wb, pid, step, lp = JP.build_joint(pp, Xfull, ds_all, dd_all, base, held, horizon, time_mode, fset)
        # simple clinical baseline (same design, same estimand, same evaluation persons)
        js = J.JointCrFit(Xsimple.loc[tr], ds_all[tr], dd_all[tr])
        ps = J.joint_cif(js, hb, horizon, time_mode, step, fset)
        ps = np.asarray(ps, float)
        # 5% local-intercept repair for each arm, on the same disjoint adaptation draws
        a_full = JP.mean_offset(lp, yb.astype(int), wb, pid, frac, splits, SEED + 61000)
        lp_s = logit(np.clip(ps, 1e-12, 1 - 1e-12))
        a_s = JP.mean_offset(lp_s, yb.astype(int), wb, pid, frac, splits, SEED + 61000)
        mf = P.metrics(yb, pj, wb, full=True); ms = P.metrics(yb, ps, wb, full=True)
        mf_rep = P.metrics(yb, expit(lp + a_full), wb); ms_rep = P.metrics(yb, expit(lp_s + a_s), wb)
        rows.append(dict(held=held, horizon_rule=rule,
                         auroc_full=mf["auroc"], auroc_simple=ms["auroc"],
                         meanpred_full=mf["mean_pred"], meanpred_simple=ms["mean_pred"],
                         obs=mf["obs_prev"], po_full=mf["pred_over_obs"], po_simple=ms["pred_over_obs"],
                         nb5_full=mf["nb_at_05"], nb5_simple=ms["nb_at_05"],
                         nb5_full_repaired=mf_rep["nb_at_05"], nb5_simple_repaired=ms_rep["nb_at_05"],
                         offset_full=a_full, offset_simple=a_s,
                         auroc_diff_full_minus_simple=mf["auroc"] - ms["auroc"],
                         po_ratio_simple_over_full=(ms["pred_over_obs"] / mf["pred_over_obs"]
                                                    if mf["pred_over_obs"] else np.nan)))
    D = pd.DataFrame(rows)
    dest = os.path.join(OUT, "incident_cr_clinical_baseline_cif_mid.csv")
    D.to_csv(dest, index=False)
    pd.set_option("display.width", 240)
    print(D.to_string(index=False, float_format=lambda v: f"{v:.4f}"))
    print(f"\nwrote {dest}")
    for _, r in D.iterrows():
        print(f"  {r['held']}: AUROC full {r['auroc_full']:.3f} vs simple {r['auroc_simple']:.3f} "
              f"(diff {r['auroc_diff_full_minus_simple']:+.3f}); P/O full {r['po_full']:.2f} vs simple "
              f"{r['po_simple']:.2f}; NB@5% full {r['nb5_full']:+.5f} vs simple {r['nb5_simple']:+.5f}")
    return D


if __name__ == "__main__":
    main()
