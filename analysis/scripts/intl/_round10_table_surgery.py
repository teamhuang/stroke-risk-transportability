"""Round-10 P0-1: promote the joint primary estimator to the formal main Table 3 / Table 4 and
demote the classifier grid and the logistic update grid to Supplementary Tables S7 / S8.

The tenth-round reviewer's P0-1: the joint multinomial competing-risks model is declared the primary
estimator, yet the formal appendix Table 3 (classifier grid) and Table 4 (logistic update) still report
the OLD model, and Methods leads the probability construction with the separately-fitted hazards. Every
main table must serve the single joint estimand.

This script:
  1. Replaces appendix "### Table 3." (classifier absolute-risk + AUROC grid) with a new JOINT-model formal
     Table 3 (four-country calibration / discrimination / decision utility), and appendix "### Table 4."
     (logistic update) with a new JOINT-model formal Table 4 (local-update trajectory).
  2. Physically relocates the old classifier block to the Supplementary section as "### Table S7." and the
     old logistic block as "### Table S8.", retitled as secondary to the joint primary estimator.
  3. Repoints the in-text "Table 3"/"Table 4" cross-references that described the classifier/logistic
     content to S7/S8 (the Figure references are handled in the P0-4 figure pass, not here).

All joint numbers are transcribed from the on-disk CSVs (incident_cr_joint.csv,
incident_cr_joint_strict_refit_cif_mid.csv); none are hand-invented. Atomic write; run.log exit code.
"""
import os, sys, io

MD = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..",
                                  "deliverables", "manuscript.md"))
MD = "H:/脑出血国际队列/deliverables/manuscript.md"

with io.open(MD, "r", encoding="utf-8") as f:
    text = f.read()
orig = text

# ---- locate section boundaries by unique heading substrings ----
def idx(marker):
    p = text.find(marker)
    assert p != -1, "marker not found: " + marker
    return p

h_t3 = idx("### Table 3. Transferred absolute risk")
h_t4 = idx("### Table 4. Which local adaptation strategy pays")
h_t5 = idx("### Table 5. Internal performance")
h_supp = idx("### Supplementary tables")
h_figs = idx("## Figures")

classifier_block = text[h_t3:h_t4]      # Table 3 + Table 3, continued
logistic_block = text[h_t4:h_t5]        # Table 4 + Table 4, continued
assert classifier_block.count("### Table") == 2 and logistic_block.count("### Table") == 2, "block split wrong"

# ---- new JOINT formal Table 3 (all values from incident_cr_joint.csv frozen_all / cif_mid / joint arm) ----
new_t3 = (
"### Table 3. The joint primary estimator: transferred four-year absolute risk, calibration, discrimination "
"and decision utility (`cif_mid`, leave-one-country-out, person-clustered 95% intervals)\n\n"
"This is the formal results table for the **primary estimator** of the paper - the joint multinomial "
"competing-risks model (`intl/incident_cr_joint.py`), the same object reported inline as Table 9b and drawn "
"in Figures 1-3. It replaces the earlier classifier grid, which is retained as Supplementary Table S7: those "
"classifiers evaluate the same *estimand* but are not the primary *estimator*. `n evaluable` and `events` are "
"the raw four-year frame counts; `mean predicted` and `observed` are IPCW-weighted, and predicted \u00f7 observed "
"is their ratio; a calibration intercept below zero means the frozen model over-predicted. Net benefit is at a "
"5% four-year-risk threshold against treat-none = 0.\n\n"
"| Held-out panel | n evaluable | events | mean predicted | observed (IPCW) | predicted \u00f7 observed [95% CI] | AUROC [95% CI] | AUPRC | Brier | calib intercept / slope | net benefit @5% |\n"
"|---|---|---|---|---|---|---|---|---|---|---|\n"
"| China | 17,474 | 399 | 0.0173 | 0.0216 | **0.802 [0.734, 0.889]** | 0.661 [0.632, 0.686] | 0.039 | 0.0210 | \u22120.65 / 0.77 | \u22120.00026 |\n"
"| Korea | 8,770 | 177 | 0.0214 | 0.0187 | **1.147 [0.999, 1.343]** | 0.708 [0.674, 0.742] | 0.041 | 0.0182 | +0.15 / 1.08 | \u22120.00019 |\n"
"| Mexico | 19,808 | 206 | 0.0283 | 0.0095 | **2.975 [2.605, 3.428]** | 0.610 [0.570, 0.648] | 0.017 | 0.0100 | \u22122.34 / 0.64 | \u22120.00372 |\n"
"| United States | 39,689 | 1,063 | 0.0226 | 0.0252 | **0.897 [0.850, 0.954]** | 0.729 [0.715, 0.742] | 0.056 | 0.0242 | +0.13 / 1.00 | +0.00119 |\n\n"
"Mexico is the only panel whose transported joint model over-predicts beyond two-fold (2.975, interval "
"excluding 1.0), and it is the only panel whose frozen net benefit is materially negative; the United States "
"is the only panel whose *unadapted* net benefit is positive with an interval excluding zero. Discrimination "
"spans 0.61-0.73 across the four panels - the ranking largely travels - while the level does not, which is "
"the dissociation the whole paper is built on. Korea's P/O is read against a transported death hazard "
"(KLoSA ascertains no competing deaths), so its interpretation is not identical to the other three panels "
"(see the KLoSA footnotes).\n\n"
)

# ---- new JOINT formal Table 4 (local-update trajectory, from incident_cr_joint.csv offset_logit / cif_mid) ----
new_t4 = (
"### Table 4. The joint primary estimator under local updating: how far one intercept moves each panel, at "
"what local sample size\n\n"
"The joint model's frozen transported prediction, then the same model after one horizon-scale intercept is "
"re-estimated on 2-50% of the held-out panel's adults and scored on the rest (40 person-disjoint "
"adaptation/evaluation splits, `cif_mid`, net benefit at a 5% threshold). This is the primary-estimator "
"counterpart of the logistic update grid, retained as Supplementary Table S8. The unconditional "
"recalibration shown here is the *always-recalibrate* arm; the prespecified *selective* rule that decides "
"whether to update at all, and its regret against an oracle, is Table 10.\n\n"
"| Panel | metric | frozen | 2% | 5% | 10% | 25% | 50% |\n"
"|---|---|---|---|---|---|---|---|\n"
"| China | predicted \u00f7 observed | 0.80 | 1.00 | 1.06 | 1.14 | 1.08 | 1.04 |\n"
"| China | net benefit @5% | \u22120.00026 | \u22120.00035 | \u22120.00029 | \u22120.00029 | \u22120.00024 | \u22120.00014 |\n"
"| Korea | predicted \u00f7 observed | 1.15 | 1.17 | 1.07 | 1.06 | 1.08 | 1.08 |\n"
"| Korea | net benefit @5% | \u22120.00019 | \u22120.00060 | \u22120.00028 | \u22120.00013 | \u22120.00013 | +0.00001 |\n"
"| Mexico | predicted \u00f7 observed | 2.98 | 1.16 | 1.14 | 1.14 | 1.11 | 1.12 |\n"
"| Mexico | net benefit @5% | \u22120.00372 | \u22120.00037 | \u22120.00006 | \u22120.00004 | \u22120.00003 | \u22120.00002 |\n"
"| United States | predicted \u00f7 observed | 0.90 | 1.02 | 1.05 | 1.05 | 1.05 | 1.05 |\n"
"| United States | net benefit @5% | +0.00119 | +0.00144 | +0.00156 | +0.00162 | +0.00159 | +0.00171 |\n\n"
"One intercept fitted on a few hundred Mexican adults pulls the level ratio from 2.98 to about 1.14 and lifts "
"the net benefit from \u22120.0037 to within a hair of zero at every sample size from 5% up - the largest "
"single repair in the study, and it is a *level* repair: the AUROC does not move, because a horizon-scale "
"intercept is a monotone map. In China and Korea the same procedure buys essentially nothing, and at 2% local "
"data it can cost net benefit (Korea \u22120.00019 \u2192 \u22120.00060), because a handful of local events pins the "
"intercept loosely on a level that was already close to right. The United States is already positive frozen "
"and the repair adds a little. This is the quantitative basis for the selective-updating rule: only a panel "
"with a large measured level gap should be updated, and a small local sample is enough for Mexico precisely "
"because its gap is large.\n\n"
)

# ---- retitle relocated blocks ----
s7 = classifier_block.replace(
    "### Table 3. Transferred absolute risk at the four-year horizon (primary estimand, `cif_mid`)",
    "### Table S7. Classifier comparison on the same estimand (secondary to the joint primary estimator; "
    "transferred absolute risk at the four-year horizon, `cif_mid`)")
s7 = s7.replace("### Table 3, continued. Four-year discrimination and decision utility on the same frame",
    "### Table S7, continued. Four-year discrimination and decision utility on the same frame")
s7 = ("\nThese classifier rows evaluate the *same* four-year estimand as the joint primary estimator (Table 3) "
      "but are **not** the primary estimator; they are reported here to show that the level-not-rank failure is "
      "a property of the estimand and observation mechanism rather than of any one learner. The joint "
      "multinomial model is the primary estimator throughout the main text.\n\n") + s7

s8 = logistic_block.replace(
    "### Table 4. Which local adaptation strategy pays, at what sample size, and on which scale",
    "### Table S8. Logistic-arm local update grid (sensitivity to the joint primary update, Table 4)")
s8 = s8.replace("### Table 4, continued. The middle of the update spectrum, at 2% local data",
    "### Table S8, continued. The middle of the update spectrum, at 2% local data")
s8 = ("\nThis is the **logistic** update arm, kept as a sensitivity to the joint primary-model update in Table 4. "
      "It is retained in full because it exposes the wrong-scale artefact (an interval-scale offset damages "
      "China) and the middle-of-spectrum strategies (pooled updating, penalised revision, de novo refit) that "
      "the joint model does not re-run; the headline update conclusions, however, are read off the joint model "
      "(Table 4) and the prespecified policies (Table 10), not from this grid.\n\n") + s8

# ---- reassemble ----
# 1) appendix: replace classifier+logistic blocks with new joint Table 3 + Table 4
text = text[:h_t3] + new_t3 + new_t4 + text[h_t5:]
# 2) supplementary: insert S7 + S8 just before "## Figures"
h_figs = text.find("## Figures")
assert h_figs != -1
text = text[:h_figs] + s7 + "\n" + s8 + "\n" + text[h_figs:]

# ---- repoint in-text references (classifier->S7, logistic->S8); Figure refs left for P0-4 pass ----
ref_fixes = [
 ("(Table 3). Discrimination was near-identical", "(Table S7). Discrimination was near-identical"),
 ("0.80\u20130.84-fold (Table 3), and the two families", "0.80\u20130.84-fold (Table S7), and the two families"),
 ("+0.0067 / \u22120.0333 / +0.0040 (Table 3). The weighted forest", "+0.0067 / \u22120.0333 / +0.0040 (Table S7). The weighted forest"),
 ("1 of 20 replicates, Table 4). Under the four-year", "1 of 20 replicates, Table S8). Under the four-year"),
 ("repair (matching Table 4's intercept correction)", "repair (matching Table S8's intercept correction)"),
 ("the 2% estimate of Table 4) from +0.00435", "the 2% estimate of Table S8) from +0.00435"),
 ("The middle of the update spectrum was filled in so this comparison is not a straw man (Table 4,",
  "The middle of the update spectrum was filled in so this comparison is not a straw man (Table S8,"),
 ("which is how Table 4 reports it.", "which is how Table S8 reports it."),
 ("Table 4's notes rather than assumed.", "Table S8's notes rather than assumed."),
 ("which is why Table 4's headline names the estimand", "which is why Table S8's headline names the estimand"),
 ("the intercept correction of Table 4 remains the binding intervention",
  "the intercept correction of Table S8 remains the binding intervention"),
 ("the four panels disagree (Table 4, Figure 1). Deployed frozen",
  "the four panels disagree (Table S8, Figure 1). Deployed frozen"),
]
for old, new in ref_fixes:
    n = text.count(old)
    assert n >= 1, "ref anchor missing: " + old[:60]
    text = text.replace(old, new)
    print("repointed x%d: %s" % (n, old[:55]))

# atomic write
tmp = MD + ".tmp"
with io.open(tmp, "w", encoding="utf-8") as f:
    f.write(text)
    f.flush(); os.fsync(f.fileno())
os.replace(tmp, MD)
print("WROTE", MD, "delta bytes", len(text) - len(orig))
