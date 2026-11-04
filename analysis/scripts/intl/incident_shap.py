"""Feature attributions (SHAP) for the incident-stroke arm.

Scope, stated so it cannot be over-read: this explains the FROZEN models' predictions, i.e. how each
model's score is arithmetically assembled. It is not mechanism evidence - a coefficient on education
in a survey hazard model is not a causal effect of education on stroke - and it is not a second
validation. It is included because a reviewer asked for it and because a linear model's attributions
are the one part of this paper a clinician can check by hand.

Two explainers, both exact for their model class: LinearExplainer for the logistic discrete-time model
and TreeExplainer for XGBoost. One-hot levels are grouped back into their concept and the group's
attributions are summed, so "education" is one row rather than three competing ones. Attributions are
computed on the rows a model would actually serve: the held-out country's own intervals for the LOCO
fits, and a stratified sample of all three panels for the pooled fit.

Usage: python incident_shap.py [--rows 4000]
"""
import os, sys, numpy as np, pandas as pd, warnings
warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)
import modeling as M
import run_loco_v2 as V2
import run_incident_loco as I
import shap

OUT = I.OUT
SEED = V2.SEED
MODELS = ["logistic", "xgboost"]
CONCEPT_OF = {}


def concept(col):
    """Map a model column back to the concept it came from, grouping one-hot levels."""
    if col in ("exposure_years", "t_since_entry_years"):
        return "time (interval length / duration in study)"
    base = col.rsplit("_", 1)[0]
    if base in M.CAT_COLS:
        return base
    return col


def flag(name, default):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default


def attributions(fr, Xs, kind):
    """Exact SHAP for the model behind a fitted Frozen, evaluated on Xs (a design frame)."""
    Z = fr._mat(Xs)                      # the same transform the model was trained under
    if kind == "logit":
        exp = shap.LinearExplainer(fr.clf, Z)
    elif kind == "tree":
        exp = shap.TreeExplainer(fr.clf)
    else:
        raise ValueError(kind)
    return np.asarray(exp.shap_values(Z))


def main():
    n_rows = int(flag("--rows", "4000"))
    pp = pd.read_csv(os.path.join(OUT, "personperiod_pooled.csv"))
    pp["country"] = pp["cohort"].map(I.COH2CTRY)
    pp = pp[pp["country"].notna()].reset_index(drop=True)
    X = I.design(pp, "common", "linear")
    y = pp["event"].astype(int).values
    rng = np.random.default_rng(SEED + 3)
    rows = []
    settings = [("pooled", np.ones(len(pp), bool))] + [
        (h, (pp["country"].values == h)) for h in ["CN", "KR", "MX"]]
    for name in MODELS:
        kind, _ = V2.estimator(name)
        for label, tr in settings:
            fr = I.Frozen(X.loc[tr], y[tr], name)
            te = pp.index[tr]
            take = rng.choice(len(te), min(n_rows, len(te)), replace=False)
            Xs = X.loc[te[take]]
            sv = attributions(fr, Xs, kind)
            cols = list(fr.out_cols)
            mp = {c: concept(c) for c in cols}
            df = pd.DataFrame(sv, columns=cols)
            g = pd.DataFrame({gr: df[[c for c in cols if mp[c] == gr]].sum(axis=1)
                              for gr in pd.unique(list(mp.values()))})
            for c in g.columns:
                rows.append(dict(model=name, setting=label, concept=c,
                                 mean_abs_shap=float(np.abs(g[c]).mean()),
                                 mean_shap=float(g[c].mean()),
                                 share_of_total=float(np.abs(g[c]).mean() /
                                                      np.abs(g.values).sum(axis=1).mean()),
                                 n_explained=len(g), n_columns=len(cols)))
            print(f"  {name:10s} {label:7s} top: " + ", ".join(
                f"{k} {v:.4f}" for k, v in
                g.abs().mean().sort_values(ascending=False).head(4).items()), flush=True)
    out = pd.DataFrame(rows).sort_values(["model", "setting", "mean_abs_shap"],
                                         ascending=[True, True, False])
    dest = os.path.join(OUT, "incident_shap.csv")
    out.to_csv(dest, index=False)
    print("wrote", dest)
    for (m, s), x in out.groupby(["model", "setting"]):
        print(f"\n{m} / {s}")
        print(x[["concept", "mean_abs_shap", "mean_shap", "share_of_total"]].head(8).round(5)
              .to_string(index=False))


if __name__ == "__main__":
    main()
