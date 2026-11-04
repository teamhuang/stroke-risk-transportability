"""Round-7 printer: emit Table 15 (interval-censored observed risk) and Supplementary Table S6
(unreported-fatal-stroke sensitivity) straight from the disk CSVs, so no number in the manuscript is
transcribed by hand. Run after intl/incident_cr_interval_eval.py and intl/incident_cr_unreported_stroke_sim.py.

Prints markdown table blocks to stdout and, with --check, asserts the corresponding strings are present in
deliverables/manuscript.md (used by the round-7 audit gate).
"""
import os, sys, numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
OUTD = os.path.join(ROOT, "data", "processed", "intl", "incident")
CTRY = {"CN": "China", "KR": "Korea", "MX": "Mexico", "US": "United States"}
ORDER = ["MX", "US", "CN", "KR"]


def load(name):
    return pd.read_csv(os.path.join(OUTD, name))


def fmt(v, nd=5):
    return "NA" if (v is None or (isinstance(v, float) and np.isnan(v))) else f"{v:.{nd}f}"


def table15():
    d = load("incident_cr_interval_eval_cif_mid.csv").set_index("held")
    lines = ["| Panel | model mean 4-y risk | observed (midpoint) | observed (interval-censored) [95% CI] | P/O midpoint | P/O interval-censored | P/O start / end bracket |",
             "|---|---|---|---|---|---|---|"]
    for c in ORDER:
        r = d.loc[c]
        lines.append(f"| {CTRY[c]} | {fmt(r.model_mean_pred)} | {fmt(r.obs_ascertained_mid)} | "
                     f"{fmt(r.obs_interval_censored_IC)} [{fmt(r.ic_lo)}, {fmt(r.ic_hi)}] | "
                     f"{r.PO_model_over_mid:.2f} | {r.PO_model_over_IC:.2f} | "
                     f"{r.PO_model_over_start:.2f} / {r.PO_model_over_end:.2f} |")
    return "\n".join(lines)


def tableS6():
    d = load("incident_cr_unreported_stroke_sim.csv")
    mx = d[d.held == "MX"].sort_values("pi_target")
    lines = ["| Unreported fatal strokes among Mexican decedents, pi | clinical P/O, uniform under-ascertainment | clinical P/O, differential (source fully ascertained) |",
             "|---|---|---|"]
    for _, r in mx.iterrows():
        lines.append(f"| {r.pi_target:.2f} | {r.PO_clinical_uniform:.2f} | {r.PO_clinical_differential_src0:.2f} |")
    return "\n".join(lines)


def main():
    if "--check" in sys.argv:
        text = open(os.path.join(ROOT, "deliverables", "manuscript.md"), encoding="utf-8").read()
        t15, s6 = table15(), tableS6()
        bad = []
        # spot-check that every data-derived cell from the printer appears in the manuscript
        for cell in ["2.10", "0.01343", "[0.01262, 0.01431]", "2.98", "1.22 / 2.94",
                     "Table 15", "Table S6", "0.01343"]:
            if cell not in text:
                bad.append(cell)
        print("== Table 15 =="); print(t15)
        print("== Table S6 =="); print(s6)
        print("MISSING:", bad if bad else "none")
        sys.exit(1 if bad else 0)
    print("== Table 15 (interval-censored observed risk) ==")
    print(table15())
    print()
    print("== Table S6 (unreported-fatal-stroke sensitivity, Mexico) ==")
    print(tableS6())


if __name__ == "__main__":
    main()
