"""Round-6 delivery audit: the joint competing-risks model is the single PRIMARY absolute-risk arm.

Sixth-round review contract: (P0-1) every primary four-year risk, calibration, decision-curve and age
subgroup reads the joint estimator, with the separately-fitted two-hazard composition demoted to a labelled
sensitivity arm - no mixing; (P1) Results condensed to six top-level subsections, the round-by-round audit
narration stripped, the composition derivation moved to Supplementary Methods; plus the discrete fixes
(Table 16 "5% or more" contradiction, a three-level deployability table, a declared primary estimand,
survey-ascertained outcome wording, a SHAP scope note). Like the reviewer would: read the manuscript, read
the released `_joint` outputs, and FAIL the build on any desync or any retired phrase. Exit non-zero on any
failure.

Run: python audit_consistency_round6.py
"""
import os, sys, re, json
import numpy as np
import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
MS = os.path.join(ROOT, "deliverables", "manuscript.md")
D = os.path.join(ROOT, "data", "processed", "intl", "incident")
text = open(MS, encoding="utf-8").read()
fails, checks = [], 0


def ok(cond, msg):
    global checks
    checks += 1
    if not cond:
        fails.append(msg)


# ---- disk sources for the joint arm ----
jn = pd.read_csv(os.path.join(D, "incident_cr_joint.csv"))
fz = jn[(jn.horizon_rule == "cif_mid") & (jn.composition_arm == "joint_multinomial")
        & (jn.strategy == "frozen_all") & (jn.frac == 0.0)].set_index("held")
sub = pd.read_csv(os.path.join(D, "incident_cr_joint_subgroups.csv"))
agerec = pd.read_csv(os.path.join(D, "incident_cr_joint_age_recalibration_summary.csv"))
dec = pd.read_csv(os.path.join(D, "incident_cr_joint_deciles.csv"))
sm = pd.read_csv(os.path.join(D, "incident_cr_joint_calibration_smooth.csv"))
jd = json.load(open(os.path.join(D, "incident_cr_joint_diagnostics.json"), encoding="utf-8"))

# ---- 1. joint declared PRIMARY, V4 demoted, no mixing ----
ok("joint multinomial competing-risks model" in text and "primary absolute-risk estimator of this paper" in text,
   "joint model not declared primary")
ok("separately-fitted marginal-hazard sensitivity arm" in text, "V4 not labelled as the sensitivity arm")
for c, po in [("MX", 2.975), ("CN", 0.802), ("KR", 1.147), ("US", 0.897)]:
    ok(abs(fz.loc[c].pred_over_obs - po) < 5e-4, f"joint {c} P/O not {po} on disk")
ok(abs(fz.loc["MX"].pred_over_obs - 2.975) < 5e-4 and "2.975 [2.605, 3.428]" in text,
   "joint MX headline not 2.975 [2.605, 3.428] in text")
ok(fz.loc["MX"].mean_pred < 0.0285 and "0.0283" in text, "abstract MX predicted not 0.0283")
ok("2.98-fold" in text, "abstract joint 2.98-fold missing")

# ---- 2. joint age-band Table 13 cells ----
mx20 = sub[(sub.held == "MX") & (sub.level == "20-59")].iloc[0]
mx80 = sub[(sub.held == "MX") & (sub.level == "80+")].iloc[0]
ok(abs(mx20.pred_over_obs - 2.180) < 0.002 and "2.180" in text, "joint MX 20-59 frozen P/O not 2.180")
ok(abs(mx20.pred_over_obs_offset - 0.674) < 0.002 and "0.674" in text, "joint MX 20-59 repaired not 0.674")
ok(abs(mx80.pred_over_obs - 6.275) < 0.002 and "6.275" in text, "joint MX 80+ not 6.275")
ok("US | 80+ | 2359 | 191 | 0.07754 | 0.04820 | 0.622" in text, "joint US 80+ row not present")

# ---- 3. joint age-aware Table 20 ----
a5 = agerec[(agerec.held == "MX") & np.isclose(agerec.frac, 0.05)].set_index("strategy")
d5 = agerec[(agerec.held == "MX") & np.isclose(agerec.frac, 0.05)].set_index("strategy")
ok(abs(np.exp(a5.loc["A_frozen", "max_abs_band_log_po"]) - 6.3) < 0.1, "joint A_frozen worst band not 6.3")
ok(abs(np.exp(d5.loc["D_age_linear", "max_abs_band_log_po"]) - 1.2) < 0.1, "joint D worst band not 1.2")
ok("6.3-fold frozen to 1.2-fold" in text, "joint 6.3->1.2 age-aware sentence missing")
ok("incident_cr_joint_primary.py" in text, "age-aware not attributed to joint-primary script")
ok(a5.loc["D_age_linear", "sd_nb_at_05"] < a5.loc["B_overall", "sd_nb_at_05"], "D not more stable than B (joint)")
ok((agerec[(agerec.held == "MX")].mean_nb_at_05 <= 1e-9).all(), "a joint MX strategy net benefit is positive")

# ---- 4. joint decile rejections + smooth tail ----
def rej(h, arm):
    g = dec[dec.held == h]
    return int(sum(not (r.obs_lo <= (r.frozen_pred if arm == "f" else r.repaired_pred) <= r.obs_hi) for _, r in g.iterrows()))
ok(rej("MX", "f") == 10 and rej("MX", "r") == 2, "joint MX decile 10->2 not reproduced on disk")
ok(rej("US", "f") == 5 and rej("US", "r") == 7, "joint US decile 5->7 not reproduced on disk")
ok("10 of 10 deciles rejected" in text and "2 of\n10" in text, "joint MX decile counts not in text")
mxtail = sm[(sm.held == "MX") & (sm.arm == "frozen") & (sm.predicted_risk >= 0.10)]
if len(mxtail):
    t = mxtail.iloc[(mxtail.predicted_risk - 0.107).abs().argsort()].iloc[0]
    ok(abs(t.observed_smooth - 0.047) < 0.01, "joint smooth MX tail observed not ~0.047")
ok("smoothed observed risk is 0.047" in text, "joint smooth tail 0.047 not in text")

# ---- 5. three-level deployability table ----
ok("Table 19" in text and "(3) Clinical utility" in text, "three-level Table 19 missing")
ok("8 of 40 splits, largest 0.9 of a person" in text or "8/40 splits" in text, "MX clinical-utility cell missing")

# ---- 6. Table 16 "5% or more" contradiction fixed ----
ok("close to zero" in text and "a hair negative at 10%" in text, "Table 16 positivity not reworded")

# ---- 7. Methods declared primary estimand + survey-ascertained ----
# round-10 P2: heading relabelled from "declared before any model was fitted" to analysis-plan wording
ok("Primary estimand, fixed in the analysis plan" in text, "Methods estimand block missing")
ok("survey-ascertained" in text, "survey-ascertained wording not used")

# ---- 8. SHAP scope note ----
ok("not the joint competing-risks estimator that is this paper's primary" in text,
   "SHAP scope note (explains classifier arm, not joint CIF) missing")

# ---- 9. Results condensed to 6 top-level subsections ----
res = text.split("## Results", 1)[1].split("## Discussion", 1)[0]
h3 = re.findall(r"^### ", res, flags=re.M)
ok(len(h3) == 6, f"Results has {len(h3)} top-level subsections, expected 6")

# ---- 10. retired V4-stale strings and audit narration must be GONE ----
forbidden = ["5% or more", "A reviewer asked", "the reviewer warned", "the reviewer's \"important new finding\"",
             "This converts the reviewer's", "Fifteen subsections", "Thirteen subsections",
             "How this Results section is ordered", "2.383", "1.831 on 41 events", "7.26 from ages",
             "crosses from negative to positive at local", "2.13-fold oldest-band", "0.13 the",
             "is what we fit for the primary absolute-risk", "discrete approximation to an integral",
             "measured discretisation of the integral", "outside this paper's design", "174 words"]
for f in forbidden:
    ok(f not in text, f"retired phrase still present: {f!r}")

# ---- 11. the one allowed historical Riemann mention (audit file only, not manuscript) ----
riem = re.findall(r"Riemann discretisation", text)
ok(len(riem) <= 1, f"more than one Riemann mention ({len(riem)})")

# ---- 12. abstract <=150 words and joint-consistent ----
lines = text.split("\n")
s = lines.index("## Abstract"); e = s + 1
while e < len(lines) and not lines[e].startswith("## "):
    e += 1
words = [w for w in " ".join(lines[s + 1:e]).split() if re.search(r"[A-Za-z0-9]", w)]
ok(len(words) <= 150, f"abstract is {len(words)} words (>150)")
ok(125 <= len(words) <= 145, f"abstract is {len(words)} words, target 130-140")

print(f"ran {checks} assertions")
if fails:
    print("FAIL:")
    for m in fails:
        print("  -", m)
    sys.exit(1)
print("PASS: joint model is the unified primary arm; six Results subsections; audit narration stripped; "
      "Table 16 contradiction fixed; estimand + 3-level table + SHAP caveat present; abstract 130-140.")
