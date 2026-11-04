"""Modeling / validation core for the NHANES stroke risk-stratification study.

All functions are leakage-aware: imputation + scaling + model are fit ONLY on the
training partition inside every pipeline; preprocessing config is identical across
every branch (internal CV / temporal / LOSO / adaptation) per the analysis-discipline
rule (sensitivity & recalibration reuse the main estimator config).
"""
import os
for _v in ("OMP_NUM_THREADS","MKL_NUM_THREADS","OPENBLAS_NUM_THREADS","NUMEXPR_NUM_THREADS"):
    os.environ[_v] = "1"
import numpy as np, pandas as pd, warnings
warnings.filterwarnings("ignore")
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.model_selection import StratifiedKFold
from sklearn.metrics import roc_auc_score, average_precision_score, brier_score_loss
from sklearn.inspection import permutation_importance
import statsmodels.api as sm
try:
    import xgboost as xgb
except Exception: xgb = None
try:
    import lightgbm as lgb
except Exception: lgb = None
import config as C

SEED = C.SEED
RACE_LABELS = {1:"Mexican American",2:"Other Hispanic",3:"Non-Hispanic White",
               4:"Non-Hispanic Black",5:"Other/Multi (incl. Asian)"}

NUMERIC = ["age","income_pir","bmi","ever_smoker","current_smoker","alcohol",
           "hypertension","high_cholesterol","diabetes","heart_attack"]
CAT_COLS = {"sex":[1,2], "race_ethnicity":[1,2,3,4,5],
            "education":[1,2,3,4,5], "marital":[1,2,3,4,5,6]}

# ---------------------------------------------------------------- encoding
def _cat_columns():
    cols = []
    for c, lv in CAT_COLS.items():
        for v in lv[1:]:                       # first level = reference
            cols.append(f"{c}_{int(v)}")
    return cols

def encode(df):
    """Deterministic one-hot (reference = lowest level) + numeric passthrough.
    Tolerant of absent columns so the same pipeline serves NHANES (with race) and the
    international cohorts (country is the grouping, no US race variable)."""
    X = pd.DataFrame(index=df.index)
    for c in NUMERIC:
        if c in df.columns:
            X[c] = pd.to_numeric(df[c], errors="coerce")
    for c, lv in CAT_COLS.items():
        if c not in df.columns:
            continue
        raw = pd.to_numeric(df[c], errors="coerce")
        for v in lv[1:]:
            X[f"{c}_{int(v)}"] = (raw == v).astype(float)
    return X[[c for c in X.columns]]

def _cat_columns_pref():
    ordered = list(NUMERIC) + _cat_columns()
    return ordered

DESIGN_COLS = None  # set on first call for column alignment across splits

def design(df):
    """Return aligned X, y, meta for any subset of rows (canonical column order)."""
    global DESIGN_COLS
    X = encode(df)
    if DESIGN_COLS is None:
        DESIGN_COLS = list(X.columns)
    X = X.reindex(columns=DESIGN_COLS, fill_value=0.0)
    y = df["stroke"].astype(int).values
    want = ["cycle","cycle_label","weight","psu","strata","age"] + [c for c in df.columns if c.startswith("phq_")]
    meta = df[[c for c in want if c in df.columns]].copy()
    return X, y, meta

# ---------------------------------------------------------------- models
def make_model(name):
    rs = SEED
    if name == "logistic":
        clf = LogisticRegression(max_iter=5000, C=1.0, random_state=rs)
    elif name == "elasticnet":
        clf = LogisticRegression(penalty="elasticnet", solver="saga", l1_ratio=0.5,
                                 C=0.1, max_iter=8000, random_state=rs)
    elif name == "random_forest":
        clf = RandomForestClassifier(n_estimators=150, max_depth=10, min_samples_leaf=25,
                                     n_jobs=1, random_state=rs, class_weight="balanced_subsample")
    elif name == "gradient_boosting":
        clf = GradientBoostingClassifier(n_estimators=120, max_depth=3, learning_rate=0.1,
                                         subsample=0.8, random_state=rs)
    elif name == "xgboost":
        clf = xgb.XGBClassifier(n_estimators=200, max_depth=4, learning_rate=0.05,
                                subsample=0.8, colsample_bytree=0.8, scale_pos_weight=None,
                                eval_metric="logloss", n_jobs=1, random_state=rs)
    elif name == "lightgbm":
        clf = lgb.LGBMClassifier(n_estimators=200, max_depth=4, learning_rate=0.05,
                                 subsample=0.8, colsample_bytree=0.8, min_child_samples=40,
                                 verbose=-1, n_jobs=1, random_state=rs)
    else:
        raise ValueError(name)
    return clf

def _is_linear(name): return name in ("logistic","elasticnet")

def get_pipeline(name):
    """Imputer(median, fit on train only) -> optional scaler -> classifier."""
    steps = [("imp", SimpleImputer(strategy="median", add_indicator=False))]
    if _is_linear(name):
        steps.append(("scale", StandardScaler()))
    steps.append(("clf", make_model(name)))
    return Pipeline(steps)

def fit_predict(Xtr, ytr, Xte, name):
    pipe = get_pipeline(name).fit(Xtr, ytr)
    return pipe, pipe.predict_proba(Xte)[:, 1]

# ---------------------------------------------------------------- metrics
def _logit(p, eps=1e-6):
    p = np.clip(p, eps, 1-eps); return np.log(p/(1-p))

def cal_intercept_slope(y, p):
    lp = _logit(p)
    try:
        res = sm.GLM(np.asarray(y, float), sm.add_constant(lp), family=sm.families.Binomial()).fit()
        return float(res.params[0]), float(res.params[1])   # intercept, slope
    except Exception:
        return np.nan, np.nan

def compute_metrics(y, p):
    y = np.asarray(y); p = np.asarray(p)
    out = {"n": int(len(y)), "events": int(y.sum()), "prevalence": float(y.mean()),
           "brier": float(brier_score_loss(y, p))}
    out["auroc"] = float(roc_auc_score(y, p)) if len(np.unique(y)) > 1 else np.nan
    out["auprc"] = float(average_precision_score(y, p)) if y.sum() > 0 else np.nan
    ci, cs = cal_intercept_slope(y, p); out["cal_intercept"], out["cal_slope"] = ci, cs
    return out

def bootstrap_ci(y, p, metric, B=1000, seed=SEED):
    """Percentile bootstrap CI for a scalar metric; resamples rows (patients)."""
    rng = np.random.default_rng(seed); y = np.asarray(y); p = np.asarray(p); n = len(y)
    vals = []
    for _ in range(B):
        idx = rng.integers(0, n, n)
        if len(np.unique(y[idx])) < 2: continue
        try:
            if metric == "auroc": v = roc_auc_score(y[idx], p[idx])
            elif metric == "auprc": v = average_precision_score(y[idx], p[idx])
            elif metric == "brier": v = brier_score_loss(y[idx], p[idx])
            else: break
            vals.append(v)
        except Exception: continue
    vals = np.array(vals)
    return float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))

def net_benefit(y, p, pt):
    y = np.asarray(y); p = np.asarray(p); n = len(y)
    tp = np.sum((p >= pt) & (y == 1)); fp = np.sum((p >= pt) & (y == 0))
    return tp/n - (fp/n)*(pt/(1-pt))
def nb_all(y, pt):
    prev = np.mean(y); return prev - (1-prev)*(pt/(1-pt))

THRESHOLDS = np.round(np.arange(0.01, 0.31, 0.005), 3)

# ---------------------------------------------------------------- validation
def internal_cv(df, name, n_splits=5, n_repeats=C.RANDOM_STATES):
    X, y, meta = design(df)
    oof_all = []
    for r in range(n_repeats):
        oof = np.zeros(len(y))
        skf = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=SEED + r)
        for tr, te in skf.split(X, y):
            _, p = fit_predict(X.iloc[tr], y[tr], X.iloc[te], name)
            oof[te] = p
        oof_all.append(oof)
    OOF = np.mean(oof_all, axis=0)
    m = compute_metrics(y, OOF)
    for met in ("auroc","auprc","brier"):
        lo, hi = bootstrap_ci(y, OOF, met); m[met+"_lo"], m[met+"_hi"] = lo, hi
    m["_oof"] = OOF
    return m

def temporal_validation(df, name):
    X, y, _ = design(df)
    dmask = df["cycle"].isin(C.DERIVATION).values
    emask = df["cycle"].isin(C.EXTERNAL).values
    _, p_ext = fit_predict(X[dmask], y[dmask], X[emask], name)
    m_ext = compute_metrics(y[emask], p_ext)
    m_int = internal_cv(df[dmask], name)          # internal on derivation only
    m_ext["auroc_decay_vs_internal"] = m_ext["auroc"] - m_int["auroc"]
    m_ext["cal_slope"] = m_ext["cal_slope"]
    m_ext["_p_ext"] = p_ext
    return m_int, m_ext

def loso_groups(df, group_col="race_ethnicity"):
    """Leave-one-group-out transportability; returns per-group held-out metrics."""
    X, y, meta = design(df)
    g = pd.to_numeric(df[group_col], errors="coerce").values
    rows = []
    for lv in sorted(pd.unique(g[~np.isnan(g)])):
        tr, te = (g != lv) & ~np.isnan(g), (g == lv)
        if y[te].sum() < 5:
            rows.append({"level": int(lv), "n": int(te.sum()), "events": int(y[te].sum()),
                         "auroc": np.nan, "brier": np.nan, "note": "too few events"}); continue
        _, p = fit_predict(X[tr], y[tr], X[te], "logistic")
        m = compute_metrics(y[te], p)
        rows.append({"level": int(lv), "group": RACE_LABELS[int(lv)], "n": m["n"],
                     "events": m["events"], "prevalence": m["prevalence"],
                     "auroc": m["auroc"], "brier": m["brier"],
                     "cal_intercept": m["cal_intercept"], "cal_slope": m["cal_slope"],
                     "note": "ok"})
    return pd.DataFrame(rows)

# ---------------------------------------------------------------- adaptation / data efficiency
def _adapt_eval(Xtr_full, ytr_full, Xte, yte, k_list, name="logistic", repeats=8, seed=SEED):
    """Fit frozen model on ALL derivation (Xtr_full). For each adaptation size k,
    draw k rows of the TARGET pool, adapt (frozen / intercept / intercept+slope /
    retrain), evaluate on the held-out target rows. Returns DataFrame + k_list."""
    frozen = get_pipeline(name).fit(Xtr_full, ytr_full)
    rng = np.random.default_rng(seed)
    methods = ["frozen","intercept","intercept+slope","retrain"]
    acc = {}  # (method,k) -> lists
    for rep in range(repeats):
        for k in k_list:
            if k >= len(Xte): break
            idx = rng.choice(len(Xte), size=k, replace=False)
            Xadapt, yadapt = Xte.iloc[idx], yte[idx]
            Xheld = Xte.drop(index=Xte.index[idx]); yheld = np.delete(yte, idx)
            if len(np.unique(yheld)) < 2 or yadapt.sum() < 5:
                continue
            lp_a = _logit(frozen.predict_proba(Xadapt)[:, 1])
            lp_h = _logit(frozen.predict_proba(Xheld)[:, 1])
            p_frozen = 1/(1+np.exp(-lp_h))
            # intercept-only recalibration: offset frozen logit, fit single intercept
            try:
                r_int = sm.GLM(yadapt.astype(float), np.ones((len(yadapt),1)),
                               family=sm.families.Binomial(), offset=lp_a).fit()
                b0 = float(r_int.params[0])
                if not np.isfinite(b0): b0 = 0.0
            except Exception: b0 = 0.0
            p_int = 1/(1+np.exp(-(lp_h + b0)))
            # intercept + slope recalibration (guard: reject degenerate/inverted fits)
            try:
                r_is = sm.GLM(yadapt.astype(float), sm.add_constant(lp_a),
                              family=sm.families.Binomial()).fit()
                a0, a1 = float(r_is.params[0]), float(r_is.params[1])
                if not np.isfinite(a1) or a1 <= 0:      # unstable tiny fit -> fall back to frozen
                    a0, a1 = 0.0, 1.0
            except Exception: a0, a1 = 0.0, 1.0
            p_is = 1/(1+np.exp(-(a0 + a1*lp_h)))
            # retrain on adaptation slice
            try:
                _, p_rt = fit_predict(Xadapt, yadapt, Xheld, name)
            except Exception:
                p_rt = p_frozen
            for method, pp in zip(methods, [p_frozen, p_int, p_is, p_rt]):
                key = (method, k); acc.setdefault(key, {"brier": [], "auroc": [], "cal_slope": []})
                acc[key]["brier"].append(brier_score_loss(yheld, pp))
                acc[key]["auroc"].append(roc_auc_score(yheld, pp))
                _, cs = cal_intercept_slope(yheld, pp); acc[key]["cal_slope"].append(cs)
    rows = [{"method": m, "k": k, "brier_mean": np.nanmean(v["brier"]),
             "auroc_mean": np.nanmean(v["auroc"]), "cal_slope_mean": np.nanmean(v["cal_slope"]),
             "reps": len(v["brier"])} for (m, k), v in acc.items()]
    return pd.DataFrame(rows), sorted(set(k for (_, k) in acc))

def importance(df, name="gradient_boosting"):
    X, y, _ = design(df)
    pipe, p = fit_predict(X, y, X, name)  # in-sample fit for a fitted model to permute
    r = permutation_importance(pipe, X, y, scoring="average_precision",
                               n_repeats=10, random_state=SEED, n_jobs=1)
    imp = pd.DataFrame({"feature": X.columns, "importance": r.importances_mean,
                        "sd": r.importances_std}).sort_values("importance", ascending=False)
    return imp
