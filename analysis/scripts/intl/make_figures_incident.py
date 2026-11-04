"""Publication figures for the INCIDENT-stroke arm.

Every panel is generated from the dated CSVs in results/tables/ that the manuscript's tables are
transcribed from, so a figure and a table cannot disagree. One independent panel per file, 5.5 x 5.5
cm, PNG (300 dpi) + vector PDF, Okabe-Ito colour-blind-safe palette, Arial - the same hygiene as the
cross-sectional arm's figures.

Two rules this script exists to enforce, both learned the expensive way (docs/SELF_AUDIT.md defects
8-15):
  * nothing reads `data/processed/` any more, only `results/tables/`, because that directory holds two
    generations of the same filename pattern and a default glob finds the superseded one;
  * every estimator that a panel can be drawn under is named in the filename (horizon rule, fitting
    scale, coverage rule), so a figure cannot silently mix two of them. The pre-audit `exclusive_start`
    frame is drawn as its own panel beside the reported one rather than as an annotation.

Panels
  incident_adapt_nb            net benefit at 5% vs local sample size, five arms, four countries
  incident_adapt_scale         the same intercept fitted on two scales, paired gain per replicate
  incident_adapt_auroc         horizon AUROC vs local sample size, frozen vs retrained, four countries
  incident_level_{interval,composed}  mean predicted risk per country per model against observed
  incident_composition         single four-year interval vs the composed hazard, per country
  incident_estimand_cif        Aalen-Johansen stroke CIF under three dating rules + naive 1-KM
  incident_ascertainment       permissive vs strict coverage: incidence, level error, repair value
  incident_subgroup_age        AUROC and net benefit by age band, held-out country by country
  incident_internal_vs_loco    internal (person-clustered) vs mean held-out AUROC, y = x reference
  incident_spread              best-minus-worst held-out AUROC across countries, by model
  incident_ablation_skill      Brier skill vs the train-prevalence constant, class-weight ablation
  incident_vs_prevalent        same model, prevalent vs incident held-out AUROC
  incident_link_grid           predicted ÷ observed under four hazard links and five ways of writing
                               the same follow-up
  incident_calibration_curves  decile calibration per panel, frozen vs locally repaired, with
                               person-clustered intervals on the observed risk
  incident_sample_flow         the cascade from interviews to the four-year evaluation frame

Usage: python make_figures_incident.py
"""
import os, sys, numpy as np, pandas as pd
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
T = os.path.join(ROOT, "results", "tables")
FIGD = os.path.join(ROOT, "deliverables", "figures", "incident"); os.makedirs(FIGD, exist_ok=True)

import nature_style as NS
NS.configure()
OI = {"blue": NS.BLUE, "orange": NS.AMB, "green": NS.GRN, "verm": NS.VERM,
      "purple": NS.PUP, "sky": NS.SKY, "grey": "#999999", "yellow": "#F0E442",
      "black": "#222222"}
SHORT = {"logistic": "Logit", "elasticnet": "ElasticNet", "spline_logistic": "Spline",
         "agesex_logistic": "Age+Sex", "random_forest": "RF", "random_forest_balanced": "RF(w)",
         "xgboost": "XGB", "gradient_boosting": "GB", "lightgbm": "LGBM",
         "rf_balanced": "RF(w)", "rf_plain": "RF", "rf_platt": "RF+Platt", "rf_iso": "RF+Iso"}
ORDER = ["logistic", "elasticnet", "spline_logistic", "random_forest", "xgboost",
         "gradient_boosting", "lightgbm", "random_forest_balanced", "agesex_logistic"]
CTRY = {"CN": "China", "KR": "Korea", "MX": "Mexico", "US": "United States"}
CC = ["CN", "KR", "MX", "US"]
CCOL = {"CN": OI["blue"], "KR": OI["orange"], "MX": OI["green"], "US": OI["purple"]}
FZ = "incident_loco_common_H4_2026-11-03.csv"
RC = "incident_horizon_recal_2026-11-03.csv"
CIF = "incident_competing_risks_cif_2026-11-03.csv"
ASC = "incident_ascertainment_sensitivity_2026-11-03.csv"
SG = "incident_subgroups_2026-11-03.csv"
IN = "incident_internal_clustered_2026-11-03.csv"
AB = "rf_probability_ablation_common_2026-11-03.csv"
PV = "loco_4country_corrected_2026-11-02.csv"
FRACS = [0.02, 0.05, 0.10, 0.25, 0.50]
RULE = "cif_mid"
DAY_CC = "2026-11-03.csv"


def primary(d):
    """Rows belonging to the reported estimand.

    The interval-scale rows of the LOCO table carry no `horizon_rule` at all - a per-interval event
    indicator is the same object under every dating convention - so a naive `== "cif_mid"` filter
    silently deletes them and draws an empty panel. Nulls are therefore part of the reported frame.
    """
    if "horizon_rule" not in d.columns:
        return d
    return d[(d.horizon_rule == RULE) | d.horizon_rule.isna()]


def need(d, what):
    if not len(d):
        sys.exit(f"empty panel: {what} - a filter dropped every row, fix the filter rather than "
                 f"publish a blank figure")
    return d


def cell(d, col, what, **kw):
    """One number for one panel position, with the row count and the ties checked rather than assumed.

    `.iloc[0]` on a filtered frame is how two estimands end up in one figure: the selection silently
    matches several rows and the first one happens to be whichever arm the writer ran last.
    """
    s = d
    for k, v in kw.items():
        s = s[s[k] == v]
    if not len(s):
        sys.exit(f"missing cell {what}: {kw}")
    vals = s[col].to_numpy(dtype=float)
    if not np.allclose(vals, vals[0], rtol=1e-9, atol=1e-12, equal_nan=True):
        sys.exit(f"ambiguous cell {what}: {kw} matched {len(vals)} different {col} values "
                 f"{np.round(vals, 6).tolist()}")
    return float(vals[0])


# titles that editorialise a conclusion on the canvas - stripped to a neutral label (the caption carries the point)
_CONCLUSION_TITLES = {
    "one intercept, fitted two ways": "one intercept, two fitting scales",
    "retraining helps the largest panel, not the others": "local retraining vs frozen",
    "the same model, composed vs one interval": "composed vs single interval",
    "the best internal model travelled worst": "internal vs held-out AUROC",
    "transport instability by model": "held-out AUROC spread",
    "class weights, not capacity": "Brier skill by class weight",
    "the estimand, not the algorithm, sets the ceiling": "prevalent vs incident outcome",
    "bars: model · dashes: treat-all": "net benefit by age band",
}


def save(fig, name, multi=None):
    """House-style finish: drop any on-figure note (suptitle), neutralise conclusion titles, snap to the
    exact 5 cm-tall canvas (5 cm wide single panel, 6.5 cm multi-panel) and write PNG + editable PDF."""
    if fig._suptitle is not None:
        fig._suptitle.set_text("")
    for ax in fig.axes:
        ttl = ax.get_title()
        if not ttl:
            continue
        if "\n" in ttl:                       # keep only the descriptive facet line, drop the conclusion lead
            ax.set_title(ttl.split("\n")[-1], fontsize=8)
        elif ttl in _CONCLUSION_TITLES:
            ax.set_title(_CONCLUSION_TITLES[ttl], fontsize=8)
        else:
            ax.title.set_fontsize(8)
    if multi is None:
        n = sum(1 for a in fig.axes if a.get_title() or a.get_xlabel() or a.get_ylabel())
        multi = n > 1
    NS.finalise(fig, name, FIGD, multi=multi)
    print("  ", name)


def read(name):
    p = os.path.join(T, name)
    if not os.path.exists(p):
        sys.exit(f"missing {name} - run intl/publish_incident_tables.py first")
    return pd.read_csv(p)


def adaptation():
    """Figure 1: net benefit against the size of the local sample, under the reported estimand.

    Five arms on identical evaluation persons, so every vertical gap inside a facet is a paired
    comparison. The two offset arms differ only in the scale the intercept was fitted on, and the
    panels show that this is not a cosmetic distinction.
    """
    r = read(RC)
    arms = [("frozen_sub", OI["grey"], "frozen"),
            ("offset_interval", OI["sky"], "intercept, interval fit"),
            ("offset_horizon", OI["blue"], "intercept, horizon fit"),
            ("recalibrate_horizon", OI["green"], "intercept + slope"),
            ("retrain_local", OI["verm"], "retrained locally")]
    for mdl in ["logistic", "xgboost"]:
        d = r[(r.model == mdl) & (r.frac > 0)]
        fig, axs = plt.subplots(2, 2, figsize=(2 * 5.5 / 2.54, 2 * 5.5 / 2.54))
        for ax, h in zip(axs.ravel(), CC):
            sub = d[d.held == h]
            band = sub[sub.strategy == "frozen_sub"].groupby("frac").nb_all_at_05.mean()
            # the band between treat-none (0) and treat-all: below it the rule is worse than
            # screening everyone, above it worse than screening no one
            ax.axhspan(0, band.mean(), color=OI["yellow"], alpha=.30, zorder=0, label="treat-all")
            ax.axhline(0, color=OI["black"], lw=.6)
            for s, c, lab in arms:
                x = sub[sub.strategy == s].groupby("frac").nb_at_05.mean()
                sd = sub[sub.strategy == s].groupby("frac").nb_at_05.std()
                x = x.reindex(FRACS); sd = sd.reindex(FRACS)
                ax.errorbar(x.index * 100, x, yerr=sd, color=c, marker="o", ms=2.6, lw=.9,
                            capsize=1.5, label=lab)
            ax.set_xscale("log"); ax.set_xticks([2, 5, 10, 25, 50])
            ax.set_xticklabels(["2", "5", "10", "25", "50"], fontsize=6)
            ax.set_title(CTRY[h], fontsize=8)
            ax.grid(axis="y")
        axs.ravel()[0].set_ylabel("net benefit")
        axs.ravel()[2].set_ylabel("net benefit")
        for ax in axs.ravel()[2:]:
            ax.set_xlabel("local sample (%)")
        h_, l_ = axs.ravel()[0].get_legend_handles_labels()
        fig.legend(h_, l_, fontsize=4.8, frameon=False, ncol=3, loc="lower center",
                   columnspacing=0.8, handlelength=1.3, bbox_to_anchor=(.5, -0.005))
        fig.suptitle(f"{SHORT[mdl]}: cif_mid four-year horizon, mean of 20 draws (SD bars)",
                     fontsize=7.5)
        fig.tight_layout(rect=[0, .19, 1, 1.0], pad=0.5, w_pad=1.6)
        save(fig, f"incident_adapt_nb_{mdl}")

    # paired gain of the two scales at the smallest sample - the P0 result on one axis
    d = r[(r.model == "logistic") & (r.frac == 0.02)]
    fig, ax = plt.subplots(figsize=(5.5 / 2.54, 5.5 / 2.54))
    pos = []
    for i, h in enumerate(CC):
        sub = d[d.held == h]
        fz = sub[sub.strategy == "frozen_sub"].set_index("rep").nb_at_05
        for j, (s, c, lab) in enumerate([("offset_interval", OI["sky"], "interval"),
                                         ("offset_horizon", OI["blue"], "horizon")]):
            g = (sub[sub.strategy == s].set_index("rep").nb_at_05 - fz).dropna()
            x = i * 2.4 + j * .8
            ax.scatter(np.full(len(g), x) + np.random.default_rng(7 + i).normal(0, .07, len(g)),
                       g, s=8, color=c, alpha=.55, lw=0)
            ax.errorbar(x, g.mean(), yerr=g.std(), color=OI["black"], marker="_", ms=12, lw=1,
                        capsize=2)
            pos.append((x, f"{h} {lab}"))
    ax.axhline(0, color=OI["black"], lw=.6, ls=":")
    ax.set_xticks([p[0] for p in pos]); ax.set_xticklabels([p[1] for p in pos], fontsize=5,
                                                           rotation=90)
    ax.set_ylabel("paired NB gain over frozen")
    ax.set_title("one intercept, fitted two ways", fontsize=7.5)
    save(fig, "incident_adapt_scale")

    # AUROC: freezing vs retraining
    fig, ax = plt.subplots(figsize=(5.5 / 2.54, 5.5 / 2.54))
    dl = r[(r.model == "logistic") & (r.frac > 0)]
    for h in CC:
        sub = dl[dl.held == h]
        for s, mk, lab in [("frozen_sub", "s", "frozen"), ("retrain_local", "o", "retrained")]:
            x = sub[sub.strategy == s].groupby("frac").auroc.mean().reindex(FRACS)
            ax.plot(x.index * 100, x, mk + "-", color=CCOL[h], ms=3,
                    label=f"{CTRY[h]} {lab}")
    ax.axhline(0.5, color=OI["black"], lw=.6, ls=":")
    ax.set_xscale("log"); ax.set_xticks([2, 5, 10, 25, 50])
    ax.set_xticklabels(["2", "5", "10", "25", "50"], fontsize=6)
    ax.set_xlabel("local sample (% of held-out adults)"); ax.set_ylabel("horizon AUROC")
    ax.set_title("retraining helps the largest panel, not the others", fontsize=7.5)
    ax.legend(fontsize=5, frameon=False, ncol=2)
    save(fig, "incident_adapt_auroc")


def levels():
    d = primary(read(FZ))
    for lv, tag, ttl in [("interval", "interval", "interval scale (per-interval hazard)"),
                         ("horizon_4y_composed", "composed", "four-year horizon, composed hazards")]:
        x = need(d[d.level == lv], f"incident_level_{tag}: level={lv}")
        ms = [m for m in ORDER if m in set(x.model)]
        pos = np.arange(len(ms)); w = .2
        fig, ax = plt.subplots(figsize=(5.5 / 2.54, 5.5 / 2.54))
        for i, h in enumerate(CC):
            v = [cell(x, "mean_pred", f"level {lv}", held=h, model=m) for m in ms]
            ob = cell(x, "obs_prev", f"observed {lv}", held=h)
            ax.bar(pos + (i - 1.5) * w, v, w, color=CCOL[h], label=CTRY[h])
            ax.hlines(ob, -0.5, len(ms) - .5, color=CCOL[h], lw=.8, ls="--")
        ax.set_yscale("log"); ax.set_xticks(pos)
        ax.set_xticklabels([SHORT[m] for m in ms], rotation=90, fontsize=6)
        ax.set_ylabel("mean predicted risk (log)")
        ax.set_title("ranking transports, level does not\n" + ttl, fontsize=7.5)
        ax.legend(fontsize=5.5, frameon=False, ncol=2)
        save(fig, f"incident_level_{tag}")

    # how much of the absolute risk is composition: one H-year interval vs ceil(H/L) hazards
    x = need(d[d.level.isin(["horizon_4y_single_interval", "horizon_4y_composed"])],
             "incident_composition")
    ms = ["logistic", "random_forest", "xgboost"]
    fig, ax = plt.subplots(figsize=(5.5 / 2.54, 5.5 / 2.54))
    pos = np.arange(len(CC)); w = .26
    for j, lv in enumerate(["horizon_4y_single_interval", "horizon_4y_composed"]):
        v = [cell(x[x.level == lv], "mean_pred", "composition", held=h, model="logistic")
             for h in CC]
        ax.bar(pos + (j - .5) * w, v, w, color=[OI["sky"], OI["blue"]][j],
               label=lv.split("_")[-1])
    ob = [cell(x[x.level == "horizon_4y_composed"], "obs_prev", "composition observed", held=h)
          for h in CC]
    ax.scatter(pos, ob, color=OI["black"], marker="h", s=18, zorder=5, label="observed")
    ax.set_yscale("log"); ax.set_xticks(pos); ax.set_xticklabels([CTRY[h] for h in CC], fontsize=6)
    ax.set_ylabel("mean predicted four-year risk (log)")
    ax.set_title("the same model, composed vs one interval", fontsize=7.5)
    ax.legend(fontsize=5.5, frameon=False)
    save(fig, "incident_composition")


def estimand():
    """What the label decision is worth: Aalen-Johansen stroke CIF under three dating rules."""
    d = read(CIF)
    fig, axs = plt.subplots(2, 2, figsize=(NS.W_PANEL_CM * NS.CM, NS.H_CM * NS.CM))
    for ax, h in zip(axs.ravel(), CC):
        sub = d[d.country == h]
        for rule, c, lab in [("start", OI["verm"], "dated at interval start"),
                             ("mid", OI["blue"], "dated at midpoint"),
                             ("end", OI["green"], "dated at interval end")]:
            s = sub[sub.stroke_dating == rule].sort_values("year")
            ax.plot(s.year, s.cif_stroke, "-", color=c, lw=1.1, label=lab)
        s = sub[sub.stroke_dating == "mid"].sort_values("year")
        ax.plot(s.year, s.naive_km1_stroke, ":", color=OI["black"], lw=1,
                label="naive 1-KM (death censored)")
        ax.set_xlim(0, 6); ax.set_xlabel("years from entry"); ax.set_ylim(0, None)
        ax.set_title(CTRY[h], fontsize=8)
    axs.ravel()[0].set_ylabel("cumulative incidence")
    axs.ravel()[2].set_ylabel("cumulative incidence")
    h_, l_ = axs.ravel()[0].get_legend_handles_labels()
    axs.ravel()[0].legend(h_, l_, fontsize=4.6, frameon=False, ncol=1, loc="upper left",
                          handlelength=1.2)
    NS.letters(fig, axs)
    fig.tight_layout(pad=0.5, w_pad=1.6, rect=(0, 0.02, 1, 1))
    save(fig, "incident_estimand_cif", multi=True)


def ascertainment():
    """Detection coverage: people known only to be alive are counted as observed in the primary frame.

    One panel of the level error (predicted / observed) per country under the primary permissive rule and the
    partial-strict sensitivity rule - the coverage rule barely moves the level error, which is the point. The
    observed incidence and the value of a repair under each rule are reported in Table 1 and Table 7 rather
    than crowded into a second and third panel.
    """
    d = read(ASC)
    d = d[d.model == "logistic"]
    rules = [("published_t_cens", NS.BLUE, "primary (permissive)"),
             ("strict_t_ask", NS.VERM, "partial-strict")]
    fig, ax = NS.grid(1, 1)
    pos = np.arange(len(CC))
    for j, (rl, c, lab) in enumerate(rules):
        v = []
        for h in CC:
            s = d[(d.held == h) & (d.coverage_rule == rl)]
            v.append(s["pred_over_obs_ipcw"].iloc[0] if len(s) else np.nan)
        ax.bar(pos + (j - .5) * .36, v, .36, color=c, label=lab)
    ax.axhline(1, color="#444444", lw=.7, ls=":")
    ax.set_xticks(pos); ax.set_xticklabels([CTRY[h] for h in CC], fontsize=6.5, rotation=20, ha="right")
    ax.set_xlim(-0.6, len(CC) - 0.4)
    ax.set_ylabel("predicted / observed")
    ax.set_title("Level error by coverage rule", fontsize=8)
    ax.legend(fontsize=5.5, frameon=False, loc="upper left")
    fig.tight_layout(pad=0.5)
    save(fig, "incident_ascertainment", multi=False)


def subgroups():
    """Where the transported model is actually right: age bands, with the default strategies beside it.

    Panel A is discrimination only, because the confidence intervals overlap 0.5 in the oldest band of
    three of four panels. Panel B puts the model's net benefit next to treat-all's on one axis, which is
    the comparison a referral rule is judged against - in the oldest US band treat-all wins outright.
    """
    d = read(SG)
    d = d[(d.model == "logistic") & (d.stratum == "age_band")]
    bands = ["20-59", "60-69", "70-79", "80+"]
    fig, axs = plt.subplots(1, 2, figsize=(2 * 5.5 / 2.54, 5.5 / 2.54))
    ax = axs[0]
    x = np.arange(len(bands))
    for h in CC:
        s = d[d.held == h].set_index("level").reindex(bands)
        ax.errorbar(x, s.auroc, yerr=[s.auroc - s.auroc_lo, s.auroc_hi - s.auroc], fmt="o-",
                    color=CCOL[h], ms=3.2, capsize=2, lw=1, label=CTRY[h])
    ax.axhline(0.5, color=OI["black"], lw=.6, ls=":")
    ax.set_xticks(x); ax.set_xticklabels(bands, fontsize=6)
    ax.set_ylim(0.4, 0.8); ax.set_ylabel("AUROC (person-clustered 95% CI)")
    ax.set_xlabel("age band")
    ax.set_title("discrimination by age band", fontsize=7)
    ax.legend(fontsize=5, frameon=False, ncol=2, loc="lower left")
    ax = axs[1]
    w = .2
    for i, h in enumerate(CC):
        s = d[d.held == h].set_index("level").reindex(bands)
        ax.bar(x + (i - 1.5) * w, s.net_benefit_5pct, w, color=CCOL[h], label=CTRY[h])
        ax.scatter(x + (i - 1.5) * w, s.net_benefit_treat_all, color=OI["black"], marker="_",
                   s=42, lw=1.1, zorder=5)
    ax.axhline(0, color=OI["black"], lw=.6, ls=":")
    ax.set_xticks(x); ax.set_xticklabels(bands, fontsize=6)
    ax.set_xlabel("age band"); ax.set_ylabel("net benefit at 5%")
    ax.set_title("bars: model · dashes: treat-all", fontsize=7)
    fig.suptitle("who the transported model is right for", fontsize=7.5)
    fig.tight_layout(rect=[0, 0, 1, .94])
    save(fig, "incident_subgroup_age")


def transport():
    d = read(IN)
    fig, ax = plt.subplots(figsize=(5.5 / 2.54, 5.5 / 2.54))
    lim = [0.55, 0.80]
    ax.plot(lim, lim, ls=":", color=OI["black"], lw=.7, label="no decay")
    for i, m in enumerate([x for x in ORDER if x in set(d.model)]):
        r = d[d.model == m].iloc[0]
        simple = m in {"logistic", "elasticnet", "spline_logistic", "agesex_logistic"}
        ax.scatter(r.auroc_clustered, r.mean_loco, s=16,
                   color=OI["blue"] if simple else OI["verm"], zorder=3)
        off = {"logistic": (-4, -8), "elasticnet": (3, 3), "spline_logistic": (-2, 6),
               "random_forest": (-4, 6), "random_forest_balanced": (3, -7),
               "xgboost": (-3, 6), "gradient_boosting": (2, -7), "lightgbm": (3, 3)}.get(
            m, (3, 3 if i % 2 == 0 else -6))
        ax.annotate(SHORT[m], (r.auroc_clustered, r.mean_loco), fontsize=5.2,
                    xytext=off, textcoords="offset points")
    ax.set_xlim(lim); ax.set_ylim(lim)
    ax.set_xlabel("internal AUROC (person-clustered CV)")
    ax.set_ylabel("mean held-out AUROC")
    ax.set_title("the best internal model travelled worst", fontsize=7.5)
    save(fig, "incident_internal_vs_loco")

    l = primary(read(FZ)); l = need(l[l.level == "interval"], "incident_spread (interval level)")
    sp = l.groupby("model").auroc.agg(lambda s: s.max() - s.min())
    ms = [m for m in ORDER if m in sp.index]
    fig, ax = plt.subplots(figsize=(5.5 / 2.54, 5.5 / 2.54))
    ax.barh(range(len(ms)), [sp[m] for m in ms],
            color=[OI["blue"] if m in {"logistic", "elasticnet", "spline_logistic"} else
                   OI["verm"] for m in ms])
    ax.set_yticks(range(len(ms))); ax.set_yticklabels([SHORT[m] for m in ms], fontsize=6)
    ax.invert_yaxis(); ax.set_xlabel("best minus worst held-out AUROC (4 countries)")
    ax.set_title("transport instability by model", fontsize=7.5)
    save(fig, "incident_spread")


def ablation():
    d = read(AB)
    order = ["logistic", "rf_plain", "rf_platt", "rf_iso", "rf_balanced", "gradient_boosting"]
    fig, ax = plt.subplots(figsize=(5.5 / 2.54, 5.5 / 2.54))
    for i, h in enumerate(CC):
        x = d[d.held == h].set_index("model").reindex(order)
        ax.bar(np.arange(len(order)) + (i - 1.5) * .2, x.skill_train, .2,
               color=CCOL[h], label=CTRY[h])
    ax.axhline(0, color=OI["black"], lw=.6)
    ax.set_xticks(np.arange(len(order)))
    ax.set_xticklabels([SHORT[m] for m in order], rotation=90, fontsize=6)
    ax.set_yscale("symlog"); ax.set_ylabel("Brier skill vs train-prevalence constant")
    ax.set_title("class weights, not capacity", fontsize=7.5)
    ax.legend(fontsize=5.5, frameon=False, ncol=2)
    save(fig, "incident_ablation_skill")


def vs_prevalent():
    inc = read(FZ); inc = inc[(inc.level == "horizon_4y_composed") &
                              (inc.horizon_rule == "cif_mid") & (inc.model.isin(
                                  ["logistic", "random_forest", "xgboost"]))]
    inc = inc.set_index(["model", "held"]).auroc
    prev = read(PV)
    prev = prev[prev.model.isin(["logistic", "random_forest", "xgboost"])]
    prev = prev.rename(columns={"held_country": "held"}).set_index(["model", "held"]).auroc
    labs = [(h, CTRY[h]) for h in CC]
    fig, ax = plt.subplots(figsize=(5.5 / 2.54, 5.5 / 2.54))
    for m, c in [("logistic", OI["blue"]), ("random_forest", OI["green"]),
                 ("xgboost", OI["verm"])]:
        p = [prev.get((m, h), np.nan) for h, _ in labs]
        q = [inc.get((m, h), np.nan) for h, _ in labs]
        ax.plot(range(len(labs)), p, "o--", color=c, ms=3, label=f"{SHORT[m]} prevalent")
        ax.plot(range(len(labs)), q, "s-", color=c, ms=3, label=f"{SHORT[m]} incident")
    ax.set_xticks(range(len(labs))); ax.set_xticklabels([l for _, l in labs], fontsize=6)
    ax.set_ylabel("held-out AUROC")
    ax.set_title("the estimand, not the algorithm, sets the ceiling", fontsize=7.5)
    ax.legend(fontsize=5, frameon=False, ncol=2)
    save(fig, "incident_vs_prevalent")


def link_and_grid():
    """Figure 8: the same four-year estimand under four hazard specifications and five ways of writing
    the follow-up - the panel's own intervals, a common 1-year grid under two event-time allocations that
    do not invent event timing, the same grid under the actual interval-censored likelihood, and the
    last-piece allocation that started this whole audit.

    Colour is the fit, not the country, because the question is how far a country's level error moves
    when the follow-up is rewritten. The vermilion column is the one that settles the question: it
    maximises d*log(1-(1-p)^n) + (1-d)*n*log(1-p) instead of re-weighting rows to match the event count,
    and it moves China 1.02 -> 0.76 and the United States 1.17 -> 0.98, past the dashed line of correct
    level, whereas the weighted-row columns stop short of it. The grey hatched column is NOT a claim:
    placing the event in the final sub-interval asserts three stroke-free years the panel never reported.
    Mexico is above two-fold in all twenty bars.
    """
    AR = ["sklearn_logistic", "logit_glm", "cloglog_glm", "cloglog_ph"]
    ICMAP = {"ic_logit_len_l2": "sklearn_logistic", "ic_logit_len": "logit_glm",
             "ic_cloglog_len": "cloglog_glm", "ic_cloglog_off": "cloglog_ph"}
    FITS = [("panel's own intervals", "incident_cloglog_2026-11-03.csv", OI["blue"], None, None),
            ("1-yr grid, uniform", "incident_cloglog_grid1_uniform_2026-11-03.csv", OI["sky"], None,
             None),
            ("1-yr grid, midpoint", "incident_cloglog_grid1_midcell_2026-11-03.csv", OI["green"], None,
             None),
            ("1-yr grid, IC likelihood", "incident_ic_likelihood_2026-11-03.csv", OI["verm"], None,
             ICMAP),
            ("1-yr grid, last piece \u2020", "incident_cloglog_grid1_last_2026-11-03.csv",
             OI["grey"], "///", None)]
    vals = {}
    for nm, f, _, _, amap in FITS:
        d = primary(read(f))
        d = d[d.strategy == "frozen_all"]
        if amap is not None:
            d = d[d.delta_years > 0]
            d = d[d.arm.isin(amap)]
            d = d.assign(arm=d["arm"].map(amap))
        s = d.set_index(["held", "arm"]).pred_over_obs
        need(s.reset_index(), f"link arm frozen rows ({nm})")
        vals[nm] = s
    fig, axes = plt.subplots(2, 2, figsize=(8.5 / 2.54, 6.4 / 2.54), sharey=True)
    x = np.arange(len(AR))
    w = 0.16
    for ax, h in zip(axes.ravel(), CC):
        for i, (nm, _, col, hatch, _) in enumerate(FITS):
            v = [vals[nm].get((h, a), np.nan) for a in AR]
            ax.bar(x + (i - 2) * w, v, w, color=col, hatch=hatch, edgecolor=OI["black"], lw=.2,
                   label=nm)
        ax.axhline(1.0, color=OI["black"], lw=.6, ls="--")
        ax.set_xticks(x)
        ax.set_xticklabels(["logit\n(pub)", "logit\nGLM", "cloglog\nlen~x", "cloglog\nlogL~off"],
                           fontsize=4.5)
        ax.set_title(f"{CTRY[h]}", fontsize=7)
        ax.tick_params(axis="y", labelsize=5.5)
    axes[0, 0].set_ylim(0, 5.4)
    axes[0, 0].set_ylabel("predicted ÷ observed\nfour-year risk", fontsize=6)
    axes[0, 0].legend(fontsize=3.8, handlelength=1.2, borderpad=.35, labelspacing=.3,
                      loc="upper left", framealpha=.95)
    fig.suptitle("four hazard specifications, one estimand, five ways of writing the same follow-up",
                 fontsize=6.5, y=1.005)
    fig.tight_layout()
    save(fig, "incident_link_grid")


def calibration():
    """Figure 9 (P1-1): calibration by risk decile, per held-out panel, with uncertainty.

    A single predicted/observed ratio per country cannot separate over-prediction at the top of the risk
    distribution from under-prediction at the bottom, and both panels have ratios near one. The deciles
    are formed ONCE on the frozen model's own predictions and held fixed, so the x-axis does not move
    under the repair; the repair therefore appears as a second marker at the same observed level. Vertical
    bars are person-clustered bootstrap intervals of the observed decile risk; the repaired markers carry
    a horizontal band across 200 adaptation/evaluation splits, which is a different uncertainty (which
    local sample was drawn, not which people are in the panel) and is labelled as such.
    """
    d = read(f"incident_calibration_curves_{DAY_CC}")
    need(d, "calibration deciles")
    fig, axes = plt.subplots(2, 2, figsize=(8.5 / 2.54, 7.0 / 2.54), sharex=True, sharey=True)
    lim = float(np.nanmax([d.frozen_pred.max(), d.repaired_pred.max(), d.obs_hi.max()])) * 1.05
    for ax, h in zip(axes.ravel(), CC):
        g = d[d.held == h].sort_values("group")
        po = cell(primary(read(RC)), "pred_over_obs", "level ratio", held=h, model="logistic",
                  strategy="frozen_all", frac=0.0)
        ax.plot([0, lim], [0, lim], ls=":", lw=.6, color=OI["black"], zorder=1)
        ax.errorbar(g.frozen_pred, g.obs, yerr=[g.obs - g.obs_lo, g.obs_hi - g.obs], fmt="o",
                    ms=3.2, color=OI["blue"], ecolor=OI["blue"], elinewidth=.7, capsize=1.6,
                    label="frozen, transferred", zorder=3)
        ax.errorbar(g.repaired_pred, g.obs, xerr=[g.repaired_pred - g.rep_lo, g.rep_hi -
                                                  g.repaired_pred], fmt="s", ms=3.0, mfc="none",
                    color=OI["verm"], ecolor=OI["verm"], elinewidth=.7, capsize=1.6, ls="none",
                    label="after 5% local intercept", zorder=2)
        ax.set_title(f"{CTRY[h]}   panel pred ÷ obs {po:.2f}", fontsize=6.2)
        ax.set_xlabel("predicted four-year risk", fontsize=5.6)
        ax.set_xlim(0, lim); ax.set_ylim(0, lim)
    axes[0, 0].set_ylabel("observed four-year risk", fontsize=5.6)
    axes[1, 0].set_ylabel("observed four-year risk", fontsize=5.6)
    axes[0, 0].legend(fontsize=4.4, handlelength=1.4, borderpad=.3, loc="upper left")
    fig.suptitle("calibration in the large hides calibration by level: deciles of the frozen model",
                 fontsize=6.4, y=1.002)
    fig.tight_layout()
    save(fig, "incident_calibration_curves")


def sample_flow():
    """Figure 6: the per-country cascade from interviews to the four-year evaluation frame.

    Four stages per country as grouped horizontal bars, drawn from `incident_sample_flow_*.csv`, which
    `intl/incident_sample_flow.py` computes from the same horizon frame every four-year table uses - so the
    bars add up to the denominators in Table 1 and cannot disagree with it. The terminal composition of the
    last stage (events, deaths counted as non-events, stroke-free through the horizon) and the prevalent /
    not-determinable exclusions are reported in Table 1 and the caption rather than printed on the canvas, so
    the figure stays legible at 6.5 x 5 cm.
    """
    d = read(f"incident_sample_flow_{DAY_CC}")
    d = d[d.country != "POOLED"].reset_index(drop=True)
    need(d, "per-country sample flow")
    stages = [("ever interviewed", "adults_ever_interviewed", NS.GREY),
              ("at risk", "at_risk_persons", NS.SKY),
              ("analysable interval", "persons_with_intervals", NS.BLUE),
              ("4-y evaluation frame", "horizon_evaluable_persons", NS.VERM)]
    fig, ax = NS.grid(1, 1)
    n = len(d)
    h = 0.2
    for i, (lab, col, colr) in enumerate(stages):
        y = (n - 1 - np.arange(n)) + (1.5 - i) * h
        v = d[col].to_numpy(dtype=float)
        ax.barh(y, v, height=h, color=colr, edgecolor="#333333", lw=.25, label=lab)
        for yy, vv in zip(y, v):
            ax.text(vv * 1.012, yy, f"{int(vv):,}", va="center", fontsize=5)
    ax.set_yticks(n - 1 - np.arange(n))
    ax.set_yticklabels([CTRY[c] for c in d.country], fontsize=7)
    ax.set_xlim(0, float(d.adults_ever_interviewed.max()) * 1.16)
    ax.set_xlabel("adults")
    ax.tick_params(axis="y", length=0)
    ax.legend(fontsize=5.6, handlelength=1.1, ncol=1, loc="upper right", framealpha=.9)
    ax.set_title("Sample flow to the four-year frame", fontsize=8)
    fig.tight_layout(pad=0.5)
    save(fig, "incident_sample_flow", multi=True)


def calibration_smooth():
    """Redraw the logistic-arm smooth calibration (S7) from its own output CSV - no refit - in house style."""
    g = pd.read_csv(os.path.join(ROOT, "data", "processed", "intl", "incident",
                                 "incident_calibration_smooth.csv"))
    fig, axs = plt.subplots(2, 2, figsize=(NS.W_PANEL_CM * NS.CM, NS.H_CM * NS.CM))
    for ax, h in zip(axs.ravel(), CC):
        for arm, col in (("frozen", OI["blue"]), ("repaired", OI["verm"])):
            s = g[(g.held == h) & (g.arm == arm)].sort_values("predicted_risk")
            ax.fill_between(s.predicted_risk, s.obs_lo, s.obs_hi, color=col, alpha=0.18, lw=0)
            ax.plot(s.predicted_risk, s.observed_smooth, color=col, lw=1.3)
        ax.plot([0.002, 0.4], [0.002, 0.4], ls=":", lw=0.8, color="#777777")
        ax.axvline(0.05, lw=0.6, color="#333333", alpha=0.6)
        ax.set_xscale("log"); ax.set_yscale("log"); ax.set_xlim(0.002, 0.4); ax.set_ylim(0.002, 0.4)
        ax.set_xlabel("predicted 4-y risk"); ax.set_title(CTRY[h], fontsize=8)
    axs.ravel()[0].set_ylabel("observed (smoothed)")
    axs.ravel()[2].set_ylabel("observed (smoothed)")
    from matplotlib.lines import Line2D
    hh = [Line2D([], [], color=OI["blue"], lw=1.3, label="frozen"),
          Line2D([], [], color=OI["verm"], lw=1.3, label="after 5% repair")]
    fig.legend(handles=hh, loc="lower center", ncol=2, fontsize=6, frameon=False,
               bbox_to_anchor=(0.5, 0.0))
    NS.letters(fig, axs)
    fig.tight_layout(pad=0.6, w_pad=1.6, rect=(0, 0.05, 1, 1))
    save(fig, "incident_calibration_smooth", multi=True)


def main():
    adaptation(); levels(); estimand(); ascertainment(); subgroups()
    transport(); ablation(); vs_prevalent(); link_and_grid()
    calibration(); calibration_smooth(); sample_flow()
    print("figures ->", FIGD)


if __name__ == "__main__":
    main()
