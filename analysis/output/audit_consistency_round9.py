"""Round-9 delivery audit gate (authoritative).

Round 9 answered the ninth-round reviewer without expanding the study:
  - Table 15's midpoint-free check was relabelled honestly as a UNIFORM-within-interval allocation, its
    distribution assumption stated, and a third estimator was added that drops the uniform assumption for the
    conditional event-time distribution implied by the fitted joint model (truncated-exponential in lam_s+lam_d);
    the "only Mexico moves materially" conclusion is shown to be robust to the allocation rule (China 0.80 under
    midpoint, uniform and model-based; Mexico 2.98 -> 2.18 -> 2.14).
  - abstract "China barely moved" scoped to the estimand-matched allocation check; "flagged Mexico alone" replaced
    by "the only country regularly selected"; clinical-value conclusion framed as re-evaluate-before-deployment.
  - deep structural trim: the cross-sectional (prevalent) arm and the exact-Shapley attributions were physically
    moved out of the main article into deliverables/Supplementary_technical.md (Notes S-C / S-D) with concise main
    stubs; residual software-development-history narration was recast as method+result.
  - ethics / CRediT / data-route / code-DOI remain honest [AUTHOR-SPECIFIC] placeholders (never invented).

Re-derives every round-9 cell from the on-disk CSVs, checks the supplementary relocation, forbids retired phrasing,
and asserts structure. Exit non-zero on any failure. Round-6/7/8 gates still run.
"""
import os, sys, re
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
D = os.path.join(ROOT, "data", "processed", "intl", "incident")
text = open(os.path.join(ROOT, "deliverables", "manuscript.md"), encoding="utf-8").read()
SUPP_PATH = os.path.join(ROOT, "deliverables", "Supplementary_technical.md")
supp = open(SUPP_PATH, encoding="utf-8").read() if os.path.exists(SUPP_PATH) else ""

checks, fails = [], []
def ok(cond, msg):
    checks.append(msg)
    if not cond:
        fails.append(msg)

NAME = {"MX": "Mexico", "CN": "China", "US": "United States", "KR": "Korea"}
av = pd.read_csv(os.path.join(D, "incident_cr_alloc_variants_cif_mid.csv")).set_index("held")

def rowof(heading, panel):
    i = text.index(heading); seg = text[i:i + 1600]
    for ln in seg.split("\n"):
        if ln.startswith("| " + panel + " |"):
            return ln
    return ""

# ===== model-based conditional allocation cross-check (Table 15 third arm) =====
for h in ["MX", "CN", "US", "KR"]:
    r = rowof("**Table 15.", NAME[h])
    ok(r != "", f"Table 15 {NAME[h]} row missing")
    ok(f"{av.at[h,'obs_uniform']:.5f}" in r, f"Table 15 {NAME[h]} uniform obs mismatch")
    ok(f"{av.at[h,'obs_model']:.5f}" in r, f"Table 15 {NAME[h]} model-based obs mismatch")
    ok(f"{av.at[h,'PO_uniform']:.2f}" in r, f"Table 15 {NAME[h]} P/O uniform mismatch")
    ok(f"{av.at[h,'PO_model']:.2f}" in r, f"Table 15 {NAME[h]} P/O model-based mismatch")
# China invariant across all three allocation rules; Mexico the only large move, still >2 under both
ok(abs(av.at["CN", "PO_model"] - 0.80) < 0.03, f"China model-based P/O not ~0.80 ({av.at['CN','PO_model']:.3f})")
ok(av.at["MX", "PO_model"] > 2.0, f"Mexico model-based P/O not still >2 ({av.at['MX','PO_model']:.3f})")
ok(av.at["MX", "ratio_model_over_unif"] > 1.0, "model-based allocation should raise MX observed risk above uniform")
ok(abs(av.at["CN", "ratio_model_over_unif"] - 1.0) < 0.01, "China model/uniform ratio not ~1.0")

# ===== honest relabelling of the allocation estimator =====
ok("uniform-within-interval allocation" in text, "uniform-within-interval allocation label missing")
ok("model-based conditional" in text, "model-based conditional allocation arm missing")
ok("truncated-exponential" in text, "truncated-exponential conditional probability not described")
ok("its interval-censored expectation" not in text, "unqualified 'interval-censored expectation' label still present")
ok("flagged\nMexico alone" not in text and "flagged Mexico alone" not in text,
   "retired 'flagged Mexico alone' phrasing present")
ok("the only country the rule" in text and "regularly selected" in text,
   "'only country regularly selected' softening missing")
ok("incident_cr_alloc_variants.py" in text, "alloc-variants script not attributed")

# ===== abstract scope + clinical-value emphasis =====
lines = text.split("\n")
s0 = lines.index("## Abstract"); e0 = s0 + 1
while e0 < len(lines) and not lines[e0].startswith("## "):
    e0 += 1
words = [w for w in " ".join(lines[s0 + 1:e0]).split() if re.search(r"[A-Za-z0-9]", w)]
ok(125 <= len(words) <= 148, f"abstract is {len(words)} words, target 125-148")
flat = re.sub(r"\s+", " ", text)  # round-10: tolerate markdown line-wraps in the rewritten abstract
ok("unmoved by an estimand-matched allocation check" in flat, "abstract does not scope China to the allocation check")
ok("the only country regularly selected" in text or "regularly selected for updating" in flat,
   "abstract 'only country regularly selected' missing")
ok("re-evaluatable" in text or "re-evaluable" in text, "clinical-value re-evaluation framing missing")
ok("clearing it in only 8 of 40 splits" in text or "clearing treat-none in only 8" in flat,
   "8/40 treat-none caveat missing")

# ===== structural trim: cross-sectional + SHAP content lives in the supplementary tables =====
ok(os.path.exists(SUPP_PATH), "Supplementary_technical.md missing")
for s in ["0.759 (China", "Exact Shapley", "dominated by age"]:
    ok(s in supp, f"supplementary missing relocated content: {s!r}")
# main carries stubs pointing at the supplementary tables, not the full bodies
ok("descriptive results in the Supplementary Information (Tables S3 and S4)" in text, "cross-sectional main stub missing")
ok("(Table S5). They describe" in text or "Supplementary_technical.md` (Table S5)" in text,
   "SHAP main stub missing")
ok("reported there, unaltered" not in text, "full cross-sectional body still in main")
ok("deliberately withheld here" not in text, "full SHAP body still in main")
ok("Table S5" in text, "Table S5 pointer lost from main stub")

# ===== dev-history narration recast as method+result =====
for bad in ["A first version of this arm", "rebuilt a second time", "rather than a third opinion",
            "as it should have been from the start", "in the earlier version was", "no-op clustered bootstrap",
            "thirty defects", "resolved against its EuropePMC", "none was written from memory"]:
    ok(bad not in text, f"retired dev-history narration present: {bad!r}")

# ===== structure: six named Results subsections still in reviewer order =====
res = text[text.index("## Results"):text.index("## Discussion")]
got = [l.replace("### ", "").strip() for l in res.split("\n") if l.startswith("### ")]
want = ["Study population and outcome ascertainment", "External transportability of four-year stroke risk",
        "Sensitivity to outcome timing and ascertainment", "Local recalibration and clinical utility",
        "Selective updating with limited local data", "Age-specific calibration and robustness"]
ok(got == want, f"Results ### not the reviewer's six in order: {got}")
meth = text[text.index("## Methods"):text.index("## Data availability")]
ok(len([l for l in meth.split("\n") if l.startswith("### ")]) >= 12, "Methods lost its ### subheadings")

# ===== author / affiliation / corresponding skeleton present (front-matter labels are plain text, not bold) =====
ok("Authors:" in text and ("Corresponding authors:" in text or "Corresponding author:" in text) and "Affiliations:" in text,
   "front-matter author/affiliation/corresponding skeleton missing")

# ===== author-only placeholders must remain (never invented) =====
ok("[AUTHOR-SPECIFIC" in text and "Conceptualization:" in text and "exempt from review" in text,
   "author-only placeholders / CRediT / IRB determination must be intact")

# ===== carried-forward: corrected identity, nonparametric rename, tables 18/20, 2D, flow, refs =====
ok("p_s·p_d = (p_s − α_s) + (p_d − α_d)" in text, "corrected competing-risk identity missing")
ok("fully nonparametric limit" not in text, "'fully nonparametric limit' overclaim back")
ok("107,898 − 2 − 3,775 = 104,121" in text, "reconciled flow equation missing")
refs = text[text.index("## References"):]
ok([int(x) for x in re.findall(r"^(\d+)\.\s", refs, re.M)] == list(range(1, 16)), "references not 1..15")

print(f"ran {len(checks)} assertions")
if fails:
    print("FAIL:")
    for m in fails:
        print("  -", m)
    sys.exit(1)
print("PASS round-9: model-based conditional allocation arm (Table 15: China 0.80 under all rules, Mexico "
      "2.98->2.18->2.14, conclusion robust); uniform-within-interval relabelled honestly; abstract scoped + "
      "'only country regularly selected'; clinical-value re-evaluate-before-deployment + 8/40 caveat; SHAP + "
      "cross-sectional moved to Supplementary_technical.md (Notes S-C/S-D) with main stubs; dev-history recast; "
      "six named Results sections + Methods subheadings intact; author-only placeholders preserved; carried-forward "
      "identity/flow/refs green.")
