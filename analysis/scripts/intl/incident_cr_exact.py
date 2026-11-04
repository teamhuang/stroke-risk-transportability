"""P0-1 audit: is the discrete Aalen-Johansen composition a valid competing-events probability?

The reviewer's charge
    "P(no event) = 1 - P(stroke) - P(death), not (1-p_s)(1-p_d). If both are separately estimated
     interval event probabilities, multiplying their complements may not represent the probability
     that neither event happened in the interval."

What the algebra says, and this script measures
    Let the two cause-specific hazards be constant at lambda_s, lambda_d over a step of length D
    (which is exactly what the cloglog + log-exposure-offset specification asserts), and let the two
    latent event times be independent. Then

        P(no first event in the step) = exp(-(lambda_s + lambda_d) D)
                                      = (1 - p_s)(1 - p_d)          p_c = 1 - exp(-lambda_c D)

    so the PRODUCT IS THE CORRECT NO-EVENT PROBABILITY, and the reviewer's `1 - p_s - p_d` is not:
    the marginal event probabilities are not exclusive, because both events can fall inside the same
    unobserved gap. Measured below as `survival_product_vs_exact_gap`, which is 0 to machine
    precision - the charge about the survival factor is answered, not argued.

    But the same algebra condemns the OTHER factor. The probability that the first event in the step
    IS a stroke is not p_s, it is

        alpha = lambda_s / (lambda_s + lambda_d) * (1 - exp(-(lambda_s + lambda_d) D)),

    and the arm the manuscript ships uses p_s in that place. The marginal over-states the exclusive one
    by p_s - alpha_s - the probability that a death also falls in the step before the stroke - which is
    NOT p_s * p_d. The both-events probability p_s * p_d is the TOTAL double-count and obeys the exact
    identity p_s * p_d = (p_s - alpha_s) + (p_d - alpha_d).
    Consequently the published step probabilities do not conserve probability:

        p_s + p_d + S = 1 + p_s * p_d  >  1.

    This is the exclusivity error, it is O(D^2) per step, and it is the thing that was previously
    described in this paper as "Riemann discretisation of the composition" - the ladder that sat
    0.1-2.6% above the analytic cumulative incidence at four pieces. It was not a discretisation
    artefact that refinement cures by luck; it is a term with a name and a closed form, and removing
    it makes the composition EXACT at every step size.

So this script adds V5, the exact exclusive composition, and reports:
  1. the per-panel difference between V4 (shipped) and V5 (exact), absolute and relative, at the grid
     the panels actually give (two-year steps for a four-year horizon), plus the four/eight-piece
     ladder for both - V5's must be flat at 1.000000, V4's must drift;
  2. whether the exclusivity term explains the old ladder gap (compare V4's 4-piece excess with
     p_s*p_d summed over steps);
  3. every headline number re-derived under V5 with identical fitted hazards: AUROC, calibration in
     the large, slope, AUPRC, Brier, net benefit at 2/5/10/15%, person-clustered bootstrap intervals,
     and the local intercept repair with the three-way above/tied/below treat-none accounting;
  4. whether the manuscript's conclusion changes - the criterion is set before running: Mexico's
     predicted/observed ratio must still exceed 2.0 with an interval excluding 1.0.

Fits are re-done here and asserted equal to the published primary arm's frozen rows when composed the
OLD way, so the only thing that differs between V4 and V5 is the composition, not the estimation.

Usage
  python incident_cr_exact.py [--horizon 4] [--reps 40] [--boot 500] [--fractions 0.02,0.05,0.10,0.25,0.50]
Outputs (data/processed/intl/incident/)
  incident_cr_exact.csv               V4 and V5 side by side, frozen + repair replicates
  incident_cr_exact_paired.csv        paired repair effects, three-way treat-none counts
  incident_cr_exact_ladder.csv        1/2/4/8-piece composition for both, and the analytic value
"""
import os, sys, json, warnings
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)
import run_incident_loco as I                                 # noqa: E402
import incident_ic_grid as IC                                 # noqa: E402
import incident_cr_primary as P                               # noqa: E402

OUT = P.OUT
SEED = P.SEED
DAY = "2026-11-03"
RULES = ["cif_mid", "cif_start", "cif_end"]
VAR = "V4_ph_competing"          # the shipped primary: cloglog + log-exposure offset + competing death


def cause_rates(m, F):
    """Per-row cause-specific hazard rate and step length from an IcFit fitted in offset mode.

    Under `length_mode == "offset"` the fitted linear predictor is eta = z + log D, so
    exp(eta) = lambda * D and lambda = exp(eta) / D. This is the only specification for which an
    exact exclusive composition exists: the logit-covariate arms do not define a rate."""
    Z, off, n, L, D = m._pieces(F)
    eta = Z @ m.params
    if off is not None:
        eta = eta + off
    lam = np.exp(np.clip(eta, -40, 20)) / np.maximum(D, 1e-9)
    return lam, D


def compose_exact(ms, md, base, horizon, time_mode, fset, step, fixed_covariates=False):
    """F_stroke(horizon) with the step probabilities made mutually exclusive.

        alpha_j = lambda_s/(lambda_s+lambda_d) * (1 - exp(-(lambda_s+lambda_d) D))
        S_j     = exp(-(lambda_s+lambda_d) D) = 1 - alpha_j - beta_j

    so alpha + beta + S = 1 in every step by construction, and the whole sum equals the analytic
    continuous CIF for piecewise-constant hazards at ANY step size (proved numerically by the ladder).

    Note the two lengths in play. The fitted IcFit subdivides each supplied interval into its own
    delta-length pieces internally, so `cause_rates` returns the per-year hazard rate, which is
    piece-count invariant; the composition is then carried out over the OUTER step length `step`,
    which is what the stepping loop is actually advancing by. Using the internal piece length here
    would evaluate a two-year step as a one-year step and halve the risk."""
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
        Fs = I.design(frame, fset, time_mode).reindex(columns=ms.cols)
        ls, _ = cause_rates(ms, Fs)
        ld, _ = cause_rates(md, Fs)
        tot = np.maximum(ls + ld, 1e-12)
        within = 1.0 - np.exp(-tot * step)
        alpha = ls / tot * within
        acc = acc + surv * alpha
        # accumulate, do not overwrite: the survival entering step j is the product over ALL earlier
        # steps. Assigning here makes every step after the second reuse S^1, which inflates the sum
        # whenever S is close to 1 - the step ladder below is the check that catches it, and it caught
        # exactly this bug on first run (a 2.4% drift at four steps against a flat theory).
        surv = surv * np.exp(-tot * step)
    return acc


def main():
    horizon = float(P.flag("--horizon", "4"))
    reps = int(P.flag("--reps", "40"))
    B = int(P.flag("--boot", "500"))
    fracs = [float(x) for x in
             P.flag("--fractions", "0.02,0.05,0.10,0.25,0.50").split(",")]
    fset, time_mode = "common", "linear"

    pp = pd.read_csv(os.path.join(OUT, "personperiod_pooled.csv"))
    pp["country"] = pp["cohort"].map(I.COH2CTRY)
    pp = pp[pp["country"].notna()].reset_index(drop=True)
    panels = sorted(set(pp["country"]))
    X = I.design(pp, fset, time_mode)
    y_stroke = pp["event"].astype(int).values
    y_death = pp["end_status"].isin(P.DEATH).astype(int).values
    link, lmode, comp = P.VARIANTS[VAR]
    assert lmode == "offset", "the exact composition is defined for the offset arms only"

    FITS = {}
    for held in panels:
        tr = (pp["country"].values != held)
        FITS[held] = (IC.IcFit(X.loc[tr], y_stroke[tr], link, lmode, 1.0),
                      IC.IcFit(X.loc[tr], y_death[tr], link, lmode, 1.0))
        ms, md = FITS[held]
        print(f"fitted {held}: stroke conv={ms.converged} it={ms.n_iter} "
              f"| death conv={md.converged} it={md.n_iter}", flush=True)

    rows, paired, ladder, diag = [], [], [], {}
    audit = []
    for rule in RULES:
        base_frame, hcounts = I.horizon_frame(pp, horizon, rule)
        print(f"\n########## event/death timing convention: {rule}", flush=True)
        for held in panels:
            tr = (pp["country"].values != held)
            step_L = round(float(np.median(pp.loc[tr, "exposure_years"])) * 4) / 4
            step = horizon / max(1, int(round(horizon / step_L)))
            hb = base_frame[base_frame["country"] == held].reset_index(drop=True)
            yb = hb["label"].astype(int).values
            wb = pd.to_numeric(hb["ipcw"], errors="coerce").fillna(1.0).to_numpy(dtype=float)
            pid = hb["pid"].values
            upid = np.unique(pid)
            ms, md = FITS[held]
            p4 = P.compose_two(ms, md, hb, horizon, time_mode, fset, step, True)
            p5 = compose_exact(ms, md, hb, horizon, time_mode, fset, step)
            lam = P.closed_form_cif(ms, md, hb, horizon, time_mode, fset)
            # the exclusivity term, measured on the real fitted rows at the step length actually
            # used by the composition: per-step p_s*p_d
            Fs1 = hb.copy(); Fs1["exposure_years"] = step
            D1 = I.design(Fs1, fset, time_mode).reindex(columns=ms.cols)
            ls1, _ = cause_rates(ms, D1)
            ld1, _ = cause_rates(md, D1)
            ps1 = 1.0 - np.exp(-ls1 * step)
            pd1 = 1.0 - np.exp(-ld1 * step)
            excl = float(np.mean(ps1 * pd1))
            m4 = P.metrics(yb, p4, wb, full=True)
            m5 = P.metrics(yb, p5, wb, full=True)
            rng = np.random.default_rng(SEED + 9000)
            c4 = P.boot_ci(yb, p4, wb, pid, B, rng) if rule == RULES[0] else {}
            rng2 = np.random.default_rng(SEED + 9001)
            c5 = P.boot_ci(yb, p5, wb, pid, B, rng2) if rule == RULES[0] else {}
            for tag, mm, ci in (("V4_shipped_product", m4, c4), ("V5_exact_exclusive", m5, c5)):
                rows.append(dict(horizon_rule=rule, held=held, composition_arm=tag, variant=VAR,
                                 strategy="frozen_all", frac=0.0, rep=0, step_years=step,
                                 local_persons=0, **mm,
                                 ci_auroc_lo=ci.get("auroc", [np.nan, np.nan])[0],
                                 ci_auroc_hi=ci.get("auroc", [np.nan, np.nan])[1],
                                 ci_po_lo=ci.get("pred_over_obs", [np.nan, np.nan])[0],
                                 ci_po_hi=ci.get("pred_over_obs", [np.nan, np.nan])[1],
                                 ci_nb_lo=ci.get("nb_at_05", [np.nan, np.nan])[0],
                                 ci_nb_hi=ci.get("nb_at_05", [np.nan, np.nan])[1]))
            # the ladder: is the corrected composition exact at every step size?
            for tag, fn in (("V4_shipped_product", P.compose_two), ("V5_exact_exclusive",
                                                                      compose_exact)):
                vals = {}
                idx = np.random.default_rng(SEED + 11).choice(len(hb), size=min(3000, len(hb)),
                                                              replace=False)
                sub = hb.iloc[idx]
                for n in (1, 2, 4, 8):
                    if tag == "V4_shipped_product":
                        v = fn(ms, md, sub, horizon, time_mode, fset, horizon / n, True,
                               fixed_covariates=True)
                    else:
                        v = fn(ms, md, sub, horizon, time_mode, fset, horizon / n,
                               fixed_covariates=True)
                    vals[n] = float(v.mean())
                ana = float(P.closed_form_cif(ms, md, sub, horizon, time_mode,
                                              fset).mean())
                for n in (1, 2, 4, 8):
                    ladder.append(dict(horizon_rule=rule, held=held, composition_arm=tag,
                                       n_steps=n, step_years=horizon / n,
                                       mean_risk=vals[n], analytic_cif=ana,
                                       ratio_over_1=vals[n] / max(vals[1], 1e-12),
                                       ratio_over_analytic=vals[n] / max(ana, 1e-12)))
            diag[f"{rule}|{held}"] = {
                "step_years": step, "mean_p_s_step": float(np.mean(ps1)),
                "mean_p_d_step": float(np.mean(pd1)),
                "mean_exclusivity_term_p_s_p_d": excl,
                "survival_product_vs_exact_gap": float(np.max(np.abs(
                    (1 - ps1) * (1 - pd1) - np.exp(-(ls1 + ld1) * step)))),
                "prob_mass_p_plus_q_plus_S": float(np.mean(ps1 + pd1 + (1 - ps1) * (1 - pd1))),
                "V4_mean_pred": round(m4["mean_pred"], 6),
                "V5_mean_pred": round(m5["mean_pred"], 6),
                "rel_change_pct": round(100 * (m5["mean_pred"] / m4["mean_pred"] - 1), 3),
                "V4_pred_over_obs": round(m4["pred_over_obs"], 4),
                "V5_pred_over_obs": round(m5["pred_over_obs"], 4),
                "repair_V5_gain_at_05": None}
            print(f"  {held}: V4 P/O {m4['pred_over_obs']:.4f} -> V5 {m5['pred_over_obs']:.4f}"
                  f" ({100*(m5['mean_pred']/m4['mean_pred']-1):+.2f}% predicted mass);"
                  f" sum p_s+p_d+S = {diag[f'{rule}|{held}']['prob_mass_p_plus_q_plus_S']:.6f}",
                  flush=True)

            # ---- the repair, under the corrected composition, on disjoint persons
            for frac in fracs:
                gains, repl, rep_po = [], [], []
                for rep_i in range(reps):
                    rng3 = np.random.default_rng(SEED + 7000 + 1000 * rep_i + int(100 * frac))
                    take = max(2, int(round(len(upid) * frac)))
                    pick = rng3.choice(upid, size=take, replace=False)
                    locm, evm = np.isin(pid, pick), ~np.isin(pid, pick)
                    assert not set(pid[locm]) & set(pid[evm]), "local and eval share a person"
                    audit.append(dict(rule=rule, held=held, frac=frac, rep=rep_i,
                                      n_local=int(locm.sum()), n_eval=int(evm.sum()),
                                      overlap=int(len(set(pid[locm]) & set(pid[evm])))))
                    if len(np.unique(yb[locm])) < 2 or len(np.unique(yb[evm])) < 2:
                        continue
                    a = IC.fit_offset_space(p5[locm], yb[locm], "logit")
                    lo = np.log(np.clip(p5[evm], 1e-12, 1 - 1e-12) /
                                (1 - np.clip(p5[evm], 1e-12, 1 - 1e-12)))
                    pr = np.clip(1.0 / (1.0 + np.exp(-(lo + a))), 0.0, 1.0)
                    for strat, pv, sh in (("frozen_sub", p5[evm], 0.0), ("offset_logit", pr, a)):
                        mm = P.metrics(yb[evm], pv, wb[evm])
                        rows.append(dict(horizon_rule=rule, held=held,
                                         composition_arm="V5_exact_exclusive", variant=VAR,
                                         strategy=strat, frac=frac, rep=rep_i, step_years=step,
                                         local_persons=int(locm.sum()), mean_repair_shift=sh, **mm,
                                         ci_auroc_lo=np.nan, ci_auroc_hi=np.nan, ci_po_lo=np.nan,
                                         ci_po_hi=np.nan, ci_nb_lo=np.nan, ci_nb_hi=np.nan))
                        if strat == "offset_logit":
                            mf = P.metrics(yb[evm], p5[evm], wb[evm])
                            gains.append(mm["nb_at_05"] - mf["nb_at_05"])
                            repl.append(mm["nb_at_05"]); rep_po.append(mm["pred_over_obs"])
                g, r, rp = np.asarray(gains), np.asarray(repl), np.asarray(rep_po)
                if not len(g):
                    continue
                paired.append(dict(horizon_rule=rule, held=held, variant=VAR, frac=frac,
                                   composition_arm="V5_exact_exclusive",
                                   n_complete_reps=int(len(g)),
                                   mean_gain_nb_at_05=float(g.mean()),
                                   sd_gain_nb_at_05=float(g.std(ddof=1)) if len(g) > 1 else 0.0,
                                   lo_gain_nb_at_05=float(np.percentile(g, 2.5)),
                                   hi_gain_nb_at_05=float(np.percentile(g, 97.5)),
                                   n_gain_positive=int((g > 0).sum()),
                                   n_repaired_nb_above_treat_none=int((r > 0).sum()),
                                   n_repaired_nb_tied_treat_none=int((r == 0).sum()),
                                   n_repaired_nb_below_treat_none=int((r < 0).sum()),
                                   max_nb_above_treat_none=float(r.max()),
                                   mean_repaired_pred_over_obs=float(rp.mean()),
                                   sd_repaired_pred_over_obs=float(rp.std(ddof=1))))
                if rule == "cif_mid" and held == "MX" and abs(frac - 0.05) < 1e-9:
                    diag[f"{rule}|{held}"]["repair_V5_gain_at_05"] = float(g.mean())

    R = pd.DataFrame(rows)
    R.to_csv(os.path.join(OUT, "incident_cr_exact.csv"), index=False)
    PA = pd.DataFrame(paired)
    PA.to_csv(os.path.join(OUT, "incident_cr_exact_paired.csv"), index=False)
    LA = pd.DataFrame(ladder)
    LA.to_csv(os.path.join(OUT, "incident_cr_exact_ladder.csv"), index=False)

    ov = pd.DataFrame(audit)
    published = os.path.join(os.path.abspath(os.path.join(HERE, "..", "..", "..")),
                             "results", "tables", f"incident_cr_primary_{DAY}.csv")
    checks = []
    if os.path.exists(published):
        d = pd.read_csv(published)
        d = d[(d.horizon_rule == "cif_mid") & (d.strategy == "frozen_all") & (d.variant == VAR)]
        here = R[(R.horizon_rule == "cif_mid") & (R.composition_arm == "V4_shipped_product")
                 & (R.strategy == "frozen_all")]
        bad = []
        for _, rr in here.iterrows():
            q = d[d.held == rr.held]
            for k in ("mean_pred", "pred_over_obs", "auroc", "nb_at_05"):
                if abs(float(q[k].iloc[0]) - float(rr[k])) > 1e-6:
                    bad.append(f"{rr.held}.{k}: published {float(q[k].iloc[0]):.6f} vs "
                               f"reproduced {float(rr[k]):.6f}")
        checks.append({"name": "V4 recomposition reproduces the published primary frozen rows "
                              "(so only the composition differs, not the estimation)",
                       "n_cells": int(len(here)), "n_mismatches": len(bad), "detail": bad[:12]})
        print(f"\nREPLICATION CHECK (V4 vs published primary): {len(here)} cells, {len(bad)} "
              f"mismatches -> {'PASS' if not bad else 'FAIL: ' + '; '.join(bad[:3])}", flush=True)
    lad = LA[LA.horizon_rule == "cif_mid"]
    flat = []
    for tag, g in lad.groupby("composition_arm"):
        rr = g.set_index("held").ratio_over_1
        flat.append((tag, float(rr.max()), float(rr.min())))
    checks.append({"name": "duration consistency of the step ladder (ratio of 8-step to 1-step risk)",
                   "by_arm": {t: [round(a, 9), round(b, 9)] for t, a, b in flat}})
    checks.append({"name": "adaptation/evaluation person overlap",
                   "overlap_total": int(ov.overlap.sum()), "rows_audited": int(len(ov))})
    report = {"generated_from": "incident_cr_exact.py", "horizon_years": horizon, "reps": reps,
              "boot": B, "fractions": fracs, "variant": VAR, "checks": checks,
              "diagnostics": diag,
              "algebra": {
                  "survival_factor": "(1-p_s)(1-p_d) = exp(-(lambda_s+lambda_d)D): correct for the "
                                     "probability that NEITHER event occurs, under independent latent "
                                     "times. NOT the same as 1-p_s-p_d, which would be right only if "
                                     "the two marginal event probabilities were mutually exclusive.",
                  "event_factor": "p_s = 1-exp(-lambda_s D) is the probability that A STROKE occurs in "
                                  "the step; the probability that the FIRST event is a stroke is "
                                  "lambda_s/(lambda_s+lambda_d)*(1-exp(-(lambda_s+lambda_d)D)); the "
                                  "marginal over-states it by p_s-alpha_s (death-first-within-step), "
                                  "which is NOT p_s*p_d; p_s*p_d=(p_s-alpha_s)+(p_d-alpha_d) is the "
                                  "total double-count.",
                  "consequence": "the shipped composition assigns total step probability "
                                 "1 + p_s*p_d > 1; V5 assigns exactly 1."}}
    with open(os.path.join(OUT, "incident_cr_exact_diagnostics.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=float)
    print(f"wrote {len(R)} rows, {len(PA)} paired, {len(LA)} ladder rows", flush=True)


if __name__ == "__main__":
    main()
