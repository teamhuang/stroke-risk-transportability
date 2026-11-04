"""Round-6 P0: the joint competing-risks model as the PRIMARY absolute-risk arm.

The fifth-round review established that the joint multinomial likelihood on the three mutually exclusive
interval outcomes (stroke-first / death-first / neither) is the statistically correct object, and that the
headline survives it (Mexico 2.98 under joint against 3.00 shipped). The sixth-round review then insisted
that "correct" and "primary" cannot be different things: if the joint model is the principled estimator,
every PRIMARY absolute-risk number - the four-year risk, the four-country calibration, the local-update
experiment, the decision curves, and the age-band heterogeneity - must be read off the joint arm, with the
separately-fitted cause-specific hazards (V4 / the shipped product) demoted to a labelled sensitivity arm.

This script produces the joint-arm version of every sub-analysis the manuscript presents as primary. It
reuses the EXACT joint machinery already published in `incident_cr_joint.py` (`JointCrFit`, `joint_cif`)
and the band / strategy helpers already published in `incident_subgroups.py`, `incident_age_recalibration.py`
and `incident_calibration_smooth.py`, so a joint number here is comparable by construction to its shipped
twin. The frozen prediction is the per-person joint horizon CIF `pj` on the `cif_mid` horizon frame - the
same `pj` that reproduces the Mexico 2.975 headline - and every table below is a grouping or thresholding
of that one quantity. Nothing here re-fits a marginal model; the shipped arm already lives in
`incident_cr_joint.csv` (`composition_arm="shipped_product"`) and in the original V4 outputs, which are
left byte-identical to serve as the sensitivity arm.

Outputs (data/processed/intl/incident/), all suffixed `_joint` so they never overwrite a V4 file:
  incident_cr_joint_subgroups.csv          held x age band: frozen P/O + AUROC(+CI) + 5%-repair P/O + NB
  incident_cr_joint_deciles.csv            held x predicted decile: observed vs predicted, frozen & repaired
  incident_cr_joint_calibration_smooth.csv + deliverables/figures/incident/..._joint.{png,pdf}
  incident_cr_joint_age_recalibration.csv / _summary.csv   five update strategies under the joint arm
  incident_cr_joint_dca.csv                held x threshold: net benefit frozen / repaired / all / none

Usage:
  python incident_cr_joint_primary.py [--horizon 4] [--rule cif_mid] [--frac 0.05] [--splits 120]
        [--boot 200] [--dboot 200] [--only subgroups,deciles,smooth,agerecal,dca]
"""
import os, sys, json, warnings
import numpy as np
import pandas as pd
warnings.filterwarnings("ignore")
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.dirname(HERE)); sys.path.insert(0, HERE)
import run_loco_v2 as V2
import run_incident_loco as I
import incident_cr_primary as P
import incident_cr_joint as J
import incident_subgroups as SUB
import incident_age_recalibration as AR
import incident_update_policy as UP
import incident_horizon_recalibration as HR
import incident_calibration_smooth as SC

OUT = I.OUT
SEED = V2.SEED
logit, expit = HR.logit, UP.sigmoid
FIGD = os.path.join(ROOT, "deliverables", "figures", "incident"); os.makedirs(FIGD, exist_ok=True)
CTRY = {"CN": "China", "KR": "Korea", "MX": "Mexico", "US": "United States"}
ORDER = ["CN", "KR", "MX", "US"]
plt.rcParams.update({"font.family": "sans-serif", "font.sans-serif": ["Arial", "DejaVu Sans"],
                     "pdf.fonttype": 42, "ps.fonttype": 42, "font.size": 7,
                     "axes.spines.top": False, "axes.spines.right": False,
                     "axes.grid": True, "grid.alpha": .25, "grid.linestyle": "--", "figure.dpi": 300})
OI = {"blue": "#0072B2", "verm": "#D55E00", "grey": "#999999", "black": "#222222",
      "green": "#009E73", "orange": "#E69F00"}


def flag(name, default):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default


def clustered_stat_ci(y, p, w, pid, stat, B, rng):
    """Person-clustered bootstrap CI of a scalar statistic (AUROC here). Draws whole persons."""
    codes = pd.factorize(pid)[0]
    uniq = np.unique(codes)
    vals = []
    for _ in range(B):
        take = rng.integers(0, len(uniq), size=len(uniq))
        rep = np.bincount(take, minlength=len(uniq))[codes]
        sel = rep > 0
        if len(np.unique(y[sel])) < 2 or sel.sum() < 5:
            continue
        ww = w[sel] * rep[sel]
        try:
            vals.append(float(stat(y[sel], p[sel], ww)))
        except Exception:
            pass
    a = np.asarray(vals, float)
    return (float(np.nanpercentile(a, 2.5)), float(np.nanpercentile(a, 97.5))) if len(a) >= 20 else (np.nan, np.nan)


def build_joint(pp, X, ds, dd, base, held, horizon, time_mode, fset):
    """Fit the joint model on the other three panels and return (jf, hb, pj, yb, wb, pid, step, a_bar)."""
    tr = (pp["country"].values != held)
    jf = J.JointCrFit(X.loc[tr], ds[tr], dd[tr])
    step_L = round(float(np.median(pp.loc[tr, "exposure_years"])) * 4) / 4
    step = horizon / max(1, int(round(horizon / step_L)))
    hb = base[base["country"] == held].reset_index(drop=True)
    pj = J.joint_cif(jf, hb, horizon, time_mode, step, fset)
    yb = hb["label"].astype(int).values
    wb = pd.to_numeric(hb["ipcw"], errors="coerce").fillna(1.0).to_numpy(float)
    pid = hb["pid"].values
    lp = logit(np.clip(np.asarray(pj, float), 1e-12, 1 - 1e-12))
    return jf, hb, np.asarray(pj, float), yb, wb, pid, step, lp


def mean_offset(lp, yb, wb, pid, frac, splits, seed_base, rng_frac=0.05):
    """The deployable 5% local intercept: mean shift over `splits` disjoint adaptation/eval draws."""
    upid = np.unique(pid); ah = []
    for s_i in range(splits):
        rng = np.random.default_rng(seed_base + 131 * s_i)
        take = max(2, int(round(len(upid) * frac)))
        pick = rng.choice(upid, size=take, replace=False)
        loc = np.isin(pid, pick); ev = ~loc
        if not set(pid[loc]) & set(pid[ev]) and len(np.unique(yb[loc])) >= 2:
            a, se, q = UP.fit_offset_clustered(lp[loc], yb[loc].astype(int), wb[loc], pid[loc])
            if np.isfinite(a):
                ah.append(a)
    return float(np.mean(ah)) if ah else 0.0


# ---------------------------------------------------------------- subgroups (age bands)
def do_subgroups(pp, X, ds, dd, base, horizon, rule, time_mode, fset, frac, splits, dboot):
    pc = I.person_clock(pp); pc["country"] = pc["cohort"].map(I.COH2CTRY)
    st = SUB.strata(pc, pp).set_index(["cohort", "pid"])
    rows = []
    for held in ORDER:
        jf, hb, pj, yb, wb, pid, step, lp = build_joint(pp, X, ds, dd, base, held, horizon, time_mode, fset)
        key = list(zip(hb["cohort"], hb["pid"]))
        hb = hb.assign(age_band=st.loc[key, "age_band"].values)
        a_bar = mean_offset(lp, yb, wb, pid, frac, splits, SEED + 61000)
        lp_rep = lp + a_bar
        p_rep = expit(lp_rep)
        rng = np.random.default_rng(SEED + 3333)
        bands = sorted({str(b) for b in hb["age_band"].values if str(b) != "unknown"}) + ["ALL"]
        for band in bands:
            m = np.ones(len(hb), bool) if band == "ALL" else (hb["age_band"].astype(str).values == band)
            if m.sum() < 20 or int(yb[m].sum()) < 5:
                continue
            mm = P.metrics(yb[m], pj[m], wb[m], full=True)
            lo, hi = clustered_stat_ci(yb[m].astype(int), pj[m], wb[m], pid[m],
                                       lambda y, p, w: __import__("sklearn.metrics", fromlist=["roc_auc_score"]).roc_auc_score(y, p, sample_weight=w),
                                       dboot, rng)
            po_off = float(np.mean(expit(lp[m] + a_bar)) / max(1e-12, mm["obs_prev"]))
            rows.append(dict(held=held, horizon_rule=rule, model="joint_cr", stratum="age_band",
                             level=band, step_years=step, realised_horizon_years=step * round(horizon / step),
                             offset_log_odds_shift=a_bar, n=int(m.sum()), events=int(yb[m].sum()),
                             events_weighted=float(np.sum(wb[m] * yb[m])),
                             prevalence_ipcw=mm["obs_prev"], mean_predicted_ipcw=mm["mean_pred"],
                             pred_over_obs=mm["pred_over_obs"], auroc=mm["auroc"], auroc_lo=lo, auroc_hi=hi,
                             cal_slope=mm.get("calib_slope", np.nan), cal_intercept=mm.get("calib_intercept", np.nan),
                             net_benefit_5pct=mm["nb_at_05"],
                             pred_over_obs_offset=po_off,
                             net_benefit_offset_5pct=P.metrics(yb[m], p_rep[m], wb[m])["nb_at_05"]))
    D = pd.DataFrame(rows)
    D.to_csv(os.path.join(OUT, "incident_cr_joint_subgroups.csv"), index=False)
    print(f"[joint subgroups] wrote {len(D)} rows", flush=True)
    return D


# ---------------------------------------------------------------- decile calibration
def do_deciles(pp, X, ds, dd, base, horizon, rule, time_mode, fset, frac, splits, dboot):
    rows = []
    for held in ORDER:
        jf, hb, pj, yb, wb, pid, step, lp = build_joint(pp, X, ds, dd, base, held, horizon, time_mode, fset)
        a_bar = mean_offset(lp, yb, wb, pid, frac, splits, SEED + 61000)
        p_rep = expit(lp + a_bar)
        dec = pd.qcut(pj, 10, labels=False, duplicates="drop")
        rng = np.random.default_rng(SEED + 4444)
        for d in sorted(pd.unique(dec[~pd.isna(dec)])):
            m = (dec == d).to_numpy() if hasattr(dec, "to_numpy") else (np.asarray(dec) == d)
            if m.sum() < 5:
                continue
            pr_f = float(np.sum(wb[m] * pj[m]) / np.sum(wb[m]))
            pr_r = float(np.sum(wb[m] * p_rep[m]) / np.sum(wb[m]))
            obs = float(np.sum(wb[m] * yb[m]) / np.sum(wb[m]))
            lo, hi = clustered_stat_ci(yb[m].astype(int), pj[m], wb[m], pid[m],
                                       lambda y, p, w: float(np.sum(w * y) / np.sum(w)), dboot, rng)
            rows.append(dict(held=held, horizon_rule=rule, arm="joint_cr", group=int(d) + 1,
                             n_panel_rows=int(m.sum()), frozen_pred=pr_f, repaired_pred=pr_r,
                             obs=obs, obs_lo=lo, obs_hi=hi))
    D = pd.DataFrame(rows)
    D.to_csv(os.path.join(OUT, "incident_cr_joint_deciles.csv"), index=False)
    print(f"[joint deciles] wrote {len(D)} rows", flush=True)
    return D


# ---------------------------------------------------------------- smooth calibration
def do_smooth(pp, X, ds, dd, base, horizon, rule, time_mode, fset, frac, splits, boot):
    grid_rows = []
    fig, axs = plt.subplots(2, 2, figsize=(2 * 5.5 / 2.54, 2 * 5.5 / 2.54))
    for ax, held in zip(axs.ravel(), ORDER):
        jf, hb, pj, yb, wb, pid, step, lp = build_joint(pp, X, ds, dd, base, held, horizon, time_mode, fset)
        ybf = yb.astype(float)
        a_bar = mean_offset(lp, yb, wb, pid, frac, splits, SEED + 61000)
        lp_rep = lp + a_bar
        lo, hi = np.quantile(lp, [0.005, 0.995]); grid_lp = np.linspace(lo, hi, 60)
        codes = pd.factorize(pid)[0]; upid = np.unique(pid)
        rng = np.random.default_rng(SEED + 7)
        for tag, lpx in (("frozen", lp), ("repaired", lp_rep)):
            curve = SC.smooth_curve(ybf, wb, lpx, grid_lp)
            bsamp = np.full((boot, len(grid_lp)), np.nan)
            for b in range(boot):
                take = rng.integers(0, len(upid), size=len(upid))
                wts = np.bincount(codes[take], minlength=len(upid))[codes]
                sel = wts > 0
                if ybf[sel].sum() < 5:
                    continue
                try:
                    bsamp[b] = SC.smooth_curve(ybf[sel], wb[sel] * wts[sel], lpx[sel], grid_lp)
                except Exception:
                    pass
            band_lo = np.nanpercentile(bsamp, 2.5, axis=0); band_hi = np.nanpercentile(bsamp, 97.5, axis=0)
            col = OI["blue"] if tag == "frozen" else OI["verm"]; xs = expit(grid_lp)
            ax.fill_between(xs, band_lo, band_hi, color=col, alpha=0.18, lw=0)
            ax.plot(xs, curve, color=col, lw=1.4, label=tag)
            for g, c, blo, bhi in zip(grid_lp, curve, band_lo, band_hi):
                grid_rows.append(dict(held=held, arm=tag, mean_offset=a_bar, predicted_risk=float(expit(g)),
                                      observed_smooth=float(c), obs_lo=float(blo), obs_hi=float(bhi)))
        ax.plot([0.002, 0.4], [0.002, 0.4], ls=":", color=OI["grey"], lw=1); ax.axvline(0.05, color=OI["black"], lw=0.6, alpha=0.5)
        ax.set_xlabel("predicted 4-year risk"); ax.set_ylabel("observed risk (smoothed)")
        ax.set_xscale("log"); ax.set_yscale("log"); ax.set_xlim(0.002, 0.4); ax.set_ylim(0.002, 0.4)
        ax.set_title(f"{CTRY[held]} (joint)", fontsize=7.5); ax.legend(fontsize=5, frameon=False, loc="upper left")
        if held == "MX":
            sub = [r for r in grid_rows if r["held"] == "MX" and r["arm"] == "frozen" and r["predicted_risk"] >= 0.10]
            tail = max(sub, key=lambda r: r["predicted_risk"]) if sub else None
            print(f"[joint smooth] MX a_bar={a_bar:+.3f} frozen tail at {tail['predicted_risk']:.3f} -> "
                  f"obs {tail['observed_smooth']:.3f} [{tail['obs_lo']:.3f},{tail['obs_hi']:.3f}]" if tail else "NA", flush=True)
    fig.tight_layout(rect=[0, 0.02, 1, 1])
    fig.savefig(os.path.join(FIGD, "incident_cr_joint_calibration_smooth.png"), dpi=300, bbox_inches="tight")
    fig.savefig(os.path.join(FIGD, "incident_cr_joint_calibration_smooth.pdf"), bbox_inches="tight")
    G = pd.DataFrame(grid_rows); G.to_csv(os.path.join(OUT, "incident_cr_joint_calibration_smooth.csv"), index=False)
    print(f"[joint smooth] wrote csv rows={len(G)}", flush=True)
    return G


# ---------------------------------------------------------------- age-aware recalibration
def do_agerecal(pp, X, ds, dd, base, horizon, rule, time_mode, fset, fracs, reps, min_events):
    pc = I.person_clock(pp); pc["country"] = pc["cohort"].map(I.COH2CTRY)
    st = SUB.strata(pc, pp).set_index(["cohort", "pid"])
    agec = pc[["cohort", "pid", "age"]].copy(); agec["age"] = pd.to_numeric(agec["age"], errors="coerce")
    agec = agec.set_index(["cohort", "pid"])
    STRATS = AR.STRATS
    det, summ = [], []
    for held in ORDER:
        jf, hb, pj, yb, wb, pid, step, lp = build_joint(pp, X, ds, dd, base, held, horizon, time_mode, fset)
        key = list(zip(hb["cohort"], hb["pid"]))
        hb = hb.assign(age_band=st.loc[key, "age_band"].values, age_base=agec.loc[key, "age"].values)
        bands = hb["age_band"].astype(str).values
        ubands = sorted({b for b in bands if b != "unknown"})
        age_c = (pd.to_numeric(hb["age_base"], errors="coerce").values
                 - np.nanmedian(pd.to_numeric(hb["age_base"], errors="coerce").values))
        upid = np.unique(pid)
        for frac in fracs:
            pooled = {s: {"nb": [], "pred": [], "obs": []} for s in STRATS}
            bandacc = {s: {b: {"p": [], "y": [], "nb": []} for b in ubands} for s in STRATS}
            for rep_i in range(reps):
                rng = np.random.default_rng(SEED + 42000 + 911 * rep_i)
                take = max(2, int(round(len(upid) * frac)))
                pick = rng.choice(upid, size=take, replace=False)
                loc = np.isin(pid, pick); ev = ~loc
                assert not set(pid[loc]) & set(pid[ev]), "adaptation and eval share a person"
                if len(np.unique(yb[loc])) < 2 or len(np.unique(yb[ev])) < 2:
                    continue
                a_o, _ = AR.offset_bisect(lp[loc], yb[loc], wb[loc])
                a0, a1 = AR.age_linear_fit(lp[loc], yb[loc], wb[loc], age_c[loc])
                band_map = {b: ((bands == b) & loc) for b in ubands}
                band_ab, tau2 = AR.band_intercepts(band_map, lp, yb, wb, a_o, min_events)
                lpe = lp[ev]; evb = bands[ev]
                lc = lpe.copy(); le = lpe.copy()
                for b in ubands:
                    m = evb == b
                    if m.sum():
                        lc[m] = lpe[m] + band_ab.get(b, (a_o, a_o))[0]
                        le[m] = lpe[m] + band_ab.get(b, (a_o, a_o))[1]
                for s, lps in (("A_frozen", lpe), ("B_overall", lpe + a_o),
                               ("D_age_linear", lpe + a0 + a1 * age_c[ev]),
                               ("C_band", lc), ("E_band_shrunk", le)):
                    p = expit(lps)
                    pooled[s]["nb"].append(AR.nb_at(yb[ev], p, wb[ev]))
                    pooled[s]["pred"].append(AR.wmean(p, wb[ev])); pooled[s]["obs"].append(AR.wmean(yb[ev], wb[ev]))
                    for b in ubands:
                        m = evb == b
                        if m.sum() >= 20 and int(np.sum(yb[ev][m])) >= 5:
                            bandacc[s][b]["p"].append(AR.wmean(p[m], wb[ev][m]))
                            bandacc[s][b]["y"].append(AR.wmean(yb[ev][m], wb[ev][m]))
                            bandacc[s][b]["nb"].append(AR.nb_at(yb[ev][m], p[m], wb[ev][m]))
            for s in STRATS:
                abslogs, nbands = [], 0
                for b in ubands:
                    pv = np.array(bandacc[s][b]["p"], float); yv = np.array(bandacc[s][b]["y"], float)
                    nv = np.array(bandacc[s][b]["nb"], float)
                    if not len(pv):
                        continue
                    po = float(np.mean(pv) / max(1e-12, np.mean(yv))); abslogs.append(abs(np.log(po))); nbands += 1
                    det.append(dict(held=held, frac=frac, strategy=s, band=b, band_pred_over_obs=po,
                                    band_log_po_abs=abs(np.log(po)), mean_band_nb_at_05=float(np.mean(nv)),
                                    sd_band_nb_at_05=float(np.std(nv)) if len(nv) > 1 else 0.0, n_reps=int(len(pv))))
                mp = float(np.mean(pooled[s]["pred"])); mo = float(np.mean(pooled[s]["obs"]))
                summ.append(dict(held=held, frac=frac, strategy=s, pooled_pred=mp, pooled_obs=mo,
                                 pooled_pred_over_obs=(mp / mo if mo else np.nan),
                                 mean_nb_at_05=float(np.mean(pooled[s]["nb"])),
                                 sd_nb_at_05=float(np.std(pooled[s]["nb"])) if len(pooled[s]["nb"]) > 1 else 0.0,
                                 mean_abs_band_log_po=float(np.mean(abslogs)) if abslogs else np.nan,
                                 max_abs_band_log_po=float(np.max(abslogs)) if abslogs else np.nan,
                                 n_bands_evaluated=nbands))
    D = pd.DataFrame(det); S = pd.DataFrame(summ)
    D.to_csv(os.path.join(OUT, "incident_cr_joint_age_recalibration.csv"), index=False)
    S.to_csv(os.path.join(OUT, "incident_cr_joint_age_recalibration_summary.csv"), index=False)
    print(f"[joint age-recal] wrote {len(D)} detail + {len(S)} summary rows", flush=True)
    return D, S


# ---------------------------------------------------------------- DCA curves
def do_dca(pp, X, ds, dd, base, horizon, rule, time_mode, fset, frac, splits):
    rows = []
    thresholds = [0.01, 0.02, 0.03, 0.05, 0.075, 0.10, 0.15, 0.20, 0.25]
    for held in ORDER:
        jf, hb, pj, yb, wb, pid, step, lp = build_joint(pp, X, ds, dd, base, held, horizon, time_mode, fset)
        a_bar = mean_offset(lp, yb, wb, pid, frac, splits, SEED + 61000)
        p_rep = expit(lp + a_bar)
        for t in thresholds:
            rows.append(dict(held=held, horizon_rule=rule, threshold=t,
                             nb_frozen=I.weighted_net_benefit(yb, pj, wb, t),
                             nb_repaired=I.weighted_net_benefit(yb, p_rep, wb, t),
                             nb_all=I.weighted_net_benefit(yb, np.ones(len(yb)), wb, t),
                             nb_none=0.0))
    D = pd.DataFrame(rows); D.to_csv(os.path.join(OUT, "incident_cr_joint_dca.csv"), index=False)
    print(f"[joint dca] wrote {len(D)} rows", flush=True)
    return D


def main():
    horizon = float(flag("--horizon", "4")); rule = flag("--rule", "cif_mid")
    frac = float(flag("--frac", "0.05")); splits = int(flag("--splits", "120"))
    boot = int(flag("--boot", "200")); dboot = int(flag("--dboot", "200"))
    reps = int(flag("--reps", "120"))
    time_mode, fset = "linear", "common"
    only = set((flag("--only", "subgroups,deciles,smooth,agerecal,dca")).split(","))
    fracs = [0.02, 0.05, 0.10, 0.25, 0.50]

    pp = pd.read_csv(os.path.join(OUT, "personperiod_pooled.csv"))
    pp["country"] = pp["cohort"].map(I.COH2CTRY); pp = pp[pp["country"].notna()].reset_index(drop=True)
    X = I.design(pp, fset, time_mode)
    ds = pp["event"].astype(int).values
    dd = pp["end_status"].isin(P.DEATH).astype(int).values
    base, hcount = I.horizon_frame(pp, horizon, rule)
    print(f"JOINT-PRIMARY | horizon={horizon} rule={rule} frac={frac} splits={splits} boot={boot} "
          f"dboot={dboot} reps={reps} only={sorted(only)}", flush=True)
    if "subgroups" in only: do_subgroups(pp, X, ds, dd, base, horizon, rule, time_mode, fset, frac, splits, dboot)
    if "deciles" in only: do_deciles(pp, X, ds, dd, base, horizon, rule, time_mode, fset, frac, splits, dboot)
    if "smooth" in only: do_smooth(pp, X, ds, dd, base, horizon, rule, time_mode, fset, frac, splits, boot)
    if "agerecal" in only: do_agerecal(pp, X, ds, dd, base, horizon, rule, time_mode, fset, fracs, reps, 5)
    if "dca" in only: do_dca(pp, X, ds, dd, base, horizon, rule, time_mode, fset, frac, splits)
    print("JOINT-PRIMARY done.", flush=True)


if __name__ == "__main__":
    main()
