"""LOCO v2 - the arm rebuilt after the mapping audit.

Why this exists, in one line per design decision (each responds to a defect found in the audit):

 1. PRIMARY feature set = the 10 concepts actually observed in all four cohorts (age, sex,
    education, marital, ever/current smoker, alcohol, hypertension, diabetes, heart attack).
    Cholesterol is observed only in NHANES, income in three cohorts, Mexican measured BMI on 7.3%
    of rows, so the previous arm scored cross-national transport on a variable list most countries
    did not have. The wider set is a labelled sensitivity, never the headline.
 2. Degenerate-column guard. When the US was held out, `high_cholesterol` was wholly unobserved in
    training. Six further one-hot columns (education_4/5, marital_3..6) were structurally dead in
    every partition. A column that is constant in TRAIN has an unidentifiable coefficient yet is
    still applied to real values in TEST, so such columns are now dropped before fitting.
    (Correction: SimpleImputer already drops a wholly-NaN column rather than imputing zero, so the
    original arm did not score the US on an invented cholesterol term; the guard is still needed for
    the constant one-hot levels, which are not NaN and so survive the imputer.)
 3. Probability post-processing is reported, not buried. The frozen pipeline's forest uses
    class_weight="balanced_subsample"; rf_probability_ablation.py shows that this single setting
    produces the Brier of 0.130 internal / 0.333 Mexico (removing it gives 0.0368 / 0.0357 at
    unchanged AUROC). The primary forest here is the unweighted one; `random_forest_balanced` is
    kept as a reported variant so the original number is still visible.
 4. Estimators are the frozen ones (modeling.make_model) so "comparable tuning budget" is true by
    construction; the only additions are two baselines the field expects: age+sex logistic, and a
    penalised spline logistic that is allowed to be non-linear, so the question "do trees buy
    anything beyond splines?" can be answered.
 5. Naive reference for every absolute metric: a constant-risk model predicting the TRAINING
    partition's prevalence, reported as Brier skill score. Korea and Mexico previously looked good
    at Brier 0.013/0.036 while that reference was 0.0129/0.0359 - almost no skill.
 6. Person-clustered inference. Respondent-wave rows are not independent (2.9-5.9 waves per adult;
    8,181 positive records are 4,983 people), so held-out CIs and model-vs-logistic paired
    differences resample PEOPLE.
 7. Paired, not subtracted. Every model is differenced against the logistic model on the identical
    test rows, with a clustered bootstrap CI on the difference.
 8. Absolute external performance is the primary outcome. Transportability decay is computed only
    in the primary configuration, from a person-clustered internal CV, and is explicitly not the
    basis of the main claim (it mixes population composition with transport).

Usage:
  python run_loco_v2.py [--features common|extended] [--unit wave|person] [--min-age 0|50]
                        [--internal-cv] [--boot 2000]

Sign convention (one definition, used everywhere in this arm):
  decay = internal AUROC - external AUROC.  POSITIVE means the model travels WORSE than it
  performs internally, i.e. transport loss. `d_auroc`/`d_brier` are model-minus-logistic on the
  identical held-out rows, so a positive d_brier is worse calibration.
"""
import os, sys, numpy as np, pandas as pd, warnings
warnings.filterwarnings("ignore")
for v in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[v] = "1"
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import modeling as M
from sklearn.base import clone
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler, SplineTransformer
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.metrics import roc_auc_score, brier_score_loss, average_precision_score

SEED = M.SEED
COMMON = ["age", "sex", "education", "marital", "ever_smoker", "current_smoker", "alcohol",
          "hypertension", "diabetes", "heart_attack"]
EXTRA = ["income_pir", "bmi", "high_cholesterol"]
# frozen estimators + two new baselines
MODELS = ["logistic", "elasticnet", "agesex_logistic", "spline_logistic",
          "random_forest", "random_forest_balanced", "xgboost", "gradient_boosting", "lightgbm"]
SPLINE_CONT = ["age", "bmi", "income_pir"]


def flag(name, default):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default


def estimator(name):
    """Return (preprocessing kind, estimator). Frozen models come from modeling.make_model;
    the two random-forest variants are matched pairs that differ ONLY in class_weight."""
    if name == "random_forest":
        p = M.make_model("random_forest").get_params()
        p["class_weight"] = None            # same n_estimators/depth/leaf/seed, no reweighting
        from sklearn.ensemble import RandomForestClassifier
        return "tree", RandomForestClassifier(**p)
    if name == "random_forest_balanced":
        return "tree", M.make_model("random_forest")   # the frozen, class-weighted forest
    if name in M.C.MODELS:
        return ("logit" if M._is_linear(name) else "tree"), M.make_model(name)
    if name == "agesex_logistic":
        return "logit_agesex", M.make_model("logistic")
    if name == "spline_logistic":
        return "spline_logit", M.make_model("logistic")
    raise ValueError(name)


def prep(A2, kind, keep):
    """Fitted preprocessing for one model family. Returns (train_matrix, apply_fn, out_columns)
    so a caller can re-apply the IDENTICAL fitted transform to new rows - the incident arm needs
    this to step a person forward in age and recompose hazards."""
    if kind == "logit_agesex":
        sub = [c for c in ["age", "sex_2"] if c in keep]
        sc = StandardScaler().fit(A2[sub])
        return sc.transform(A2[sub]), (lambda f: sc.transform(f[sub])), sub
    if kind == "spline_logit":
        cont = [c for c in SPLINE_CONT if c in keep]
        rest = [c for c in keep if c not in cont]
        st = SplineTransformer(n_knots=4, degree=3, include_bias=False).fit(A2[cont])
        s_names = list(st.get_feature_names_out(cont))
        fA = pd.concat([pd.DataFrame(st.transform(A2[cont]), columns=s_names, index=A2.index),
                       A2[rest]], axis=1)
        sc = StandardScaler().fit(fA)
        def apply(f, st=st, sc=sc, s_names=s_names, cont=cont, rest=rest):
            sp = pd.DataFrame(st.transform(f[cont]), columns=s_names, index=f.index)
            return sc.transform(pd.concat([sp, f[rest]], axis=1))
        return sc.transform(fA), apply, list(fA.columns)
    if kind == "logit":
        sc = StandardScaler().fit(A2)
        return sc.transform(A2), (lambda f: sc.transform(f)), keep
    return A2.values, (lambda f: f.values), keep


def transform(A, Bm, kind, cols):
    """Imputed train/test frames -> model-ready matrices. The degenerate guard drops columns
    that are constant (or wholly unobserved) in TRAIN, so no unidentifiable term can be applied
    to values the model never saw. Returns (A_mat, B_mat, kept_columns)."""
    keep = [c for c in cols if A[c].notna().any() and A[c].nunique(dropna=True) > 1]
    A_mat, apply_fn, out_cols = prep(A[keep], kind, keep)
    return A_mat, apply_fn(Bm[keep]), out_cols


def fit_predict(Xtr, ytr, Xte, name, cols):
    kind, clf = estimator(name)
    imp = SimpleImputer(strategy="median").fit(Xtr)
    # an all-NaN column in the training partition is DROPPED by SimpleImputer, so the surviving
    # names must come from the imputer itself, not from the original column list
    kept_names = list(imp.get_feature_names_out())
    A = pd.DataFrame(imp.transform(Xtr), columns=kept_names, index=Xtr.index)
    Bm = pd.DataFrame(imp.transform(Xte), columns=kept_names, index=Xte.index)
    A_mat, B_mat, kept = transform(A, Bm, kind, kept_names)
    return clone(clf).fit(A_mat, ytr).predict_proba(B_mat)[:, 1], kept


def bootstrap_draws(groups, rng, n):
    """Person-clustered bootstrap: draw PEOPLE with replacement (equal probability, so a
    person contributing three waves is three times as likely to be chosen as one contributing
    a single wave), then expand each draw back to that person's rows.
    Vectorised over rows so a 24k-person resample costs no python-level loop.

    A GENERATOR on purpose. Materialising n draws costs n x rows x 8 bytes, and with the RAND HRS
    panel in the incident design the largest held-out country is 257,794 intervals, so 2,000
    stored draws would be 4.1 GB of index arrays for a statistic that only needs them one at a
    time. The random stream is identical to the list version - same calls, same order."""
    uniq, inv = np.unique(groups, return_inverse=True)
    counts = np.bincount(inv)
    order = np.argsort(inv, kind="stable")           # rows grouped by person
    first = np.zeros(len(uniq), dtype=np.int64)      # offset of each person inside `order`
    first[1:] = np.cumsum(counts)[:-1]
    for _ in range(n):
        k = rng.integers(0, len(uniq), len(uniq))
        reps = np.bincount(k, minlength=len(uniq)) * counts   # rows each person contributes
        sel = np.nonzero(reps)[0]
        r = reps[sel]
        bfirst = np.zeros(len(sel), dtype=np.int64)
        bfirst[1:] = np.cumsum(r)[:-1]
        block = np.repeat(np.arange(len(sel), dtype=np.int64), r)
        # a person drawn k times needs k COPIES of the same row block, so the offset inside the
        # block must wrap on the person's own row count rather than run on into the next person
        sel_count = counts[sel][block]
        within = np.arange(int(r.sum()), dtype=np.int64) - bfirst[block]
        yield order[first[sel][block] + np.mod(within, sel_count)]


def bootstrap_indices(groups, rng, n):
    return list(bootstrap_draws(groups, rng, n))


def bootstrap_seeded_draws(groups, n, seed):
    """The same clustered resample, but replicate i comes from its own generator seeded by
    (seed, i) rather than from one long stream. Two things that buys: a caller can walk the whole
    draw set once per fitted model without holding n x rows index arrays in memory (4.1 GB for
    2,000 draws of the 257,794-interval US panel), and every model still sees EXACTLY the same
    resamples, which is what makes a cross-model paired comparison well defined."""
    for i in range(n):
        yield next(bootstrap_draws(groups, np.random.default_rng([seed, i]), 1))


def main():
    fset, unit = flag("--features", "common"), flag("--unit", "wave")
    min_age = float(flag("--min-age", "0"))
    n_boot = int(flag("--boot", "2000"))
    do_internal = "--internal-cv" in sys.argv
    d = os.path.abspath(os.path.join(HERE, "..", "..", "..", "data", "processed", "intl", "corrected"))
    df = pd.concat([pd.read_csv(os.path.join(d, f"std_{c}.csv"))
                    for c in ["NHANES", "CHARLS", "KLoSA", "MHAS"]], ignore_index=True)
    base = COMMON + (EXTRA if fset == "extended" else [])
    df = df[["country", "cohort", "pid", "wave", "stroke"]
            + [c for c in base if c in df.columns]].copy()
    df["age"] = pd.to_numeric(df["age"], errors="coerce")
    if min_age:
        df = df[df["age"] >= min_age].copy()
    if unit == "person":
        df = (df.sort_values(["cohort", "pid", "wave"])
                .groupby(["cohort", "pid"], as_index=False).last())
    df = df.reset_index(drop=True)
    grp = (df["cohort"].astype(str) + "|" + df["pid"].astype(str)).values
    X = M.encode(df)
    cols = list(X.columns)
    y = df["stroke"].astype(int).values
    label = f"{fset}_{unit}_age{int(min_age)}"
    print(f"LOCO v2 [{label}] rows={len(df)} persons={pd.Series(grp).nunique()} "
          f"events={int(y.sum())} countries={sorted(set(df.country))} design_cols={len(cols)}",
          flush=True)

    internal = {}
    if do_internal:
        rng_i = np.random.default_rng(SEED)
        for name in MODELS:
            oof = np.full(len(y), np.nan)
            sgkf = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=SEED)
            for tr, te in sgkf.split(X, y, grp):
                p, _ = fit_predict(X.iloc[tr], y[tr], X.iloc[te], name, cols)
                oof[te] = p
            ok = ~np.isnan(oof)
            internal[name] = float(roc_auc_score(y[ok], oof[ok]))
            print(f"  internal(person-clustered) {name:24s} AUROC {internal[name]:.4f} "
                  f"covered={ok.mean():.3f}", flush=True)

    rng = np.random.default_rng(SEED + 7)
    rows = []
    for held in sorted(set(df["country"])):
        tr = (df["country"].values != held); te = (df["country"].values == held)
        yt = y[te]
        prev_train = float(y[tr].mean()); qte = float(yt.mean())
        # Two different "naive" references, because they answer different questions:
        #  naive_train  = the empirical Brier of a constant model frozen at the TRAINING
        #                 prevalence, i.e. what a transported model actually degrades to.
        #                 NOT prev_train*(1-prev_train), which is that constant's Brier only
        #                 when the test prevalence equals it.
        #  naive_oracle = the TEST base rate q(1-q). It peeks at the labels, which is why the
        #                 field uses it as the scaled-Brier denominator, and it is much harder
        #                 to beat.
        naive_train = prev_train ** 2 * (1 - qte) + (1 - prev_train) ** 2 * qte
        naive_oracle = qte * (1 - qte)
        draws = bootstrap_indices(grp[te], rng, n_boot)
        probs, nfeat = {}, None
        for name in MODELS:
            probs[name], kept = fit_predict(X.iloc[tr], y[tr], X.iloc[te], name, cols)
            nfeat = len(kept)
        # precompute per-draw metrics for every model at once (shared resamples -> comparable CIs)
        boot = {name: {"auc": np.empty(n_boot), "brier": np.empty(n_boot)} for name in MODELS}
        valid = 0
        for idx in draws:
            yy = yt[idx]
            if yy.min() == yy.max():
                continue
            for name in MODELS:
                boot[name]["auc"][valid] = roc_auc_score(yy, probs[name][idx])
                boot[name]["brier"][valid] = brier_score_loss(yy, probs[name][idx])
            valid += 1
        sl = slice(0, valid)
        for name in MODELS:
            p = probs[name]
            auc = float(roc_auc_score(yt, p)); br = float(brier_score_loss(yt, p))
            a1, a2 = boot[name]["auc"][sl], boot["logistic"]["auc"][sl]
            b1, b2 = boot[name]["brier"][sl], boot["logistic"]["brier"][sl]
            q = lambda v: (float(np.nanpercentile(v, 2.5)), float(np.nanpercentile(v, 97.5)))
            ci_a, cs = M.cal_intercept_slope(yt, p)
            lo_a, hi_a = q(a1); lo_b, hi_b = q(b1)
            d1, d2 = q(a1 - a2); e1, e2 = q(b1 - b2)
            s1, s2 = q((naive_train - b1) / naive_train)
            g1, g2 = q((naive_oracle - b1) / naive_oracle)
            rows.append(dict(feature_set=fset, unit=unit, min_age=min_age, model=name, held=held,
                             n=int(te.sum()), events=int(yt.sum()), obs_prev=qte,
                             prev_train=prev_train, brier_naive_train=naive_train,
                             brier_naive_oracle=naive_oracle, mean_pred=float(p.mean()),
                             auroc=auc, auroc_lo=lo_a, auroc_hi=hi_a,
                             auprc=float(average_precision_score(yt, p)), brier=br,
                             brier_lo=lo_b, brier_hi=hi_b,
                             skill_train=float((naive_train - br) / naive_train),
                             skill_train_lo=s1, skill_train_hi=s2,
                             scaled_brier=float((naive_oracle - br) / naive_oracle),
                             sb_lo=g1, sb_hi=g2,
                             cal_intercept=ci_a, cal_slope=cs,
                             d_auroc=float(auc - roc_auc_score(yt, probs["logistic"])),
                             d_auroc_lo=d1, d_auroc_hi=d2,
                             d_brier=float(br - brier_score_loss(yt, probs["logistic"])),
                             d_brier_lo=e1, d_brier_hi=e2,
                             n_features=nfeat, n_boot=valid,
                             internal_auroc=internal.get(name, np.nan),
                             decay=internal.get(name, np.nan) - auc))
            r = rows[-1]
            print(f"  {held} {name:24s} AUROC {r['auroc']:.4f} [{r['auroc_lo']:.4f},{r['auroc_hi']:.4f}] "
                  f"Brier {r['brier']:.5f} naive(train) {r['brier_naive_train']:.5f} "
                  f"skill {r['skill_train']:+.4f} scaledB {r['scaled_brier']:+.4f} "
                  f"slope {r['cal_slope']:.3f} int {r['cal_intercept']:+.3f} "
                  f"dAUROC-vs-logit {r['d_auroc']:+.4f} [{r['d_auroc_lo']:+.4f},{r['d_auroc_hi']:+.4f}]",
                  flush=True)
    out = pd.DataFrame(rows)
    dest = os.path.join(d, f"loco_v2_{label}.csv")
    out.to_csv(dest, index=False)
    print("\nwrote", dest)
    pv = out.pivot_table(index="model", columns="held", values="auroc").round(4)
    pv["mean"] = out.groupby("model")["auroc"].mean().round(4)
    pv["skill_train"] = out.groupby("model")["skill_train"].mean().round(4)
    pv["scaled_brier"] = out.groupby("model")["scaled_brier"].mean().round(4)
    if internal:
        pv["internal"] = out.groupby("model")["internal_auroc"].first().round(4)
    print(pv.to_string())


if __name__ == "__main__":
    main()
