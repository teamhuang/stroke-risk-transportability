import io

# ---------- SUBMISSION_BLOCKERS.md ----------
p = "deliverables/SUBMISSION_BLOCKERS.md"
s = io.open(p, encoding="utf-8").read()
r8_anchor = "| Round 8: post-review reconciliation |"
r9_row = ("| Round 9: honest allocation relabel + structural trim | **DONE 2026-11-04.** | Table 19 relabelled "
          "as a uniform-within-interval allocation (distribution assumption stated) and a third, joint-model-based "
          "conditional (truncated-exponential) allocation added (`incident_cr_alloc_variants.py`): China 0.80 under "
          "midpoint/uniform/model-based, Mexico the only move 2.98->2.18->2.14, so 'only Mexico' is robust to the "
          "allocation rule; abstract 'China barely moved' scoped to the allocation check; 'flagged Mexico alone' -> "
          "'only country regularly selected'; clinical value framed as re-evaluate-before-deployment (8/40 splits, "
          "<1 net person); SHAP + cross-sectional/V4 physically moved to `Supplementary_technical.md` (Notes S-C/S-D); "
          "residual dev-history recast; front-matter author/affiliation/corresponding skeleton added; "
          "audit_consistency_round9.py 64 PASS. |")
if "Round 9: honest allocation relabel" not in s:
    s = s.replace(r8_anchor, r9_row + "\n" + r8_anchor, 1)

# explicit author-only enumeration block
enum = """

## Z. Complete list of remaining author-only items (36 [AUTHOR-SPECIFIC] placeholders in manuscript.md)

These are facts the analysis cannot produce and must NEVER be invented by it. Each is a required author action:

- Front matter: full author list + order, numbered affiliations + ORCIDs, corresponding author (name/dept/institution/email).
- Ethics: the submitting institution's named exemption/approval determination (the study is a secondary analysis of
  de-identified public releases, but the exempt/not-exempt call is the authors' institution's to make, not inferable
  from de-identification), and, per cohort (HRS/CHARLS/KLoSA/MHAS), the parent-study ethics body, protocol/approval
  identifier, consent procedure and secondary-use authorisation, read from each study's own documentation.
- Data-use terms: confirm each cohort's licence permits automated/AI-assisted processing and describes this analysis
  as used; if a cohort's terms prohibit it, that cohort must be removed from the four-country comparison (KLoSA needs
  registration + a study creation code; MHAS/ELES terms must be read individually).
- Code availability: the release repository URL, version tag and archived version DOI (e.g. Zenodo) for the versioned
  snapshot; nothing here should be filled with a placeholder DOI.
- Author contributions: CRediT roles assigned by author initials; approval of the final version; accountability.
- Competing interests and funding: all-author confirmation; declare any grant numbers and any data-use restriction
  limiting redistribution of harmonised files.

Until these are supplied and every author signs off, the file is a complete, audited scientific draft but NOT an
uploadable submission (journal policy: authorship, ethics and data/code access statements must be real and complete).
"""
if "## Z. Complete list of remaining author-only items" not in s:
    s = s.rstrip() + "\n" + enum
io.open(p, "w", encoding="utf-8").write(s)
print("SUBMISSION_BLOCKERS updated")

# ---------- data_dictionary.md ----------
p = "deliverables/data_dictionary.md"
s = io.open(p, encoding="utf-8").read()
add = """
## Round-9 output (allocation-estimator cross-check)

  incident_cr_alloc_variants_cif_mid.csv   per held country the observed four-year risk and P/O under three
    estimand-matched allocation rules on the identical cif_mid frame + IPCW weights - midpoint, uniform-within-interval
    (`clip((H-t_start)/(t_end-t_start))`), and a joint-model-based conditional (truncated-exponential in the fitted
    total hazard lam_s+lam_d) - with the model/uniform ratio. Source of Table 19 (both allocation arms) and of the
    round-9 reviewer cross-check that 'only Mexico moves materially' is not a uniform-allocation artefact
    (China 0.80 under all three; Mexico 2.98 -> 2.18 uniform -> 2.14 model-based). `intl/incident_cr_alloc_variants.py`;
    reverse-checked by `analysis/output/audit_consistency_round9.py`. The relocated Notes S-C (cross-sectional) and
    S-D (exact-Shapley) now live in `deliverables/Supplementary_technical.md`, not the main article.
"""
io.open(p, "w", encoding="utf-8").write(s.rstrip() + "\n" + add)
print("data_dictionary updated")

# ---------- README_reproducibility.md ----------
p = "deliverables/README_reproducibility.md"
s = io.open(p, encoding="utf-8").read()
cmd = """
#   ROUND 9 (allocation-estimator cross-check): 
#     intl/incident_cr_alloc_variants.py --horizon 4
#         -> three estimand-matched observed-risk allocations (midpoint / uniform-within-interval / joint-model
#            truncated-exponential conditional), confirming Table 19's 'only Mexico moves materially' is robust to
#            the within-interval allocation rule (China 0.80 under all three). audit_consistency_round9.py (64) PASS.
"""
io.open(p, "w", encoding="utf-8").write(s.rstrip() + "\n" + cmd)
print("README updated")

# ---------- docs/SELF_AUDIT.md ----------
p = "docs/SELF_AUDIT.md"
s = io.open(p, encoding="utf-8").read()
mark = "## What changed since the previous audit of this file"
add = r"""
### Round 9 (honest allocation relabel + cross-check + structural trim) — 2026-11-04

- **Defect 33 — Table 19's midpoint-free estimator was mis-described as a general interval-censored
  conditional.** The clip((H-t_start)/(t_end-t_start)) allocation is a UNIFORM-within-interval assumption, not
  the interval-censored conditional event-time probability; the reviewer was right. Relabelled as
  "uniform-within-interval allocation" with the assumption stated. Added a joint-model-based conditional
  allocation (truncated-exponential in the fitted total hazard, `incident_cr_alloc_variants.py`) that drops the
  uniform assumption; result unchanged: China P/O 0.80 under midpoint/uniform/model-based, Mexico the only move
  2.98->2.18->2.14 (model-based pulls observed risk up ~1.9%, exactly as decreasing within-interval survival implies).
  audit_consistency_round9 checks the third arm's numbers against the CSV and forbids the unqualified
  "interval-censored expectation" label.
- **Wording tightened (no claim change).** abstract "China barely moved" now scoped to the estimand-matched
  allocation check (distinct from Table 15/18's parametric 0.40-0.47); "the rule flagged Mexico alone" ->
  "Mexico was the only country regularly selected" (others fire 2-24%); clinical value explicitly
  "re-evaluate-before-deployment" with the 8/40-splits / <1-net-person caveat.
- **Structure (reviewer's second length flag).** Physically moved the cross-sectional (prevalent) arm and the
  exact-Shapley attributions out of the main article into `deliverables/Supplementary_technical.md` (Notes S-C/S-D),
  leaving concise main stubs with the headline number + scope caveat; recast residual software-development-history
  ("a first version", "rebuilt a second time", "as it should have been from the start", "in the earlier version was")
  as method+result. Kept the grid/likelihood and composition subsections in main because they define primary-model
  tables (Table 8, joint-primary) the reviewer said must remain to understand the primary model.
- **Front matter.** Added author / affiliation / corresponding-author skeleton as [AUTHOR-SPECIFIC] placeholders
  (the file previously carried only a title); enumerated all 36 author-only items in SUBMISSION_BLOCKERS section Z.
- **Gates.** audit_consistency_round9.py 64 PASS; round-8 patched for Table 19's new columns (123 PASS);
  round-7 86 PASS; round-6 53 PASS. manuscript.docx, cover_letter.docx and the new Supplementary_technical.docx
  rebuilt from audited md and validate PASS.
"""
s = s.replace(mark, mark + "\n" + add, 1)
io.open(p, "w", encoding="utf-8").write(s)
print("SELF_AUDIT round-9:", "Defect 33" in io.open(p, encoding="utf-8").read())
print("ALL COMPANIONS SYNCED")
