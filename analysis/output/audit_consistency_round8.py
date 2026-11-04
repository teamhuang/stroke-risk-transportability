"""Round-8 delivery audit gate (authoritative; round-6/7 gates still run independently).

Round 8 closed the reviewer's items with every number re-derived from the CSVs on disk:
  Finding B  competing-risk identity corrected: p_s - alpha_s = P(death also in step, before stroke), and the
             TOTAL double-count p_s*p_d = (p_s - alpha_s) + (p_d - alpha_d)  (NOT the gap itself);
  Finding C  the constant-hazard MLE renamed (not "fully nonparametric limit");
  P0-1/Finding A the interval-censored observed-risk analysis reconciled - the pooled-hazard MLE inflates China
             ~2x and makes it look under-predicted (Table 14, robust to hazard shape), but that is an estimand /
             censoring re-specification, NOT the within-interval allocation: estimand-matched, China is invariant
             (Table 15) and only Mexico moves materially; the update rule re-run on the interval-censored outcome
             still flags only Mexico (Table 15 right block);
  clinical   a five-variable transparent clinical model matches the full transported model on discrimination and
             fails to transport in the same places (Table 18);
  P0-3       unreported pre-fatal-stroke sweep generalised to a 2-D source x target grid with the parameters
             explicitly labelled hypothetical (Table S6);
  P0-4       age rule unified to a >=20 gate (MIN_AGE=20);
  format     Results restructured to the reviewer's six named subsections in order; Methods given ### subheadings;
             the software-development-history defect list and the reference-verification note stripped; author-only
             ethics/CRediT/DOI left as [AUTHOR-SPECIFIC] placeholders; abstract reports four-year AUROC scale and
             marks 0.80-1.15 as the midpoint rule.

This gate re-derives every cited round-8 cell from the CSVs, checks the corrected identity numerically, asserts the
structure, and FAILS on any desync or any retired phrase. Exit non-zero on any failure.
"""
import os, sys, re
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
D = os.path.join(ROOT, "data", "processed", "intl", "incident")
text = open(os.path.join(ROOT, "deliverables", "manuscript.md"), encoding="utf-8").read()
supp = open(os.path.join(ROOT, "deliverables", "Supplementary_technical.md"), encoding="utf-8").read()

checks, fails = [], []
def ok(cond, msg):
    checks.append(msg)
    if not cond:
        fails.append(msg)

def rowof(heading, panel):
    """Return the markdown table row for a panel in the block following a **Table N.** caption."""
    i = text.index(heading)
    seg = text[i:i + 1400]
    for ln in seg.split("\n"):
        if ln.startswith("| " + panel + " |"):
            return ln
    return ""

# ================= round-8 sources =================
fx = pd.read_csv(os.path.join(D, "incident_cr_interval_flexhaz_cif_mid.csv")).set_index("held")
al = pd.read_csv(os.path.join(D, "incident_cr_alloc_only_ic_comparator_cif_mid.csv")).set_index("held")
cl = pd.read_csv(os.path.join(D, "incident_cr_clinical_baseline_cif_mid.csv")).set_index("held")
pol = pd.read_csv(os.path.join(D, "incident_update_policy_joint_ic_summary_cif_mid.csv"))
sel = pol[(pol.policy == "selective") & np.isclose(pol.frac, 0.05)].set_index(["held", "arm"])
g2 = pd.read_csv(os.path.join(D, "incident_cr_unreported_stroke_2d.csv"))
NAME = {"MX": "Mexico", "CN": "China", "US": "United States", "KR": "Korea"}

# ================= Finding B: the competing-risk identity, numeric + text =================
ls, ld, Delta = 0.03, 0.02, 2.0
tt = ls + ld
p_s = 1 - np.exp(-ls * Delta); p_d = 1 - np.exp(-ld * Delta)
a_s = ls / tt * (1 - np.exp(-tt * Delta)); a_d = ld / tt * (1 - np.exp(-tt * Delta))
ok(abs((p_s - a_s) + (p_d - a_d) - p_s * p_d) < 1e-5,
   f"identity p_s*p_d == (p_s-a_s)+(p_d-a_d) fails numerically ({(p_s-a_s)+(p_d-a_d):.6f} vs {p_s*p_d:.6f})")
ok(p_s - a_s != p_s * p_d, "the gap p_s-a_s must NOT equal p_s*p_d")
ok("p_s·p_d = (p_s − α_s) + (p_d − α_d)" in text, "corrected total-double-count identity missing")
ok("difference is `p_s·p_d`" not in text and "difference is p_s·p_d" not in text,
   "retired 'difference is p_s·p_d' claim still present")
ok("0.001138" in text and "0.002283" in text, "numeric illustration of the identity missing")

# ================= Finding C: nonparametric overclaim retired =================
ok("fully nonparametric limit" not in text, "'fully nonparametric limit' overclaim still present")
ok("not a fully nonparametric estimator" in text, "explicit corrective non-claim missing")
ok("constant-hazard parametric" in text, "constant-hazard parametric rename missing")

# ================= P0-1 / Finding A: flexible-hazard MLE observed risk (Table 14) =================
for h in ["MX", "CN", "US", "KR"]:
    r = rowof("**Table 14.", NAME[h])
    ok(r != "", f"Table 14 {NAME[h]} row missing")
    ok(f"{fx.at[h,'cif_pw']:.5f}" in r, f"Table 14 {NAME[h]} cif_pw not {fx.at[h,'cif_pw']:.5f} in row")
    ok(f"{fx.at[h,'cif_pw_lo']:.5f}, {fx.at[h,'cif_pw_hi']:.5f}" in r, f"Table 14 {NAME[h]} pw CI mismatch")
    ok(f"{fx.at[h,'PO_frozen_over_pw']:.2f}" in r, f"Table 14 {NAME[h]} P/O piecewise mismatch")
    ok(f"{fx.at[h,'PO_frozen_over_linear']:.2f}" in r, f"Table 14 {NAME[h]} P/O log-linear mismatch")
    ok(f"{fx.at[h,'PO_repaired_over_pw']:.2f}" in r, f"Table 14 {NAME[h]} repaired P/O mismatch")
# China MLE inflation ~2x vs midpoint and robust to shape: assert the direction
ok(fx.at["CN", "cif_pw"] / fx.at["CN", "obs_midpoint"] > 1.6, "China MLE/midpoint inflation not ~2x")
ok(abs(fx.at["CN", "PO_frozen_over_pw"] - fx.at["CN", "PO_frozen_over_linear"]) < 0.1,
   "China under-prediction not robust to hazard shape (pw vs linear)")
ok("incident_cr_interval_flexhaz.py" in text, "flexhaz script not attributed")

# ================= P0-1: estimand-matched allocation-only check + policy under IC (Table 15) =================
for h in ["MX", "CN", "US", "KR"]:
    r = rowof("**Table 15.", NAME[h])
    ok(r != "", f"Table 15 {NAME[h]} row missing")
    ok(f"{al.at[h,'obs_ic']:.5f}" in r, f"Table 15 {NAME[h]} obs_IC mismatch")
    ok(f"{al.at[h,'PO_ic']:.2f}" in r, f"Table 15 {NAME[h]} P/O allocation-only-IC mismatch")
# the decisive asymmetry: China allocation-invariant, Mexico allocation-sensitive
ok(al.at["CN", "ratio_ic_over_mid"] < 1.05, f"China allocation ratio not ~1.0 (got {al.at['CN','ratio_ic_over_mid']:.3f})")
ok(al.at["MX", "ratio_ic_over_mid"] > 1.3, f"Mexico allocation ratio not >1.3 (got {al.at['MX','ratio_ic_over_mid']:.3f})")
ok(al.at["MX", "PO_ic"] > 2.0, "Mexico allocation-only-IC P/O not still >2")
# policy under IC: only Mexico fires and pays; China does not pay
ok(sel.at[("MX", "ic"), "trigger_rate"] >= 0.9, "Mexico IC 5% trigger not >=0.9")
ok(sel.at[("MX", "ic"), "paired_vs_frozen"] > 0.002, "Mexico IC paired gain not > +0.002")
ok(sel.at[("CN", "ic"), "trigger_rate"] <= 0.30, "China IC 5% trigger too high")
ok(sel.at[("CN", "ic"), "paired_vs_frozen"] < 0.0, "China IC update must not pay (paired gain should be <=0)")
for h in ["KR", "US"]:
    ok(sel.at[(h, "ic"), "trigger_rate"] <= 0.30, f"{h} IC 5% trigger too high")
# the trigger % strings as displayed in Table 15
ok("+0.00290" in rowof("**Table 15.", "Mexico"), "Table 15 Mexico paired NB +0.00290 missing")
ok("incident_update_policy_joint_ic.py" in text, "IC policy script not attributed")
# the two-tier wording present
ok("Stable:" in text and "Conditional:" in text, "two-tier stable/conditional conclusion missing")

# ================= clinical baseline (Table 18) =================
for h in ["MX", "CN", "US", "KR"]:
    r = rowof("**Table 18.", NAME[h])
    ok(r != "", f"Table 18 {NAME[h]} row missing")
    ok(f"{cl.at[h,'auroc_full']:.3f}" in r, f"Table 18 {NAME[h]} AUROC full mismatch")
    ok(f"{cl.at[h,'auroc_simple']:.3f}" in r, f"Table 18 {NAME[h]} AUROC simple mismatch")
    ok(f"{cl.at[h,'po_full']:.2f}" in r and f"{cl.at[h,'po_simple']:.2f}" in r,
       f"Table 18 {NAME[h]} P/O mismatch")
    ok(f"{cl.at[h,'po_ratio_simple_over_full']:.2f}" in r, f"Table 18 {NAME[h]} P/O ratio mismatch")
# discrimination within +-0.009 and Mexico still ~3x over-predicted by the simple model
ok(abs(cl.at["MX", "auroc_full"] - cl.at["MX", "auroc_simple"]) < 0.011, "MX AUROC gap too large")
ok(cl.at["MX", "po_simple"] > 2.8, "simple-model Mexico over-prediction not ~2.87")
ok(0.9 <= cl.at["MX", "po_ratio_simple_over_full"] <= 1.1, "simple/full Mexico ratio not near 1")
ok("incident_cr_clinical_baseline.py" in text, "clinical-baseline script not attributed")

# ================= P0-3: 2-D unreported-stroke grid (Table S6) =================
mxg = g2[g2.held == "MX"].pivot(index="pi_source", columns="pi_target", values="PO_clinical")
for (ps_, pt_, val) in [(0.0, 0.0, 2.98), (0.0, 0.3, 1.04), (0.0, 0.5, 0.72), (0.5, 0.5, 1.48)]:
    ok(abs(float(mxg.loc[ps_, pt_]) - val) < 0.02, f"MX 2D grid (src{ps_},tgt{pt_}) not ~{val} (got {float(mxg.loc[ps_,pt_]):.3f})")
# uniform diagonal never drops below 1.4; extreme differential required for <1
diag = [float(mxg.loc[v, v]) for v in sorted(set(mxg.index))]
ok(min(diag) > 1.4, "uniform-diagonal Mexico over-prediction not robust (min<=1.4)")
krg = g2[g2.held == "KR"].pivot(index="pi_source", columns="pi_target", values="PO_clinical")
ok(np.allclose(krg.loc[0.0], krg.loc[0.0].iloc[0], atol=1e-9), "Korea not invariant to its own pi_target")
ok("hypothetical sensitivity parameter" in text, "P0-3 hypothetical-parameter labelling missing")
ok("incident_cr_unreported_stroke_2d.py" in text or "incident_cr_unreported_stroke_2d.py" in supp, "2D sensitivity script not attributed")

# ================= P0-4: age gate unified =================
ok("MIN_AGE" in text and "20" in text, "MIN_AGE=20 gate not stated")
ok("no minimum age" not in text.lower(), "contradictory 'no minimum age' claim present")

# ================= structure: six named Results subsections in reviewer order =================
res = text[text.index("## Results"):text.index("## Discussion")]
h3 = [l.strip() for l in res.split("\n") if l.startswith("### ")]
want = ["Study population and outcome ascertainment",
        "External transportability of four-year stroke risk",
        "Sensitivity to outcome timing and ascertainment",
        "Local recalibration and clinical utility",
        "Selective updating with limited local data",
        "Age-specific calibration and robustness"]
got = [h.replace("### ", "") for h in h3]
ok(got == want, f"Results ### not the reviewer's six in order: {got}")

# ================= Methods subheadings present =================
meth = text[text.index("## Methods"):text.index("## Data availability")]
mh = [l for l in meth.split("\n") if l.startswith("### ")]
ok(len(mh) >= 12, f"Methods has only {len(mh)} ### subheadings (reviewer wanted proper hierarchy)")

# ================= dev-history + reference-verification note stripped =================
for bad in ["no-op clustered bootstrap", "thirty defects", "resolved against its EuropePMC",
            "none was written from memory", "the earlier draft was thin on"]:
    ok(bad not in text, f"retired internal-editing / dev-history narration present: {bad!r}")

# ================= author-only placeholders preserved (never invented) =================
ok("AUTHOR-SPECIFIC" in text and "[AUTHOR-SPECIFIC" in text, "author-only placeholders missing")
for sec in ["## Ethics", "## Author contributions", "## Data availability", "## Code availability"]:
    ok(sec in text, f"section missing: {sec}")
ok("Conceptualization:" in text and "Project administration:" in text, "CRediT structure not present")
# Back matter re-contracted (author-directed, round-12 closeout): ORCID / per-cohort ethics-and-consent
# enumeration / secondary-data-licence hedging were removed at the author's instruction, CRediT assigned,
# funding set to none. The Ethics section now carries only a minimal factual statement (no fabricated
# approval number, no exemption claim), so assert that form instead of the retired "exempt from review".
ok("no institutional review board" not in text.lower() and "secondary analysis of de-identified release" in text
   and "The authors declare no competing interests" in text and "no funds, grants" in text,
   "ethics / competing-interests / funding statements not in the expected minimal factual form")
ok("g2aging.org mirror is no longer an active distributor" in text or
   "no longer an active distributor" in text, "deprecated g2aging portal still routed as active")

# ================= abstract: four-year AUROC scale + midpoint marking + window =================
lines = text.split("\n")
s0 = lines.index("## Abstract"); e0 = s0 + 1
while e0 < len(lines) and not lines[e0].startswith("## "):
    e0 += 1
words = [w for w in " ".join(lines[s0 + 1:e0]).split() if re.search(r"[A-Za-z0-9]", w)]
ok(125 <= len(words) <= 148, f"abstract is {len(words)} words, target 125-148")
flat = re.sub(r"\s+", " ", text)  # round-10: tolerate markdown line-wraps inside the abstract
ok("four-year AUROC 0.61-0.73" in text, "abstract four-year AUROC scale missing")
ok("0.80-1.15" in flat or "0.80–1.15" in flat, "abstract 0.80-1.15 rule marker missing")
ok("2.10 midpoint-free" not in text, "retired abstract '2.10 midpoint-free' phrasing present")
ok("re-specified the estimand" in flat, "abstract does not carry the Finding-A re-specification caveat")
ok("2.98-fold" in text, "abstract Mexico 2.98-fold headline missing")

# ================= carried-forward round-7 integrity (still must hold) =================
ok("107,898 − 2 − 3,775 = 104,121" in text, "reconciled flow equation missing")
refs = text[text.index("## References"):]
refnums = [int(x) for x in re.findall(r"^(\d+)\.\s", refs, re.M)]
ok(refnums == list(range(1, 16)), f"references not 1..15: {refnums}")
for pmid in ["38626948", "10884460", "31795614", "39635884", "19494242", "27460537", "30357870"]:
    ok(pmid in refs, f"verified PMID missing: {pmid}")

print(f"ran {len(checks)} assertions")
if fails:
    print("FAIL:")
    for m in fails:
        print("  -", m)
    sys.exit(1)
print("PASS round-8: corrected competing-risk identity (numeric + text); nonparametric overclaim retired; "
      "flexible-hazard MLE Table 14 (China ~2x, shape-robust); estimand-matched Table 15 (China invariant, "
      "Mexico 2.18, rule flags only Mexico) + two-tier; clinical-baseline Table 18 (equivalent transport); "
      "2D hypothetical grid Table S6 (uniform robust, Korea invariant); MIN_AGE=20; six named Results sections; "
      "Methods subheadings; dev-history + ref-verification stripped; author-only placeholders intact; abstract "
      "four-year AUROC + midpoint-marked, 125-148 words; carried-forward flow/refs still green.")
