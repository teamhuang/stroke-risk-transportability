"""REAL NHANES analysis driver. Computes all headline numbers and dumps them to
analysis/output/ (CSV + JSON + arrays). Figures are produced by make_figures.py FROM
these saved outputs (traceability: figure is newer than, and derived from, the numbers).
"""
import os, sys, json, time, numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(__file__))
import config as C, modeling as M

HERE = os.path.dirname(__file__)
OUT = os.path.abspath(os.path.join(HERE, "..", "output"))
os.makedirs(OUT, exist_ok=True)
DPROC = os.path.abspath(os.path.join(HERE, "..", "..", "data", "processed"))

def log(*a): print(time.strftime("%H:%M:%S"), *a, flush=True)

# ---------------- survey design helpers ----------------
def weighted_prop(y, w):
    w = np.asarray(w, float); y = np.asarray(y, float)
    m = ~np.isnan(w) & ~np.isnan(y)
    return float(np.sum(w[m]*y[m]) / np.sum(w[m]))

def cluster_bootstrap_prop(df, ycol, B=500, seed=C.SEED):
    """Design-aware CI for a weighted proportion: resample PSUs within strata."""
    rng = np.random.default_rng(seed)
    d = df.dropna(subset=["psu","strata",ycol,"weight"]).copy()
    d["_y"] = d[ycol].astype(float)
    by_str = {s: g for s, g in d.groupby("strata")}
    props = []
    for _ in range(B):
        rows = []
        for s, g in by_str.items():
            psus = g["psu"].unique()
            if len(psus) == 0: continue
            # take 2 PSUs per stratum (NHANES balanced design); resample with replacement
            pick = rng.choice(psus, size=min(len(psus), len(psus)), replace=True)
            # replicate each picked PSU's rows with multiplicity
            for pu in pick:
                rows.append(g[g["psu"] == pu])
        samp = pd.concat(rows) if rows else g
        try: props.append(weighted_prop(samp["_y"].values, samp["weight"].values))
        except Exception: continue
    p = np.array(props)
    return float(np.percentile(p,2.5)), float(np.percentile(p,97.5))

# ---------------- Table 1 ----------------
def table1(df):
    deriv = df[df["cycle"].isin(C.DERIVATION)]
    rows = []
    def add(label, series, kind):
        for grp, name in [(df[df.stroke==1], "stroke"), (df[df.stroke==0], "nostroke"), (df, "overall")]:
            sub = grp.dropna(subset=[series])
            if sub.empty: rows.append({"var":label,"group":name,"n":0,"val":np.nan}); continue
            if kind=="cont":
                w=sub["weight"].values; v=sub[series].values
                wm=float(np.sum(w*v)/np.sum(w)) if not np.all(np.isnan(w)) else np.nanmean(v)
                rows.append({"var":label,"group":name,"n":len(sub),"val":wm})
            else:
                p=weighted_prop(sub[series].values, sub["weight"].values)
                rows.append({"var":label,"group":name,"n":len(sub),"val":p})
    add("Age (years)", "age", "cont")
    add("Female", "sex", "cat")            # sex coded 1/2 -> handled below
    add("BMI (kg/m2)", "bmi", "cont")
    add("Income-to-poverty ratio", "income_pir", "cont")
    for v,nm in [("hypertension","Hypertension"),("diabetes","Diabetes"),("high_cholesterol","High cholesterol"),
                 ("heart_attack","Myocardial infarction"),("ever_smoker","Ever smoker"),
                 ("current_smoker","Current smoker"),("alcohol","Regular alcohol use")]:
        add(nm, v, "bin")
    t = pd.DataFrame(rows)
    t.to_csv(os.path.join(OUT,"table1_characteristics.csv"), index=False)
    return t

# ---------------- main ----------------
def main():
    df = pd.read_csv(os.path.join(DPROC,"nhanes_stroke_harmonized.csv"))
    # fix sex for display (1=male,2=female) -> female proportion
    df["sex_female"] = (pd.to_numeric(df["sex"],errors="coerce")==2).astype(float)
    df.loc[pd.to_numeric(df["sex"],errors="coerce").isna(), "sex_female"]=np.nan
    # replace the 'sex' used in table1 helper above:
    log("rows", len(df), "events", int(df['stroke'].sum()), "prevalence", round(df['stroke'].mean(),4))

    # ---- design-weighted prevalence (overall + by cycle) ----
    prov = {"overall_unweighted": float(df["stroke"].mean()),
            "overall_weighted": weighted_prop(df["stroke"].values, df["weight"].values)}
    lo,hi = cluster_bootstrap_prop(df, "stroke")
    prov["overall_weighted_ci"] = [lo,hi]
    by_cycle = {}
    for lab,g in df.groupby("cycle_label"):
        w=weighted_prop(g["stroke"].values,g["weight"].values)
        try:
            cl,cu=cluster_bootstrap_prop(g,"stroke")
        except Exception: cl=cu=np.nan
        by_cycle[lab]={"n":int(len(g)),"events":int(g["stroke"].sum()),
                       "crude_prev":float(g["stroke"].mean()),"weighted_prev":w,"w_ci":[cl,cu]}
    prov["by_cycle"]=by_cycle
    log("weighted prevalence", round(prov["overall_weighted"],4), prov["overall_weighted_ci"])

    deriv = df[df["cycle"].isin(C.DERIVATION)].copy()
    ext   = df[df["cycle"].isin(C.EXTERNAL)].copy()

    # ---- 6-model internal CV (derivation) + temporal external ----
    perf_int, perf_ext = [], []
    for name in C.MODELS:
        m_int = M.internal_cv(deriv, name)
        m_int_ext = M.internal_cv(ext, name) if False else None
        # temporal frozen
        Xd,yd,_ = M.design(deriv); Xe,ye,_ = M.design(ext)
        _, pe = M.fit_predict(Xd, yd, Xe, name)
        me = M.compute_metrics(ye, pe); me["model"]=name; me["train_auroc_internal"]=m_int["auroc"]
        me["auroc_decay"]=me["auroc"]-m_int["auroc"]
        m_int["model"]=name
        perf_int.append({k:m_int[k] for k in ["model","n","events","auroc","auroc_lo","auroc_hi",
                        "auprc","brier","cal_intercept","cal_slope"]})
        perf_ext.append({k:me[k] for k in ["model","n","events","prevalence","auroc","auprc",
                        "brier","cal_intercept","cal_slope","train_auroc_internal","auroc_decay"]})
        log(f"[{name}] internal AUROC {m_int['auroc']:.3f} ext AUROC {me['auroc']:.3f} decay {me['auroc_decay']:+.3f}")

    perf_int=pd.DataFrame(perf_int); perf_ext=pd.DataFrame(perf_ext)
    base=perf_int.loc[perf_int.model=="logistic","auroc"].values[0]
    perf_int["gain_vs_logistic"]=perf_int["auroc"]-base
    base_e=perf_ext.loc[perf_ext.model=="logistic","auroc"].values[0]
    perf_ext["gain_vs_logistic"]=perf_ext["auroc"]-base_e
    perf_int.to_csv(os.path.join(OUT,"model_internal.csv"),index=False)
    perf_ext.to_csv(os.path.join(OUT,"model_temporal.csv"),index=False)

    # ---- save probs for figures (logistic + gradient_boosting) ----
    M.DESIGN_COLS=None
    Xd,yd,_=M.design(deriv); Xe,ye,_=M.design(ext)
    plog_oof = M.internal_cv(deriv,"logistic")["_oof"]
    _, plog_ext = M.fit_predict(Xd,yd,Xe,"logistic")
    _, pgb_ext = M.fit_predict(Xd,yd,Xe,"gradient_boosting")
    pgb_oof = M.internal_cv(deriv,"gradient_boosting")["_oof"]
    _, prf_ext = M.fit_predict(Xd,yd,Xe,"random_forest")
    prf_oof = M.internal_cv(deriv,"random_forest")["_oof"]
    np.savez(os.path.join(OUT,"probs.npz"),
             y_int=yd, p_log_int=plog_oof, p_gb_int=pgb_oof, p_rf_int=prf_oof,
             y_ext=ye, p_log_ext=plog_ext, p_gb_ext=pgb_ext, p_rf_ext=prf_ext)

    # ---- race-LOSO transportability (all cycles) ----
    loso = M.loso_groups(df)
    loso.to_csv(os.path.join(OUT,"loso_race.csv"),index=False)

    # ---- adaptation / data-efficiency on external (frozen logistic from derivation) ----
    kmax=len(Xe)
    k_list=[int(f*kmax) for f in [0.02,0.05,0.1,0.2,0.35,0.5]]
    adapt, ks = M._adapt_eval(Xd,yd,Xe,ye,k_list=k_list,name="logistic",repeats=10)
    adapt.to_csv(os.path.join(OUT,"adaptation_external.csv"),index=False)

    # ---- permutation importance (gradient boosting, derivation) ----
    imp = M.importance(deriv,"gradient_boosting")
    imp.to_csv(os.path.join(OUT,"importance.csv"),index=False)

    # ---- DCA net benefit (logistic OOF internal + external frozen) ----
    thr = M.THRESHOLDS
    nb = {"threshold":thr.tolist(),
          "internal_model":[float(M.net_benefit(yd,plog_oof,t)) for t in thr],
          "internal_all":[float(M.nb_all(yd,t)) for t in thr],
          "external_model":[float(M.net_benefit(ye,plog_ext,t)) for t in thr],
          "external_all":[float(M.nb_all(ye,t)) for t in thr]}
    pd.DataFrame(nb).to_csv(os.path.join(OUT,"dca_curves.csv"),index=False)

    # ---- calibration (binned) internal OOF + external ----
    def cal_bins(y,p,nb=10):
        q=pd.qcut(p,nb,labels=False,duplicates="drop")
        return pd.DataFrame({"bin":q,"pred":p,"obs":y}).groupby("bin").agg(
            pred=("pred","mean"),obs=("obs","mean"),n=("obs","size")).reset_index()
    cal_bins(yd,plog_oof).to_csv(os.path.join(OUT,"calibration_internal.csv"),index=False)
    cal_bins(ye,plog_ext).to_csv(os.path.join(OUT,"calibration_external.csv"),index=False)

    # ---- risk-score vs PHQ>=10 association (cross-fitted OOF risk, derivation) ----
    phq_cols=[c for c in deriv.columns if c.startswith("phq_")]
    dd=deriv.copy(); dd["risk"]=plog_oof
    valid=dd[phq_cols].notna().all(axis=1)
    d2=dd[valid].copy()
    d2["phq_total"]=d2[phq_cols].clip(0,3).sum(axis=1)
    d2["phq10"]=(d2["phq_total"]>=C.PHQ_CUTOFF).astype(int)
    d2["risk_decile"]=pd.qcut(d2["risk"],10,labels=False,duplicates="drop")
    dec=d2.groupby("risk_decile").apply(lambda g: pd.Series({
        "n":len(g),"risk_mean":g["risk"].mean(),
        "phq10_w": weighted_prop(g["phq10"].values,g["weight"].values),
        "phq_total_mean": g["phq_total"].mean()})).reset_index()
    dec.to_csv(os.path.join(OUT,"phq_by_risk_decile.csv"),index=False)
    # OR per SD of risk: UNWEIGHTED logistic with HC1 robust SE (do NOT use freq_weights:
    # treating survey weights as case counts pseudo-replicates and destroys the CI).
    import statsmodels.api as sm
    rz = ((d2["risk"]-d2["risk"].mean())/d2["risk"].std()).values
    try:
        lr = sm.GLM(d2["phq10"].values, sm.add_constant(rz),
                    family=sm.families.Binomial()).fit(cov_type="HC1")
        or_sd=float(np.exp(lr.params[1])); ci=np.exp(lr.conf_int()[1]).tolist(); pv=float(lr.pvalues[1])
    except Exception:
        lr=sm.Logit(d2["phq10"].values, sm.add_constant(rz)).fit(disp=0)
        or_sd=float(np.exp(lr.params[1])); ci=np.exp(lr.conf_int()[1]).tolist(); pv=float(lr.pvalues[1])
    assoc={"or_per_sd_risk":or_sd,"ci":ci,"p":pv,
           "method":"unweighted logistic, HC1 robust SE, n=%d"%len(d2),
           "spearman_risk_phqtotal": float(pd.Series(d2["risk"]).corr(pd.Series(d2["phq_total"]),method="spearman")),
           "n":int(len(d2))}

    summary = {"n_analyzed":int(len(df)),"events":int(df["stroke"].sum()),
               "prevalence":prov,"model_internal":perf_int.to_dict("records"),
               "model_temporal":perf_ext.to_dict("records"),
               "association":assoc,
               "adaptation_at_max":adapt[adapt.k==max(ks)].to_dict("records")}
    with open(os.path.join(OUT,"summary.json"),"w") as f: json.dump(summary,f,indent=2,default=float)
    table1(df)
    log("DONE. outputs written to", OUT)

if __name__=="__main__":
    main()
