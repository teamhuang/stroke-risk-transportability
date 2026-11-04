"""P1-1: calibration curves with uncertainty, on the reported estimand.

The manuscript's headline calibration statistic is one number per panel - mean predicted risk over mean
observed - and a pooled ratio of 1.0 is compatible with over-prediction at low risk and
under-prediction at high risk. This script draws what that ratio cannot substitute for: predicted
four-year risk by decile against observed risk in the same deciles, per held-out panel, with
person-clustered bootstrap intervals, for the frozen transferred model and for the model after the
one-parameter local intercept repair.

Design decisions, stated because each one is contestable:

 * Groups are defined ONCE by the FROZEN model's predicted risk and kept fixed while bootstrapping and
   while repairing. Re-forming deciles inside each resample would let the x-axis move, turning a
   calibration plot into a smoothing exercise.
 * Observed risk is the IPCW-weighted proportion of a first reported stroke within the horizon under
   the reported estimand (`cif_mid`) - the same quantity every other four-year number in this paper
   uses - with a competing death counted as a determined non-event.
 * The observed column is shared by the frozen and repaired curves: a repair moves the *prediction*,
   not the outcome. What is plotted for the repair is therefore the repaired predicted level in the
   same decile, with a band across adaptation/evaluation splits. Those are two different uncertainties
   and they get two different columns: `obs_lo/obs_hi` is who is in the panel, `rep_lo/rep_hi` is
   which local sample was drawn.
 * Repair rows exclude the adaptation persons, so the plotted repaired levels are out-of-sample
   (asserted per split, the same invariant as `intl/incident_update_policy.py`).

Usage
  python incident_calibration_curves.py [--horizon 4] [--rule cif_mid] [--groups 10]
                                        [--boot 500] [--frac 0.05] [--splits 200]
"""
import os, sys, json, numpy as np, pandas as pd, warnings
warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)
import run_loco_v2 as V2
import run_incident_loco as I
import incident_horizon_recalibration as HR
import incident_update_policy as UP

OUT = I.OUT
SEED = V2.SEED


def flag(name, default):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default


def wmean(x, w):
    s = float(np.sum(w))
    return float(np.sum(np.asarray(x, float) * w) / s) if s > 0 else np.nan


def clustered_boot(y, w, cluster_codes, B, seed):
    """Person-clustered bootstrap of a weighted proportion: draw whole people, expand each draw to
    their rows, recompute. Returns the draws (nan where a resample has no weight)."""
    k = int(cluster_codes.max()) + 1
    rng = np.random.default_rng(seed)
    out = np.full(B, np.nan)
    for b in range(B):
        counts = rng.multinomial(k, np.full(k, 1.0 / k))
        if not counts.any():
            continue
        rep = np.repeat(counts, np.bincount(cluster_codes, minlength=k))
        sw = float(np.sum(w * rep))
        if sw > 0:
            out[b] = float(np.sum(w * rep * y) / sw)
    return out


def main():
    horizon = float(flag("--horizon", "4"))
    rule = flag("--rule", "cif_mid")
    ng = int(flag("--groups", "10"))
    B = int(flag("--boot", "500"))
    frac = float(flag("--frac", "0.05"))
    splits = int(flag("--splits", "200"))

    pp = pd.read_csv(os.path.join(OUT, "personperiod_pooled.csv"))
    pp["country"] = pp["cohort"].map(I.COH2CTRY)
    pp = pp[pp["country"].notna()].reset_index(drop=True)
    X = I.design(pp, "common", "linear")
    y = pp["event"].astype(int).values
    base, hcount = I.horizon_frame(pp, horizon, rule)
    print(f"calibration curves | rule={rule} groups={ng} boot={B} frac={frac} splits={splits}",
          flush=True)

    rows = []
    for held in sorted(set(pp["country"])):
        tr = (pp["country"].values != held)
        step_L = round(float(np.median(pp.loc[tr, "exposure_years"])) * 4) / 4
        hb = base[base["country"] == held].reset_index(drop=True)
        yb = hb["label"].astype(int).values.astype(float)
        wb = pd.to_numeric(hb["ipcw"], errors="coerce").fillna(1.0).to_numpy(float)
        pid = hb["pid"].values
        frozen = I.Frozen(X.loc[tr], y[tr], "logistic")
        ph, realised = I.horizon_risk(frozen, hb, horizon, "linear", "common", step=step_L)
        groups = pd.qcut(ph, ng, labels=False, duplicates="drop").astype(int)
        nga = int(groups.max() + 1)
        _, pcode = np.unique(pid, return_inverse=True)
        lp = HR.logit(ph)
        upid = np.unique(pid)
        print(f"\n=== {held}: n={len(hb)} deciles={nga} "
              f"pred/obs={wmean(ph, wb) / wmean(yb, wb):.3f}", flush=True)

        # ---- repaired predicted level, per decile, across adaptation/evaluation splits
        acc = {g: [] for g in range(nga)}
        ahat, n_eval_by_group = [], {g: 0 for g in range(nga)}
        for s_i in range(splits):
            rng = np.random.default_rng(SEED + 51000 + 131 * s_i)
            take = max(2, int(round(len(upid) * frac)))
            pick = rng.choice(upid, size=take, replace=False)
            loc = np.isin(pid, pick); ev = ~loc
            assert not set(pid[loc]) & set(pid[ev]), "adaptation and eval share a person"
            if len(np.unique(yb[loc])) < 2:
                continue
            a, se, q = UP.fit_offset_clustered(lp[loc], yb[loc].astype(int), wb[loc], pid[loc])
            if not np.isfinite(a):
                continue
            ahat.append(a)
            pr = 1.0 / (1.0 + np.exp(-(lp + a)))
            for g in range(nga):
                m = (groups == g) & ev
                if m.sum():
                    acc[g].append(wmean(pr[m], wb[m]))
                    n_eval_by_group[g] += 1
        a_bar = float(np.mean(ahat)) if ahat else 0.0
        pr_rep = 1.0 / (1.0 + np.exp(-(lp + a_bar)))

        for g in range(nga):
            m = groups == g
            obs_b = clustered_boot(yb[m], wb[m], pcode[m], B, 777000 + 17 * int(g) +
                                   abs(hash(held)) % 1000)
            v = np.array(acc[g], dtype=float)
            rows.append(dict(held=held, group=int(g), n_panel_rows=int(m.sum()),
                             n_persons=int(len(np.unique(pid[m]))),
                             frozen_pred=wmean(ph[m], wb[m]), repaired_pred=wmean(pr_rep[m], wb[m]),
                             obs=wmean(yb[m], wb[m]),
                             obs_lo=float(np.nanpercentile(obs_b, 2.5)),
                             obs_hi=float(np.nanpercentile(obs_b, 97.5)),
                             obs_boot_draws=int(np.isfinite(obs_b).sum()),
                             rep_lo=float(np.percentile(v, 2.5)) if v.size >= 10 else np.nan,
                             rep_hi=float(np.percentile(v, 97.5)) if v.size >= 10 else np.nan,
                             rep_splits=int(v.size),
                             mean_offset_logodds=a_bar,
                             offset_sd_across_splits=float(np.std(ahat)) if ahat else np.nan))
        print(f"    offset at {frac:.0%} local data: {a_bar:+.3f} "
              f"(SD across {len(ahat)} splits {np.std(ahat):.3f}); top decile frozen "
              f"{rows[-1]['frozen_pred']:.4f} -> repaired {rows[-1]['repaired_pred']:.4f}, "
              f"observed {rows[-1]['obs']:.4f}", flush=True)

    out = pd.DataFrame(rows)
    dest = os.path.join(OUT, f"incident_calibration_curves_{rule}.csv")
    out.to_csv(dest, index=False)
    doc = {"horizon_rule": rule, "groups_requested": ng, "bootstrap_B": B,
           "local_fraction": frac, "splits": splits, "mean_offset_per_panel":
               {r["held"]: round(r["mean_offset_logodds"], 4) for r in rows if r["group"] == 0},
           "group_definition": ("deciles of the FROZEN model's predicted four-year risk, fixed across "
                                "bootstrap resamples and across the repair"),
           "observed_estimator": ("IPCW-weighted proportion of a first reported stroke within the "
                                  "horizon, competing death a determined non-event"),
           "interval_kinds": {
               "obs_lo_obs_hi": "person-clustered bootstrap of the observed decile risk (panel noise)",
               "rep_lo_rep_hi": ("2.5/97.5 percentile of the repaired decile prediction across "
                                 "adaptation/evaluation splits (local-sample noise, NOT a population "
                                 "interval for the repaired model)")},
           "horizon_person_accounting": hcount, "n_rows": int(len(out))}
    rep = os.path.join(ROOT, "results", "reports")
    os.makedirs(rep, exist_ok=True)
    with open(os.path.join(rep, f"incident_calibration_curves_{rule}.json"), "w",
              encoding="utf-8") as fh:
        json.dump(doc, fh, indent=1)
    print(f"\nwrote {dest} rows={len(out)}")
    return out


if __name__ == "__main__":
    main()
