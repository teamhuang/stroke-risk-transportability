"""Round-10 P0-2: the partial-strict coverage refit re-run on the JOINT competing-risks primary model.

Round 7's `incident_strict_refit.py` refitted the coverage objection under partial-strict ascertainment but
only for the LOGISTIC arm; the manuscript's primary estimator is the joint multinomial competing-risks model.
The tenth-round reviewer's P0-2 is exactly that gap: the joint primary model's Mexico repair and four-country
calibration must be shown to survive the stricter coverage rule, or be labelled as untested secondary evidence.

This script closes it with no new machinery: it builds the SAME partial-strict frame the logistic refit used
(training rows = pooled intervals minus the non-interview `alive_nr`/`vital_status_unknown` tails, all 23,347
death intervals retained; evaluation frame = `t_ask` coverage on the untruncated person clock, asserted
person-for-person equal to the published strict arm 17,267 / 8,770 / 16,828 / 35,553), and then fits the JOINT
competing-risks model by leave-one-country-out on that frame, reporting per held panel the transported mean
prediction, the observed partial-strict incidence, the P/O, the four-year AUROC, and the frozen and 5%
local-intercept-repaired net benefit at the illustrative 5% threshold. Output:
data/processed/intl/incident/incident_cr_joint_strict_refit_cif_mid.csv

Usage: python incident_cr_joint_strict_refit.py [--horizon 4] [--reps 40] [--fractions 0.02,0.05,0.10,0.25,0.50]
"""
import os, sys, json, warnings
import numpy as np, pandas as pd
warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE)); sys.path.insert(0, HERE)
import run_loco_v2 as V2
import run_incident_loco as I
import incident_cr_primary as P
import incident_cr_joint_primary as JP
import incident_adaptation as A
from incident_ascertainment_sensitivity import frame_from_clock, ask_time

OUT = I.OUT
SEED = V2.SEED
NON_INTERVIEW_TAIL = ("alive_nr", "vital_status_unknown")
ORDER = ["CN", "KR", "MX", "US"]
logit, expit = A.logit if hasattr(A, "logit") else (lambda p: np.log(np.clip(p, 1e-9, 1 - 1e-9) / (1 - np.clip(p, 1e-9, 1 - 1e-9)))), (lambda z: 1.0 / (1.0 + np.exp(-z)))


def flag(name, default):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default


def main():
    horizon = float(flag("--horizon", "4"))
    reps = int(flag("--reps", "40"))
    fracs = [float(x) for x in flag("--fractions", "0.02,0.05,0.10,0.25,0.50").split(",")]
    rule, time_mode, fset = "cif_mid", "linear", "common"

    pp = pd.read_csv(os.path.join(OUT, "personperiod_pooled.csv"))
    pp["country"] = pp["cohort"].map(I.COH2CTRY); pp = pp[pp["country"].notna()].reset_index(drop=True)
    tail = pp[pp["end_status"].isin(NON_INTERVIEW_TAIL)]
    keep_rows = pp[~pp["end_status"].isin(NON_INTERVIEW_TAIL)].copy().reset_index(drop=True)
    deaths_kept = int(keep_rows["end_status"].isin(P.DEATH).sum())
    print(f"partial-strict training rows {len(keep_rows):,} (non-interview tails dropped {len(tail):,}); "
          f"death intervals retained {deaths_kept:,}", flush=True)

    pc = I.person_clock(pp)
    pc["t_ask"] = ask_time(pp).reindex(pd.MultiIndex.from_arrays([pc["cohort"], pc["pid"]])).to_numpy()
    frame, counts = frame_from_clock(pc, horizon, "t_ask")
    print(f"partial-strict eval frame {json.dumps(counts)}", flush=True)

    Xk = I.design(keep_rows, fset, time_mode)
    ds_k = keep_rows["event"].astype(int).values
    dd_k = keep_rows["end_status"].isin(P.DEATH).astype(int).values

    rows = []
    for held in ORDER:
        jf, hb, pj, yb, wb, pid, step, lp = JP.build_joint(
            keep_rows, Xk, ds_k, dd_k, frame, held, horizon, time_mode, fset)
        yb = np.asarray(yb, int); wb = np.asarray(wb, float); ph = np.asarray(pj, float); lp = np.asarray(lp, float)
        mp = float(np.sum(wb * ph) / np.sum(wb)); ob = float(np.sum(wb * yb) / np.sum(wb))
        from sklearn.metrics import roc_auc_score
        au = float(roc_auc_score(yb, ph, sample_weight=wb)) if len(np.unique(yb)) > 1 else np.nan
        nb_frozen = I.weighted_net_benefit(yb, ph, wb, 0.05)
        a_bar, gain_mean, beats = np.nan, np.nan, np.nan
        if len(fracs):
            upid = np.unique(pid); fr0 = fracs[min(1, len(fracs) - 1)] if len(fracs) > 1 else fracs[0]
            gains = []; offs = []
            for rep in range(reps):
                rng = np.random.default_rng(SEED + 9100 + 977 * rep + int(10000 * fr0))
                pick = rng.choice(upid, size=max(2, int(round(len(upid) * fr0))), replace=False)
                loc = np.isin(pid, pick); ev = ~loc
                if len(np.unique(yb[loc])) < 2 or len(np.unique(yb[ev])) < 2:
                    continue
                a = A.fit_offset(lp[loc], yb[loc])[0]
                if not np.isfinite(a):
                    continue
                offs.append(a)
                p_re = expit(lp[ev] + a)
                gains.append(I.weighted_net_benefit(yb[ev], p_re, wb[ev], 0.05)
                             - I.weighted_net_benefit(yb[ev], ph[ev], wb[ev], 0.05))
            a_bar = float(np.mean(offs)) if offs else np.nan
            gain_mean = float(np.mean(gains)) if gains else np.nan
            beats = float(np.mean(np.asarray(gains) > 0)) if gains else np.nan
        rows.append(dict(held=held, model="joint_cr", coverage="partial_strict", horizon_years=horizon,
                         n_eval=len(yb), events=int(np.sum(wb * yb)), mean_pred=mp, obs_prev=ob,
                         pred_over_obs=mp / ob if ob else np.nan, auroc_4y=au,
                         nb_frozen_at_05=nb_frozen, offset_frac=(fracs[1] if len(fracs) > 1 else fracs[0]),
                         offset_log_odds=a_bar, paired_nb_gain=gain_mean, beats_frozen_rate=beats))
    D = pd.DataFrame(rows)
    dest = os.path.join(OUT, "incident_cr_joint_strict_refit_cif_mid.csv")
    D.to_csv(dest, index=False)
    pd.set_option("display.width", 220)
    print("\n=== partial-strict refit, JOINT competing-risks primary model ===")
    print(D.to_string(index=False, float_format=lambda v: f"{v:.5f}"))
    print(f"\nwrote {dest}")
    for _, r in D.iterrows():
        print(f"  {r['held']}: permissive P/O was ~"
              f"{ {'MX':2.98,'CN':0.80,'KR':1.15,'US':0.90}[r['held']] } -> partial-strict "
              f"{r['pred_over_obs']:.2f}; frozen NB {r['nb_frozen_at_05']:+.5f}; "
              f"5%-repair paired gain {r['paired_nb_gain']:+.6f} (beats frozen {r['beats_frozen_rate']:.0%})")
    return D


if __name__ == "__main__":
    main()
