"""Link-function arm: does the incident-stroke transport result survive a cloglog discrete-time
hazard, and does it survive being fitted on a common interval grid?

The reviewer's request, verbatim:

  "你的模型本身仍然使用 logistic discrete-time hazard，而手稿承认 complementary log-log 模型尚未
   完成。考虑到不同国家随访间隔差异很大，我认为 cloglog 敏感性分析应该在投稿前完成。"

Two things are being asked, and they are different, so this script separates them.

(1) THE LINK. A logistic discrete-time hazard models P(event in this interval) as a logistic
    function of the covariates and of the interval's own length. Nothing in that specification
    says what should happen when the same follow-up is cut into smaller pieces: the composed
    four-year risk is a different function of the covariates at every step size, because
    1 - prod(1 - h_j) is not a link-preserving operation. A complementary log-log hazard IS
    link-preserving in the interval length: 1 - exp(-Lambda) with Lambda additive across
    intervals, which is why cloglog is the discrete-time form of proportional hazards. So the
    question is whether the transport result - the ranking survives, the level does not - is an
    artefact of the logistic link, and whether the one-intercept repair is an artefact of it too.

(2) THE GRID. The panels are not sampled on a common clock (median interval 2.00 yr in KLoSA and
    HRS, 2.08 in CHARLS, 3.00 in MHAS, tails to 16-21 yr), so an exposure-by-covariate interaction
    can absorb panel-specific slicing. `incident_grid_reframe.py --delta 1` re-writes every
    interval as sub-year pieces at the same dated event times, and this script refits every arm on
    it while still scoring against the horizon frame from the UNSPLIT file. A difference there is
    attributable to the grid and to nothing else.

Arms, all fitted on the same interval rows, the same one-hot encoding, the same LOCO split:
  sklearn_logistic  the published primary model (L2, C=1.0) - the anchor, and a reproduction check
  logit_glm         unpenalised logistic discrete-time hazard, same design matrix as above
  cloglog_glm       cloglog link, same design matrix (exposure_years still a covariate) - isolates
                    the link from everything else
  cloglog_ph        cloglog link with log(exposure_years) as an OFFSET and exposure removed from
                    the covariates - the proportional-hazards formulation, duration-consistent by
                    construction

Two extra diagnostics, because "is the link the problem" has a checkable answer:
  duration_consistency  hold one person's covariates fixed and compose the H-year risk from
                        1 / 2 / 4 / 8 equal pieces. A duration-consistent specification returns
                        the same number every time; a logistic one drifts. Reported as the ratio
                        of the 8-piece risk to the 1-piece risk.
  repair                the one-intercept correction refitted in the arm's OWN link space (log-odds
                        for the logit arms, log-cumulative-hazard for the cloglog arms) and, for
                        comparison, in log-odds space regardless of arm - because that is the
                        correction the manuscript currently reports. Local samples are drawn with
                        the identical seed formula as incident_horizon_recalibration.py, so every
                        replicate here is the same local sample as the published arm's.

Usage
  python incident_cloglog.py [--horizon 4] [--horizon-rule cif_mid] [--reps 20]
                             [--pp personperiod_pooled.csv|personperiod_grid1.csv]
                             [--frame-pp personperiod_pooled.csv]
"""
import os, sys, json, numpy as np, pandas as pd, warnings
warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)
import modeling as M
import run_loco_v2 as V2
import run_incident_loco as I
import incident_adaptation as A
import incident_horizon_recalibration as R
import statsmodels.api as sm
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler

OUT = I.OUT
REP = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results", "reports"))
SEED = V2.SEED
LOGIT = sm.families.links.Logit()
CLOGLOG = sm.families.links.CLogLog()
ARM_LINK = {"sklearn_logistic": "logit", "logit_glm": "logit",
            "cloglog_glm": "cloglog", "cloglog_ph": "cloglog"}
ARM_OBJ = {"logit_glm": (LOGIT, None), "cloglog_glm": (CLOGLOG, None),
           "cloglog_ph": (CLOGLOG, "exposure_years")}
FRACS = (0.02, 0.05, 0.10, 0.25, 0.50)


def flag(name, default):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default


class FrozenGlm:
    """The same preprocessing contract as run_incident_loco.Frozen - impute, drop degenerate
    columns, standardise, all fitted on TRAINING rows only - with a statsmodels GLM behind it and
    an optional log-exposure offset. `.cols` and `.predict` keep the interface that
    `I.horizon_risk` composes through, and `.eta` exposes the linear predictor in the arm's own
    link space so the repair is fitted where the model lives."""

    def __init__(self, Xtr, ytr, link, offset_col=None, weights=None):
        self.link, self.offset_col = link, offset_col
        self.cols = list(Xtr.columns)
        self.imp = SimpleImputer(strategy="median").fit(Xtr)
        self.names = list(self.imp.get_feature_names_out())
        A2 = pd.DataFrame(self.imp.transform(Xtr), columns=self.names, index=Xtr.index)
        keep = [c for c in self.names if A2[c].notna().any() and A2[c].nunique(dropna=True) > 1]
        self.cov = [c for c in keep if c != offset_col]
        self.sc = StandardScaler().fit(A2[self.cov])
        off = (np.log(np.clip(A2[offset_col].to_numpy(dtype=float), 1e-6, None))
               if offset_col else None)
        Z = sm.add_constant(self.sc.transform(A2[self.cov]), prepend=True, has_constant="add")
        self.res = sm.GLM(np.asarray(ytr, dtype=float), Z, offset=off, freq_weights=weights,
                          family=sm.families.Binomial(link=link)).fit(maxiter=100)
        self.converged = bool(getattr(self.res, "converged", False))
        self.deviance = float(self.res.deviance)
        self.params = np.asarray(self.res.params, dtype=float)
        self.term_names = (["const"] + [f"b[{c}]" for c in self.cov]
                           + (["offset:log(exposure_years)"] if offset_col else []))

    def _z(self, F):
        Fi = pd.DataFrame(self.imp.transform(F[self.cols]), columns=self.names, index=F.index)
        return sm.add_constant(self.sc.transform(Fi[self.cov]), prepend=True, has_constant="add")

    def eta(self, F):
        e = self._z(F) @ self.params
        if self.offset_col:
            e = e + np.log(np.clip(F[self.offset_col].to_numpy(dtype=float), 1e-6, None))
        return np.asarray(e, dtype=float)

    def predict(self, F):
        return self.link.inverse(np.clip(self.eta(F), -40.0, 40.0))


def frozen_or_glm(name, Xtr, ytr, wtr=None):
    """`wtr` is the row weight a grid file carries: under the `uniform` event-time allocation a
    stroke window's sub-intervals each hold 1/n of an event, emitted as a weighted 0/1 row pair, so
    the fit is the weighted-dataset likelihood rather than an invented event date. None means an
    unweighted fit, which is what the pooled file and the published arm use."""
    if name == "sklearn_logistic":
        return I.Frozen(Xtr, ytr, "logistic", sample_weight=wtr)
    link, off = ARM_OBJ[name]
    return FrozenGlm(Xtr, ytr, link, off, weights=wtr)


def link_of(p):
    return np.log(np.clip(p, 1e-12, 1 - 1e-12) / (1.0 - np.clip(p, 1e-12, 1 - 1e-12)))


def cumhaz_of(p):
    p = np.clip(np.asarray(p, dtype=float), 1e-12, 1 - 1e-12)
    return np.log(-np.log(1.0 - p))


def inv_link(z, space):
    z = np.clip(np.asarray(z, dtype=float), -40.0, 40.0)
    if space == "logit":
        return 1.0 / (1.0 + np.exp(-z))
    return 1.0 - np.exp(-np.exp(z))


def fit_offset_space(p, y, space):
    """Calibration-in-the-large in the arm's own link space: the single shift that makes the mean
    predicted risk equal the observed local rate. Bisection, as in incident_adaptation.fit_offset,
    because the map is monotone in the shift for both links."""
    q = float(np.mean(y))
    if not (0 < q < 1):
        return 0.0
    z = link_of(p) if space == "logit" else cumhaz_of(p)
    lo, hi = -12.0, 12.0
    for _ in range(80):
        mid = (lo + hi) / 2.0
        if inv_link(z + mid, space).mean() < q:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2.0


def compose(fr, base, horizon, time_mode, fset, n_pieces):
    """H-year risk from n_pieces EQUAL pieces with the covariates held fixed (no age advancing).
    n_pieces=1 is the single-interval answer; a duration-consistent specification gives the same
    value at every n_pieces. This is a diagnostic of the link, not a prediction anyone would ship:
    the shipped predictions advance age between steps, as in the primary arm."""
    step = horizon / float(n_pieces)
    surv = np.ones(len(base))
    for _ in range(int(n_pieces)):
        frame = base.copy()
        frame["exposure_years"] = step
        if time_mode == "linear":
            frame["t_since_entry_years"] = 0.0
        surv *= (1.0 - fr.predict(design_cols(fr, frame, fset, time_mode)))
    return 1.0 - surv


def design_cols(fr, frame, fset, time_mode):
    return I.design(frame, fset, time_mode).reindex(columns=fr.cols)


def main():
    horizon = float(flag("--horizon", "4"))
    rule = flag("--horizon-rule", "cif_mid")
    reps = int(flag("--reps", "20"))
    fit_file = flag("--pp", "personperiod_pooled.csv")
    frame_file = flag("--frame-pp", "personperiod_pooled.csv")
    arms = flag("--arms", ",".join(ARM_LINK)).split(",")
    fset, time_mode = "common", "linear"

    pp = pd.read_csv(os.path.join(OUT, fit_file))
    pp["country"] = pp["cohort"].map(I.COH2CTRY)
    pp = pp[pp["country"].notna()].reset_index(drop=True)
    X = I.design(pp, fset, time_mode)
    y = pp["event"].astype(int).values
    # a grid file carries row weights whenever its event-time allocation spreads an interval-censored
    # stroke over more than one sub-interval; the pooled file and the `last` allocation do not
    wt = None
    if "row_weight" in pp.columns:
        rw = pd.to_numeric(pp["row_weight"], errors="coerce").to_numpy(dtype=float)
        if not np.allclose(rw, 1.0):
            wt = rw
    fp = pd.read_csv(os.path.join(OUT, frame_file)) if frame_file != fit_file else pp
    fp["country"] = fp["cohort"].map(I.COH2CTRY)
    fp = fp[fp["country"].notna()].reset_index(drop=True)
    base_frame, hcounts = I.horizon_frame(fp, horizon, rule)
    print(f"fit rows={len(pp)} from {fit_file} | horizon frame from {frame_file} [{rule}]",
          flush=True)
    print(f"horizon person accounting: {json.dumps(hcounts)}", flush=True)

    rows, diag = [], {}
    for held in sorted(set(pp["country"])):
        tr = (pp["country"].values != held)
        te = (pp["country"].values == held)
        cmode = pp.loc[te, "censor_mode"].iloc[0]
        step_L = round(float(np.median(pp.loc[tr, "exposure_years"])) * 4) / 4
        n_steps = max(1, int(round(horizon / step_L)))
        step_used = horizon / n_steps            # keeps the realised horizon exactly at H
        hb = base_frame[base_frame["country"] == held].reset_index(drop=True)
        yb_all = hb["label"].astype(int).values
        wb = pd.to_numeric(hb["ipcw"], errors="coerce").fillna(1.0).to_numpy(dtype=float)
        pid_all = hb["pid"].values
        upid = np.unique(pid_all)
        print(f"\n=== {held}: horizon-evaluable persons={len(hb)} events={int(yb_all.sum())} "
              f"prevalence={yb_all.mean():.4f} censor={cmode} step_L={step_L} "
              f"step_used={step_used}", flush=True)
        for name in arms:
            space = ARM_LINK[name]
            fr = frozen_or_glm(name, X.loc[tr], y[tr], None if wt is None else wt[tr])
            if isinstance(fr, FrozenGlm):
                diag[f"{held}|{name}"] = {"converged": fr.converged,
                                          "deviance": round(fr.deviance, 2),
                                          "terms": fr.term_names,
                                          "params": [round(float(v), 5) for v in fr.params],
                                          "offset": fr.offset_col}
            ph, realised = I.horizon_risk(fr, hb, horizon, time_mode, fset, step=step_used)
            ph1, _ = I.horizon_risk(fr, hb, horizon, time_mode, fset, step=None)
            # duration-consistency on a fixed subsample, covariates frozen
            rng0 = np.random.default_rng(SEED + 11)
            idx = rng0.choice(len(hb), size=min(3000, len(hb)), replace=False)
            ratios = {}
            for n in (1, 2, 4, 8):
                ratios[n] = compose(fr, hb.iloc[idx], horizon, time_mode, fset, n)
            drift = {f"ratio_pieces{n}_over_1": float(np.mean(ratios[n] / np.maximum(ratios[1], 1e-12)))
                     for n in (2, 4, 8)}
            drift["max_abs_log_ratio"] = float(np.max(np.abs(np.log(
                np.maximum(ratios[8], 1e-12) / np.maximum(ratios[1], 1e-12)))))
            diag.setdefault(f"{held}|{name}", {}).update(
                {"duration_consistency_mean_risk_1pc": round(float(ratios[1].mean()), 5),
                 **{k: round(v, 5) for k, v in drift.items()},
                 "frozen_mean_pred_step": round(float(ph.mean()), 5),
                 "frozen_mean_pred_single_interval": round(float(ph1.mean()), 5)})
            z_all = link_of(ph) if space == "logit" else cumhaz_of(ph)

            rows.append(dict(held=held, arm=name, link=space, strategy="frozen_all", frac=0.0,
                             rep=0, censor_mode=cmode, realised_horizon_years=realised,
                             local_persons=0, n_eval_persons=int(len(hb)),
                             mean_repair_shift=np.nan, **R.metrics(yb_all, ph, wb)))
            for frac in FRACS:
                for rep_i in range(reps):
                    rng = np.random.default_rng(SEED + 7000 + 1000 * rep_i + int(100 * frac))
                    take = max(2, int(round(len(upid) * frac)))
                    pick = rng.choice(upid, size=take, replace=False)
                    loc = np.isin(pid_all, pick)
                    ev = ~loc
                    # Regression guard for the adaptation/evaluation independence the manuscript claims.
                    # ev is the complement of loc, so this cannot fire unless a future edit splits by row
                    # instead of by person; incident_adaptation_leakage_audit.py measures it empirically.
                    assert not (set(pid_all[loc]) & set(pid_all[ev])), "local-adaptation and evaluation persons overlap"
                    if len(np.unique(yb_all[loc])) < 2 or len(np.unique(yb_all[ev])) < 2:
                        continue
                    y_e, ph_e = yb_all[ev], ph[ev]
                    w_e = wb[ev]
                    a_link = fit_offset_space(ph[loc], yb_all[loc], space)
                    a_logit = fit_offset_space(ph[loc], yb_all[loc], "logit")
                    common = dict(held=held, arm=name, link=space, frac=frac, rep=rep_i,
                                  censor_mode=cmode, realised_horizon_years=realised,
                                  local_persons=int(loc.sum()),
                                  local_events=int(yb_all[loc].sum()),
                                  n_eval_persons=int(len(y_e)))
                    for strat, sh, z in (("frozen_sub", 0.0, z_all[ev]),
                                         (f"offset_{space}", a_link, z_all[ev] + a_link),
                                         ("offset_logit", a_logit, z_all[ev] + a_logit)
                                         if space != "logit" else (None, None, None)):
                        if strat is None:
                            continue
                        p = ph_e if strat == "frozen_sub" else inv_link(z, space)
                        rows.append(dict(**common, strategy=strat, mean_repair_shift=float(sh),
                                         **R.metrics(y_e, p, w_e)))
                    if rep_i == reps - 1:
                        fz = [r for r in rows if r["held"] == held and r["arm"] == name
                              and r["frac"] == frac and r["rep"] == rep_i
                              and r["strategy"] == "frozen_sub"][-1]
                        rp = [r for r in rows if r["held"] == held and r["arm"] == name
                              and r["frac"] == frac and r["rep"] == rep_i
                              and r["strategy"] == f"offset_{space}"][-1]
                        print(f"  {held} {name:16s} frac={frac:5.2f} shift={rp['mean_repair_shift']:+.3f} "
                              f"mean_p {fz['mean_pred']:.4f}->{rp['mean_pred']:.4f} "
                              f"p/obs {fz['oe_ratio']:.2f}->{rp['oe_ratio']:.2f} "
                              f"NB@5% {fz['nb_at_05']:+.5f}->{rp['nb_at_05']:+.5f} "
                              f"dAUROC {rp['auroc'] - fz['auroc']:+.6f}", flush=True)

    out = pd.DataFrame(rows)
    fshort = "" if fit_file == "personperiod_pooled.csv" else \
        "_" + os.path.splitext(fit_file)[0].replace("personperiod_", "")
    dest = os.path.join(OUT, f"incident_cloglog_{rule}{fshort}.csv")
    out.to_csv(dest, index=False)

    # paired gains: the same local sample, the same evaluation persons, the same replicate
    paired = []
    for held in sorted(set(out["held"])):
        for name in [a for a in arms if a in set(out["arm"])]:
            fz = out[(out.held == held) & (out.arm == name) & (out.strategy == "frozen_sub")] \
                .pivot_table(index="frac", columns="rep", values="nb_at_05")
            for strat in out[(out.held == held) & (out.arm == name)]["strategy"].unique():
                if strat == "frozen_sub":
                    continue
                s = out[(out.held == held) & (out.arm == name) & (out.strategy == strat)] \
                    .pivot_table(index="frac", columns="rep", values="nb_at_05")
                for frac in s.index.intersection(fz.index):
                    a, b = s.loc[frac].dropna(), fz.loc[frac].dropna()
                    ix = a.index.intersection(b.index)
                    if len(ix) < 3:
                        continue
                    d = (a.loc[ix] - b.loc[ix]).to_numpy()
                    paired.append(dict(held=held, arm=name, strategy=strat, frac=float(frac),
                                       n_complete_reps=int(len(ix)),
                                       mean_gain_nb_at_05=float(d.mean()),
                                       sd_gain_nb_at_05=float(d.std(ddof=1)),
                                       n_gain_positive=int((d > 0).sum()),
                                       min_gain=float(d.min()), max_gain=float(d.max())))
    pdf = pd.DataFrame(paired)
    pdf.to_csv(os.path.join(OUT, f"incident_cloglog_paired_{rule}{fshort}.csv"), index=False)

    # the anchor must reproduce the published arm exactly, or this script is measuring nothing
    anchor = out[(out.arm == "sklearn_logistic") & (out.strategy == "frozen_all")]
    pub_path = os.path.join(OUT, f"incident_horizon_recalibration_{rule}.csv")
    check = {"anchor_arm": "sklearn_logistic", "published_file": os.path.basename(pub_path)}
    if os.path.exists(pub_path) and fshort == "" and len(anchor):
        pub = pd.read_csv(pub_path)
        pub = pub[(pub.model == "logistic") & (pub.strategy == "frozen_all")]
        m = anchor.merge(pub, on="held", suffixes=("", "_pub"))
        for c in ("mean_pred", "obs_prev", "oe_ratio", "nb_at_05", "auroc", "n_eval_persons"):
            diff = (m[c] - m[f"{c}_pub"]).abs().max()
            check[f"max_abs_diff_{c}"] = float(diff)
        check["reproduces_published"] = bool(all(
            check.get(f"max_abs_diff_{c}", 1) < (1e-9 if c == "n_eval_persons" else 1e-9)
            for c in ("mean_pred", "obs_prev", "oe_ratio", "nb_at_05", "auroc", "n_eval_persons")))
    doc = {"horizon_years": horizon, "horizon_rule": rule, "fit_file": fit_file,
           "frame_file": frame_file, "reps": reps, "fractions": list(FRACS),
           "row_weighted_fit": wt is not None,
           "event_time_allocation": ("the file's own convention; a `uniform` grid file spreads each "
                                     "interval-censored stroke over its sub-intervals with fractional "
                                     "weight 1/n, so the fit is the weighted-dataset likelihood and no "
                                     "event date is invented"
                                     if wt is not None else
                                     "unweighted rows: the pooled file, or a grid file whose events sit "
                                     "in one piece (`last` / `midcell`)"),
           "arms": {k: {"link": ARM_LINK[k],
                        "offset": (ARM_OBJ[k][1] if k in ARM_OBJ else None),
                        "exposure_years_as_covariate": (k != "cloglog_ph")} for k in arms},
           "horizon_person_accounting": hcounts, "fit_and_linkage_diagnostics": diag,
           "anchor_reproduction": check,
           "n_rows": int(len(out)),
           "note": ("interval-level discrete-time hazards fitted on the LOCO training panels; the "
                    "evaluation frame and its IPCW weights always come from --frame-pp, so the "
                    "pooled and grid runs are scored on identical persons")}
    os.makedirs(REP, exist_ok=True)
    with open(os.path.join(REP, f"incident_cloglog_{rule}{fshort}.json"), "w",
              encoding="utf-8") as f:
        json.dump(doc, f, indent=2, ensure_ascii=False)
    print(f"\nwrote {dest} rows={len(out)}")
    print("anchor reproduction of the published arm:", json.dumps(check))
    if fshort == "" and check.get("reproduces_published") is False:
        raise AssertionError("the sklearn anchor did not reproduce the published frozen row")


if __name__ == "__main__":
    main()
