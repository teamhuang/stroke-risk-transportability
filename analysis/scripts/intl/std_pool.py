"""One rule for which harmonised panels a CROSS-SECTIONAL (prevalent-outcome) run may load.

Why this exists: the prevalent arm leaves one COUNTRY out, and it uses NHANES as its United States
panel. RAND HRS is also United States. Dropping `std_HRS.csv` in `data/processed/intl/corrected/`
therefore makes any `std_*.csv` glob silently merge two US panels into one held-out "country", so
the published four-country numbers would change without any error being raised. The incident arm
does not have this problem - NHANES contributes zero person-intervals, so HRS is its only US panel.

So HRS is excluded from the prevalent pool by name, here, in one place, with the reason printed -
rather than by hiding the file somewhere unusual and hoping nobody globs for it.

The incident arm selects its cohorts explicitly (`incident_personperiod.SPECS`), so it is
unaffected by this filter.
"""
import glob
import os
import sys

PREVALENT_EXCLUDED = {"HRS"}


def std_files(d):
    """Sorted std_*.csv paths that belong in a prevalent-outcome LOCO run."""
    kept, dropped = [], []
    for f in sorted(glob.glob(os.path.join(d, "std_*.csv"))):
        cohort = os.path.basename(f)[len("std_"):-len(".csv")]
        (dropped if cohort in PREVALENT_EXCLUDED else kept).append((cohort, f))
    if dropped:
        print(f"  std_pool: excluded {sorted(c for c, _ in dropped)} from the prevalent arm - "
              f"they carry a country key a `std_*.csv` glob would merge into an existing country. "
              f"Load them only through the incident SPECS.", file=sys.stderr)
    return [f for _, f in kept]
