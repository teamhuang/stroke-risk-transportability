"""List harmonised-gate columns and labels for the time/mortality fields.

The incident-stroke arm needs, per cohort and per wave: the interview date (start and end),
the death date, and whether a person's stroke item was actually asked. This prints exactly
those columns with their official labels so the person-period script is written against the
file's own metadata rather than a guess, and so the audit trail names the variables.

Usage:
  python probe_event_fields.py CHARLS
  python probe_event_fields.py MHAS
"""
import os, sys, re
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
PATHS = {
    "CHARLS": os.path.join(ROOT, "data", "raw", "intl", "CHARLS", "H_CHARLS_D_Data.dta"),
    "MHAS": os.path.join(ROOT, "H_MHAS_d.dta"),
}
# anything that can place an event or a censoring time on a calendar axis
PATTERN = re.compile(
    r"^(r[1-9]|s[1-9]|h[1-9])?"
    r"(a?intw|iw|intv|iam|iay|astart|aend|endm|endy|d(ie|ea|y|ead)|dyr|dyear|death|"
    r"ham|hap|had|stroke|agey|age|birth|byear|wtresp|wave|r[n]?w)", re.I)
LOOSE = re.compile(r"(intw|year|death|die|died|age|stroke|birth|wave|last)", re.I)


def main():
    cohort = sys.argv[1] if len(sys.argv) > 1 else "CHARLS"
    path = PATHS[cohort]
    with pd.io.stata.StataReader(path) as r:
        labs = r.variable_labels()
    names = list(labs)
    print(f"{cohort}: {len(names)} columns  ({path})")
    hits = [n for n in names if PATTERN.match(n)]
    print(f"  strict-prefix matches: {len(hits)}")
    for n in sorted(hits):
        print(f"    {n:16s} {str(labs[n])[:70]}")
    label_hits = [n for n in names if LOOSE.search(str(labs[n] or ""))]
    print(f"  label matches (time/death vocabulary): {len(label_hits)}")
    for n in sorted(label_hits)[:120]:
        print(f"    {n:16s} {str(labs[n])[:70]}")


if __name__ == "__main__":
    main()
