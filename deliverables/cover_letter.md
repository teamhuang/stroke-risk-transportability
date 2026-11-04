Dear Editors,

We submit an original research manuscript, **"Which country needs recalibration depends on how risk is
defined and composed: absolute-risk transport and local adaptation of incident-stroke models across four
national ageing cohorts,"** for consideration by npj Digital Medicine.

The paper tests a claim the digital-health literature makes constantly and rarely verifies: that a
prediction model is deployable because its discrimination survived a hold-out set. To make the test
possible we rebuilt our own study. The outcome is no longer "has anyone ever told you that you had a
stroke" but a **first reported stroke** between interviews, constructed as discrete-time hazards on
430,521 person-intervals from 94,005 stroke-free adults in four nationally representative ageing
cohorts (US RAND HRS, China CHARLS, Korea KLoSA, Mexico MHAS), 1,062,341 person-years and 6,979 incident
events, with mortality recovered from the interview-status field rather than the sparse death-date
field, and competing death handled as an Aalen–Johansen non-event rather than as censoring.

Eight findings, each quantified on identical held-out rows:

1. **The apparently strongest model was the worst traveller.** Under person-clustered internal
   cross-validation over all four panels, the boosted learners beat the logistic model by ~3.5 AUROC
   points at home (0.731 vs 0.697). Leave-one-country-out, mean held-out AUROC was 0.676 for XGBoost
   against 0.677 for the logistic model: an internal-to-external discrimination difference of +0.055 versus +0.020. A row-level split
   moves the internal reference by ≤0.0012, so the gradient is not a leakage artefact.
2. **What failed was level, not rank — and AUROC could not see it.** The frozen logistic model ranked
   Mexico's intervals at AUROC 0.659 while predicting a mean four-year risk of 0.0306 against 0.0095
   observed: over-prediction by a factor of 3.2, negative net benefit, and a screening rule that would
   flag one adult in seven. The sign of that level error flips with model family (linear models
   over-predict the United States by 1.16-fold; tree ensembles under-predict it by 0.82-fold), so no
   single "the model over/under-predicts" sentence is true.
3. **The repair is one parameter, and it is only worth applying where the level is actually wrong — and
   it reduces harm before it produces benefit.** An intercept re-estimated on 396 Mexican adults (2% of
   the panel) moved four-year net benefit from −0.00449 to −0.00021, a paired gain of +0.00429 (SD 0.00045,
   better than the frozen model in 19 of 19 replicate pairs) with AUROC unchanged to six decimals. That is
   still below treat-none at the prespecified 5% threshold: the honest claim is that horizon-scale
   recalibration *substantially reduced decision harm*, not that it established positive clinical net
   benefit. It does the latter under the stricter coverage rule described in finding 4, where the repaired
   net benefit turns positive at local samples of 5% and above. In China the same parameter did nothing; in
   the United States it cost 0.00065 under this composition and was neutral-to-positive under the
   competing-risks composition of finding 6, which is why we no longer state a US-level verdict. We also show that fitting that identical parameter
   on the wrong scale — inside the per-interval hazard rather than on the composed four-year risk the rule
   is deployed on — turns a neutral repair in China into a 33-fold worsening that lost in 20 of 20
   replications. Retraining is not the ambitious option by default: at 2% local data it cost Korea 0.140
   horizon AUROC and gained the United States 0.006. And we report the intercept's own sampling error
   (SD 0.44 log-odds on a 337-adult Mexican sample carrying a median of four events, tracking 1/√events),
   because "396 local adults" is the point at which the direction of the repair becomes unambiguous, not a
   verified minimum sample size.
4. **The label decisions moved the headline more than any model did — and when we refitted the whole
   design to test the strongest of them, the headline survived.** Three conventions — where inside an
   interview gap an interval-censored event is dated, whether pre-horizon death is a competing event or an
   exclusion, and whether a person merely known to be alive counts as observed — change the four-year
   incidence of first stroke by up to 3.8-fold and reverse which country a study says needs repair. Our own
   previous headline (China under-predicted threefold, worth +0.0153 net benefit to fix) was an artefact of
   the first two conventions. The coverage convention drew the sharpest objection, and our first response —
   re-label the evaluation frame while leaving the models trained on the permissive risk set — was wrong in
   its conclusion even though the invariant it appealed to is real. We therefore refitted every classifier
   leave-one-panel-out on a risk set that ends where stroke ascertainment ends, retaining all 23,347 death
   intervals. Every conclusion held and the most exposed one strengthened: Mexico's level error falls
   3.22 → 2.61, its AUROC rises 0.611 → 0.645, and the one-intercept repair moves its net benefit from
   −0.00194 to positive at ≥5% local data. A constraint worth reporting to other groups emerged in the
   process: in these panels a death is recorded on the interval that *begins* at the last answered
   interview, so strictening coverage by truncation deletes every competing death with it — "fully strict"
   and "competing-risks adjusted" are not simultaneously available, and a paper claiming both has silently
   switched estimands.
5. **A fourth family of conventions — the hazard's link, the interval grid, where the event sits inside an
   interval, and whether the objective is the interval-censored likelihood — localises the failure rather
   than dissolving it.** We fitted the same interval rows, same
   encoding, same splits under four discrete-time specifications: the published L2 logistic, an
   unpenalised logistic GLM, a cloglog hazard with interval length as a covariate, and the
   proportional-hazards formulation (cloglog with log-length as an offset), each refitted after re-cutting
   every interval onto a common one-year grid. Re-cutting an interval that contains a stroke forces a
   choice the unsplit risk set never makes — which piece carries the event — and our first version of the
   tool made it silently, putting the stroke in the parent's last piece. That asserts three stroke-free
   years nobody reported and it deflates the fitted hazard: mean predicted risk in China fell 0.0209 →
   0.0173 and US discrimination fell 0.727 → 0.718, which no finer grid should do. We rebuilt the arm with
   the allocation as an argument and three values reported side by side — fractional event weight, the
   midpoint piece, and the last-piece version kept only as a labelled, non-claiming column — and two
   conclusions from the first version were withdrawn. The reviewer then pointed out that our replacement
   was still not the right likelihood: splitting an event into fractional rows matches the event *count*
   inside a gap, whereas an interval-censored observation contributes 1 − ∏ⱼ(1 − pⱼ), the *probability*
   that the event lies in the gap. That is correct, and we rebuilt the arm a second time to maximise the
   actual interval-censored likelihood over parent intervals (`incident_ic_grid.py`; all 32 fits
   converged; at one piece per gap it collapses to the published likelihood and reproduces the three GLM
   arms' frozen rows to 4 × 10⁻⁸, which is what makes the grid column readable against the published
   column). The second rebuild changed two numbers we had quoted: under the correct likelihood China's
   level error moves 1.02 → 0.76 and the United States' 1.17 → 0.98, so both cross the line of correct
   level, while the weighted-row version had stopped them at 0.90 and 1.03–1.08. The sentence "the other
   three panels' level errors shrink toward one without changing sign" is therefore withdrawn too. What
   survives both rebuilds, and is now supported by 16 honest specifications rather than 12: **Mexico
   over-predicts by more than two-fold in every one of them (3.04–3.23), and the one-intercept repair is
   worth fitting only there** (positive in 12 of 12 interval-censored cells and 18 of 18 weighted-row
   cells, +0.0036 to +0.0043 at 2% of the local panel) — a gain against the frozen model only, since at
   2% of a panel the repaired absolute net benefit remains ≈0.0002 below treat-none in all of them.
   Discrimination is unaffected (within-panel AUROC range ≤0.004 in three panels). Duration consistency
   belongs to the exposure specification, not the grid or the likelihood: eight half-year pieces give
   4.43–5.65 times the answer of one four-year piece under either covariate-length link, 0.69–1.54 after
   refitting on the grid under the correct likelihood, and exactly 1.000 for the proportional-hazards arm
   at every grid and every allocation — for that arm the invariance is algebra, (1 − p)ⁿ = exp(−λnD) =
   exp(−λL), measured to 1.4 × 10⁻¹². The duration-consistent model is within 0.82–1.26 of
   observed incidence in three countries and still 3.08–3.18-fold high in the fourth. Building its anchor
   also surfaced a limit we now disclose rather than paper over: the published primary model is sklearn at
   its default tolerance (10 iterations), and the identical objective solved to 10⁻¹⁰ moves the US
   predicted-to-observed ratio from 1.161 to 1.170, so Table 8's first column is accurate to about two
   decimals. No conclusion depends on that difference.
6. **Rebuilding the absolute-risk analysis on a duration-consistent, competing-mortality model — which
   is what a four-year risk has to be — confirms the central finding and changes one of our own claims.**
   The estimand mixing was real: the observed comparator is an Aalen–Johansen cumulative incidence while
   the composed prediction was 1 − exp(−Λ_stroke), treating death as censoring. We therefore refitted two
   cause-specific interval-censored hazards (stroke and death) and composed them as
   F_s(4) = Σⱼ S(tⱼ₻₁)p_s,j with S(tⱼ) = Π_k(1 − p_s,k)(1 − p_d,k), in four specifications, under three
   event-time conventions, with 500-resample person-clustered intervals and 40 adaptation/evaluation
   splits per cell. The correction moves the level ratio by 0.5–3.2% relative across the eight
   panel-by-link cells and changes no panel's side of 1.0: **Mexico still over-predicts, 3.00-fold
   (95% CI 2.63–3.46) under the fully corrected arm, and the repair still pays (+0.00366 net benefit,
   positive in 40 of 40 splits, level 3.00 → 1.14) while beating treat-none in only 3 of 40 splits, each
   of those 3 by less than one net person in the 18,818-person evaluation
   sample.** Korea
   is the honest limit case: KLoSA's released waves carry no vital-status field, so its death hazard is
   transported and its cumulative incidence coincides with 1 − Kaplan–Meier by construction. Two things
   came out of the rebuild that we did not expect. The duration-consistency claim needed qualifying: the
   proportional-hazards cause-specific risk is invariant to the grid to the last decimal (ratio exactly
   1.000000), but the discrete Aalen–Johansen composition is not — its one-piece value equals the
   cause-specific risk and it converges on the analytic continuous CIF as pieces shrink (0.1–2.6% above
   at four pieces, crossing below at eight), so we report the discretisation against a closed form rather
   than calling it consistency. And the sign of the United States repair flipped with the composition, so
   the claim "recalibration costs money in the United States" is now stated per specification instead of
   as a finding about that country. A further audit of the composition itself asked whether the step
   product is a valid competing-events probability at all. The specific charge — that the
   survival factor should read 1 − p_s − p_d — is not correct under independent latent times (the product
   (1 − p_s)(1 − p_d) equals exp(−(λ_s+λ_d)D) exactly, gap 1.1 × 10⁻¹⁶), but writing the answer down
   exposed a *different* real error: the marginal composition multiplied each cause's step probability
   where an exclusive first-event composition needs α_s = λ_s/(λ_s+λ_d)·(1 − exp(−(λ_s+λ_d)D)), so a step
   carried mass 1 + p_s·p_d > 1. Following this through, **we have made the joint multinomial competing-risks
   likelihood — a single model on the three mutually exclusive interval outcomes, analytic gradient self-tested
   to 1.5 × 10⁻⁹, interval probabilities conserved to 2.2 × 10⁻¹⁶, step ladder flat at 1.000000 — the paper's
   PRIMARY absolute-risk estimator**, reported uniformly across abstract, Results, Discussion, age subgroups,
   calibration curves and decision analysis, with the separately-fitted two-hazard composition retained as a
   labelled sensitivity arm. The headline is invariant to the choice: Mexico reads 2.98 (95% CI 2.61–3.43)
   under the primary joint model against 3.00 under the marginal arm, a 0.96% relative shift, with the
   one-intercept repair still paying (+0.00368, every evaluated split, repaired level 1.14). We also made the
   headline honest about its one remaining assumption: the model side integrates the event time over each
   interview interval, but the primary observed comparator dates a stroke at the interval midpoint, and
   re-estimating the observed risk **midpoint-free** with an interval-censored competing-risks estimator puts
   Mexico at 2.10 rather than 2.98 — so the ~three-fold is stated as the value of the survey-ascertained,
   midpoint-dated estimand, not as a measurement-free fact about clinical risk. A further reviewer round then separated two estimators we had conflated: under a pooled-hazard interval-censored maximum likelihood China reads as severely under-predicted (P/O 0.40-0.47), which we confirmed is not a constant-hazard artefact by refitting piecewise-constant and log-linear hazards (Table 18), but which an estimand-matched midpoint-free check - relaxing only the within-interval allocation on the identical evaluable frame and IPCW weights - shows is a property of that estimator's re-specified censoring, not of the event-time rule: China barely moves (P/O stays 0.80) while Mexico alone moves materially (2.98 to 2.18), and our update rule re-run on the interval-censored outcome still flags only Mexico. We therefore state the conclusion in two tiers - stable, that transportability depends on the observation mechanism and event-time rule and cannot be licensed by AUROC; conditional, that the identity of the miscalibrated country is rule-dependent - and we added a five-variable transparent clinical model (age, sex, hypertension, diabetes, smoking) that matches the full transported model's discrimination (AUROC within 0.009 in all four panels) and fails to transport in the same places, plus a two-dimensional sensitivity to unreported pre-fatal stroke showing the Mexican over-prediction is robust to uniform under-ascertainment and only falls below one under an extreme, unsupported differential. A subsequent pass then made us state the estimator's assumption honestly: the estimand-matched midpoint-free check is a *uniform-within-interval allocation*, so we added a second allocation derived from the joint model itself (a truncated-exponential conditional event-time law). Dropping the uniform assumption changed almost nothing - China stays 0.80 and Mexico stays the only material move (2.98 to 2.18 under uniform, 2.14 under the model-based allocation) - which is now reported as a robustness result rather than an assumption-dependent reading. We also moved the prevalent-outcome (cross-sectional) arm and the exact-Shapley attributions out of the main article into a Supplementary technical file, and added an author/affiliation/corresponding front-matter skeleton; the ethics bodies, author identities, CRediT initials, code DOI and per-cohort data-use terms remain [AUTHOR-SPECIFIC] placeholders that only the authors can and must complete. We added a three-level
   summary table keeping statistical calibration, relative decision benefit and actual clinical utility
   explicitly separate, because the central finding sits at the first two levels and not the third.
7. **Two results that a deployment can act on, rather than read.** First, decile calibration curves with
   person-clustered intervals show that a panel-level ratio of 1.0 is not calibration: the observed
   decile risk rejects the frozen model's prediction in 10 of 10 Mexican deciles (1.7–3.9-fold at every
   level) and in 5 of 10 United States deciles, and after the one-intercept repair Mexico falls to 2 of 10
   while the United States gets worse, not better — 5 of 10 deciles rejected before the repair and 7 of 10
   after — a level problem in Mexico, a shape problem in the United
   States, which is the strongest argument here against treating intercept recalibration as a universal
   fix. Replacing the ten deciles with a smooth spline calibration curve and a person-clustered band makes
   the residual shape explicit: the intercept pulls Mexico's whole curve down, yet its top still runs below
   the diagonal — predicted near 0.11 against an observed 0.047 (95% band 0.019–0.108) before the repair — so the
   high-risk tail that a 5% threshold actually acts on is not repaired by a level shift (Figure 9b).
   Second, we replaced the retrospective "which country needs updating" with a decision rule — now evaluated
   on the **joint competing-risks model itself**, so the policy and the primary estimator are the same object —
   scored on persons who never entered the decision: update only when the local offset is both statistically
   resolved (|â| > 1.96 SE) and practically large (|â| ≥ 0.25). At 2% local data it fires in 70% of Mexican
   samples and captures +0.00261 of the +0.00357 that unconditional recalibration would obtain; once the local
   sample reaches 5% it fires in every evaluated split and captures the full +0.00370 repair, while staying
   frozen in 95% of United States samples. The magnitude gate earns its place: the US offset is small and
   positive (â ≈ +0.11), and a significance-only rule starts chasing it once 25% of the panel is available,
   which the |â| ≥ 0.25 gate suppresses. Promoting the estimator also **removed** an apparent failure mode
   rather than confirming it: under the joint arm Korea's frozen model already sits at predicted ÷ observed
   1.15, so recalibration there costs net benefit and the rule correctly declines to fire (three local events
   give â = −0.29 against SE = 0.61). Adaptation is therefore a statement about local sample size as much as
   about miscalibration.
8. **The central number is a risk difference, not a measurement artefact — and one intercept cannot fix
   a country's age gradient.** Four national questionnaires do not ask the same questions, so we refitted
   everything (both hazards, both compositions, the repair) after removing the two concepts whose *wording*
   differs - a lifetime "heart problems" item in the US and China against a specific heart-attack item in
   Korea and Mexico, and an "ever drinks" item against a last-year item - and again after removing the two
   whose availability differs, taking the model from 19 columns to 17 to 11. Mexico's four-year
   predicted-to-observed ratio went 3.004 -> 3.171 -> 3.106, i.e. 5.5% relative and *away* from correct,
   with the repair gain holding (+0.00365 -> +0.00454 -> +0.00430); the first tier is the published arm
   re-derived through the ablation script's own code path and reproduces all eight frozen cells to within
   1e-6, so the three rows are comparable by construction rather than by assertion. Separately, the
   published per-stratum repair column shows what a single panel-wide intercept actually does inside a
   country: Mexico's 20-59 band moves from 2.18 to 0.67 - the repair that makes the headline ratio
   correct creates a 33% under-prediction in 60% of the panel - and the United States' offset takes its
   20-59 band from 1.20 to 1.35 while lifting its 80+ band from 0.62 to 0.70. Acting on that, we tested
   whether the update itself could be made age-aware: five strategies fitted on local adults and scored on
   persons who never entered the fit, judged on the *worst* age band rather than only the panel average. A
   population intercept leaves some band roughly 2.0-fold wrong at any local sample; naive per-band
   intercepts buy nothing there; empirical-Bayes shrinking correctly collapses onto the population shift
   when 5% of the panel is too little to move a band; only a smooth intercept-plus-age term cuts the worst
   band from 6.3-fold (frozen) to 1.2-fold at 5% and 1.1-fold at 25%, and it carries the lowest net-benefit
   variance of any strategy. The honest negative sits alongside it: no age-aware update lifts Mexico's net
   benefit above treat-none - age-aware recalibration reduced age-stratified calibration heterogeneity in this retrospective evaluation, without making the model worth deploying, because
   the problem was never the ranking. Table 13.

We think this is the question a deploying health system actually has, and that the answer reverses the
default: adaptation should be triggered by a measured level gap of the right sign and magnitude, on the
scale the rule will be used, not applied by default — and the estimand has to be published alongside the
intervention, because the intervention is a function of it.

The study uses de-identified release files retrieved from each cohort's own portal: RAND HRS via the University of Michigan, CHARLS via charls.charlsdata.com, KLoSA via the Korea Longitudinal Study of Ageing (registration plus a study creation code), MHAS/ELES via its distributor, and NHANES from CDC/NCHS public distribution; the former Gateway to Global Aging Data mirror is no longer an active distributor. Each cohort is accessed under its own data-use agreement, no harmonised or restricted file is redistributed, and each study's terms of use - including any limit on automated or AI-assisted processing - are to be confirmed against the licence before submission; the accompanying runbook itemises every access route and the authors take responsibility for compliance. It follows TRIPOD+AI reporting guidance. All confidence intervals are
person-clustered bootstraps; every absolute-risk metric is reported against two naive references (a
constant at the training prevalence and the oracle base rate); the pipeline was validated end-to-end on
synthetic ground truth before any real-data run.

`docs/SELF_AUDIT.md` accompanies the submission. It lists thirty defects we found in our own analysis
code during this rebuild — a mis-mapped education variable, a last-writer-wins output file that shipped
a six-year accounting under a four-year label, a statistic whose name asserted a unit its value did not
carry, a published column called `oe_ratio` that in fact held predicted-over-observed, a Methods
justification for the primary coverage rule that we tested and withdrew, an event-time assumption
that hid inside a robustness check until we rebuilt that check without it, a fractional-event
re-weighting that we had described as the interval-censored likelihood and is not, and a published primary
model converged to the optimiser's default tolerance rather than to machine precision — what each one
invalidated, and
its status. Every table and figure in the manuscript is now *printed* from the published
CSVs by generator scripts rather than transcribed, because two of these defects were only caught when a
quoted number failed to reproduce.

We report the limitations plainly in the manuscript: interval-censored self-reported events with no
imaging confirmation or stroke subtype, and therefore a *detected*-first-stroke estimand; one panel
(KLoSA) whose main waves carry no vital-status field, so its competing-mortality incidence coincides with
the naive estimator by construction rather than by agreement; interview gaps from 2 to 26 years; no PSU
or stratum identifiers in the harmonised files, so design-weighted inference is bootstrap-based; a
discrete-time hazard whose link, interval grid and within-interval event placement we then varied — and
found that the link changes
almost nothing while the *length specification* changes the apparent calibration of three of the four
panels (the proportional-hazards formulation, log-interval-length as an offset, is the duration-consistent
one and is reported beside the primary arm as Table 8); this check had to be rebuilt once, because our
first version of the one-year grid assigned each stroke to its interval's last piece and so assumed event
timing the panels do not report (defect 19 of the same file);
discrimination that collapses to chance in the oldest age bands (US 80+ AUROC 0.505, 95% CI 0.465–0.546,
where referring everyone beats the model); and four countries, not a global panel. This is a research
estimate of absolute risk, not a validated clinical device.

The manuscript is original, is not under consideration elsewhere, and all named authors approve
submission and declare no competing interests.

Thank you for your consideration.

Sincerely,
Jianhuang Huang (corresponding author)
Department of Neurosurgery, Affiliated Hospital of Putian University, Putian, Fujian, China
teamhuang@sina.com
