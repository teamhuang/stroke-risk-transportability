"""Round-9 structural trim: physically move two self-contained 'old-analysis' subsections
(cross-sectional/prevalent-arm and the SHAP attribution) OUT of the main manuscript into a separate
Supplementary_technical.md, leaving concise main-text stubs that keep the headline number and the scope caveat.
The grid/likelihood and composition subsections are NOT moved: they define primary-model tables (Table 8 and the
joint-primary rationale) the reviewer said must stay to understand the primary model.
Deterministic, lossless-checked (the moved blocks are reproduced verbatim in the new file)."""
import io, os

SRC = "deliverables/manuscript.md"
DST = "deliverables/Supplementary_technical.md"
t = io.open(SRC, encoding="utf-8").read()


def cut(text, start_marker, end_marker):
    i = text.index(start_marker)
    j = text.index(end_marker, i)
    return text[i:j].rstrip("\n"), i, j


xsec_head = "#### What the cross-sectional version of this study would have claimed"
xsec_end = "### Age-specific calibration and robustness"
shap_head = "#### What the frozen model actually uses"
shap_end = "## Discussion"

xsec_block, xi, xj = cut(t, xsec_head, xsec_end)
shap_block, si, sj = cut(t, shap_head, shap_end)

xsec_stub = xsec_head + """

Applying the same estimators, pipeline and shared encoding to the *prevalent* outcome overstates transportable
discrimination: logistic leave-one-country-out AUROC 0.759 (China), 0.737 (Korea), 0.738 (Mexico) and 0.798
(NHANES, US) against an incident arm 0.06-0.12 AUROC lower in every country. That gap is the price of honesty
about the estimand and the reason the prospectively ascertained incident outcome - not the cross-sectional
case-mix - is the reported one. The full cross-sectional arm and its within-US analyses (temporal transport,
race/ethnicity leave-one-group-out, association with concurrent depressive symptoms) are reported unaltered as
descriptive results in `Supplementary_technical.md` (Note S-C).

"""

shap_stub = shap_head + """

Exact-Shapley attributions for the logistic and XGBoost fits (Table S5) are reported in
`Supplementary_technical.md` (Note S-D). They describe only the *ranking-classifier arm* (the per-interval hazard
and its composed horizon risk of Tables 2/3), not the joint competing-risks estimator that is this paper's primary
absolute-risk model, and are reported on the classifier's log-odds rather than the four-year cumulative incidence:
they explain what drives discrimination, not the absolute-risk level or the transport failure. The score is
dominated by age, hypertension and the interval-length term, with the ordering of those three differing by panel.

"""

# rebuild main text with stubs (order-independent: replace by index from the end so offsets stay valid)
pairs = sorted([(xi, xj, xsec_stub), (si, sj, shap_stub)], key=lambda z: -z[0])
mt = t
for a, b, stub in pairs:
    # keep one trailing blank line separation consistent with the block that followed
    mt = mt[:a] + stub + mt[b:]
io.open(SRC, "w", encoding="utf-8").write(mt)

# supplementary file
supp = """# Supplementary technical notes

Extended specification and auxiliary analyses kept out of the main article to keep the primary narrative on the
joint competing-risks model, four-country transportability, the observation mechanism, local recalibration and
clinical decision value. Every number below is produced by a script that reads the published CSVs and is
reverse-checked by `analysis/output/audit_consistency_round9.py`; table and figure numbering continues the main
article.

""" + xsec_block + "\n\n" + shap_block + "\n"

# relabel the moved headings as supplementary Notes (S-C cross-sectional, S-D attributions)
supp = supp.replace(xsec_head, "## Note S-C. What the cross-sectional (prevalent) version of this study would have claimed")
supp = supp.replace(shap_head, "## Note S-D. What the frozen ranking classifier actually uses (exact-Shapley attributions)")

io.open(DST, "w", encoding="utf-8").write(supp)

# verification
newmain = io.open(SRC, encoding="utf-8").read()
print("xsec body in main now:", "reported there, unaltered, as descriptive results" in newmain)  # old phrasing gone
print("cross-sectional full paragraph moved to supp:", xsec_block.split(chr(10))[3][:40] in io.open(DST, encoding='utf-8').read())
print("supp file exists:", os.path.exists(DST), "lines:", len(io.open(DST, encoding='utf-8').read().split(chr(10))))
print("main line count:", len(newmain.split(chr(10))), " (was", len(t.split(chr(10))), ")")
print("stubs present:", "descriptive results in `Supplementary_technical.md` (Note S-C)" in newmain,
      "Table S5) are reported in\n`Supplementary_technical.md` (Note S-D)" in newmain)
