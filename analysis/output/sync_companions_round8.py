import io

# ---- 1. data_dictionary.md : repair the mangled path token ----
p = "deliverables/data_dictionary.md"
s = io.open(p, encoding="utf-8").read()
s = s.replace(
    "all reading the same horizon frame + joint CIF so nothing drifts;\n re-derives every round-8 cell",
    "all reading the same horizon frame + joint CIF so nothing drifts;\n"
    "`analysis/output/audit_consistency_round8.py` re-derives every round-8 cell")
io.open(p, "w", encoding="utf-8").write(s)
assert "`analysis/output/audit_consistency_round8.py` re-derives every round-8 cell" in s
print("data_dictionary repaired")

# ---- 2. README_reproducibility.md : append round-8 run commands ----
p = "deliverables/README_reproducibility.md"
s = io.open(p, encoding="utf-8").read()
block = r"""

#   ROUND 8 (post-review reconciliation): four new analyses on the same horizon frame + joint CIF, all
#   reverse-checked by analysis/output/audit_consistency_round8.py (127 assertions).
#     intl/incident_cr_interval_flexhaz.py --horizon 4 --boot 300 --dt 0.05 --bands 3
#         -> observed 4-y risk under piecewise-constant and log-linear cause-specific hazards (Table 18);
#            China inflated ~2x by the pooled-hazard MLE, robust to hazard shape.
#     intl/incident_update_policy_joint_ic.py --reps 200 --fractions 0.02,0.05,0.10,0.25,0.50 --horizon 4
#         -> the four policies re-run on the interval-censored outcome (midpoint and IC arms on identical
#            person-disjoint splits); Table 19 right block - at 5% the rule fires Mexico 98%/IC (+0.00290),
#            China 24%/IC (net loss). Also writes incident_cr_alloc_only_ic_comparator via the evaluable-frame
#            interval-censored expectation (Table 19 left block: China ratio 1.00, Mexico 1.37, P/O 2.98->2.18).
#     intl/incident_cr_clinical_baseline.py  -> five-variable clinical joint model vs full model on the same
#            estimand/validation/threshold (Table 20, 120 splits; AUROC within 0.009, Mexico ~3x for both).
#     intl/incident_cr_unreported_stroke_2d.py --horizon 4 --grid 0,0.1,0.2,0.3,0.4,0.5
#            -> 2-D source x target under-ascertainment grid (Supplementary Table S6, hypothetical sensitivity
#               parameters; uniform diagonal keeps Mexico >=1.48, only extreme differential crosses 1.0).
"""
if "ROUND 8 (post-review reconciliation)" not in s:
    s = s.replace("is `tokens 137 | words 137`", block + "\nis `tokens 137 | words 137`")
    io.open(p, "w", encoding="utf-8").write(s)
print("README round-8 appended:", "ROUND 8 (post-review reconciliation)" in io.open(p, encoding="utf-8").read())

# ---- 3. SUBMISSION_BLOCKERS.md : round-8 row + refreshed author-only items ----
p = "deliverables/SUBMISSION_BLOCKERS.md"
s = io.open(p, encoding="utf-8").read()
row = ("| Round 8: post-review reconciliation | **DONE 2026-11-04.** | "
       "Competing-risk identity corrected (p_s - alpha_s = P(death-first in step); total double-count "
       "p_s*p_d = (p_s-alpha_s)+(p_d-alpha_d)) in text + scripts; 'fully nonparametric' overclaim renamed; "
       "Finding A resolved - pooled-hazard MLE China 0.40-0.47 (Table 18, shape-robust) is an estimand "
       "re-specification, estimand-matched IC leaves China invariant and flags only Mexico (Tables 19); "
       "clinical baseline (Table 20); 2-D unreported-stroke grid (Table S6); age gate unified to >=20; "
       "Results restructured to six named subsections; Methods given ### subheadings; dev-history + reference "
       "verification notes stripped; audit_consistency_round8.py 127 PASS. |")
if "Round 8: post-review reconciliation" not in s:
    s = s.replace("| Round 7: submission-hardening pass |", row + "\n| Round 7: submission-hardening pass |")
# refresh author-only blockers (A2/A3) to reflect the structured placeholders now in the manuscript
s = s.replace("### A2. Ethics approvals — four statements, none of them written yet",
              "### A2. Ethics approvals — four per-cohort [AUTHOR-SPECIFIC] fields plus the institutional exemption determination")
s = s.replace("### A3. Authorship, contributions and the AI-tool statement",
              "### A3. Authorship, CRediT initials and the AI-tool statement (structured [AUTHOR-SPECIFIC: initials] placeholders now present)")
io.open(p, "w", encoding="utf-8").write(s)
print("SUBMISSION_BLOCKERS round-8 row:", "Round 8: post-review reconciliation" in io.open(p, encoding="utf-8").read())

# ---- 4. docs/SELF_AUDIT.md : round-8 changelog + defects ----
p = "docs/SELF_AUDIT.md"
s = io.open(p, encoding="utf-8").read()
mark = "## What changed since the previous audit of this file"
add = r"""
### Round 8 (post-review reconciliation) — 2026-11-04

- **Defect 31 — competing-risk double-count identity was wrong (Finding B, reviewer-correct).** The text and
  scripts asserted `p_s - alpha_s = p_s * p_d`. Numerically false: with lambda_s=0.03, lambda_d=0.02, D=2 the
  gap p_s - alpha_s = 0.001138 and p_d - alpha_d = 0.001148, while p_s * p_d = 0.002283. Correct identity:
  the gap p_s - alpha_s = P(death also falls in the step before the stroke), and the *total* probability-mass
  double-count obeys p_s*p_d = (p_s-alpha_s) + (p_d-alpha_d). Fixed at four sites (manuscript Results + Methods,
  incident_cr_joint.py, incident_cr_exact.py); incident_cr_simulation.py's "bias is the p_s*p_d term" retained
  because it correctly names the total double-count. audit_consistency_round8 checks the identity numerically.
- **Defect 32 — the interval-censored observed risk was mislabelled and its estimand conflated (Findings A + C).**
  Round 7 called the intercept-only MLE "the fully nonparametric limit" and let China's P/O 0.43 stand beside a
  main line of "only Mexico is miscalibrated." Renamed to a constant-hazard parametric model (overclaim
  "fully nonparametric limit" removed). New analyses show the China figure is a *pooled-hazard re-specification*,
  not a time-allocation effect: flexible hazards keep it ~0.40-0.47 (Table 18, so not a flat-hazard artefact), but
  an estimand-matched allocation-only check (identical evaluable frame + IPCW) leaves China at 0.80 (ratio 1.00)
  while Mexico alone moves (2.98->2.18, ratio 1.37; Table 19). The update rule re-run on the interval-censored
  outcome still flags only Mexico (fires 98% and pays in MX, 24% and net-loss in CN). Conclusion rewritten into a
  stable / conditional two-tier.
- **Round-8 additions (not defects, robustness the reviewer required):** five-variable transparent clinical
  baseline (Table 20) - matches discrimination (AUROC within 0.009) and fails to transport in the same places;
  2-D unreported-pre-fatal-stroke sensitivity with parameters explicitly labelled hypothetical (Table S6) -
  uniform under-ascertainment never erases the Mexican over-prediction, only an extreme differential does;
  age gate unified to MIN_AGE=20.
- **Structure:** Results reordered/retitled to the reviewer's six named subsections (population, transportability,
  sensitivity to timing/ascertainment, local recalibration & utility, selective updating, age & robustness);
  Methods converted to ### subheadings (19); the software-development-history defect list and the reference
  verification/selection note were removed from the manuscript; Ethics/CRediT/Data/Code availability rewritten with
  honest [AUTHOR-SPECIFIC] placeholders (never invented). Data availability no longer routes via the retired
  g2aging.org mirror.
"""
s = s.replace(mark, mark + "\n" + add, 1)
io.open(p, "w", encoding="utf-8").write(s)
print("SELF_AUDIT round-8:", "Defect 31" in io.open(p, encoding="utf-8").read())
print("ALL COMPANIONS SYNCED")
