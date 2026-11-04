"""Round-7 P0-2: how much of the four-year P/O could be unreported pre-fatal stroke rather than risk miscalibration?

The joint model's "death-first" label is what the SURVEY observes: a person who reports no stroke at the
last interview and is later recorded dead. If a fatal stroke occurred before that death but was never
reported at an interview - which a two-yearly survey cannot rule out - the true clinical sequence was
stroke-then-death, coded here as death-first (a non-event). The model is therefore estimating the
SURVEY-ASCERTAINED first-stroke estimand, not the complete clinical event process. The manuscript's
headline (Mexico ~2.98-fold over-prediction) compares a transported ascertained prediction to an
ascertained observation, so it is internally consistent for that estimand. The question this simulation
answers, with a synthetic ground-truth misclassification (labelled as such):

  (1) Is the reported P/O robust to UNIFORM under-ascertainment (the same fraction of silent fatal strokes
      missed in every panel)? If it cancels, the headline is not a measurement artifact.
  (2) How far would the CLINICAL P/O move under DIFFERENTIAL ascertainment (the target panel misses a
      larger share of fatal pre-strokes than the source it was trained on)? This is the scenario that
      would make part of the over-prediction an artefact of who reports strokes, not of who has them.

It uses only real quantities already in the horizon frame - the ascertained 4-year observed incidence
q_asc, the IPCW-weighted died-first-within-horizon fraction d_df (the pool where an unreported fatal stroke
could hide), and the transported model prediction `pj` - and posits a fraction pi of the decedent pool as
unreported strokes. Nothing is fitted on the synthetic labels; pi is swept and its effect on P/O read off
analytically. Ground truth here is synthetic and is only a sensitivity, never an adjustment applied to the
reported headline.

Usage: python incident_cr_unreported_stroke_sim.py [--horizon 4] [--pis 0,0.05,0.10,0.20,0.30,0.50]
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
    """IPCW-weighted ascertained observed incidence and died-first-within-horizon fraction on a person set."""
    s = base_df[held_mask]
    y = s["label"].astype(int).to_numpy(float)
    ddf = (s["horizon_status"].to_numpy() == "died_first_within_horizon").astype(float)
    w = pd.to_numeric(s["ipcw"], errors="coerce").fillna(1.0).to_numpy(float)
    sw = float(np.sum(w))
    return (float(np.sum(w * y) / sw) if sw else np.nan,
            float(np.sum(w * ddf) / sw) if sw else np.nan,
            int(len(s)))


def main():
    horizon = float(flag("--horizon", "4"))
    pis = [float(x) for x in flag("--pis", "0,0.05,0.10,0.20,0.30,0.50").split(",")]
    rule, time_mode, fset = "cif_mid", "linear", "common"

    pp = pd.read_csv(os.path.join(OUT, "personperiod_pooled.csv"))
    pp["country"] = pp["cohort"].map(I.COH2CTRY); pp = pp[pp["country"].notna()].reset_index(drop=True)
    X = I.design(pp, fset, time_mode)
    ds_all = pp["event"].astype(int).values
    dd_all = pp["end_status"].isin(P.DEATH).astype(int).values
    base, hc = I.horizon_frame(pp, horizon, rule)

    detail = []
    for held in ORDER:
        jf, hb, pj, yb, wb, pid, step, lp = JP.build_joint(
            pp, X, ds_all, dd_all, base, held, horizon, time_mode, fset)
        mp = float(np.sum(wb * pj) / np.sum(wb))
        q_asc_t, d_df_t, n_t = asc_and_df(base, (base["country"] == held).to_numpy())
        q_asc_s, d_df_s, n_s = asc_and_df(base, (base["country"] != held).to_numpy())
        for pi_t in pis:
            # target clinical incidence under pi_t of its decedent pool being unreported strokes
            q_clin_t = q_asc_t + pi_t * d_df_t
            # uniform scenario: same pi on the source -> source prediction-correction factor
            q_clin_s_u = q_asc_s + pi_t * d_df_s
            kappa_u = q_clin_s_u / q_asc_s if q_asc_s else np.nan          # source hides pi_t too
            po_uniform = mp * kappa_u / q_clin_t if q_clin_t else np.nan    # numerator & denominator both corrected
            # differential scenario: source is a GOOD ascertainment panel (pi_src = 0), target is worse (pi_t)
            po_diff_src0 = mp / q_clin_t if q_clin_t else np.nan            # model trained on fully-ascertained source
            detail.append(dict(held=held, pi_target=pi_t, model_mean_pred=mp,
                               q_ascertained_target=q_asc_t, d_deathefirst_target=d_df_t,
                               q_ascertained_source=q_asc_s, d_deathefirst_source=d_df_s,
                               PO_reported_ascertained=mp / q_asc_t if q_asc_t else np.nan,
                               q_clinical_target=q_clin_t,
                               PO_clinical_uniform=po_uniform,
                               PO_clinical_differential_src0=po_diff_src0,
                               n_target=n_t, n_source=n_s))
    D = pd.DataFrame(detail)
    dest = os.path.join(OUT, "incident_cr_unreported_stroke_sim.csv")
    D.to_csv(dest, index=False)
    print(D[D["held"] == "MX"].to_string(index=False, float_format=lambda v: f"{v:.5f}"))
    print(f"\nwrote {dest} rows={len(D)}")
    print("\n=== uniform vs differential unreported-fatal-stroke scenarios (clinical P/O) ===")
    for held in ORDER:
        sub = D[D["held"] == held]
        base_po = float(sub["PO_reported_ascertained"].iloc[0])
        print(f"  {held}: reported (ascertained) P/O = {base_po:.3f}")
        for _, r in sub.iterrows():
            print(f"     pi={r['pi_target']:.2f}  uniform {r['PO_clinical_uniform']:.3f}"
                  f"   differential(src0) {r['PO_clinical_differential_src0']:.3f}")
    return D


if __name__ == "__main__":
    main()
