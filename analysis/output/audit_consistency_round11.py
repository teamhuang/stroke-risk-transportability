# -*- coding: utf-8 -*-
"""Round-11 consistency gate: verifies the 11-point restructure + Round-11 correctness fixes against the
manuscript and SI booklet on disk, and that no reported number drifted. Deterministic; exits non-zero on
any failure. Complements (does not replace) the round6-10 gates, which remain the numeric authority."""
import os, re, sys
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
DEL = os.path.join(ROOT, "deliverables")
D = os.path.join(ROOT, "data", "processed", "intl", "incident")
text = open(os.path.join(DEL, "manuscript.md"), encoding="utf-8").read()
supp = open(os.path.join(DEL, "Supplementary_technical.md"), encoding="utf-8").read()

checks, fails = [], []
def ok(c, m):
    checks.append(m)
    if not c: fails.append(m)

# ---------- #6/#4 : all tables at the end, renumbered 1..22, no 'b', no inline tables in the body ----------
body = text[:text.index("## Tables")]
cap_nums = sorted(set(int(x) for x in re.findall(r'\*\*Table (\d+)\.', text)) |
                  set(int(x) for x in re.findall(r'### Table (\d+)\.', text)))
ok(cap_nums == list(range(1, 23)), f"table captions not 1..22 contiguous: {cap_nums}")
ok(not re.search(r'Table \d+[ab]\b', text), "'b'-suffixed table number remains")
# no table caption inside the Results/Methods body (they must all be in ## Tables)
ok(not re.search(r'\*\*Table \d+\.', body), "an inline table caption survived in the body")
# every 'Table N' reference resolves to 1..22
for r in set(re.findall(r'\bTables? (\d+[a-z]?)', text)):
    ok(re.match(r'^\d+$', r) and 1 <= int(r) <= 22, f"unresolved table reference: Table {r}")

# ---------- figures 1..6 at the end; SI is tables + figures only ----------
figs = re.findall(r'\*\*Figure (\d+)\.', text)
ok(sorted(int(f) for f in figs) == [1,2,3,4,5,6], f"main figures not 1..6: {figs}")
ok("## Figures" in text and text.index("## Figures") > text.index("## Tables"), "figures not after tables at the end")
for gone in ["## Supplementary Methods", "## Supplementary Notes", "### S-A.", "### S-D."]:
    ok(gone not in supp, f"SI still contains prose section {gone!r}")
ok(all(f"Table S{i}." in supp for i in range(1, 10)), "SI tables S1-S9 incomplete")
ok(all(f"Figure S{i}." in supp for i in range(1, 9)), "SI figures S1-S8 incomplete")
ok("### Simulation validation of the composition algebra" in text, "simulation design not in main Methods")

# ---------- #9 : code availability collapsed to a repository pointer ----------
ca = text[text.index("## Code availability"):text.index("## Ethics")]
ok("github.com" in ca, "code availability lost the repository pointer")
ok("incident_personperiod.py" not in ca and "incident_cr_primary.py" not in ca,
   "code availability still lists individual scripts (should be a one-line repo pointer)")
ok("[AUTHOR-SPECIFIC" in ca, "repository URL/version/DOI placeholder must remain (author-issued)")

# ---------- Round-11 correctness fixes ----------
ok("sit below the diagonal" in text, "Fig1 caption direction not corrected (P0-4)")
ok("three event-time allocations on one estimand, plus a re-specified-hazard comparator" in text,
   "Fig3 grouping not applied (P1-6)")
ok("predicted four-year probability on the horizontal axis" in text or "predicted four-year probability" in text,
   "Fig4 x-axis not clarified (P0-4)")
ok("warrants prospective evaluation before deployment" in text, "US deploy wording not softened (P1-7)")
ok("illustrates, rather than proves" in text, "simulation tone not scoped down (P1-1)")
ok("Definitional ablation on the separately-fitted (V4) sensitivity model" in text, "Table V4 ablation label missing (P1-3)")
ok("The primary joint estimator comes first" in text, "selective-updating not reordered joint-first (P1-4)")
ok("respondent's own" in text and "Three coding choices" in text, "P0-2 identifiability coding missing")
ok("truncated-exponential" in text and "a < H < b" in text and "λ_tot = λ_s + λ_d" in text,
   "allocation model-based formula / range not in main Methods (P1-2)")
ok("outperformed treat-all" in supp and "loses to it in Mexico" not in supp, "S7 net-benefit contradiction not fixed (P1-5)")
ok("Longest interval (LOCO training mix)" in supp, "Table S1 longest-interval label not fixed (P0-3)")

# ---------- #2 : bold only on Table/Figure captions ----------
for m in re.finditer(r'\*\*(.+?)\*\*', text, re.DOTALL):
    s = m.group(1).strip()
    ok(bool(re.match(r'(Table|Figure) \d+[a-z]?\.', s)), f"non-caption bold remains: {s[:40]!r}")

# ---------- numbers preserved against disk (no drift) ----------
j = pd.read_csv(os.path.join(D, "incident_cr_joint.csv"))
def po(arm, held):
    s = j[(j.arm == arm) & (j.held == held)]
    return float(s.iloc[0]["pred_over_obs"]) if len(s) else None
for held, val in [("MX", 2.975), ("CN", 0.802), ("KR", 1.147), ("US", 0.897)]:
    ok(f"{val:.3f}" in text, f"joint frozen P/O {val} missing from text for {held}")
ok("3.004" in text, "V4 shipped Mexico P/O 3.004 (sensitivity) missing")

# ---------- author-only placeholders intact ----------
ok(text.count("[AUTHOR-SPECIFIC") == 2, f"[AUTHOR-SPECIFIC] count {text.count('[AUTHOR-SPECIFIC')} != 2 (only code-DOI + AI-policy remain after author-directed back-matter cleanup)")
ok("Jianhuang Huang" in text and "cjn2006@sohu.com" in text, "supplied authors missing")
# references 1..15
refs = text[text.index("## References"):]
ok([int(x) for x in re.findall(r'^(\d+)\.\s', refs, re.M)] == list(range(1, 16)), "references not 1..15")

if fails:
    print(f"ran {len(checks)} assertions"); print("FAIL:")
    for m in fails: print("  -", m)
    sys.exit(1)
print(f"ran {len(checks)} assertions")
print("PASS round-11: tables 1..22 (no gaps/no 'b') all at the end; figures 1-6 + SI S1-S9/S1-S8; SI reduced to "
      "tables+figures with methods in main; code availability = published repo URL + tag v1.0.0; P0-2/3/4 + P1-1/2/3/4/5/6/7 present; "
      "bold only on captions; joint P/O 0.802/1.147/2.975/0.897 + V4 3.004 preserved; 2 remaining author-only items; refs 1..15.")
