"""Publication figures for the NHANES stroke risk-stratification study.

Every figure is produced FROM the saved numeric outputs (analysis/output/*.csv|npz|json)
so the picture can never drift from the reported numbers. Each panel is an independent
5.5 x 5.5 cm file saved as 300-dpi PNG + editable vector PDF (fonttype 42).
"""
import os, json, numpy as np, pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter
from sklearn.metrics import roc_curve, auc

OUT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "output"))
FIG = os.path.abspath(os.path.join(OUT, "figures")); os.makedirs(FIG, exist_ok=True)

OI = {"black":"#000000","blue":"#0072B2","orange":"#E69F00","green":"#009E73",
      "verm":"#D55E00","sky":"#56B4E9","purple":"#CC79A7","yellow":"#F0E442","grey":"#999999"}
plt.rcParams.update({"font.family":"sans-serif","font.sans-serif":["Arial","DejaVu Sans"],
    "svg.fonttype":"none","pdf.fonttype":42,"ps.fonttype":42,"font.size":7,
    "axes.labelsize":7,"axes.titlesize":8,"xtick.labelsize":6,"ytick.labelsize":6,
    "axes.spines.top":False,"axes.spines.right":False,"axes.grid":True,
    "grid.alpha":0.25,"grid.linestyle":"--","legend.fontsize":6,"figure.dpi":300})
CM = 5.5/2.54

def save(fig, name):
    for ext in ("png","pdf"):
        fig.savefig(os.path.join(FIG, f"{name}.{ext}"), dpi=300, bbox_inches="tight")
    plt.close(fig)

def _new():
    fig, ax = plt.subplots(figsize=(CM, CM)); return fig, ax

MODEL_COLORS = {"logistic":OI["blue"],"elasticnet":OI["green"],"random_forest":OI["verm"],
    "gradient_boosting":OI["orange"],"xgboost":OI["purple"],"lightgbm":OI["sky"]}
MODEL_SHORT = {"logistic":"Logit","elasticnet":"ENet","random_forest":"RF",
    "gradient_boosting":"GB","xgboost":"XGB","lightgbm":"LGB"}

def cal_bins(y, p, nb=10):
    q = pd.qcut(p, nb, labels=False, duplicates="drop")
    d = pd.DataFrame({"b":q,"pred":p,"obs":y}).groupby("b").agg(pred=("pred","mean"),obs=("obs","mean"))
    return d.reset_index()

def fig_auroc(df, kind, path):
    fig, ax = _new()
    x=np.arange(len(df)); cols=[MODEL_COLORS[m] for m in df.model]
    if path=="internal" and "auroc_lo" in df:
        ax.bar(x, df.auroc, color=cols, edgecolor=OI["black"], lw=0.4)
        ax.errorbar(x, df.auroc, yerr=[df.auroc-df.auroc_lo, df.auroc_hi-df.auroc],
                    fmt="none", ecolor=OI["black"], capsize=2, lw=0.6)
    else:
        ax.bar(x, df.auroc, color=cols, edgecolor=OI["black"], lw=0.4)
    ax.axhline(0.5, color=OI["grey"], lw=0.6, ls=":")
    ax.set_xticks(x); ax.set_xticklabels([MODEL_SHORT[m] for m in df.model], fontsize=6)
    ax.set_ylim(0.4,0.9); ax.set_ylabel("AUROC")
    ax.set_title(f"Discrimination ({kind})")
    ax.axhline(df[df.model=="logistic"].auroc.iloc[0], color=OI["black"], lw=0.6, ls="--")
    save(fig, path); return fig

def fig_brier(df, kind):
    fig, ax = _new(); x=np.arange(len(df))
    ax.bar(x, df.brier, color=[MODEL_COLORS[m] for m in df.model], edgecolor=OI["black"], lw=0.4)
    ax.axhline(df[df.model=="logistic"].brier.iloc[0], color=OI["black"], lw=0.6, ls="--")
    ax.set_xticks(x); ax.set_xticklabels([MODEL_SHORT[m] for m in df.model], fontsize=6)
    ax.set_ylabel("Brier score"); ax.set_title(f"Calibration reliability ({kind})")
    save(fig, f"brier_{kind}"); return fig

def fig_roc(y, pdict, kind):
    fig, ax = _new()
    for lab,p in pdict.items():
        fpr,tpr,_=roc_curve(y,p); ax.plot(fpr,tpr,lw=1.0,color=MODEL_COLORS.get(lab,OI["black"]),label=MODEL_SHORT.get(lab,lab))
    ax.plot([0,1],[0,1],color=OI["grey"],lw=0.6,ls=":"); ax.set_xlabel("1 - specificity")
    ax.set_ylabel("sensitivity"); ax.set_title(f"ROC ({kind})"); ax.legend(loc="lower right")
    save(fig, f"roc_{kind}"); return fig

def fig_calibration(caldict, kind):
    fig, ax = _new()
    ax.plot([0,1],[0,1],color=OI["grey"],lw=0.8,ls=":")
    for lab,d in caldict.items():
        ax.plot(d["pred"], d["obs"], marker="o", ms=3, lw=1.0, color=MODEL_COLORS.get(lab,OI["black"]), label=MODEL_SHORT.get(lab,lab))
    ax.set_xlabel("Predicted risk"); ax.set_ylabel("Observed frequency")
    ax.set_title(f"Calibration ({kind})"); ax.legend(loc="upper left")
    save(fig, f"calibration_{kind}"); return fig

def fig_dca(dca, kind):
    fig, ax = _new(); thr=np.array(dca["threshold"])
    m=np.array(dca[f"{kind}_model"]); a=np.array(dca[f"{kind}_all"])
    ax.plot(thr,m,color=MODEL_COLORS["logistic"],lw=1.2,label="Model")
    ax.plot(thr,a,color=OI["verm"],lw=1.0,ls="--",label="Treat all")
    ax.axhline(0,color=OI["black"],lw=0.8,label="Treat none")
    ax.set_xlabel("Threshold probability"); ax.set_ylabel("Net benefit")
    ax.set_title(f"Decision curve ({kind})"); ax.legend(loc="upper right")
    ax.set_xlim(0,0.3); save(fig, f"dca_{kind}"); return fig

def fig_loso(loso, metric):
    fig, ax = _new(); x=np.arange(len(loso))
    ax.bar(x, loso[metric], color=OI["blue"], edgecolor=OI["black"], lw=0.4)
    if metric=="auroc": ax.axhline(0.5,color=OI["grey"],lw=0.6,ls=":")
    if metric=="cal_slope": ax.axhline(1,color=OI["black"],lw=0.6,ls="--")
    ax.set_xticks(x); ax.set_xticklabels([g.replace(" ","\n").replace("Non-Hispanic","NH")
        .replace("Mexican American","MexAm").replace("Other/Multi (incl. Asian)","Other")
        .replace("Other Hispanic","OthHisp") for g in loso.group], fontsize=5)
    ax.set_ylabel({"auroc":"AUROC","cal_slope":"Calibration slope"}[metric])
    ax.set_title("Race/ethnicity LOSO")
    save(fig, f"loso_{metric}"); return fig

def fig_adapt(adapt, metric):
    fig, ax = _new()
    for m,lab in [("frozen","Frozen"),("intercept","Intercept"),
                  ("intercept+slope","Int+Slope"),("retrain","Retrain")]:
        d=adapt[adapt.method==m].sort_values("k")
        ax.plot(d.k, d[metric], marker="o", ms=3, lw=1.1, label=lab)
    ax.set_xscale("log"); ax.set_xlabel("Local adaptation sample size (n)")
    ax.set_ylabel({"cal_slope_mean":"Calibration slope","brier_mean":"Brier",
                   "auroc_mean":"AUROC"}[metric])
    if metric=="cal_slope_mean": ax.axhline(1,color=OI["black"],lw=0.6,ls="--")
    ax.set_title("Data-efficient adaptation"); ax.legend(fontsize=5)
    save(fig, f"adaptation_{metric}"); return fig

def fig_importance(imp):
    fig, ax = _new(); top=imp.head(10).iloc[::-1]
    names={"age":"Age","income_pir":"Income (PIR)","heart_attack":"Myocardial infarction",
           "bmi":"BMI","hypertension":"Hypertension","diabetes":"Diabetes","current_smoker":"Current smoker",
           "ever_smoker":"Ever smoker","alcohol":"Alcohol","high_cholesterol":"High cholesterol",
           "education_2":"Education <HS","education_3":"Education HS/GED","education_4":"Education Some college",
           "education_5":"Education College+","race_ethnicity_2":"Other Hispanic","race_ethnicity_3":"NH White",
           "race_ethnicity_4":"NH Black","race_ethnicity_5":"Other/Multi race","marital_2":"Widowed",
           "marital_3":"Divorced","marital_4":"Separated","marital_5":"Never married","marital_6":"Marital other",
           "sex_2":"Female"}
    def lbl(f): return names.get(f, f.replace("_"," ").title())
    ax.barh(range(len(top)), top.importance, xerr=top.sd, color=OI["green"], edgecolor=OI["black"],
            lw=0.4, height=0.7, capsize=2)
    ax.set_yticks(range(len(top))); ax.set_yticklabels([lbl(f) for f in top.feature], fontsize=5.5)
    ax.set_xlabel("Permutation importance (AUPRC drop)"); ax.set_title("Feature contribution")
    ax.grid(axis="x"); ax.spines["left"].set_visible(False)
    save(fig, "importance"); return fig

def fig_phq(dec):
    fig, ax = _new()
    ax.bar(dec.risk_decile+1, dec.phq10_w*100, color=OI["purple"], edgecolor=OI["black"], lw=0.4)
    ax2=ax.twinx(); ax2.plot(dec.risk_decile+1, dec.risk_mean*100, color=OI["black"], lw=1.0, marker="o", ms=3)
    ax2.set_ylabel("Mean predicted stroke risk (%)", fontsize=6); ax2.grid(False)
    ax.set_xlabel("Stroke-risk decile"); ax.set_ylabel("% with clinically significant\ndepressive symptoms (PHQ>=10)")
    ax.set_title("Risk score tracks mental health")
    save(fig, "phq_association"); return fig

def main():
    mi=pd.read_csv(os.path.join(OUT,"model_internal.csv")); me=pd.read_csv(os.path.join(OUT,"model_temporal.csv"))
    fig_auroc(mi,"Internal CV","auroc_internal"); fig_auroc(me,"Temporal external","auroc_external")
    fig_brier(mi,"internal"); fig_brier(me,"external")
    pr=np.load(os.path.join(OUT,"probs.npz"))
    fig_roc(pr["y_int"], {"logistic":pr["p_log_int"],"gradient_boosting":pr["p_gb_int"],"random_forest":pr["p_rf_int"]}, "internal")
    fig_roc(pr["y_ext"], {"logistic":pr["p_log_ext"],"gradient_boosting":pr["p_gb_ext"],"random_forest":pr["p_rf_ext"]}, "external")
    cal_i = {"logistic":cal_bins(pr["y_int"],pr["p_log_int"]),
             "gradient_boosting":cal_bins(pr["y_int"],pr["p_gb_int"]),
             "random_forest":cal_bins(pr["y_int"],pr["p_rf_int"])}
    cal_e = {"logistic":cal_bins(pr["y_ext"],pr["p_log_ext"]),
             "gradient_boosting":cal_bins(pr["y_ext"],pr["p_gb_ext"]),
             "random_forest":cal_bins(pr["y_ext"],pr["p_rf_ext"])}
    fig_calibration(cal_i, "internal"); fig_calibration(cal_e, "external")
    dca=pd.read_csv(os.path.join(OUT,"dca_curves.csv"), index_col=None)
    for kind in ("internal","external"):
        fig_dca({ "threshold":dca["threshold"].values,
                  "internal_model":dca["internal_model"].values,"internal_all":dca["internal_all"].values,
                  "external_model":dca["external_model"].values,"external_all":dca["external_all"].values}, kind)
    loso=pd.read_csv(os.path.join(OUT,"loso_race.csv"))
    fig_loso(loso,"auroc"); fig_loso(loso,"cal_slope")
    adapt=pd.read_csv(os.path.join(OUT,"adaptation_external.csv"))
    fig_adapt(adapt,"cal_slope_mean"); fig_adapt(adapt,"brier_mean")
    fig_importance(pd.read_csv(os.path.join(OUT,"importance.csv")))
    fig_phq(pd.read_csv(os.path.join(OUT,"phq_by_risk_decile.csv")))
    files=sorted(os.listdir(FIG)); print(f"{len(files)} files in figures/:"); print(files)

if __name__=="__main__":
    main()
