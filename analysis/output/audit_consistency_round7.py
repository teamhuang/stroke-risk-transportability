"""Round-7 delivery audit gate (authoritative; supersedes nothing from round-6, which still runs).

Round-7 closed the reviewer's P0 items with numbers re-derived from disk:
  P0-1 cohort flow reconciles as ever - not-determinable - prevalent = at risk (the 2 MHAS gap),
  P0-2 outcome-observation mapping (Table 21) + unreported-fatal-stroke sweep (Table S6),
  P0-3 interval-censored midpoint-free observed risk (Table 12) -> MX P/O 2.98 -> 2.10,
  P0-4 KLoSA reworded (no 'lower bound' / 'bias direction' conflict),
  P0-5 consolidated weight disclosure (Table 22),
  P0-6 selective-updating policy re-run on the JOINT model (Table 11, no longer logistic),
  P0-7 prespecified tiered to analysis-plan-specified,
  + references expanded to 15 EuropePMC-verified entries cited in first-appearance order,
  + Funding folded into Acknowledgments, Limitations label folded.

This gate re-derives every one of those cells from the CSVs on disk and FAILS on any desync or any retired
phrase. Exit non-zero on any failure. Run after the round-7 analyses and make_round7_rows.py.
"""
import os, sys, re, json
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
D = os.path.join(ROOT, "data", "processed", "intl", "incident")
text = open(os.path.join(ROOT, "deliverables", "manuscript.md"), encoding="utf-8").read()
# round-10: supplementary tables/figures relocated into the SI booklet; search both files
_sp = os.path.join(ROOT, "deliverables", "Supplementary_technical.md")
supp = open(_sp, encoding="utf-8").read() if os.path.exists(_sp) else ""

checks, fails = [], []
def ok(cond, msg):
    checks.append(msg)
    if not cond:
        fails.append(msg)

# ---------- sources ----------
flow = pd.read_csv(os.path.join(D, "incident_sample_flow_cif_mid.csv")).set_index("country")
pol = pd.read_csv(os.path.join(D, "incident_update_policy_joint_summary_cif_mid.csv"))
ice = pd.read_csv(os.path.join(D, "incident_cr_interval_eval_cif_mid.csv")).set_index("held")
uns = pd.read_csv(os.path.join(D, "incident_cr_unreported_stroke_sim.csv"))

# ---------- P0-1 cohort flow reconciles on disk and in text ----------
for c in ["CN", "KR", "MX", "US", "POOLED"]:
    e = int(flow.at[c, "adults_ever_interviewed"]); nd = int(flow.at[c, "no_determinable_stroke"])
    pv = int(flow.at[c, "prevalent_at_entry_excluded"]); ar = int(flow.at[c, "at_risk_persons"])
    ok(e - nd - pv == ar, f"flow {c}: ever {e} - nd {nd} - prev {pv} != at_risk {ar}")
ok(int(flow.at["POOLED", "adults_ever_interviewed"]) == 107898, "pooled ever != 107,898")
ok(int(flow.at["POOLED", "no_determinable_stroke"]) == 2, "pooled not-determinable != 2")
ok(int(flow.at["POOLED", "prevalent_at_entry_excluded"]) == 3775, "pooled prevalent != 3,775")
ok(int(flow.at["POOLED", "at_risk_persons"]) == 104121, "pooled at-risk != 104,121")
ok("107,898 − 2 − 3,775 = 104,121" in text, "manuscript missing reconciled flow equation")
ok("Baseline stroke status not determinable, excluded" in text, "Table 1 missing not-determinable row")
ok("never gave a determinable stroke" in text or "never gave a determinable answer" in text,
   "prose not explaining the 2-person exclusion")

# ---------- P0-6 joint-model selective-updating policy (Table 11) ----------
def cell(held, frac, policy, col):
    r = pol[(pol.held == held) & np.isclose(pol.frac, frac) & (pol.policy == policy)]
    return float(r.iloc[0][col])
mx_trig = cell("MX", 0.02, "selective", "updated_rate")
mx_pair = cell("MX", 0.02, "selective", "paired_vs_frozen")
mx_fzn = cell("MX", 0.02, "always_frozen", "nb_at_05")
mx_sel = cell("MX", 0.02, "selective", "nb_at_05")
mx_reg = cell("MX", 0.02, "selective", "regret_vs_oracle")
ok(abs(mx_trig - 0.70) < 0.03, f"joint MX 2% trigger not ~0.70 (got {mx_trig:.3f})")
ok(abs(mx_pair - 0.00261) < 1e-4, f"joint MX 2% paired gain not ~0.00261 (got {mx_pair:.5f})")
ok(abs(mx_fzn + 0.00372) < 1e-4, f"joint MX frozen NB not ~-0.00372 (got {mx_fzn:.5f})")
ok(abs(mx_sel + 0.00111) < 1e-4, f"joint MX selective NB not ~-0.00111 (got {mx_sel:.5f})")
ok(abs(mx_reg - 0.00096) < 1e-4, f"joint MX 2% regret not ~0.00096 (got {mx_reg:.5f})")
# the other three panels must NOT fire much at 2%
for h, cap in [("US", 0.10), ("CN", 0.15), ("KR", 0.10)]:
    ok(cell(h, 0.02, "selective", "updated_rate") <= cap, f"joint {h} fires too often at 2%")
# text: joint caption + rows, logistic caption gone
ok("joint\ncompeting-risks model, `cif_mid`, net benefit at a 5% threshold" in text or
   "competing-risks model, `cif_mid`, net benefit at a 5% threshold" in text,
   "Table 11 caption not joint-model")
ok("logistic model, `cif_mid`, net benefit" not in text, "old logistic Table 11 caption still present")
ok("incident_update_policy_joint_summary_2026-11-03.csv" in text, "Table 11 not pointing at joint summary CSV")
ok("| Mexico | 4 events median | 70% | −0.00372 | −0.00111 | +0.00261 | +0.00096 |" in text,
   "joint MX Table 11 row not present verbatim")
ok("−0.00450 | −0.00094 | +0.00356" not in text, "old logistic MX Table 11 row still present")
ok("incident_update_policy_joint.py" in text, "joint policy script not attributed")

# ---------- P0-3 interval-censored observed risk (Table 12) ----------
ok(abs(ice.at["MX", "PO_model_over_mid"] - 2.98) < 0.02, f"MX P/O_mid not ~2.98 (got {ice.at['MX','PO_model_over_mid']:.3f})")
ok(abs(ice.at["MX", "PO_model_over_IC"] - 2.10) < 0.02, f"MX P/O_IC not ~2.10 (got {ice.at['MX','PO_model_over_IC']:.3f})")
ok(abs(ice.at["MX", "obs_interval_censored_IC"] - 0.01343) < 5e-4, "MX interval-censored observed not ~0.01343")
ok(abs(ice.at["MX", "PO_model_over_start"] - 1.22) < 0.03, "MX P/O start bracket not ~1.22")
ok(abs(ice.at["MX", "PO_model_over_end"] - 2.94) < 0.03, "MX P/O end bracket not ~2.94")
# model mean-pred reproduces the primary (MX 0.02825)
ok(abs(ice.at["MX", "model_mean_pred"] - 0.02825) < 3e-4, "interval-eval MX model mean-pred not 0.02825")
for s in ["2.10", "0.01343", "[0.01262, 0.01431]", "1.22 / 2.94", "Table 12", "midpoint-free",
          "incident_cr_interval_eval.py"]:
    ok(s in text, f"Table 12 / interval-censored string missing: {s!r}")

# ---------- P0-2 unreported-stroke sweep (Table S6) + mapping (Table 21) ----------
mx = uns[uns.held == "MX"].set_index("pi_target")
ok(abs(float(mx.at[0.10, "PO_clinical_uniform"]) - 2.21) < 0.02, "MX uniform pi=0.10 not ~2.21")
ok(abs(float(mx.at[0.10, "PO_clinical_differential_src0"]) - 1.83) < 0.02, "MX differential pi=0.10 not ~1.83")
ok(abs(float(mx.at[0.00, "PO_reported_ascertained"]) - 2.98) < 0.02, "MX reported P/O not ~2.98")
for s in ["Table S6", "| 0.10 | 3.60 | 2.22 | 1.60 | 1.25 | 1.03 | 0.87 |",
          "Table 21", "stroke-first", "death-first", "Outcome-observation mapping"]:
    ok(s in text or s in supp, f"Table S6 / mapping string missing: {s!r}")
# the unreported-stroke sweep script is now attributed to the code repository (Code availability), not the prose
ok(os.path.exists(os.path.join(ROOT, "analysis", "scripts", "intl", "incident_cr_unreported_stroke_sim.py")),
   "incident_cr_unreported_stroke_sim.py not present on disk")

# ---------- P0-4 KLoSA reword ----------
ok("lower bound" not in text, "'lower bound' still present (P0-4 not fully reworded)")
ok("bias direction is not" not in text and "bias direction is not identified" not in text,
   "'bias direction' conflict still present")
ok("Incomplete mortality ascertainment" in text or "incomplete mortality ascertainment" in text,
   "KLoSA estimand-identification reword missing")

# ---------- P0-5 weight disclosure (Table 22) ----------
for s in ["Table 22", "Weight and estimand disclosure", "Same sampling distribution as the deployment target"]:
    ok(s in text, f"Table 22 weight-disclosure string missing: {s!r}")

# ---------- P0-7 prespecified tiering ----------
ok("analysis-plan-specified" in text, "prespecified tiering (analysis-plan-specified) missing")
ok("no timestamped prospective registration" in text, "explicit no-registration disclosure missing")

# ---------- P1 wording ----------
ok("raised net benefit in 40/40 splits" not in text, "abstract 40/40 phrasing not retired")
ok("positive in all 40" not in text, "'positive in all 40' not retired")
tx=" ".join(text.split())
ok("net benefit in every split" in tx or "every evaluated split" in tx, "abstract split-scope phrasing missing")
ok("split-variability band" in text, "P1-2 split-variability reframe missing")
ok("binding quantity for update stability is the number of observed events" in text,
   "P1-1 events-based sizing sentence missing")
ok("predeclared candidate set" in text, "P1-3 predefined-candidate framing missing")

# ---------- format ----------
ok("## Funding" not in text, "standalone ## Funding section still present")
ok("## Acknowledgments" in text, "## Acknowledgments missing")
ok("Limitations. The outcome" not in text, "standalone 'Limitations.' label still present")
ok("Several limitations follow" in text, "folded limitations transition missing")

# ---------- references integrity (15 verified, cited in order) ----------
refs = text[text.index("## References"):]
refnums = [int(x) for x in re.findall(r"^(\d+)\.\s", refs, re.M)]
ok(refnums == list(range(1, 16)), f"references not 1..15: {refnums}")
body = text[:text.index("## References")]
cited = set()
for m in re.finditer(r"\[(\d+(?:[,-]\d+)*)\]", body):
    for part in m.group(1).split(","):
        if "-" in part:
            a, b = part.split("-"); cited.update(range(int(a), int(b) + 1))
        else:
            cited.add(int(part))
ok(cited == set(range(1, 16)), f"citations not 1..15: {sorted(cited)}")
# verified PMIDs must appear
for pmid in ["17099194", "20010215", "24898551", "25560714", "38626948", "10884460",
             "19433651", "31795614", "39304265", "39635884", "19494242", "27460537",
             "30347470", "30357870"]:
    ok(pmid in refs, f"verified PMID missing from references: {pmid}")

# ---------- abstract word count + joint headline ----------
lines = text.split("\n")
s0 = lines.index("## Abstract"); e0 = s0 + 1
while e0 < len(lines) and not lines[e0].startswith("## "):
    e0 += 1
words = [w for w in " ".join(lines[s0 + 1:e0]).split() if re.search(r"[A-Za-z0-9]", w)]
ok(125 <= len(words) <= 148, f"abstract is {len(words)} words, target 125-148")
ok("2.10 midpoint-free" in text or "lowered Mexico to 2.10" in text, "abstract interval-censored caveat missing (round-7 or round-8 wording)")
ok("2.98-fold" in text, "abstract joint 2.98-fold headline missing")

print(f"ran {len(checks)} assertions")
if fails:
    print("FAIL:")
    for m in fails:
        print("  -", m)
    sys.exit(1)
print("PASS: cohort flow reconciles (107,898-2-3,775=104,121); joint-model policy (Table 11, MX 70%/+0.00261); "
      "interval-censored P/O 2.98->2.10 (Table 12); unreported-stroke sweep (Table S6) + mapping (Table 21); "
      "KLoSA reworded; weight disclosure (Table 22); prespecified tiered; 15 verified refs cited 1..15; "
      "Funding->Acknowledgments; Limitations folded; abstract 125-148 words.")
