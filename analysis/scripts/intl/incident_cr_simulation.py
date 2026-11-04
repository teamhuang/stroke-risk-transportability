"""P0-1 simulation: which competing-risks composition is unbiased when the truth is known?

The reviewer's action item 5 was to test, on simulated data with both cause-specific hazards elevated,
whether the shipped composition carries a systematic bias. This script does that, because on real data
the question cannot be settled - the true cumulative incidence is never observed - and prose about
"consistency" is not evidence.

Generator (independent latent failure times, the assumption the product form relies on)
    x       ~ N(0,1) per person
    lambda_s(x) = exp(a0 + a1 x)    stroke
    lambda_d(x) = exp(b0 + b1 x)    death (competing)
    T_s ~ Exp(lambda_s), T_d ~ Exp(lambda_d), independent
    TRUTH   F_s(tau) = P(T_s <= tau and T_s < T_d)
                   = lambda_s/(lambda_s+lambda_d) * (1 - exp(-(lambda_s+lambda_d) tau))

Observation model, matching the panels
    Interview grid with gaps of length L. A person's FIRST event category in a gap is observed as
    stroke / death / neither; nothing inside a gap is seen. Intervals are generated until the person
    has a first event or the study window closes, which is exactly the interval-censored discrete-time
    risk set the real analysis uses.

Estimators compared, all fitted on the same simulated rows
    M1  shipped V4 - two separate interval-censored cause-specific fits, composed as
        sum_j S_{j-1} p_s,j with p_s = 1-exp(-lambda_s D) and S = prod(1-p_s)(1-p_d).
    M2  exact V5  - the SAME two fitted hazards, composed as
        sum_j S_{j-1} lambda_s/(lambda_s+lambda_d)(1-exp(-(lambda_s+lambda_d)D)).
    M3  cause-specific-only - sum with death ignored: 1-exp(-Lambda_s(tau)). Expected to over-predict,
        included as the reference for what "treating death as censoring" costs.
    M4  exact formula on the TRUE hazards - not an estimator, the yardstick: plug the simulated
        lambda_s, lambda_d into M2's formula. If M2 is unbiased it tracks M4.

Scenarios
    realistic     lambda_s ~ 0.6%/yr, lambda_d ~ 5%/yr, 2-year gaps   (what these panels look like)
    elevated      lambda_s ~ 3%/yr,   lambda_d ~ 15%/yr, 2-year gaps  (the reviewer's both-high case)
    severe        lambda_s ~ 6%/yr,   lambda_d ~ 30%/yr, 2-year gaps
    long_gaps     elevated rates with 4-year gaps                     (bias should grow with D^2)
    frailty       elevated rates with a SHARED gamma frailty scaling both hazards - the independent
                  latent times assumption is violated, so M1 and M2 are expected to differ from truth
                  for a different and disclosed reason

Usage: python incident_cr_simulation.py [--persons 40000] [--reps 8] [--tau 4]
Outputs: data/processed/intl/incident/incident_cr_simulation.csv
"""
import os, sys, warnings
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)
import incident_ic_grid as IC                                    # noqa: E402
import incident_cr_exact as EX                                   # noqa: E402


def flag(name, default):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default

OUT = EX.OUT
SEED = 20261101


def simulate(n, a0, a1, b0, b1, gap, tau, rng, frailty=False):
    """One simulated panel: person-level truth plus the interval rows an interviewer would see."""
    x = rng.standard_normal(n)
    if frailty:
        # a shared frailty Z multiplies BOTH hazards, so the two latent times are dependent given Z
        Z = rng.gamma(1.0 / 0.5, 0.5, size=n)
    else:
        Z = np.ones(n)
    ls = np.exp(a0 + a1 * x) * Z
    ld = np.exp(b0 + b1 * x) * Z
    Ts = rng.exponential(1.0 / np.maximum(ls, 1e-9))
    Td = rng.exponential(1.0 / np.maximum(ld, 1e-9))
    first = np.minimum(Ts, Td)
    truth_is_stroke = Ts <= Td
    truth_F = (ls / (ls + ld)) * (1.0 - np.exp(-(ls + ld) * tau))

    rows = []
    t0 = np.zeros(n)
    alive = np.ones(n, dtype=bool)
    k = 0
    while np.any(alive & (t0 < tau)):
        idx = np.where(alive & (t0 < tau))[0]
        t_end = np.minimum(t0[idx] + gap, tau)
        L = t_end - t0[idx]
        in_gap = (first[idx] > t0[idx]) & (first[idx] <= t_end)
        d_s = (in_gap & truth_is_stroke[idx]).astype(int)
        d_d = (in_gap & ~truth_is_stroke[idx]).astype(int)
        rows.append(pd.DataFrame({"pid": idx, "k": k, "x": x[idx], "exposure_years": L,
                                  "t_start": t0[idx], "d_s": d_s, "d_d": d_d,
                                  "truth_ls": ls[idx], "truth_ld": ld[idx]}))
        # The clock advances for EVERYONE in the risk set, not only for those who had an event: a
        # person who reached t_end event-free starts the next interval at t_end. Advancing only the
        # event rows re-issued the identical interval for the event-free, forever - an infinite loop
        # that looked like a slow fit.
        t0[idx] = t_end
        alive[idx[(d_s.astype(bool) | d_d.astype(bool)) | (t_end >= tau)]] = False
        k += 1
    R = pd.concat(rows, ignore_index=True)
    assert not R.duplicated(subset=["pid", "k"]).any(), "risk set re-issued an interval"
    assert float(R.exposure_years.min()) > 0, "zero-length interval"
    return R, dict(x=x, truth_F=truth_F, truth_ls=ls, truth_ld=ld, tau=tau, gap=gap)


def fitted_rates(fit, x, t_start, step):
    """The per-year cause-specific hazard the fitted offset model implies at these covariates.

    The frame is rebuilt with the fitted column order spelled out, because `cause_rates` goes through
    the model's own imputer, which rejects a frame whose columns are not in the order it saw at fit."""
    F = pd.DataFrame({"x": x, "exposure_years": np.full(len(x), float(step)),
                      "t_start": np.asarray(t_start, dtype=float)})
    lam, _ = EX.cause_rates(fit, F[fit.cols])
    return lam


def compose_pair(ls, ld, step, tau, exact):
    """CIF under one of the two compositions, with piecewise-constant hazards over the window."""
    n_steps = max(1, int(round(tau / step)))
    if exact:
        tot = np.maximum(ls + ld, 1e-12)
        S = np.exp(-tot * step)
        alpha = ls / tot * (1.0 - S)
        acc = np.zeros(len(ls))
        surv = np.ones(len(ls))
        for _ in range(n_steps):
            acc = acc + surv * alpha
            surv = surv * S
        return acc
    p_s = 1.0 - np.exp(-ls * step)
    p_d = 1.0 - np.exp(-ld * step)
    S = (1.0 - p_s) * (1.0 - p_d)
    acc = np.zeros(len(ls))
    surv = np.ones(len(ls))
    for _ in range(n_steps):
        acc = acc + surv * p_s
        surv = surv * S
    return acc


def main():
    n = int(flag("--persons", "40000"))
    reps = int(flag("--reps", "8"))
    tau = float(flag("--tau", "4"))
    SCEN = {
        "realistic": dict(a0=np.log(0.006), a1=0.6, b0=np.log(0.05), b1=0.4, gap=2.0, frailty=False),
        "elevated": dict(a0=np.log(0.03), a1=0.6, b0=np.log(0.15), b1=0.4, gap=2.0, frailty=False),
        "severe": dict(a0=np.log(0.06), a1=0.6, b0=np.log(0.30), b1=0.4, gap=2.0, frailty=False),
        "long_gaps": dict(a0=np.log(0.03), a1=0.6, b0=np.log(0.15), b1=0.4, gap=4.0, frailty=False),
        "frailty": dict(a0=np.log(0.03), a1=0.6, b0=np.log(0.15), b1=0.4, gap=2.0, frailty=True),
    }
    out = []
    for name, cfg in SCEN.items():
        for rep in range(reps):
            rng = np.random.default_rng(SEED + 1000 * rep + abs(hash(name)) % 997)
            R, T = simulate(n, cfg["a0"], cfg["a1"], cfg["b0"], cfg["b1"], cfg["gap"], tau, rng,
                            cfg["frailty"])
            persons = np.unique(R.pid.values)
            bx = T["x"][persons]
            bt = np.zeros(len(persons))
            step = cfg["gap"]
            Xtr = R[["x", "exposure_years", "t_start"]]
            fs = IC.IcFit(Xtr, R.d_s.values, "cloglog", "offset", 1.0)
            fd = IC.IcFit(Xtr, R.d_d.values, "cloglog", "offset", 1.0)
            lt = fitted_rates(fs, bx, bt, step)
            dt = fitted_rates(fd, bx, bt, step)
            est4 = compose_pair(lt, dt, step, tau, exact=False)
            est5 = compose_pair(lt, dt, step, tau, exact=True)
            est_cause_only = 1.0 - np.exp(-lt * tau)
            truth = T["truth_F"][persons]
            tot = np.maximum(lt + dt, 1e-12)
            yardstick = lt / tot * (1.0 - np.exp(-tot * tau))
            assert abs(est5.mean() - yardstick.mean()) / max(yardstick.mean(), 1e-12) < 0.02,                 "the exact composition should already equal the analytic CIF within the step grid" 
            out.append(dict(scenario=name, rep=rep, n_persons=len(persons),
                            n_intervals=len(R), step_years=step,
                            truth_mean_F=float(truth.mean()),
                            M1_shipped_product=float(est4.mean()),
                            M2_exact_exclusive=float(est5.mean()),
                            M3_cause_specific_only=float(est_cause_only.mean()),
                            M4_exact_on_true_hazards=float(truth.mean()),
                            M4b_exact_on_fitted_hazards=float(yardstick.mean()),
                            bias_M1_pct=float(100 * (est4.mean() / truth.mean() - 1)),
                            bias_M2_pct=float(100 * (est5.mean() / truth.mean() - 1)),
                            bias_M3_pct=float(100 * (est_cause_only.mean() / truth.mean() - 1)),
                            obs_stroke_rate=float(R.d_s.mean()), obs_death_rate=float(R.d_d.mean()),
                            mean_ls=float(T["truth_ls"][persons].mean()),
                            mean_ld=float(T["truth_ld"][persons].mean())))
        print(f"{name}: done", flush=True)
    S = pd.DataFrame(out)
    S.to_csv(os.path.join(OUT, "incident_cr_simulation.csv"), index=False)
    print("\n" + "=" * 100)
    print("MEAN BIAS vs THE KNOWN TRUTH, % (positive = over-predicts the cumulative incidence)")
    print("=" * 100)
    g = S.groupby("scenario").mean(numeric_only=True)
    print(g[["mean_ls", "mean_ld", "truth_mean_F", "M1_shipped_product", "M2_exact_exclusive",
             "bias_M1_pct", "bias_M2_pct", "bias_M3_pct"]].round(4).to_string())
    print("\n" + "-" * 100)
    print("INTERPRETATION")
    for s in SCEN:
        r = g.loc[s]
        print(f"  {s:<10} shipped {r.bias_M1_pct:+.2f}%  exact {r.bias_M2_pct:+.2f}%  "
              f"death-as-censoring {r.bias_M3_pct:+.2f}%  "
              f"({'exact composition is the unbiased one' if abs(r.bias_M2_pct) < abs(r.bias_M1_pct) else 'NOT the case here'})")
    print("\n  If M2 sits at ~0% while M1 is positive and grows with the product of the hazards, the "
          "shipped\n  composition has a systematic upward bias that the exact form removes, and the "
          "bias is the\n  p_s*p_d term rather than grid discretisation. The frailty row is expected to "
          "break both,\n  because there the independent-latent-times assumption the product survival "
          "needs is false.")


if __name__ == "__main__":
    main()
