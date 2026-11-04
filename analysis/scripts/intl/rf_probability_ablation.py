"""Ablation: is the random forest's Brier blow-up an intrinsic cost of complexity, or an
artefact of how we configured it?

Why this exists. The manuscript's headline dissociation (near-identical AUROC, ~9x worse Brier)
rests almost entirely on ONE model, `random_forest`. In modeling.make_model the forest is built
with `class_weight="balanced_subsample"`, which reweights the minority class inside every tree's
bootstrap. Class-balance corrections are known to leave ranking almost untouched while inflating
predicted probabilities - exactly the pattern we report. Meanwhile gradient boosting, XGBoost and
LightGBM, all equally "complex", have Brier scores indistinguishable from the logistic model.
So the honest reading may be "one of our probability settings was miscalibrated by design", not
"complex models sacrifice reliability".

This script measures it. For each model variant and each held-out country it fits on the other
countries and reports AUROC / Brier / scaled Brier against a naive constant-risk reference /
calibration intercept and slope, plus the mean predicted risk versus observed prevalence.
Variants:
  logistic                  - the reference model
  rf_balanced               - class_weight="balanced_subsample" (what the paper reports)
  rf_plain                  - identical forest WITHOUT any class weighting
  rf_platt                  - rf_plain wrapped in CalibratedClassifierCV (sigmoid, CV on the
                              TRAINING partition only)
  rf_iso                  - rf_plain wrapped in isotonic calibration, training partition only
  gradient_boosting         - reported for contrast (no class weighting, already near-logistic)

Nothing here re-tunes hyperparameters: every forest uses the frozen n_estimators=150,
max_depth=10, min_samples_leaf=25 from config.py, so the only moving part is the probability
post-processing.

Usage: python rf_probability_ablation.py [std_dir] [feature_set common|extended]
"""
import os, sys, numpy as np, pandas as pd, warnings
warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import modeling as M
from sklearn.ensemble import RandomForestClassifier
from sklearn.calibration import CalibratedClassifierCV
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression

SEED = M.SEED
COMMON = ["age", "sex", "education", "marital", "ever_smoker", "current_smoker", "alcohol",
          "hypertension", "diabetes", "heart_attack"]
EXTRA = ["income_pir", "bmi", "high_cholesterol"]


def base_to_design(base):
    """Map canonical concept names onto the one-hot design columns they generate."""
    out = []
    for c in base:
        if c in M.NUMERIC:
            out.append(c)
        else:
            out.extend([f"{c}_{int(v)}" for v in M.CAT_COLS.get(c, [])[1:]])
    return out


def drop_degenerate(Xtr):
    keep = [c for c in Xtr.columns if Xtr[c].notna().any() and Xtr[c].nunique(dropna=True) > 1]
    return keep


def forest(weighted):
    return RandomForestClassifier(n_estimators=150, max_depth=10, min_samples_leaf=25,
                                  n_jobs=1, random_state=SEED,
                                  class_weight="balanced_subsample" if weighted else None)


def predict(Xtr, ytr, Xte, kind):
    imp = SimpleImputer(strategy="median")
    tr_mat = imp.fit_transform(Xtr)
    # an all-NaN column in TRAIN is DROPPED by SimpleImputer, so the surviving names must come
    # from the imputer AFTER fitting; labelling with Xtr.columns mislabels the frame as soon as
    # one is dropped (which is what happened for the held-out US, where cholesterol is unobserved)
    out_names = list(imp.get_feature_names_out())
    Xtr_i = pd.DataFrame(tr_mat, columns=out_names, index=Xtr.index)
    Xte_i = pd.DataFrame(imp.transform(Xte), columns=out_names, index=Xte.index)
    keep = drop_degenerate(Xtr_i)
    Xtr_i, Xte_i = Xtr_i[keep], Xte_i[keep]
    if kind == "logistic":
        from sklearn.preprocessing import StandardScaler
        sc = StandardScaler().fit(Xtr_i)
        clf = LogisticRegression(max_iter=5000, random_state=SEED).fit(sc.transform(Xtr_i), ytr)
        return clf.predict_proba(sc.transform(Xte_i))[:, 1], keep
    if kind == "rf_balanced":
        return forest(True).fit(Xtr_i, ytr).predict_proba(Xte_i)[:, 1], keep
    if kind == "rf_plain":
        return forest(False).fit(Xtr_i, ytr).predict_proba(Xte_i)[:, 1], keep
    if kind in ("rf_platt", "rf_iso"):
        method = "sigmoid" if kind == "rf_platt" else "isotonic"
        cal = CalibratedClassifierCV(forest(False), method=method, cv=3, ensemble=False)
        return cal.fit(Xtr_i, ytr).predict_proba(Xte_i)[:, 1], keep
    if kind == "gradient_boosting":
        pipe = M.get_pipeline("gradient_boosting").fit(Xtr, ytr)
        return pipe.predict_proba(Xte)[:, 1], keep
    raise ValueError(kind)


def metrics(y, p, prev_train):
    from sklearn.metrics import roc_auc_score, brier_score_loss
    y = np.asarray(y)
    q = float(y.mean())
    # Two naive references, because they answer different questions.
    #   naive_train  - the EMPIRICAL Brier of a constant predictor frozen at the training
    #                  prevalence, i.e. what a transported model actually degrades to. The earlier
    #                  version of this function used prev_train*(1-prev_train), which is that
    #                  constant's Brier only if the test prevalence equals it, so it graded on a
    #                  curve that ignored the very transport error it was meant to measure.
    #   naive_oracle - the test base rate q(1-q); it peeks at the labels, which is why the field
    #                  uses it as the scaled-Brier denominator, and it is far harder to beat.
    naive_train = prev_train ** 2 * (1 - q) + (1 - prev_train) ** 2 * q
    naive_oracle = q * (1 - q)
    b = brier_score_loss(y, p)
    ci, cs = M.cal_intercept_slope(y, p)
    return dict(n=len(y), events=int(y.sum()), obs_prev=q, prev_train=float(prev_train),
                auroc=float(roc_auc_score(y, p)), brier=float(b),
                brier_naive_train=float(naive_train), brier_naive_oracle=float(naive_oracle),
                skill_train=float((naive_train - b) / naive_train) if naive_train > 0 else np.nan,
                scaled_brier=float((naive_oracle - b) / naive_oracle) if naive_oracle > 0 else np.nan,
                mean_pred=float(np.mean(p)), cal_intercept=ci, cal_slope=cs,
                log_brier_ratio_vs_naive=float(np.log(b / naive_train)))


def flag(name, default):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default


def main():
    # flags take their value with --name value, so a value can never be mistaken for the
    # positional data directory (an earlier version read "--features/std_NHANES.csv")
    fset = flag("--features", "extended")
    d = flag("--dir", os.path.abspath(
        os.path.join(HERE, "..", "..", "..", "data", "processed", "intl", "corrected")))
    stray = [a for a in sys.argv[1:] if not a.startswith("--")
             and a not in (fset, d)]
    if stray:
        print(f"  ignoring unrecognised positional arguments: {stray}", file=sys.stderr)
    cols = COMMON + (EXTRA if fset == "extended" else [])
    df = pd.concat([pd.read_csv(os.path.join(d, f"std_{c}.csv"))
                    for c in ["NHANES", "CHARLS", "KLoSA", "MHAS"]], ignore_index=True)
    y = df["stroke"].astype(int).values
    Xall = M.encode(df)
    # the --features flag has to actually subset the design. An earlier version computed `cols`
    # and then ignored it, so common and extended produced byte-identical tables and the
    # NHANES-only race columns leaked into a run that claimed to be the harmonised subset.
    Xall = Xall[[c for c in Xall.columns if c in cols or c.rsplit("_", 1)[0] in cols]]
    kinds = ["logistic", "rf_balanced", "rf_plain", "rf_platt", "rf_iso", "gradient_boosting"]
    rows = []
    for held in ["CN", "KR", "MX", "US"]:
        tr = (df["country"].values != held); te = (df["country"].values == held)
        prev_train = y[tr].mean()
        for kind in kinds:
            p, keep = predict(Xall[tr], y[tr], Xall[te], kind)
            m = metrics(y[te], p, prev_train)
            m.update(model=kind, held=held, feature_set=fset,
                     dropped_cols=int(Xall.shape[1] - len(keep)), n_features=len(keep))
            rows.append(m)
            print(f"{held} {kind:18s} AUROC {m['auroc']:.4f}  Brier {m['brier']:.5f}  "
                  f"naive(train) {m['brier_naive_train']:.5f} skill {m['skill_train']:+.4f} "
                  f"scaledB {m['scaled_brier']:+.4f}  "
                  f"mean-pred {m['mean_pred']:.4f} vs obs {m['obs_prev']:.4f}  "
                  f"int {m['cal_intercept']:+.3f} slope {m['cal_slope']:.3f}", flush=True)
    out = pd.DataFrame(rows)
    dest = os.path.join(d, f"rf_ablation_{fset}.csv")
    out.to_csv(dest, index=False)
    print("\nwrote", dest)
    piv = out.pivot_table(index="model", columns="held", values="skill_train").round(4)
    print("\nBrier skill vs the train-prevalence constant reference (higher = better):\n",
          piv.to_string())


if __name__ == "__main__":
    main()
