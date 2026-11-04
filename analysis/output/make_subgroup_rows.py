"""Print the stratum-level transportability table (Table 12) and verify the Discussion's age-band prose.

Review item P1-6 asked for the age subgroups to be promoted from a Discussion sentence to a table. The
sentence quoted four numbers with no printer behind them, which is the same failure mode as defect 24 -
a manuscript that claims nothing is transcribed by hand while one table has no printer - so the
promotion and the verification are done together here.

Reads only results/tables/incident_subgroups_2026-11-03.csv (produced by
`intl/incident_subgroups.py`), which is the published logistic classifier evaluated at the four-year
horizon on the primary event-timing rule. Nothing here refits anything.

Usage: python make_subgroup_rows.py
"""
import os, sys
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
T = os.path.join(ROOT, "results", "tables")
DAY = "2026-11-03"
PANELS = ["CN", "KR", "MX", "US"]
BANDS = ["ALL", "20-59", "60-69", "70-79", "80+"]


def load(name):
    p = os.path.join(T, name)
    if not os.path.exists(p):
        sys.exit(f"missing published table: results/tables/{name} "
                 f"(run intl/incident_subgroups.py then publish_incident_tables.py)")
    return pd.read_csv(p)


def main():
    full = load(f"incident_subgroups_{DAY}.csv")
    d = full[(full.horizon_rule == "cif_mid") & (full.model == "logistic")]
    rows = []
    for held in PANELS:
        for band in BANDS:
            st = "ALL" if band == "ALL" else "age_band"
            lv = "all held-out persons" if band == "ALL" else band
            q = d[(d.held == held) & (d.stratum == st) & (d.level == lv)]
            if not len(q):
                sys.exit(f"no published row for {held}/{lv}")
            rows.append(q.iloc[0])
    R = pd.DataFrame(rows)

    print("=" * 118)
    print("TABLE 12 - stratum-level transportability of the frozen four-year model (logistic arm,")
    print("             primary event-timing rule). One row per panel x age band.")
    print("=" * 118)
    print("%-4s %-20s %7s %7s %10s %10s %8s %20s %10s %6s" %
          ("held", "band", "n", "events", "obs CIF", "mean pred", "P/O", "AUROC [95% CI]",
           "NB@5%", "interp"))
    for _, r in R.iterrows():
        print("%-4s %-20s %7d %7d %10.5f %10.5f %8.3f %6.3f [%5.3f,%5.3f] %+10.5f %6s" %
              (r.held, r.level, r.n, r.events, r.prevalence_ipcw, r.mean_predicted_ipcw,
               r.pred_over_obs, r.auroc, r.auroc_lo, r.auroc_hi, r.net_benefit_5pct,
               "yes" if r.interpretable else "no"))

    print("\n" + "-" * 118)
    print("READY-TO-PASTE MARKDOWN FOR TABLE 12 (pasted verbatim; this block is the source of truth)")
    print("| Panel | age band | n | events | observed 4-year CIF | mean predicted | P/O | AUROC [95% CI] | NB at 5% |")
    print("|---|---|---|---|---|---|---|---|---|")
    for _, r in R.iterrows():
        band = "all ages" if r.level == "all held-out persons" else r.level
        print(f"| {r.held} | {band} | {r.n} | {r.events} | {r.prevalence_ipcw:.5f} | "
              f"{r.mean_predicted_ipcw:.5f} | {r.pred_over_obs:.3f} | {r.auroc:.3f} "
              f"[{r.auroc_lo:.3f}, {r.auroc_hi:.3f}] | {r.net_benefit_5pct:+.5f} |")
    print("<!-- AUROC cells are printed to three decimals; the stored table carries four. Two cells")
    print("(US 80+ auroc_lo 0.4645, KR 80+ auroc 0.4865) sit on the three-decimal rounding boundary, so")
    print("where the manuscript quotes those two it carries the published four digits. -->")

    print("\n" + "-" * 118)
    print("THE PATTERN TABLE 12 EXISTS TO SHOW")
    for held in PANELS:
        s = R[(R.held == held) & (R.level != "all held-out persons")]
        po = s.set_index("level").pred_over_obs
        order = [b for b in ["20-59", "60-69", "70-79", "80+"] if b in po.index]
        print(f"  {held}: level error by band " +
              " -> ".join(f"{b} {po[b]:.2f}" for b in order) +
              f"  | gradient {po[order[-1]] - po[order[0]]:+.2f} from youngest to oldest")
    print("\n  Discrimination and level behave OPPOSITELY across the bands, which is why both columns")
    print("  are in the table. The panel with the flattest level gradient (United States, where the")
    print("  oldest band is the only one UNDER-predicted) is also the panel whose oldest band loses")
    print("  ranking entirely, so a reader cannot infer one from the other.")

    print("\n" + "-" * 118)
    print("VERIFICATION OF THE DISCUSSION'S QUOTED AGE-BAND SENTENCES")
    q = {f"{r.held}|{r.level}": r for _, r in R.iterrows() if r.stratum == "age_band"}
    checks = [("MX|80+", "pred_over_obs", 7.26), ("MX|20-59", "pred_over_obs", 2.38),
              ("US|80+", "auroc", 0.505), ("US|80+", "auroc_lo", 0.465),
              ("US|80+", "auroc_hi", 0.546), ("KR|80+", "auroc", 0.487),
              ("KR|80+", "auroc_lo", 0.354), ("KR|80+", "auroc_hi", 0.604)]
    bad, edge = [], []
    for key, col, quoted in checks:
        got = float(q[key][col])
        nd = len(f"{quoted}".split(".")[1])
        tol = 0.5 * 10 ** -nd
        err = abs(got - quoted)
        tag = "MATCH"
        if err > tol + 1e-12:
            tag = "MISMATCH"; bad.append((key, col, quoted, got))
        elif abs(err - tol) <= 1e-12:
            # the published table is stored to four decimals, so a quote that lands exactly on the
            # half-way point cannot be resolved from it - the prose must carry the published digits
            tag = "BOUNDARY"
            edge.append(f"{key} {col}: published {got}, manuscript rounded to {quoted}")
        print(f"  {key:<9} {col:<14} manuscript {quoted:.3f}  published {got:.4f}  {tag}")
    if edge:
        print(f"\n  {len(edge)} quote(s) sit on the rounding boundary and should carry the published"
              " digits instead:\n    " + "\n    ".join(edge))
    print(f"\n  {len(checks)} quoted cells checked, {len(bad)} mismatches, {len(edge)} on the rounding "
          f"boundary -> "
          f"{'TABLE 12 BACKS THE PROSE' if not bad else 'PROSE IS WRONG: ' + str(bad)}")

    print("\n  Smallest strata in the table, because an age band with ten events cannot carry a")
    print("  recommendation: " +
          ", ".join(f"{r.held} {r.level} n={r.n} events={r.events}"
                   for _, r in R.iterrows()
                   if r.stratum == "age_band" and r.events < 20))
    print("  The published table also carries the random-forest arm "
          f"({int((full.model == 'random_forest').sum())} rows) and the sex / hypertension / education / "
          "interval-length strata; they are supplementary, and only the age gradient is claimed in the "
          "main text.")


if __name__ == "__main__":
    main()
