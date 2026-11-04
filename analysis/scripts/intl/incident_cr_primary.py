"""Competing-risks-consistent primary absolute-risk analysis.

Why this script exists. The reported estimand is the Aalen-Johansen cumulative incidence of a first
stroke within four years: `run_incident_loco.horizon_frame` keeps a person who dies inside the window
without a stroke as a DETERMINED NON-EVENT, so `obs_prev` estimates

    F_stroke(4) = P(stroke by 4 years, stroke before death)                 [competing risks]

while the model side, `I.horizon_risk`, composes only the stroke hazards,

    1 - prod_j (1 - h_stroke,j) = 1 - exp(-Lambda_stroke(4))                [cause-specific]

which is the probability of stroke if death could not happen - death is treated as censoring, not as a
competing outcome. Those are different quantities whenever people die, and the difference is
systematically upward. Every predicted-to-observed ratio in this project has therefore compared a
cause-specific risk to a competing-risks target. This script measures that gap and then closes it.

The corrected prediction fits TWO cause-specific discrete-time hazards by the interval-censored
likelihood (incident_ic_grid.IcFit) and composes them into a cumulative incidence:

    p_s,j = P(stroke in step j | alive and stroke-free at its start)
    p_d,j = P(death  in step j | alive and stroke-free at its start)
    S_j   = prod_{k<=j} (1 - p_s,k)(1 - p_d,k)
    F_stroke(tau) = sum_j S_{j-1} * p_s,j

which is the discrete Aalen-Johansen estimator of the same functional the evaluation frame estimates,
so prediction and target are now the same object. For the proportional-hazards specification the
continuous limit is available in closed form,

    F_stroke(tau) = lambda_s / (lambda_s + lambda_d) * (1 - exp(-(lambda_s + lambda_d) tau)),

and it is computed as well: the discrete composition approaches it as the step shrinks, so the pair
reports both the corrected level and how much of any residual step-dependence is approximation rather
than specification.

Four model variants are carried so the two conventions can be told apart rather than conflated:

  V1 logit, interval length as a covariate, stroke-only composition   - the published primary analysis
  V2 logit, interval length as a covariate, competing-risks composition
  V3 cloglog with log-exposure offset, stroke-only composition        - duration-consistent, ignores death
  V4 cloglog with log-exposure offset, competing-risks composition    - BOTH corrected: the new primary

and each is reported twice more under the death-timing conventions the evaluation frame supports
(`cif_start`, `cif_mid`, `cif_end`), which is the sensitivity the reviewer asked for: those are
identification assumptions about when inside an interview gap an unobserved event fell, not
verifications of the true date.

A disclosure this script cannot avoid, and does not: KLoSA contributes ZERO observed deaths
(`end_status` never takes a death value in its main waves), so when Korea is the held-out panel the
death hazard is transported from the other three panels and Korea's own Aalen-Johansen target
coincides with 1 - Kaplan-Meier by construction rather than by agreement. Korea's competing-risks
numbers are therefore the least identified of the four and are printed with that caveat attached.

Evaluation hygiene (docs/SELF_AUDIT.md, P0-3 audit): the local sample used to fit any repair is a set
of PERSONS, the evaluation set is its complement by person id, and the script asserts the intersection
is empty rather than relying on the construction being read correctly. IPCW weights and the estimand's
coverage come from the whole held-out country's frame, because they define the target being estimated -
they are not fitted on the evaluation labels - and that distinction is stated in the report.

Usage
  python incident_cr_primary.py [--horizon 4] [--reps 40] [--boot 500]
                                [--rules cif_mid,cif_start,cif_end] [--fractions 0.02,0.05,0.10,0.25,0.50]
"""
import os, sys, json, numpy as np, pandas as pd, warnings
warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)
import modeling as M
import run_loco_v2 as V2
import run_incident_loco as I
import incident_horizon_recalibration as R
import incident_ic_grid as IC
from sklearn.metrics import roc_auc_score, average_precision_score

OUT = I.OUT
REP = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results", "reports"))
SEED = V2.SEED
DEATH = I.DEATH_STATUS
VARIANTS = {                       # name -> (link, length_mode, competing-risks composition)
    "V1_logit_cause_specific": ("logit", "covariate", False),
    "V2_logit_competing": ("logit", "covariate", True),
    "V3_ph_cause_specific": ("cloglog", "offset", False),
    "V4_ph_competing": ("cloglog", "offset", True),
}


def flag(name, default):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default


def compose_two(ms, md, base, horizon, time_mode, fset, step, competing, fixed_covariates=False):
    """Four-year risk from the two cause-specific hazards, stepping `step` years at a time.

    competing=False -> 1 - prod(1 - p_s): stroke-only, death ignored (the published composition).
    competing=True  -> sum_j S_{j-1} p_s,j with S from BOTH hazards: the discrete Aalen-Johansen CIF,
                       i.e. the same functional the evaluation frame estimates.
    `fixed_covariates=True` holds age and time put (the duration-consistency diagnostic); the shipped
    prediction advances them, exactly as `I.horizon_risk` does.
    """
    n_steps = max(1, int(round(horizon / step)))
    surv = np.ones(len(base))
    acc = np.zeros(len(base))
    for j in range(n_steps):
        frame = base.copy()
        if not fixed_covariates:
            frame["age"] = pd.to_numeric(base["age"], errors="coerce").values + j * step
            if time_mode == "linear":
                frame["t_since_entry_years"] = j * step
        frame["exposure_years"] = step
        D = I.design(frame, fset, time_mode).reindex(columns=ms.cols)
        ps = ms.predict(D)
        if competing:
            pd_ = md.predict(D)
            acc = acc + surv * ps
            surv = surv * (1.0 - ps) * (1.0 - pd_)
        else:
            surv = surv * (1.0 - ps)
    return acc if competing else (1.0 - surv)


def closed_form_cif(ms, md, base, horizon, time_mode, fset):
    """F_stroke(tau) for the proportional-hazards pair, treating both hazards constant over the window
    at their interval-start covariate values: lambda_s/(lambda_s+lambda_d)*(1-exp(-(lambda_s+lambda_d)tau)).
    Duration-consistent by construction, so it is the target the stepped composition converges to."""
    frame = base.copy()
    frame["exposure_years"] = horizon
    if time_mode == "linear":
        frame["t_since_entry_years"] = 0.0
    D = I.design(frame, fset, time_mode).reindex(columns=ms.cols)
    ls = np.exp(np.clip(ms.eta(D), -40, 20))
    ld = np.exp(np.clip(md.eta(D), -40, 20))
    tot = np.maximum(ls + ld, 1e-12)
    return ls / tot * (1.0 - np.exp(-tot * horizon))


def metrics(y, p, w, full=False):
    """The reported metric set. `full` adds AUPRC and the recalibration slope, which need a GLM and a
    second ranking pass; they are computed once per frozen row, not per replicate, because the repair
    is a monotone map of the linear predictor (so AUROC and slope are invariant to it by construction)
    and 19,200 GLM fits would make the arm unrunnable."""
    y = np.asarray(y).astype(int); p = np.asarray(p, dtype=float)
    w = np.ones(len(y)) if w is None else np.asarray(w, dtype=float)
    wt = bool(np.any(np.abs(w - 1.0) > 1e-12))
    q = I.w_mean(y, y, w); mp = I.w_mean(y, p, w)
    b = I.w_mean(y, (p - y) ** 2, w)
    out = dict(auroc=float(roc_auc_score(y, p, sample_weight=w if wt else None)),
               brier=float(b),
               scaled_brier=float((q * (1 - q) - b) / (q * (1 - q))) if 0 < q < 1 else np.nan,
               mean_pred=float(mp), obs_prev=float(q),
               pred_over_obs=float(mp / q) if q > 0 else np.nan,
               nb_at_02=I.weighted_net_benefit(y, p, w, 0.02),
               nb_at_05=I.weighted_net_benefit(y, p, w, 0.05),
               nb_at_10=I.weighted_net_benefit(y, p, w, 0.10),
               nb_at_15=I.weighted_net_benefit(y, p, w, 0.15),
               nb_all_at_05=I.weighted_net_benefit(y, np.ones(len(y)), w, 0.05),
               n_eval=int(len(y)))
    if not full:
        return out
    lp = np.log(np.clip(p, 1e-12, 1 - 1e-12) / (1 - np.clip(p, 1e-12, 1 - 1e-12)))
    try:
        out["auprc"] = float(average_precision_score(y, p, sample_weight=w if wt else None))
    except ValueError:
        out["auprc"] = float("nan")
    try:
        import statsmodels.api as sm
        res = sm.GLM(y, sm.add_constant(lp), family=sm.families.Binomial(),
                     freq_weights=w if wt else None).fit(maxiter=50)
        out["calib_slope"] = float(res.params[1]); out["calib_intercept"] = float(res.params[0])
    except Exception:
        out["calib_slope"] = float("nan"); out["calib_intercept"] = float("nan")
    return out


def boot_ci(y, p, w, ids, B, rng):
    """Person-clustered bootstrap intervals for the three numbers the manuscript headlines."""
    order = np.argsort(ids, kind="stable")
    ids_s, y_s, p_s, w_s = ids[order], y[order], p[order], w[order]
    uniq, start = np.unique(ids_s, return_index=True)
    bounds = np.append(start, len(ids_s))
    y, p, w = np.asarray(y), np.asarray(p), np.asarray(w)
    out = {k: [] for k in ("auroc", "pred_over_obs", "nb_at_05")}
    for _ in range(B):
        take = rng.integers(0, len(uniq), size=len(uniq))
        idx = np.concatenate([np.arange(bounds[t], bounds[t + 1]) for t in take])
        m = metrics(y_s[idx], p_s[idx], w_s[idx])
        for k in out:
            out[k].append(m[k])
    return {k: [float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))]
            for k, v in out.items()}


def main():
    horizon = float(flag("--horizon", "4"))
    reps = int(flag("--reps", "40"))
    B = int(flag("--boot", "500"))
    rules = flag("--rules", "cif_mid,cif_start,cif_end").split(",")
    fracs = [float(x) for x in flag("--fractions", "0.02,0.05,0.10,0.25,0.50").split(",")]
    fset, time_mode = "common", "linear"

    pp = pd.read_csv(os.path.join(OUT, "personperiod_pooled.csv"))
    pp["country"] = pp["cohort"].map(I.COH2CTRY)
    pp = pp[pp["country"].notna()].reset_index(drop=True)
    X = I.design(pp, fset, time_mode)
    y_stroke = pp["event"].astype(int).values
    y_death = pp["end_status"].isin(DEATH).astype(int).values
    print(f"intervals={len(pp)} | stroke rows={int(y_stroke.sum())} | death rows={int(y_death.sum())} "
          f"| deaths observed per panel: "
          + ", ".join(f"{c}={int((pp.country == c).mul(y_death, axis=0).sum())}"
                      for c in sorted(set(pp["country"]))), flush=True)

    # The eight cause-specific fits per held-out panel do not depend on the event-timing convention -
    # only the evaluation frame does - so they are made once and reused across all three rules.
    FITS = {}
    for held in sorted(set(pp["country"])):
        tr = (pp["country"].values != held)
        FITS[held] = {}
        for vname, (link, lmode, comp) in VARIANTS.items():
            FITS[held][vname] = (IC.IcFit(X.loc[tr], y_stroke[tr], link, lmode, 1.0),
                                 IC.IcFit(X.loc[tr], y_death[tr], link, lmode, 1.0), comp)
            g = FITS[held][vname]
            print(f"  fitted {held} {vname}: stroke conv={g[0].converged} it={g[0].n_iter} "
                  f"| death conv={g[1].converged} it={g[1].n_iter}", flush=True)

    rows, diag, audit = [], {}, []
    acct = {}
    for rule in rules:
        base_frame, hcounts = I.horizon_frame(pp, horizon, rule)
        acct[rule] = hcounts
        print(f"\n########## death/event timing convention: {rule}", flush=True)
        for held in sorted(set(pp["country"])):
            tr = (pp["country"].values != held)
            cmode = pp.loc[~tr, "censor_mode"].iloc[0]
            step_L = round(float(np.median(pp.loc[tr, "exposure_years"])) * 4) / 4
            step = horizon / max(1, int(round(horizon / step_L)))
            hb = base_frame[base_frame["country"] == held].reset_index(drop=True)
            yb = hb["label"].astype(int).values
            wb = pd.to_numeric(hb["ipcw"], errors="coerce").fillna(1.0).to_numpy(dtype=float)
            pid = hb["pid"].values
            upid = np.unique(pid)
            fits = FITS[held]
            print(f"=== {held}: evaluable={len(hb)} events={int(yb.sum())} obs CIF={yb.mean():.4f} "
                  f"censor={cmode} step={step}", flush=True)
            for vname, (ms, md, comp) in fits.items():
                link, lmode, _ = VARIANTS[vname]
                ph = compose_two(ms, md, hb, horizon, time_mode, fset, step, comp)
                m = metrics(yb, ph, wb, full=True)
                rng = np.random.default_rng(SEED + 9000)
                ci = boot_ci(yb, ph, wb, pid, B, rng) if rule == rules[0] else {}
                # the estimand-mixing decomposition: same fitted stroke hazard, two compositions
                alt = compose_two(ms, md, hb, horizon, time_mode, fset, step, not comp)
                lam = closed_form_cif(ms, md, hb, horizon, time_mode, fset) if lmode == "offset" else None
                # duration consistency at fixed covariates, 1/2/4/8 steps
                dc = {}
                idx = np.random.default_rng(SEED + 11).choice(
                    len(hb), size=min(3000, len(hb)), replace=False)
                sub = hb.iloc[idx]
                for n in (1, 2, 4, 8):
                    dc[n] = float(compose_two(ms, md, sub, horizon, time_mode, fset,
                                              horizon / n, comp, fixed_covariates=True).mean())
                diag[f"{rule}|{held}|{vname}"] = {
                    "converged_stroke": bool(ms.converged), "converged_death": bool(md.converged),
                    "n_iter_stroke": int(ms.n_iter), "n_iter_death": int(md.n_iter),
                    "mean_pred": round(m["mean_pred"], 5), "obs_prev": round(m["obs_prev"], 5),
                    "pred_over_obs": round(m["pred_over_obs"], 4),
                    "mean_pred_other_composition": round(float(alt.mean()), 5),
                    "closed_form_cif_mean": (round(float(lam.mean()), 5) if lam is not None else None),
                    "duration_ratio_8_over_1": round(dc[8] / max(dc[1], 1e-12), 4),
                    "duration_mean_risk_by_step": {str(k): round(v, 5) for k, v in dc.items()}}
                rows.append(dict(horizon_rule=rule, held=held, variant=vname,
                                 composition=("competing_risks_CIF" if comp else "cause_specific_only"),
                                 strategy="frozen_all", frac=0.0, rep=0, censor_mode=cmode,
                                 step_years=step, local_persons=0, **m,
                                 ci_auroc_lo=ci.get("auroc", [np.nan, np.nan])[0],
                                 ci_auroc_hi=ci.get("auroc", [np.nan, np.nan])[1],
                                 ci_po_lo=ci.get("pred_over_obs", [np.nan, np.nan])[0],
                                 ci_po_hi=ci.get("pred_over_obs", [np.nan, np.nan])[1],
                                 ci_nb_lo=ci.get("nb_at_05", [np.nan, np.nan])[0],
                                 ci_nb_hi=ci.get("nb_at_05", [np.nan, np.nan])[1]))
                # ---- local adaptation, strictly disjoint person sets, asserted not assumed
                for frac in fracs:
                    for rep_i in range(reps):
                        rng2 = np.random.default_rng(SEED + 7000 + 1000 * rep_i + int(100 * frac))
                        take = max(2, int(round(len(upid) * frac)))
                        pick = rng2.choice(upid, size=take, replace=False)
                        locm = np.isin(pid, pick)
                        evm = ~locm
                        assert not set(pid[locm]) & set(pid[evm]), "adaptation and eval share a person"
                        audit.append(dict(rule=rule, held=held, variant=vname, frac=frac, rep=rep_i,
                                          n_local=int(locm.sum()), n_eval=int(evm.sum()),
                                          overlap=int(len(set(pid[locm]) & set(pid[evm])))))
                        if len(np.unique(yb[locm])) < 2 or len(np.unique(yb[evm])) < 2:
                            continue
                        a = IC.fit_offset_space(ph[locm], yb[locm], "logit")
                        for strat, sh in (("frozen_sub", 0.0), ("offset_logit", a)):
                            p = ph[evm] if strat == "frozen_sub" else np.clip(
                                1.0 / (1.0 + np.exp(-(np.log(np.clip(ph[evm], 1e-12, 1 - 1e-12) /
                                                            (1 - np.clip(ph[evm], 1e-12, 1 - 1e-12))) + a))),
                                0.0, 1.0)
                            rows.append(dict(horizon_rule=rule, held=held, variant=vname,
                                             composition=("competing_risks_CIF" if comp else
                                                           "cause_specific_only"),
                                             strategy=strat, frac=frac, rep=rep_i, censor_mode=cmode,
                                             step_years=step, local_persons=int(locm.sum()),
                                             local_events=int(yb[locm].sum()),
                                             mean_repair_shift=float(sh), **metrics(yb[evm], p, wb[evm])))

    out = pd.DataFrame(rows)
    out.to_csv(os.path.join(OUT, f"incident_cr_primary.csv"), index=False)

    paired = []
    for (rule, held, vname, frac), g in out[out.strategy != "frozen_all"].groupby(
            ["horizon_rule", "held", "variant", "frac"]):
        fz = g[g.strategy == "frozen_sub"].pivot_table(index="rep", values="nb_at_05")
        for strat in [s for s in g.strategy.unique() if s != "frozen_sub"]:
            s = g[g.strategy == strat].pivot_table(index="rep", values="nb_at_05")
            ix = s.index.intersection(fz.index)
            if len(ix) < 3:
                continue
            d = (s.loc[ix, "nb_at_05"] - fz.loc[ix, "nb_at_05"]).to_numpy()
            pr = g[(g.strategy == strat)].groupby("rep")["pred_over_obs"].mean()
            paired.append(dict(horizon_rule=rule, held=held, variant=vname, strategy=strat,
                               frac=float(frac), n_complete_reps=int(len(ix)),
                               mean_gain_nb_at_05=float(d.mean()), sd_gain_nb_at_05=float(d.std(ddof=1)),
                               lo_gain_nb_at_05=float(np.percentile(d, 2.5)),
                               hi_gain_nb_at_05=float(np.percentile(d, 97.5)),
                               n_gain_positive=int((d > 0).sum()),
                               n_repaired_nb_above_treat_none=int((g[g.strategy == strat]
                                                                   .groupby("rep")["nb_at_05"]
                                                                   .mean().loc[ix] > 0).sum()),
                               mean_repaired_pred_over_obs=float(pr.loc[ix].mean())))
    pd.DataFrame(paired).to_csv(os.path.join(OUT, "incident_cr_primary_paired.csv"), index=False)

    ov = pd.DataFrame(audit)
    checks = {"adaptation_eval_person_overlap_total": int(ov.overlap.sum()),
              "adaptation_eval_rows_audited": int(len(ov)),
              "ipcw_and_coverage_note": ("IPCW weights and the determined/non-determined status come "
                                         "from the whole held-out country's frame because they DEFINE "
                                         "the estimand; no evaluation LABEL is used to fit any repair - "
                                         "the intercept sees only the local sample's predictions and "
                                         "labels, and the local and evaluation person sets are asserted "
                                         "disjoint."),
              "klosa_death_ascertainment": (f"KLoSA contributes "
                                            f"{int(((pp.cohort == 'KLoSA') & (pp.end_status.isin(DEATH))).sum())} "
                                            "observed deaths, so Korea's competing-risks target and "
                                            "death hazard are not identified from Korean data alone")}
    doc = {"horizon_years": horizon, "rules": rules, "reps": reps, "bootstrap_B": B,
           "fractions": fracs, "variants": {k: {"link": v[0], "length_enters_as": v[1],
                                                 "composition": ("Aalen-Johansen CIF over both "
                                                                  "cause-specific hazards" if v[2]
                                                                  else "1 - exp(-Lambda_stroke), "
                                                                       "death ignored")}
                                            for k, v in VARIANTS.items()},
           "estimand_of_the_observed_target": ("Aalen-Johansen cumulative incidence of a first stroke "
                                               "within the horizon, competing death kept in as a "
                                               "determined non-event"),
           "estimand_the_published_composition_estimates": ("1 - exp(-Lambda_stroke(horizon)), the "
                                                             "cause-specific stroke risk under a "
                                                             "censoring interpretation of death"),
           "horizon_person_accounting": acct,
           "diagnostics": diag, "leakage_checks": checks, "n_rows": int(len(out))}
    os.makedirs(REP, exist_ok=True)
    with open(os.path.join(REP, "incident_cr_primary.json"), "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=2, ensure_ascii=False)
    print("\nwrote incident_cr_primary.csv rows=", len(out), "| paired rows=", len(paired))
    print("leakage checks:", json.dumps({k: v for k, v in checks.items()
                                          if not isinstance(v, str)}))
    if checks["adaptation_eval_person_overlap_total"] != 0:
        raise AssertionError("local adaptation and evaluation sets share persons")


if __name__ == "__main__":
    main()
