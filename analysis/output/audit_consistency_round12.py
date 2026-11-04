# -*- coding: utf-8 -*-
"""Round-12 gate: verifies the reviewer-round-12 fixes against disk. Images embedded, code-availability
honest, estimand lead, Korea footnotes on all core tables, dev language gone, version tag synced, numbers
unchanged. Exits non-zero on any failure."""
import os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
DEL = os.path.join(ROOT, "deliverables")
FIG = os.path.join(DEL, "figures", "incident")
text = open(os.path.join(DEL, "manuscript.md"), encoding="utf-8").read()
supp = open(os.path.join(DEL, "Supplementary_technical.md"), encoding="utf-8").read()

checks, fails = [], []
def ok(c, m):
    checks.append(m)
    if not c: fails.append(m)

# ---------- P0-1 : figures embedded as images ----------
main_embeds = re.findall(r'!\[Figure (\d+)', text)
si_embeds = re.findall(r'!\[Figure (S\d+)', supp)
ok(sorted(set(main_embeds), key=int) == ["1","2","3","4","5","6"], f"main figure embeds: {sorted(set(main_embeds))}")
ok(sorted(set(si_embeds)) == [f"S{i}" for i in range(1, 9)], f"SI figure embeds: {sorted(set(si_embeds))}")
# every referenced png exists
for p in re.findall(r'\]\((figures/incident/[^)]+\.png)\)', text + supp):
    ok(os.path.exists(os.path.join(DEL, p.replace("/", os.sep))), f"embedded image missing on disk: {p}")

# ---------- P0-3 / P1-9 : code availability honest (now actually published) ----------
ok("released as one versioned, citable repository at https://github.com/teamhuang/stroke-risk-transportability" in text,
   "code availability does not state the real published repository URL")
ok("frozen release tag v1.0.0" in text, "code availability missing the frozen release tag v1.0.0")
ok("cannot drift apart" not in text, "absolute 'cannot drift apart' overclaim remains")
ok("[AUTHOR-SPECIFIC" in text[text.index("## Code availability"):text.index("## Ethics")], "Zenodo-DOI placeholder must remain (author-issued)")

# ---------- P0-4 / P1-1 ----------
ok("survey-ascertainable probability of a first reported stroke" in text, "P0-4 estimand lead missing")
ok("Every figure in this paragraph is on the separately-fitted (V4) arm" in text, "P1-1 model-identity note missing")

# ---------- P1-4 : Korea qualifier on all core tables ----------
ok(text.count("partial-outcome external validation") >= 5,
   f"Korea partial-outcome qualifier not on all core tables ({text.count('partial-outcome external validation')})")

# ---------- P1-5 / P1-8 ----------
ok("not a replicate mean" in text, "Table 3 estimator clarification missing (P1-5)")
ok("not directly comparable with it" in text, "Table 4 estimator clarification missing (P1-5)")
ok("hypothetical ascertainment scenarios in Supplementary Table S6" in text, "S6 hypothetical emphasis missing (P1-8)")

# ---------- P2 batch ----------
ok("round-11 frozen build" in supp and "round-10" not in supp, "SI version tag not synced (P2-1)")
ok("`(Supplementary_technical.md)`" not in text and "`Supplementary_technical.md`" not in text,
   "internal .md filename still cited in main prose (P2-2)")
ok("(Tables 3, 4, 10, 11, 17)" in text, "Korea footnote table order not fixed (P2-3)")
ok("shipped" not in text, "'shipped' dev language remains in main (P2-6)")
ok("pre-audit" not in supp and "wrong-scale" not in supp, "dev language remains in SI (P2-6)")

# ---------- numbers preserved ----------
for v in ["0.802", "1.147", "2.975", "0.897", "3.004"]:
    ok(v in text, f"joint/V4 value {v} missing")
ok(text.count("[AUTHOR-SPECIFIC") == 2, f"AUTHOR-SPECIFIC count {text.count('[AUTHOR-SPECIFIC')} != 2 (back-matter author items resolved/removed at author instruction; only code-DOI + AI-policy confirm remain)")

if fails:
    print(f"ran {len(checks)} assertions"); print("FAIL:")
    for m in fails: print("  -", m)
    sys.exit(1)
print(f"ran {len(checks)} assertions")
print("PASS round-12: 14 figures embedded (6 main + 8 SI, all PNGs on disk); code availability honest; "
      "P0-4 survey-ascertainable lead; Korea partial-outcome qualifier on Tables 3/4/10/11/17; Table 3/4 "
      "estimator clarified; S6 hypothetical emphasised; SI version tag round-11; internal .md filename removed; "
      "Korea footnote order fixed; dev language stripped; joint 0.802/1.147/2.975/0.897 + V4 3.004 preserved; 2 remaining author-only items (code-DOI, AI-policy).")
