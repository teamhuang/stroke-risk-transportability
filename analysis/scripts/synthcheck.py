"""End-to-end pipeline VALIDATION on synthetic data with KNOWN ground truth.

Nothing here is a study result; it only proves the machinery is correct so that the
REAL NHANES numbers can be trusted. Checks: no-leakage, signal recovery, calibration
~1 in-distribution, attenuation under domain shift, adaptation restores calibration,
LOSO/temporal run, DCA net-benefit behaves, bootstrap CI brackets the estimate.
"""
import os, sys, numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(__file__))
import config as C, modeling as M

rng = np.random.default_rng(C.SEED)

def synth(n, slope=1.0, intercept_shift=0.0, seed=1):
    r = np.random.default_rng(seed)
    age = r.normal(52, 18, n).clip(20, 90)
    pir = r.normal(2.2, 1.4, n).clip(0.1, 6)
    bmi = r.normal(28, 6, n).clip(15, 60)
    es = r.binomial(1, .4, n)
    cs_full = np.zeros(n, dtype=int)
    es_idx = es == 1
    cs_full[es_idx] = r.binomial(1, .3, es_idx.sum())
    alcohol = r.binomial(1,.5,n); htn = r.binomial(1,.35,n)
    chol = r.binomial(1,.4,n); dm = r.binomial(1,.12,n); mi = r.binomial(1,.06,n)
    sex = r.binomial(1,.5,n)+1
    race = r.integers(1,6,n); edu = r.integers(1,6,n); mar = r.integers(1,7,n)
    lp = (-3.0 + slope*(0.05*(age-52) + 0.5*htn + 0.6*dm + 0.5*mi + 0.4*es
                        + 0.3*cs_full + 0.02*(bmi-28) - 0.15*(pir-2.2))
          ) + intercept_shift
    p = 1/(1+np.exp(-lp)); y = r.binomial(1, p)
    phq = np.zeros((n,9), dtype=int)
    # tie a mild association between true risk and depressive items (for assoc test only)
    for j in range(9):
        phq[:,j] = (r.binomial(1, np.clip(0.05+0.25*p,0,1)))
    df = pd.DataFrame({
        "age":age,"income_pir":pir,"bmi":bmi,"ever_smoker":es,"current_smoker":cs_full,
        "alcohol":alcohol,"hypertension":htn,"high_cholesterol":chol,"diabetes":dm,
        "heart_attack":mi,"sex":sex,"race_ethnicity":race,"education":edu,"marital":mar,
        "stroke":y})
    for j,it in enumerate(C.PHQ_ITEMS): df["phq_"+it]=phq[:,j]
    df["weight"]=1.0; df["psu"]=r.integers(1,50,n); df["strata"]=r.integers(1,30,n)
    return df

def main():
    checks = []
    # build derivation (two cycles) + external (attenuated signal => slope<1 on frozen model)
    d1 = synth(9000, seed=11); d1["cycle"]="_I"; d1["cycle_label"]="synth A"
    d2 = synth(9000, seed=12); d2["cycle"]="_J"; d2["cycle_label"]="synth B"
    ext = synth(6000, slope=0.6, intercept_shift=-0.3, seed=13); ext["cycle"]="_L"; ext["cycle_label"]="synth ext"
    deriv = pd.concat([d1,d2], ignore_index=True)
    allp  = pd.concat([d1,d2,ext], ignore_index=True)

    # (1) leakage unit test: imputer must use TRAIN median, never test median
    Xtr = pd.DataFrame({"a":[1.,2.,3.,4.,5.]})  # median 3
    ytr = np.array([0,1,0,1,0])
    Xte = pd.DataFrame({"a":[100.,100.,np.nan]})  # extreme + missing
    pipe = M.get_pipeline("logistic").fit(Xtr, ytr)
    impmed = pipe.named_steps["imp"].statistics_[0]
    checks.append(("imputer fit on train only (median==3.0)", abs(impmed-3.0)<1e-9, f"got {impmed}"))

    # (2) pure-noise feature => AUROC ~ 0.5 (no spurious signal, no leakage)
    noise = deriv.copy()
    noise["stroke"] = np.random.default_rng(99).permutation(noise["stroke"].values)
    mnoise = M.internal_cv(noise, "logistic")  # label permuted => near chance
    checks.append(("permuted-label AUROC ~0.5 (<0.56)", mnoise["auroc"]<0.56, f"{mnoise['auroc']:.3f}"))

    # (3) signal recovery on real synthetic derivation
    mint = M.internal_cv(deriv, "logistic")
    checks.append(("signal recovered AUROC>0.70", mint["auroc"]>0.70, f"{mint['auroc']:.3f}"))
    checks.append(("bootstrap CI brackets AUROC", mint["auroc_lo"]<mint["auroc"]<mint["auroc_hi"],
                   f"[{mint['auroc_lo']:.3f},{mint['auroc_hi']:.3f}]"))

    # (3b) calibration metric validity via clean holdout (fit half -> predict half): slope ~1
    from sklearn.model_selection import train_test_split
    M.DESIGN_COLS = None
    Xa, ya, _ = M.design(deriv)
    Xtr, Xte_h, ytr, yte_h = train_test_split(Xa, ya, test_size=0.4, random_state=C.SEED, stratify=ya)
    _, p_h = M.fit_predict(Xtr, ytr, Xte_h, "logistic")
    ci_h, cs_h = M.cal_intercept_slope(yte_h, p_h)
    checks.append(("holdout cal slope ~1 (0.85-1.15)", 0.85<cs_h<1.15, f"slope {cs_h:.3f} int {ci_h:.3f}"))

    # (4) domain shift => frozen model attenuated on external (slope<1)
    _, mext = M.temporal_validation(allp, "logistic")
    checks.append(("frozen-on-shifted cal slope<0.9 (attenuation)", mext["cal_slope"]<0.9, f"{mext['cal_slope']:.3f}"))

    # (5) adaptation restores calibration + monotonic recalibration never hurts AUROC
    M.DESIGN_COLS = None
    Xd, yd, _ = M.design(deriv); Xe, ye, _ = M.design(ext)
    tbl, ks = M._adapt_eval(Xd, yd, Xe, ye, k_list=[150,300,600,1200,2400], name="logistic", repeats=8)
    tbl.to_csv(os.path.join(os.path.dirname(__file__), "..", "output", "synth_adaptation.csv"), index=False)
    froz_s = tbl[tbl.method=="frozen"]["cal_slope_mean"].mean()
    kmax = max(ks)
    is_at_kmax = tbl[(tbl.method=="intercept+slope") & (tbl.k==kmax)]["cal_slope_mean"].iloc[0]
    checks.append((f"intercept+slope cal_slope at k={kmax} closer to 1 than frozen",
                   abs(is_at_kmax-1) < abs(froz_s-1), f"frozen {froz_s:.2f} -> i+s {is_at_kmax:.2f}"))
    is_auroc = tbl[(tbl.method=="intercept+slope") & (tbl.k==kmax)]["auroc_mean"].iloc[0]
    froz_auroc = tbl[tbl.method=="frozen"]["auroc_mean"].mean()
    checks.append(("monotonic recalibration keeps AUROC == frozen (no inversion)",
                   abs(is_auroc - froz_auroc) < 0.02, f"{froz_auroc:.3f} vs {is_auroc:.3f}"))
    # data-efficiency: retrain AUROC should rise with k toward internal level
    rt = tbl[tbl.method=="retrain"].sort_values("k")
    checks.append(("retrain AUROC rises with adaptation size",
                   rt["auroc_mean"].iloc[-1] > rt["auroc_mean"].iloc[0] + 0.02,
                   f"k{rt['k'].iloc[0]}:{rt['auroc_mean'].iloc[0]:.3f} -> k{rt['k'].iloc[-1]}:{rt['auroc_mean'].iloc[-1]:.3f}"))

    # (6) LOSO runs and yields one row per race group
    loso = M.loso_groups(allp)
    checks.append(("LOSO returns >=4 groups", len(loso)>=4, f"{len(loso)} rows"))

    # (7) DCA: model net benefit exceeds treat-all somewhere in range
    p_oof = mint["_oof"]; y = deriv["stroke"].values
    nbs = np.array([M.net_benefit(y,p_oof,pt) for pt in M.THRESHOLDS])
    nba = np.array([M.nb_all(y,pt) for pt in M.THRESHOLDS])
    checks.append(("model NB > treat-all at low thresholds", np.nanmax(nbs-nba) > 1e-3,
                   f"max gain {np.nanmax(nbs-nba):.4f}"))

    # (8) importance is finite & sorted
    imp = M.importance(deriv, "gradient_boosting")
    checks.append(("permutation importance computed", np.isfinite(imp["importance"]).all(),
                   f"top={imp.iloc[0]['feature']}"))

    print("\n===== SYNTHETIC PIPELINE VALIDATION =====")
    allok = True
    for name, ok, detail in checks:
        print(f"[{'PASS' if ok else 'FAIL'}] {name}  ({detail})")
        allok &= bool(ok)
    print("\nVERDICT:", "ALL PASS - pipeline safe for real data" if allok else "SOME FAILED - fix before real run")
    sys.exit(0 if allok else 1)

if __name__ == "__main__":
    main()
