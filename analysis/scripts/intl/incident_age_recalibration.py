"""P1 (the reviewer's "more publishable than a new model"): does AGE-AWARE recalibration fix the
subgroup sign errors that a single population-wide intercept manufactures?

The manuscript already shows (Table 12) that a one-intercept repair, tuned to make the PANEL-average
calibration right, can flip a within-panel age band from over- to under-prediction: Mexico's 20-59 band
moves from P/O 2.38 to 0.73 once a single national intercept is fitted, and the US 80+ band from 0.79 to
0.68. The published text then declares age-aware recalibration "outside this paper's design." This
script closes that gap instead of disclaiming it.

Design (analysis unit = person; horizon frame is one row per person):
  For each held-out panel the frozen logistic discrete-time hazard is fitted on the OTHER three panels
  and scored on the held-out panel exactly as Table 12 / incident_subgroups.py do (I.Frozen +
  I.horizon_risk, `cif_mid`, `common` features). Persons are split into a LOCAL adaptation sample and a
  DISJOINT independent evaluation sample (asserted per replicate), and five recalibration strategies are
  fitted on the local sample ONLY, then applied to the independent evaluation rows:

    A frozen           no update
    B overall          one intercept a (current practice)            -> logit(p)+a
    C band-intercept   one intercept per age band, unshrunk          -> logit(p)+a_band
    D age-linear       intercept + linear in (centred) baseline age  -> logit(p)+a0+a1*age_c
    E band-shrunk      per-band intercept shrunk toward the overall  -> empirical-Bayes (James-Stein)
                       by  w_b = tau2/(tau2+se_b^2),  tau2 = max(0, Var(a_b) - mean(se_b^2))

  E is the direct answer to the reviewer's caution: do NOT fit several band intercepts on a handful of
  local events; shrink them. C is the naive version kept on purpose so the instability cost is visible.

On the independent evaluation set we report, pooled and per age band, at EACH local fraction: calibration
in the large (mean predicted / observed), net benefit at a 5% threshold, a SIGN-ERROR measure - the mean
and max over bands of |log(P/O)| - and the across-replicate standard deviation of band net benefit
(instability). The question the reviewer wants answered is answered as a comparison: which strategy
reduces the age-band sign error on data no parameter was fitted to, and how much extra instability it
buys, especially at 2-5% local data.

Nothing here re-estimates the cause-specific hazards; it recalibrates the published classifier-arm
prediction, so it is directly comparable to Table 12 and the selective-update arm.

Usage
  python incident_age_recalibration.py [--horizon 4] [--reps 120]
        [--fractions 0.02,0.05,0.10,0.25,0.50] [--rule cif_mid] [--min-band-events 5]
Outputs (data/processed/intl/incident/)
  incident_age_recalibration.csv               held x frac x strategy x band  (band 'ALL' = pooled)
  incident_age_recalibration_summary.csv       held x frac x strategy  (pooled + sign-error + stability)
"""
import os, sys, json, warnings
import numpy as np
import pandas as pd
warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)
import run_loco_v2 as V2
import run_incident_loco as I
import incident_update_policy as UP
import incident_horizon_recalibration as HR
import incident_subgroups as SUB
import statsmodels.api as sm

OUT = I.OUT
SEED = V2.SEED
logit, expit = HR.logit, UP.sigmoid
STRATS = ("A_frozen", "B_overall", "C_band", "D_age_linear", "E_band_shrunk")


def flag(name, default):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default


def wmean(x, w):
    s = float(np.sum(w))
    return float(np.sum(np.asarray(x, float) * w) / s) if s > 0 else np.nan


def offset_bisect(lp, y, w):
    """The single log-odds shift making weighted mean prediction equal weighted prevalence, plus its
    Fisher-information SE (1/sqrt(sum w p(1-p)))."""
    s = float(np.sum(w))
    q = float(np.sum(w * np.asarray(y, float)) / s) if s > 0 else np.nan
    if not (0.0 < q < 1.0):
        return 0.0, np.nan
    lo, hi = -12.0, 12.0
    for _ in range(80):
        mid = (lo + hi) / 2.0
        if float(np.sum(w * expit(lp + mid)) / s) < q:
            lo = mid
        else:
            hi = mid
    a = (lo + hi) / 2.0
    p = expit(lp + a)
    info = float(np.sum(w * p * (1.0 - p)))
    se = 1.0 / np.sqrt(info) if info > 0 else np.nan
    return a, se


def age_linear_fit(lp, y, w, age_c):
    """logit(p_new) = lp + a0 + a1*age_c, weighted logistic with lp as a fixed offset."""
    if len(np.unique(y)) < 2 or np.sum(w) <= 0:
        return 0.0, 0.0
    Xd = np.column_stack([np.ones(len(age_c)), np.asarray(age_c, float)])
    try:
        res = sm.GLM(np.asarray(y, float), Xd, family=sm.families.Binomial(),
                     offset=np.asarray(lp, float),
                     freq_weights=np.asarray(w, float)).fit(maxiter=100)
        return float(res.params[0]), float(res.params[1])
    except Exception:
        return 0.0, 0.0


def band_intercepts(band_local_map, lp_loc, y_loc, w_loc, a_overall, min_events):
    """Per-band offsets on the local sample (C, unshrunk) plus an empirical-Bayes shrink toward the
    overall intercept (E). Bands with < min_events local events fall back to the overall intercept for
    both C and E (no information -> no separate shift), and are excluded from the tau^2 estimate."""
    raw = {}
    for b, m in band_local_map.items():
        if m.sum() < 1:
            continue
        if int(np.sum(y_loc[m])) < min_events or len(np.unique(y_loc[m])) < 2:
            raw[b] = (a_overall, np.nan)
        else:
            a, se = offset_bisect(lp_loc[m], y_loc[m], w_loc[m])
            raw[b] = (a, se)
    a_fit = np.array([v[0] for v in raw.values() if np.isfinite(v[1])])
    se_fit = np.array([v[1] for v in raw.values() if np.isfinite(v[1])])
    tau2 = (max(0.0, float(np.var(a_fit, ddof=1)) - float(np.mean(se_fit ** 2)))
            if len(a_fit) >= 2 else 0.0)
    out = {}
    for b, (a_b, se_b) in raw.items():
        if not np.isfinite(se_b):
            out[b] = (a_b, a_overall)
        else:
            wgt = tau2 / (tau2 + se_b ** 2) if tau2 > 0 else 0.0
            out[b] = (a_b, wgt * a_b + (1.0 - wgt) * a_overall)
    return out, tau2


def nb_at(y, p, w, thr=0.05):
    return float(I.weighted_net_benefit(np.asarray(y).astype(int), np.asarray(p, float),
                                        np.asarray(w, float), thr))


def main():
    horizon = float(flag("--horizon", "4"))
    reps = int(flag("--reps", "120"))
    fracs = [float(x) for x in flag("--fractions", "0.02,0.05,0.10,0.25,0.50").split(",")]
    rule = flag("--rule", "cif_mid")
    min_events = int(flag("--min-band-events", "5"))

    pp = pd.read_csv(os.path.join(OUT, "personperiod_pooled.csv"))
    pp["country"] = pp["cohort"].map(I.COH2CTRY)
    pp = pp[pp["country"].notna()].reset_index(drop=True)
    X = I.design(pp, "common", "linear")
    y = pp["event"].astype(int).values
    base, hcount = I.horizon_frame(pp, horizon, rule)
    pc = I.person_clock(pp)
    pc["country"] = pc["cohort"].map(I.COH2CTRY)
    st = SUB.strata(pc, pp).set_index(["cohort", "pid"])
    agec = pc[["cohort", "pid", "age"]].copy()
    agec["age"] = pd.to_numeric(agec["age"], errors="coerce")
    agec = agec.set_index(["cohort", "pid"])
    print(f"age recalibration | horizon={horizon} rule={rule} reps={reps} fracs={fracs} "
          f"min_band_events={min_events}", flush=True)

    det, summ = [], []
    for held in sorted(set(pp["country"])):
        tr = (pp["country"].values != held)
        step_L = round(float(np.median(pp.loc[tr, "exposure_years"])) * 4) / 4
        hb = base[base["country"] == held].reset_index(drop=True)
        key = list(zip(hb["cohort"], hb["pid"]))
        hb["age_band"] = st.loc[key, "age_band"].values
        hb["age"] = agec.loc[key, "age"].values
        yb = hb["label"].astype(int).values
        wb = pd.to_numeric(hb["ipcw"], errors="coerce").fillna(1.0).to_numpy(float)
        pid = hb["pid"].values
        upid = np.unique(pid)
        fr_model = I.Frozen(X.loc[tr], y[tr], "logistic")
        ph, realised = I.horizon_risk(fr_model, hb, horizon, "linear", "common", step=step_L)
        lp = logit(np.asarray(ph, float))
        age_c = (pd.to_numeric(hb["age"], errors="coerce")
                 - np.nanmedian(pd.to_numeric(hb["age"], errors="coerce").values)).values
        bands = hb["age_band"].values
        ubands = sorted({str(b) for b in bands if str(b) != "unknown"})
        print(f"\n=== {held}: n={len(hb)} persons={len(upid)} events={int(yb.sum())} "
              f"bands={ubands} realised={realised:.2f}y", flush=True)

        # accum[(frac)][strategy] -> pooled lists + per-band lists
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
                a_o, _ = offset_bisect(lp[loc], yb[loc], wb[loc])
                a0, a1 = age_linear_fit(lp[loc], yb[loc], wb[loc], age_c[loc])
                band_map = {b: ((bands == b) & loc) for b in ubands}
                band_ab, tau2 = band_intercepts(band_map, lp, yb, wb, a_o, min_events)
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
                    pooled[s]["nb"].append(nb_at(yb[ev], p, wb[ev]))
                    pooled[s]["pred"].append(wmean(p, wb[ev]))
                    pooled[s]["obs"].append(wmean(yb[ev], wb[ev]))
                    for b in ubands:
                        m = evb == b
                        if m.sum() >= 20 and int(np.sum(yb[ev][m])) >= 5:
                            bandacc[s][b]["p"].append(wmean(p[m], wb[ev][m]))
                            bandacc[s][b]["y"].append(wmean(yb[ev][m], wb[ev][m]))
                            bandacc[s][b]["nb"].append(nb_at(yb[ev][m], p[m], wb[ev][m]))
            # ---- per-band detail rows (this held x frac)
            for s in STRATS:
                abslogs, nbands = [], 0
                for b in ubands:
                    pv = np.array(bandacc[s][b]["p"], float); yv = np.array(bandacc[s][b]["y"], float)
                    nv = np.array(bandacc[s][b]["nb"], float)
                    if not len(pv):
                        continue
                    po = float(np.mean(pv) / max(1e-12, np.mean(yv)))
                    abslogs.append(abs(np.log(po))); nbands += 1
                    det.append(dict(held=held, frac=frac, strategy=s, band=b,
                                    band_pred_over_obs=po, band_log_po_abs=abs(np.log(po)),
                                    mean_band_nb_at_05=float(np.mean(nv)),
                                    sd_band_nb_at_05=float(np.std(nv)) if len(nv) > 1 else 0.0,
                                    n_reps=int(len(pv))))
                # pooled ('ALL') row
                mp = float(np.mean(pooled[s]["pred"])); mo = float(np.mean(pooled[s]["obs"]))
                det.append(dict(held=held, frac=frac, strategy=s, band="ALL",
                                band_pred_over_obs=(mp / mo if mo else np.nan),
                                band_log_po_abs=abs(np.log(mp / mo)) if mo else np.nan,
                                mean_band_nb_at_05=float(np.mean(pooled[s]["nb"])),
                                sd_band_nb_at_05=float(np.std(pooled[s]["nb"])) if len(pooled[s]["nb"]) > 1 else 0.0,
                                n_reps=int(len(pooled[s]["nb"]))))
                summ.append(dict(held=held, frac=frac, strategy=s,
                                 pooled_pred=mp, pooled_obs=mo,
                                 pooled_pred_over_obs=(mp / mo if mo else np.nan),
                                 mean_nb_at_05=float(np.mean(pooled[s]["nb"])),
                                 sd_nb_at_05=float(np.std(pooled[s]["nb"])) if len(pooled[s]["nb"]) > 1 else 0.0,
                                 mean_abs_band_log_po=float(np.mean(abslogs)) if abslogs else np.nan,
                                 max_abs_band_log_po=float(np.max(abslogs)) if abslogs else np.nan,
                                 n_bands_evaluated=nbands))
            print(f"  frac={frac:4.0%}  " + "  ".join(
                f"{s[0]}:NB={np.mean(pooled[s]['nb']):+.5f},maxbP/Olog="
                f"{summ[-(len(STRATS)-i)]['max_abs_band_log_po']:.2f}"
                for i, s in enumerate(STRATS)), flush=True)

    D = pd.DataFrame(det); S = pd.DataFrame(summ)
    D.to_csv(os.path.join(OUT, "incident_age_recalibration.csv"), index=False)
    S.to_csv(os.path.join(OUT, "incident_age_recalibration_summary.csv"), index=False)
    doc = {"horizon": horizon, "horizon_rule": rule, "reps": reps, "fractions": fracs,
           "min_band_events": min_events, "analysis_unit": "person (horizon frame, one row/person)",
           "prediction_arm": ("frozen logistic discrete-time hazard, cif_mid, common features "
                              "(comparable to Table 12 / incident_subgroups)"),
           "strategies": {"A_frozen": "no update",
                          "B_overall": "one population-wide intercept (current practice)",
                          "C_band": "one intercept per age band, unshrunk",
                          "D_age_linear": "intercept + linear centred baseline age",
                          "E_band_shrunk": "per-band intercept shrunk to overall (empirical Bayes)"},
           "sign_error_measure": ("mean and max over age bands of |log(band mean predicted / observed)| "
                                  "on persons independent of the adaptation sample"),
           "band_cell_rule": "band evaluated on eval rows with n>=20 and >=5 events",
           "horizon_person_accounting": hcount, "n_detail_rows": int(len(D))}
    rep = os.path.join(ROOT, "results", "reports")
    os.makedirs(rep, exist_ok=True)
    with open(os.path.join(rep, "incident_age_recalibration.json"), "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=1, default=float)
    print("\n" + S.sort_values(["held", "frac", "strategy"]).to_string(index=False))
    print(f"\nwrote incident_age_recalibration.csv ({len(D)}) + summary ({len(S)})")


if __name__ == "__main__":
    main()
