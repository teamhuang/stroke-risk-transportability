"""P1: smooth calibration curves with a person-clustered bootstrap band (the decile table, smoothed).

incident_calibration_curves.py publishes a decile table with a person-clustered bootstrap interval on
each observed decile. The reviewer asked for the continuous object that table approximates: a smooth
calibration curve - observed risk as a flexible function of predicted risk (the "calibration
hierarchy" mean-calibration curve) - with an honest band, for the frozen transferred model AND for the
model after the one-parameter local intercept update that a new country would actually fit, so the
question "the panel-average ratio is ~1 - but is the HIGH-RISK TAIL still wrong?" can be read directly
rather than inferred from one number.

Method
  * predictions: the frozen logistic discrete-time hazard, cif_mid, `common` features (same arm as the
    decile figure and Table 12). One row per evaluable person.
  * smooth curve: a cubic regression-spline logistic fit of the label on the model's linear predictor,
    y ~ cr(lp, df=4), weighted by the IPCW weight. Evaluated on a grid of predicted risk. This is the
    flexible version of the calibration slope (df = 2 would be the ordinary slope; df = 1 is the level).
  * band: person-clustered bootstrap (resample whole persons, refit the spline) at B draws, pointwise
    2.5/97.5 percentiles. The ideal line is y = x.
  * repair: the deployable one-intercept update, its shift `a_bar` the mean over adaptation/evaluation
    splits at 5% local data (persons disjoint from the evaluation rows, asserted), exactly as the
    decile figure fits it. The repaired curve re-smooths observed risk against the SHIFTED predictor,
    so it shows the residual SHAPE after the level has been corrected.

Outputs
  deliverables/figures/incident/incident_calibration_smooth.{png,pdf}   (2 x 2, one panel per country)
  data/processed/intl/incident/incident_calibration_smooth.csv          the curve grid (for the text)
"""
import os, sys, warnings
import numpy as np
import pandas as pd
warnings.filterwarnings("ignore")
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from patsy import dmatrix
import statsmodels.api as sm

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE)); sys.path.insert(0, HERE)
import run_loco_v2 as V2
import run_incident_loco as I
import incident_horizon_recalibration as HR
import incident_update_policy as UP

OUT = I.OUT
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
FIGD = os.path.join(ROOT, "deliverables", "figures", "incident"); os.makedirs(FIGD, exist_ok=True)
SEED = V2.SEED
logit, expit = HR.logit, UP.sigmoid

plt.rcParams.update({"font.family": "sans-serif", "font.sans-serif": ["Arial", "DejaVu Sans"],
                     "pdf.fonttype": 42, "ps.fonttype": 42, "font.size": 7,
                     "axes.spines.top": False, "axes.spines.right": False,
                     "axes.grid": True, "grid.alpha": .25, "grid.linestyle": "--",
                     "figure.dpi": 300})
OI = {"blue": "#0072B2", "orange": "#E69F00", "green": "#009E73", "verm": "#D55E00",
      "grey": "#999999", "black": "#222222"}
CTRY = {"CN": "China", "KR": "Korea", "MX": "Mexico", "US": "United States"}


def flag(name, default):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default


def wmean(x, w):
    s = float(np.sum(w)); return float(np.sum(np.asarray(x, float) * w) / s) if s > 0 else np.nan


def smooth_curve(y, w, lp, grid_lp):
    """Spline calibration: y ~ cr(lp, df=4); predicted observed risk at grid_lp."""
    Xb = dmatrix("cr(x, df=4)", {"x": lp}, return_type="dataframe")
    Xg = dmatrix("cr(x, df=4)", {"x": grid_lp}, return_type="dataframe")
    # patsy needs the same column set for the grid; cr(...) is basis of x only, so align
    Xg = Xg.reindex(columns=Xb.columns)
    res = sm.GLM(np.asarray(y, float), np.asarray(Xb, float), family=sm.families.Binomial(),
                 freq_weights=np.asarray(w, float)).fit()
    return np.asarray(res.predict(np.asarray(Xg, float)), float)


def main():
    horizon = float(flag("--horizon", "4"))
    rule = flag("--rule", "cif_mid")
    B = int(flag("--boot", "200"))
    frac = float(flag("--frac", "0.05"))
    splits = int(flag("--splits", "120"))

    pp = pd.read_csv(os.path.join(OUT, "personperiod_pooled.csv"))
    pp["country"] = pp["cohort"].map(I.COH2CTRY)
    pp = pp[pp["country"].notna()].reset_index(drop=True)
    X = I.design(pp, "common", "linear")
    y = pp["event"].astype(int).values
    base, hcount = I.horizon_frame(pp, horizon, rule)
    print(f"smooth calibration | rule={rule} boot={B} frac={frac} splits={splits}", flush=True)

    grid_rows = []
    fig, axs = plt.subplots(2, 2, figsize=(2 * 5.5 / 2.54, 2 * 5.5 / 2.54))
    for ax, held in zip(axs.ravel(), ["CN", "KR", "MX", "US"]):
        tr = (pp["country"].values != held)
        step_L = round(float(np.median(pp.loc[tr, "exposure_years"])) * 4) / 4
        hb = base[base["country"] == held].reset_index(drop=True)
        yb = hb["label"].astype(int).values.astype(float)
        wb = pd.to_numeric(hb["ipcw"], errors="coerce").fillna(1.0).to_numpy(float)
        pid = hb["pid"].values; upid = np.unique(pid)
        fr = I.Frozen(X.loc[tr], y[tr], "logistic")
        ph, realised = I.horizon_risk(fr, hb, horizon, "linear", "common", step=step_L)
        lp = logit(np.asarray(ph, float))
        # deployable 5% intercept, averaged over disjoint adaptation/eval splits
        ahat = []
        for s_i in range(splits):
            rng = np.random.default_rng(SEED + 61000 + 131 * s_i)
            take = max(2, int(round(len(upid) * frac)))
            pick = rng.choice(upid, size=take, replace=False)
            loc = np.isin(pid, pick); ev = ~loc
            assert not set(pid[loc]) & set(pid[ev]), "adaptation and eval share a person"
            if len(np.unique(yb[loc])) < 2:
                continue
            a, se, q = UP.fit_offset_clustered(lp[loc], yb[loc].astype(int), wb[loc], pid[loc])
            if np.isfinite(a):
                ahat.append(a)
        a_bar = float(np.mean(ahat)) if ahat else 0.0
        lp_rep = lp + a_bar

        lo, hi = np.quantile(lp, [0.005, 0.995])
        grid_lp = np.linspace(lo, hi, 60)
        rng = np.random.default_rng(SEED + 7)
        codes = pd.factorize(pid)[0]
        for tag, lpx in (("frozen", lp), ("repaired", lp_rep)):
            try:
                curve = smooth_curve(yb, wb, lpx, grid_lp)
            except Exception:
                curve = smooth_curve(yb, wb, lpx, grid_lp) if False else np.full(len(grid_lp), np.nan)
            boot = np.full((B, len(grid_lp)), np.nan)
            for b in range(B):
                take = rng.integers(0, len(upid), size=len(upid))
                wts = np.bincount(codes[take], minlength=len(upid))[codes]
                sel = wts > 0
                if yb[sel].sum() < 5:
                    continue
                try:
                    boot[b] = smooth_curve(yb[sel], wb[sel] * wts[sel], lpx[sel], grid_lp)
                except Exception:
                    pass
            band_lo = np.nanpercentile(boot, 2.5, axis=0); band_hi = np.nanpercentile(boot, 97.5, axis=0)
            col = OI["blue"] if tag == "frozen" else OI["verm"]
            xs = expit(grid_lp)
            ax.fill_between(xs, band_lo, band_hi, color=col, alpha=0.18, lw=0)
            ax.plot(xs, curve, color=col, lw=1.4, label=tag)
            for gi, (g, c, blo, bhi) in enumerate(zip(grid_lp, curve, band_lo, band_hi)):
                grid_rows.append(dict(held=held, arm=tag, mean_offset=a_bar,
                                      predicted_risk=float(expit(g)), observed_smooth=float(c),
                                      obs_lo=float(blo), obs_hi=float(bhi)))
        ax.plot([0.002, 0.4], [0.002, 0.4], ls=":", color=OI["grey"], lw=1)
        ax.axvline(0.05, color=OI["black"], lw=0.6, alpha=0.5)
        ax.set_xlabel("predicted 4-year risk")
        ax.set_ylabel("observed risk (smoothed)")
        ax.set_xscale("log"); ax.set_yscale("log")
        ax.set_xlim(0.002, 0.4); ax.set_ylim(0.002, 0.4)
        ax.set_title(f"{CTRY[held]}", fontsize=7.5)
        ax.legend(fontsize=5, frameon=False, loc="upper left")
        if held == "MX":
            sub = [rr for rr in grid_rows if rr["held"] == "MX" and rr["arm"] == "frozen"]
            sub = [rr for rr in sub if rr["predicted_risk"] >= 0.10]
            tail = max(sub, key=lambda r: r["predicted_risk"]) if sub else None
            print(f"MX: a_bar={a_bar:+.3f}; frozen high-risk tail at predicted "
                  f"{tail['predicted_risk']:.3f} -> observed {tail['observed_smooth']:.3f} "
                  f"[{tail['obs_lo']:.3f}, {tail['obs_hi']:.3f}]" if tail else "MX tail NA", flush=True)
    fig.tight_layout(rect=[0, 0.02, 1, 1])
    fig.savefig(os.path.join(FIGD, "incident_calibration_smooth.png"), dpi=300, bbox_inches="tight")
    fig.savefig(os.path.join(FIGD, "incident_calibration_smooth.pdf"), bbox_inches="tight")
    G = pd.DataFrame(grid_rows)
    G.to_csv(os.path.join(OUT, "incident_calibration_smooth.csv"), index=False)
    print(f"wrote incident_calibration_smooth.{{png,pdf}} + csv rows={len(G)}")


if __name__ == "__main__":
    main()
