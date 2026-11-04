"""P0 audit: competing mortality, and what the four-year estimand actually is.

Why this exists
---------------
The manuscript predicts "probability of a first stroke within four years". The discrete-time model
composes hazards as 1 - prod(1 - h_stroke), which silently assumes the person is still alive to be
at risk at every step. In these panels that is not a small assumption: 4-year mortality is more
than twice 4-year stroke incidence (pooled CIF of death 0.051 against 0.020 for stroke). Two things
have to be measured rather than argued:

1. THE TARGET. P(stroke by H) with competing death is the Aalen-Johansen cumulative incidence,
   which is SMALLER than 1 - KM_stroke, the Kaplan-Meier complement that treats death as ordinary
   censoring. This script computes both, so the size of that error is a number and not a claim.

2. THE DATING. A stroke is only known to have happened BETWEEN two interviews. Dating it to the
   interval START counts an interval that straddles the horizon as an event inside the horizon;
   dating it to the END refuses to count it; the MIDPOINT is what the discrete-time composition
   implicitly assumes. All three are reported, because the calibration intercept - the single
   parameter the whole paper turns on - moves by more than the difference between any two models.

A pre-horizon death is treated as a NON-EVENT of the incidence estimand, not as missing data: a
person who died did not have a stroke within four years. Loss to follow-up is carried by IPCW.
Both of those live in `run_incident_loco.horizon_frame`, which this script calls rather than
reimplementing - two copies of a censoring-weight formula is how the first inconsistency was found.

Korea is the honest limit case: its nine wave workbooks hold no vital-status field at all, so every
Korean death is invisible to this design, its Aalen-Johansen incidence equals its Kaplan-Meier
complement by construction, and its event count is a lower bound. That is printed, not smoothed.

Outputs (data/processed/intl/incident/)
  incident_competing_risks_cif.csv     - Aalen-Johansen vs naive KM, per country, 3 dating rules
  incident_competing_risks_estimands.csv - every rule x estimand, model by model, with repair

Usage
  python incident_competing_risks.py [--horizon 4] [--models logistic,xgboost]
                                     [--rules cif_mid,exclusive_start]
                                     [--fractions 0.05,0.10,0.25] [--reps 10]
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

OUT = I.OUT
SEED = V2.SEED
# the three ways a panel dates an interval-censored first stroke
DATING = {"start": "t_stroke_start", "mid": "t_stroke_mid", "end": "t_stroke_end"}


def flag(name, default):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default


def logit(p):
    p = np.clip(np.asarray(p, dtype=float), 1e-9, 1 - 1e-9)
    return np.log(p / (1.0 - p))


def sigmoid(z):
    return 1.0 / (1.0 + np.exp(-z))


def aalen_johansen(pc, stroke_col, grid):
    """CIF of first stroke with death as a competing risk, plus the naive 1-KM complement that
    treats death as censoring. Same people, same times, so the gap between the two columns is the
    point of the table."""
    t_s = pc[stroke_col].to_numpy(dtype=float)
    t_d = pc["t_death"].to_numpy(dtype=float)
    t_c = pc["t_cens"].to_numpy(dtype=float)
    t_obs = np.fmin(np.fmin(t_s, t_d), t_c)
    order = np.argsort(t_obs, kind="stable")
    t_s, t_d, t_o = t_s[order], t_d[order], t_obs[order]
    n = len(t_o)
    surv, surv_km, cs, cd, ckm, i = 1.0, 1.0, 0.0, 0.0, 0.0, 0
    rows = []
    for gt in sorted(grid):
        while i < n and np.isfinite(t_o[i]) and t_o[i] <= gt:
            j = i
            while j < n and t_o[j] == t_o[i]:
                j += 1
            at_risk = n - i
            ds = int(np.sum(t_s[i:j] == t_o[i]))
            dd = int(np.sum(t_d[i:j] == t_o[i]))
            if at_risk > 0:
                cs += surv * ds / at_risk
                cd += surv * dd / at_risk
                ckm += surv_km * ds / at_risk          # deaths censored in the naive curve
                surv *= (1.0 - (ds + dd) / at_risk)
                surv_km *= (1.0 - ds / at_risk)
            i = j
        rows.append(dict(year=gt, persons=n, cif_stroke=cs, cif_death=cd, naive_km1_stroke=ckm))
    return rows


def main():
    horizon = float(flag("--horizon", "4"))
    models = flag("--models", "logistic,xgboost").split(",")
    rules = flag("--rules", "cif_mid,exclusive_start").split(",")
    fracs = [float(x) for x in flag("--fractions", "0.05,0.10,0.25").split(",")]
    reps = int(flag("--reps", "10"))
    fset, time_mode = "common", "linear"

    pp = pd.read_csv(os.path.join(OUT, "personperiod_pooled.csv"))
    pp["country"] = pp["cohort"].map(I.COH2CTRY)
    pp = pp[pp["country"].notna()].reset_index(drop=True)
    pc = I.person_clock(pp)

    # ---------------------------------------------------------------- 1. the target
    grid = [0.5, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0]
    cif_rows = []
    for dating, col in DATING.items():
        for country, sub in pc.groupby("country"):
            for r in aalen_johansen(sub, col, grid):
                r.update(country=country, censor_mode=sub["censor_mode"].iloc[0],
                         stroke_dating=dating)
                cif_rows.append(r)
        for r in aalen_johansen(pc, col, grid):
            r.update(country="POOLED", censor_mode="mixed", stroke_dating=dating)
            cif_rows.append(r)
    cif = pd.DataFrame(cif_rows)[["country", "stroke_dating", "year", "persons", "cif_stroke",
                                 "cif_death", "naive_km1_stroke", "censor_mode"]]
    cif["inflation_naive_minus_cif"] = cif["naive_km1_stroke"] - cif["cif_stroke"]
    cif["ratio_naive_over_cif"] = cif["naive_km1_stroke"] / cif["cif_stroke"].replace(0, np.nan)
    cif.to_csv(os.path.join(OUT, "incident_competing_risks_cif.csv"), index=False)
    at_h = cif[np.isclose(cif["year"], horizon)]
    print(f"=== cumulative incidence of FIRST STROKE within {horizon:g} years")
    print("    columns: AJ = Aalen-Johansen with competing death; naive = 1-KM treating death as")
    print("    censoring; dating = which end of the interview interval the stroke is attributed to")
    print(at_h.pivot_table(index="country", columns="stroke_dating", values="cif_stroke").round(5)
          .to_string())
    print(at_h.pivot_table(index="country", columns="stroke_dating",
                           values="naive_km1_stroke").round(5).to_string())
    print(at_h.pivot_table(index="country", columns="stroke_dating",
                           values="cif_death").round(5).to_string())
    print("    naive/AJ inflation at the midpoint dating, by country:")
    print(at_h[at_h["stroke_dating"] == "mid"][["country", "naive_km1_stroke", "cif_stroke",
                                                "ratio_naive_over_cif"]].round(5).to_string(index=False))

    # ---------------------------------------------------------------- 2. estimand x model
    X = I.design(pp, fset, time_mode)
    y = pp["event"].astype(int).values
    rows = []
    for rule in rules:
        frame, counts = I.horizon_frame(pp, horizon, rule)
        print(f"\n=== estimand {rule}: {json.dumps(counts)}", flush=True)
        for country in sorted(frame["country"].dropna().unique()):
            tr = (pp["country"].values != country)
            step_L = round(float(np.median(pp.loc[tr, "exposure_years"])) * 4) / 4
            hb = frame[frame["country"] == country].reset_index(drop=True)
            yb = hb["label"].astype(int).to_numpy()
            wb = pd.to_numeric(hb["ipcw"], errors="coerce").fillna(1.0).to_numpy(dtype=float)
            pid = hb["pid"].to_numpy()
            for name in models:
                frozen = I.Frozen(X.loc[tr], y[tr], name)
                ph, realised = I.horizon_risk(A.Adapter(frozen, 0.0, 1.0), hb, horizon, time_mode,
                                              fset, step=step_L)
                base = dict(estimand=rule, country=country, model=name, frac=0.0, rep=0,
                            censor_mode=hb["censor_mode"].iloc[0], realised_years=realised,
                            step_years=step_L, local_persons=0, n_eval=int(len(yb)),
                            strategy="frozen", offset_intercept=0.0,
                            mean_pred_unrepaired=float(I.w_mean(yb, ph, wb)))
                rows.append(dict(**base, **weighted_metrics(yb, ph, wb)))
                lp = logit(ph)
                for frac in fracs:
                    for rep in range(reps):
                        rng = np.random.default_rng(SEED + 5000 + 1000 * rep + int(100 * frac))
                        up = np.unique(pid)
                        pick = rng.choice(up, size=max(2, int(round(len(up) * frac))),
                                          replace=False)
                        loc = np.isin(pid, pick)
                        evm = ~loc
                        if yb[loc].sum() < 1 or len(np.unique(yb[evm])) < 2:
                            continue
                        a, _ = fit_offset_weighted(lp[loc], yb[loc], wb[loc])
                        cm = dict(base, frac=frac, rep=rep, local_persons=int(loc.sum()),
                                 n_eval=int(evm.sum()), offset_intercept=float(a),
                                 strategy="offset_horizon")
                        rows.append(dict(cm, **weighted_metrics(yb[evm], sigmoid(lp[evm] + a),
                                                               wb[evm])))
                        rows.append(dict(cm, strategy="frozen_same_rows", offset_intercept=0.0,
                                         **weighted_metrics(yb[evm], ph[evm], wb[evm])))
    out = pd.DataFrame(rows)
    out.to_csv(os.path.join(OUT, "incident_competing_risks_estimands.csv"), index=False)
    fz = out[out["strategy"] == "frozen_same_rows"]
    rp = out[out["strategy"] == "offset_horizon"]
    k = ["estimand", "country", "model", "frac", "rep", "local_persons"]
    fz2 = fz.set_index(k)
    rp = rp.merge(fz2[["nb_at_05", "oe_ratio", "mean_pred"]].rename(
        columns={"nb_at_05": "nb_frozen", "oe_ratio": "oe_frozen",
                 "mean_pred": "mean_pred_frozen"}), on=k, how="left", validate="one_to_one")
    rp.to_csv(os.path.join(OUT, "incident_competing_risks_estimands_paired.csv"), index=False)
    rp["nb_gain"] = rp["nb_at_05"] - rp["nb_frozen"]
    print("\n=== frozen four-year risk against each estimand (mean over replicates)")
    show = out[out["strategy"] == "frozen"].pivot_table(
        index=["estimand", "country"], columns="model",
        values=["prevalence", "mean_pred", "oe_ratio", "recal_slope", "auroc", "nb_at_05",
                "nb_all_at_05"], aggfunc="mean")
    print(show.round(4).to_string())
    print("\n=== paired gain from the one intercept, by estimand")
    print(rp.pivot_table(index=["estimand", "country"], columns=["model", "frac"],
                         values=["oe_frozen", "oe_ratio", "nb_gain"],
                         aggfunc="mean").round(5).to_string())
    return cif, out, rp


def fit_offset_weighted(lp, y, w):
    """Intercept-only correction that matches the WEIGHTED mean predicted risk to the weighted
    observed risk; slope pinned at 1. Returns (a, 1.0) so it can stand in for
    incident_adaptation.fit_offset wherever the estimand carries IPCW weights."""
    s = float(np.sum(w))
    q = float(np.sum(w * y) / s) if s > 0 else 0.0
    if not (0 < q < 1):
        return 0.0, 1.0
    lo, hi = -12.0, 12.0
    for _ in range(80):
        mid = (lo + hi) / 2.0
        if float(np.sum(w * sigmoid(lp + mid)) / s) < q:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2.0, 1.0


def weighted_metrics(yb, ph, w):
    from sklearn.metrics import roc_auc_score, brier_score_loss
    yb = np.asarray(yb).astype(int); ph = np.asarray(ph, dtype=float)
    weighted = bool(np.any(np.abs(w - 1.0) > 1e-12))
    q = I.w_mean(yb, yb, w)
    b = float(np.sum(w * (ph - yb) ** 2) / np.sum(w))
    mp = I.w_mean(yb, ph, w)
    ri, rs = I.weighted_recal(yb, ph, w)
    return dict(n=len(yb), events=int((w * yb).sum()), prevalence=q,
                prevalence_unweighted=float(yb.mean()), mean_pred=mp,
                mean_pred_unweighted=float(ph.mean()),
                oe_ratio=float(mp / q) if q else np.nan, brier=b,
                scaled_brier=float((q * (1 - q) - b) / (q * (1 - q))) if 0 < q < 1 else np.nan,
                recal_intercept=ri, recal_slope=rs,
                auroc=float(roc_auc_score(yb, ph, sample_weight=w if weighted else None)),
                nb_at_05=I.weighted_net_benefit(yb, ph, w, 0.05),
                nb_all_at_05=I.weighted_net_benefit(yb, np.ones(len(yb)), w, 0.05),
                flagged_at_05=float(np.sum(w * (ph >= 0.05)) / np.sum(w)),
                median_ipcw_weight=float(np.median(w)))


if __name__ == "__main__":
    main()
