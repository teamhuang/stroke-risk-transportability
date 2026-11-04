"""Round-10 P0-1 + P1-2: rewrite Methods 'How the predicted probability is built' so the JOINT
multinomial competing-risks likelihood is defined FIRST (primary estimator), the separately-fitted
two-hazard Aalen-Johansen composition is demoted to a sensitivity arm, the exclusive first-event
probability alpha_{s,j} is introduced with its own symbol and recursion, the marginal p_{s,j} is kept
separate, and the 'one-piece Aalen-Johansen equals cause-specific risk exactly' sentence is qualified as
an algebraic property of the single-step discrete approximation rather than a general continuous-time fact.

Marker-based slice (long block with en-dashes/minus signs), atomic write."""
import io, os

MD = "H:/脑出血国际队列/deliverables/manuscript.md"
with io.open(MD, "r", encoding="utf-8") as f:
    text = f.read()
orig = text

START = "### How the predicted probability is built"
END = "### Local adaptation, and the audit that it does not look at the answer"
i0 = text.find(START); i1 = text.find(END)
assert i0 != -1 and i1 != -1 and i1 > i0, "section markers not found"
old_block = text[i0:i1]
assert "Two cause-specific hazards are fitted" in old_block and "not in the released data." in old_block, "unexpected block content"

new_block = (
"### How the predicted probability is built\n\n"
"**The primary estimator is a single joint multinomial competing-risks likelihood** "
"(`intl/incident_cr_joint.py`). Each person-interval is classified into one of three mutually exclusive "
"interval outcomes - stroke-first, death-first, or neither - and one set of coefficients is fitted by "
"maximising the joint likelihood of those three outcomes, so the interval probabilities sum to 1 by "
"construction (measured 2.2 \u00d7 10\u207b\u00b9\u2076) rather than needing an after-the-fact exclusivity correction. Write "
"\u03b1_s,j and \u03b1_d,j for the joint model's probabilities that the *first* event in step j is a stroke or a "
"death, and let S(t_j) = \u03a0_{k\u2264j}(1 \u2212 \u03b1_s,k \u2212 \u03b1_d,k) be the model's own probability of remaining "
"event-free through step j. The four-year cumulative incidence of a first stroke is then\n\n"
"F_s(4) = \u03a3_j S(t_{j\u22121}) \u00b7 \u03b1_s,j,\n\n"
"read over the panel's own interval grid. Because the \u03b1's are exclusive by construction, a stroke and a "
"death falling inside one unobserved interview gap cannot both be counted, and no double-count term has to "
"be removed afterwards. Convergence is recorded per fit (`converged_stroke`, `converged_death`, iteration "
"counts); every primary-arm joint fit converged in 42-55 L-BFGS-B iterations under `ftol = 1e-14`, "
"`gtol = 1e-10`, and the analytic gradient matches finite differences to 1.5 \u00d7 10\u207b\u2079 at a non-degenerate "
"probe, so no published number in the joint tables sits at a loose optimum. Korea's death hazard is "
"transported rather than estimated, because KLoSA's main waves carry no vital-status field, so Korea's "
"observed cumulative incidence coincides with 1 \u2212 Kaplan\u2013Meier by construction; the arm that would fix "
"this - an exit-module death file - is not in the released data (see the KLoSA predict-side / observe-side "
"footnotes).\n\n"
"**The separately-fitted two-hazard composition is the sensitivity arm, not the primary estimator.** For "
"comparison, two cause-specific hazards are also fitted on the same person-interval rows by maximising the "
"interval-censored likelihood of each - a stroke known only to lie inside the interview gap (a, b] "
"contributing \u2212log{1 \u2212 (1 \u2212 p)^n} for an interval cut into n pieces, and an event-free gap contributing "
"n log(1 \u2212 p) - with the piece length standardised and, in the proportional-hazards arms, entering as a "
"log-exposure offset rather than as a covariate. Writing p_s,j and p_d,j for these *marginal*, "
"order-ignoring step probabilities, the discrete Aalen\u2013Johansen composition is\n\n"
"F_s(4) = \u03a3_j S(t_{j\u22121}) p_s,j,  S(t_j) = \u03a0_{k\u2264j} (1 \u2212 p_s,k)(1 \u2212 p_d,k),\n\n"
"with the companion cause-specific composition 1 \u2212 \u03a0_k(1 \u2212 p_s,k) reported beside it so the size of the "
"competing-mortality correction is visible in the same table rather than assumed. The marginal p_s,j and "
"the joint \u03b1_s,j are different objects and are never mixed inside one formula: p_s,j is the probability "
"that *a stroke occurs* in the step, \u03b1_s,j that the *first* event in the step is a stroke. Three properties "
"of this sensitivity construction are checked rather than asserted "
"(`analysis/output/make_cr_rows.py`, blocks 2 and 9). The offset arm's risk is invariant to how the "
"interval is chopped, measured at ratio 1.000000 between one piece and eight in all four panels. Refining "
"the pieces moves the marginal composition toward the analytic continuous CIF, "
"\u03bb_s/(\u03bb_s + \u03bb_d)[1 \u2212 exp(\u2212(\u03bb_s + \u03bb_d)\u03c4)], which the script prints next to the ladder; the shipped "
"product composition sits 0.1-2.6% above that closed form at four pieces and drifts to 0.9424 across the "
"one-to-eight ladder. The composition audit establishes that this is not a discretisation residual but an "
"exclusivity term: the marginal step uses `p_s` where the exclusive first-event probability "
"\u03b1_s = \u03bb_s/(\u03bb_s+\u03bb_d)(1 \u2212 exp(\u2212(\u03bb_s+\u03bb_d)D)) is required; the marginal over-states the exclusive one "
"by `p_s \u2212 \u03b1_s` (the death-first-within-step case), and the summed event probabilities therefore "
"double-count by the both-events term `p_s\u00b7p_d = (p_s \u2212 \u03b1_s) + (p_d \u2212 \u03b1_d)`. (That the one-piece "
"Aalen\u2013Johansen value coincides with the cause-specific risk is an algebraic property of that single-step "
"discrete approximation - with one piece there is no *later* step for a death to occupy - and not a general "
"fact about continuous-time competing risks; it is reported for transparency and is not relied on for any "
"conclusion.) Every separately-fitted arm in Table 9 converged in 20-25 L-BFGS-B iterations under the same "
"tolerances. The exact (V5) and joint-multinomial compositions remove the exclusivity term and are flat at "
"1.000000, leaving Mexico at 2.93-2.98-fold (Table 9b), and the joint model is the estimator every headline "
"is read off.\n\n"
)

text = text[:i0] + new_block + text[i1:]
tmp = MD + ".tmp"
with io.open(tmp, "w", encoding="utf-8") as f:
    f.write(text); f.flush(); os.fsync(f.fileno())
os.replace(tmp, MD)
print("rewrote 'How the predicted probability is built'; delta bytes", len(text) - len(orig))
