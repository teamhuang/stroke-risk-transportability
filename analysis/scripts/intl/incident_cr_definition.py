"""P1-5: does Mexico's over-prediction survive a refit on strictly-verified comparable variables?

The question this arm answers, and the only question that matters for it:

    Is the Mexican level gap a RISK difference the model gets wrong, or a MEASUREMENT difference the
    four panels' questionnaires cannot express?

The primary "common" feature set is already the intersection of what every panel asks - income,
measured BMI and cholesterol are excluded from it for exactly that reason. But two concepts inside
that intersection are asked ABOUT DIFFERENT THINGS in different countries, and harmonisation cannot
fix a question, only a code:

    heart_attack  "ever had heart problems" in the US and China, a specific heart-attack /
                    myocardial-infarction item in Korea and Mexico
    alcohol       "ever drinks any alcohol" in the US, a last-year item in China

So the ablation drops them and refits everything - both cause-specific hazards, both compositions,
the local intercept repair - from scratch. A stricter third tier additionally drops the items whose
AVAILABILITY rather than meaning differs (hypertension, missing on 29.1% of Korean interval rows;
marital status, 16.1%), which is a missingness stress test rather than a definitional one and is
reported as such.

What would weaken the paper: if Mexico's predicted/observed ratio fell from ~3.0 toward 1.0 when the
two non-comparable items left the model, then the headline level error is an artefact of how the four
questionnaires describe cardiac disease and drinking, not a transportable miscalibration, and the
recalibration story becomes a data-processing story. What would strengthen it: the ratio stays where
it is, because a level error driven by an intercept the source panels estimate too high is a property
of the risk model's centre, and two binary covariates with small coefficients cannot move it threefold.

Design notes
  * Reuses `incident_cr_primary`'s composition, metric and bootstrap functions unchanged, so the only
    difference between this arm and the paper's primary absolute-risk arm is the column list.
  * The `common` tier is refitted here even though it is already published, as a replication check:
    it must reproduce the published frozen rows. If it does not, this script's design() path changed
    and every number in this file is suspect.
  * One event-timing convention (`cif_mid`, the manuscript's primary) rather than three; the dating
    sensitivity is already measured in the primary arm and does not interact with the column list.
  * Local adaptation samples are person-disjoint from evaluation samples and asserted so, exactly as
    in the primary arm.
  * Treat-none net benefit is exactly zero, so the repair is counted three ways - above / exactly tied
    / below - never as a binary (docs/SELF_AUDIT.md defect 25).

Usage
  python incident_cr_definition.py [--horizon 4] [--reps 20] [--boot 200]
                                   [--fsets common,core,core_strict]
Outputs (data/processed/intl/incident/)
  incident_cr_definition.csv            one row per fset x panel x variant x strategy x rep
  incident_cr_definition_paired.csv     paired repair effects with the three-way treat-none split
  incident_cr_definition_missingness.csv per-panel missingness of every item the ablation touches
"""
import os, sys, json, warnings
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)
import modeling as M                                    # noqa: E402
import run_loco_v2 as V2                                # noqa: E402
import run_incident_loco as I                            # noqa: E402
import incident_ic_grid as IC                            # noqa: E402
import incident_cr_primary as P                          # noqa: E402

OUT = P.OUT
SEED = P.SEED
RULE = "cif_mid"
VARNAME = ["V1_logit_cause_specific", "V4_ph_competing"]


def flag(name, default):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default


def main():
    horizon = float(flag("--horizon", "4"))
    reps = int(flag("--reps", "20"))
    B = int(flag("--boot", "200"))
    fsets = flag("--fsets", "common,core,core_strict").split(",")
    fracs = [float(x) for x in flag("--fractions", "0.02,0.05").split(",")]

    pp = pd.read_csv(os.path.join(OUT, "personperiod_pooled.csv"))
    pp["country"] = pp["cohort"].map(I.COH2CTRY)
    pp = pp[pp["country"].notna()].reset_index(drop=True)
    panels = sorted(set(pp["country"]))

    # ---------------------------------------------------------------- the justification table
    items = ["age", "sex", "education", "marital", "ever_smoker", "current_smoker", "alcohol",
             "hypertension", "diabetes", "heart_attack"]
    miss = {}
    for v in items:
        s = pd.to_numeric(pp[v], errors="coerce")
        miss[v] = s.isna().groupby(pp["cohort"]).mean()
    miss = (pd.DataFrame(miss).T * 100).round(2)
    miss.to_csv(os.path.join(OUT, "incident_cr_definition_missingness.csv"))
    print("share of interval rows MISSING (%), the measured basis for each ablation tier:")
    print(miss.to_string(), flush=True)

    base_frame, hcounts = I.horizon_frame(pp, horizon, RULE)
    print(f"\nhorizon frame ({RULE}): " + json.dumps(hcounts, default=str)[:600], flush=True)

    rows, paired, diag = [], [], {}
    for fset in fsets:
        X = I.design(pp, fset, "linear")
        cols = list(X.columns)
        n_drop = len(I.design(pp, "common", "linear").columns) - len(cols)
        print(f"\n########## feature set {fset!r}: {len(cols)} columns "
              f"({n_drop} fewer than the published primary arm)", flush=True)
        y_stroke = pp["event"].astype(int).values
        y_death = pp["end_status"].isin(P.DEATH).astype(int).values
        fits = {}
        for held in panels:
            tr = (pp["country"].values != held)
            fits[held] = {}
            for vn in VARNAME:
                link, lmode, comp = P.VARIANTS[vn]
                ms = IC.IcFit(X.loc[tr], y_stroke[tr], link, lmode, 1.0)
                md = IC.IcFit(X.loc[tr], y_death[tr], link, lmode, 1.0)
                fits[held][vn] = (ms, md, comp)
                print(f"  fitted {held} {vn}: stroke conv={ms.converged} it={ms.n_iter}"
                      f" | death conv={md.converged} it={md.n_iter}", flush=True)
        for held in panels:
            tr = (pp["country"].values != held)
            step_L = round(float(np.median(pp.loc[tr, "exposure_years"])) * 4) / 4
            step = horizon / max(1, int(round(horizon / step_L)))
            hb = base_frame[base_frame["country"] == held].reset_index(drop=True)
            yb = hb["label"].astype(int).values
            wb = pd.to_numeric(hb["ipcw"], errors="coerce").fillna(1.0).to_numpy(dtype=float)
            pid = hb["pid"].values
            upid = np.unique(pid)
            for vn in VARNAME:
                ms, md, comp = fits[held][vn]
                link, lmode, _ = P.VARIANTS[vn]
                ph = P.compose_two(ms, md, hb, horizon, "linear", fset, step, comp)
                m = P.metrics(yb, ph, wb, full=True)
                rng = np.random.default_rng(SEED + 9000)
                ci = P.boot_ci(yb, ph, wb, pid, B, rng)
                rows.append(dict(fset=fset, horizon_rule=RULE, held=held, variant=vn,
                                 composition=("competing_risks_CIF" if comp
                                              else "cause_specific_only"),
                                 strategy="frozen_all", frac=0.0, rep=0, step_years=step,
                                 local_persons=0, n_features=len(cols), **m,
                                 ci_po_lo=ci["pred_over_obs"][0], ci_po_hi=ci["pred_over_obs"][1],
                                 ci_auroc_lo=ci["auroc"][0], ci_auroc_hi=ci["auroc"][1],
                                 ci_nb_lo=ci["nb_at_05"][0], ci_nb_hi=ci["nb_at_05"][1]))
                diag[f"{fset}|{held}|{vn}"] = {
                    "converged_stroke": bool(ms.converged), "converged_death": bool(md.converged),
                    "n_features": len(cols),
                    "mean_pred": round(m["mean_pred"], 5), "obs_prev": round(m["obs_prev"], 5),
                    "pred_over_obs": round(m["pred_over_obs"], 4),
                    "ci_pred_over_obs": [round(ci["pred_over_obs"][0], 3),
                                         round(ci["pred_over_obs"][1], 3)]}
                rep_nb = {}
                for frac in fracs:
                    gains, repl, rep_po = [], [], []
                    for rep_i in range(reps):
                        rng2 = np.random.default_rng(SEED + 7000 + 1000 * rep_i + int(100 * frac))
                        take = max(2, int(round(len(upid) * frac)))
                        pick = rng2.choice(upid, size=take, replace=False)
                        locm, evm = np.isin(pid, pick), ~np.isin(pid, pick)
                        assert not set(pid[locm]) & set(pid[evm]), "local and eval share a person"
                        if len(np.unique(yb[locm])) < 2 or len(np.unique(yb[evm])) < 2:
                            continue
                        a = IC.fit_offset_space(ph[locm], yb[locm], "logit")
                        lo = np.log(np.clip(ph[evm], 1e-12, 1 - 1e-12) /
                                    (1 - np.clip(ph[evm], 1e-12, 1 - 1e-12)))
                        pr = np.clip(1.0 / (1.0 + np.exp(-(lo + a))), 0.0, 1.0)
                        mf = P.metrics(yb[evm], ph[evm], wb[evm])
                        mr = P.metrics(yb[evm], pr, wb[evm])
                        for strat, mm, sh in (("frozen_sub", mf, 0.0), ("offset_logit", mr, a)):
                            rows.append(dict(fset=fset, horizon_rule=RULE, held=held, variant=vn,
                                             composition=("competing_risks_CIF" if comp
                                                          else "cause_specific_only"),
                                             strategy=strat, frac=frac, rep=rep_i,
                                             step_years=step, local_persons=int(locm.sum()),
                                             n_features=len(cols), mean_repair_shift=sh, **mm,
                                             ci_po_lo=np.nan, ci_po_hi=np.nan,
                                             ci_auroc_lo=np.nan, ci_auroc_hi=np.nan,
                                             ci_nb_lo=np.nan, ci_nb_hi=np.nan))
                        gains.append(mr["nb_at_05"] - mf["nb_at_05"])
                        repl.append(mr["nb_at_05"])
                        rep_po.append(mr["pred_over_obs"])
                    g = np.asarray(gains); r = np.asarray(repl)
                    rep_po = np.asarray(rep_po)
                    if not len(g):
                        continue
                    paired.append(dict(fset=fset, held=held, variant=vn, frac=frac,
                                       n_complete_reps=int(len(g)),
                                       mean_gain_nb_at_05=float(g.mean()),
                                       sd_gain_nb_at_05=float(g.std(ddof=1)) if len(g) > 1 else 0.0,
                                       n_gain_positive=int((g > 0).sum()),
                                       n_nb_above_treat_none=int((r > 0).sum()),
                                       n_nb_tied_treat_none=int((r == 0).sum()),
                                       n_nb_below_treat_none=int((r < 0).sum()),
                                       max_nb_above_treat_none=float(r.max()),
                                       mean_repaired_pred_over_obs=float(rep_po.mean())))
                    rep_nb[frac] = float(g.mean())
                diag[f"{fset}|{held}|{vn}"]["repair_mean_gain_by_frac"] = {
                    str(k): round(v, 6) for k, v in rep_nb.items()}

    R = pd.DataFrame(rows)
    R.to_csv(os.path.join(OUT, "incident_cr_definition.csv"), index=False)
    PA = pd.DataFrame(paired)
    PA.to_csv(os.path.join(OUT, "incident_cr_definition_paired.csv"), index=False)

    # ---------------------------------------------------------------- replication check
    checks = []
    published = os.path.join(os.path.abspath(os.path.join(HERE, "..", "..", "..")),
                             "results", "tables", "incident_cr_primary_2026-11-03.csv")
    if "common" in fsets and os.path.exists(published):
        d = pd.read_csv(published)
        d = d[(d.horizon_rule == RULE) & (d.strategy == "frozen_all")]
        here = R[(R.fset == "common") & (R.strategy == "frozen_all")]
        bad = []
        for _, rr in here.iterrows():
            q = d[(d.held == rr.held) & (d.variant == rr.variant)]
            if not len(q):
                bad.append(f"{rr.held}/{rr.variant}: absent from the published table")
                continue
            for k in ("mean_pred", "obs_prev", "pred_over_obs", "auroc", "nb_at_05"):
                if abs(float(q[k].iloc[0]) - float(rr[k])) > 1e-6:
                    bad.append(f"{rr.held}/{rr.variant}.{k}: "
                               f"{float(q[k].iloc[0]):.6f} published vs {float(rr[k]):.6f} here")
        checks.append({"name": "common tier reproduces the published primary frozen rows",
                       "n_cells": int(len(here)), "n_mismatches": len(bad), "detail": bad[:12]})
        print(f"\nREPLICATION CHECK (common tier vs published primary): "
              f"{len(here)} cells, {len(bad)} mismatches "
              f"-> {'PASS' if not bad else 'FAIL: ' + '; '.join(bad[:4])}", flush=True)

    report = {"generated_from": "incident_cr_definition.py", "horizon_years": horizon,
              "horizon_rule": RULE, "reps": reps, "boot": B, "fractions": fracs,
              "feature_columns": {f: list(I.design(pp.head(50), f, "linear").columns)
                                  for f in fsets},
              "definition_drops": {k: v for k, v in I.DEFINITION_DROPS.items()},
              "per_panel_missingness_pct": json.loads(miss.to_json()),
              "checks": checks, "diagnostics": diag}
    with open(os.path.join(OUT, "incident_cr_definition_diagnostics.json"), "w",
              encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=float)
    print(f"\nwrote {len(R)} rows, {len(PA)} paired rows, diagnostics + missingness to "
          f"{OUT}", flush=True)


if __name__ == "__main__":
    main()
