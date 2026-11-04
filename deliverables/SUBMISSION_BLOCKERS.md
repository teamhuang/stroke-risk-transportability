# Submission blockers and open author decisions

Companion to `docs/SELF_AUDIT.md`. That file records what is wrong with the **analysis**; this file
records what is missing from the **submission**. Nothing here is a scientific defect. Every item is
either a fact only a human can supply, a licence or ethics condition that has not been read from an
authoritative source, or a decision whose cost is a change to published numbers.

The manuscript is not submittable until every item marked BLOCKING is closed. `## Ethics`,
`Author contributions`, `Competing interests` and `Funding` in `deliverables/manuscript.md` currently
contain placeholder prose, and placeholders must not survive into a submission.

---

## A. BLOCKING — cannot be resolved by any further computation

### A1. Data-use authorisations (two panels, one attestation each)

| Panel | Status | What must happen |
|---|---|---|
| RAND HRS 1992–2022 v1 (`randhrs1992_2022v1.sas7bdat` + Tracker) | **Attested, not verified.** Supplied by the user; the licence terms could not be read from this machine (`SELF_AUDIT.md` O22). | A person must confirm the terms under which this file is held and whether an analysis of this kind, and any derived table or code release, is permitted by RAND / the HRS protocol. If the file arrived through a route the user is not entitled to use, the US arm must be dropped and the whole incident design re-run on three panels. |
| MHAS (harmonised release D) | **Attested, not verified**, on the user's statement "确认有授权，我来处理". Recorded, not independently checked. | The same confirmation, from the licence text rather than from memory. |
| CHARLS, KLoSA (harmonised, Gateway to Global Aging Data) | Used under the standard gateway data-user agreement as understood by the user. | Re-read the current agreement for redistribution limits on **derived** datasets, since the package ships reconstructed person-interval tables. |

Withdrawal path, agreed in advance and tested once: deleting `corrected/std_HRS.csv`,
`incident/hrs_times.csv`, `incident/personperiod_HRS.csv`,
`reports/hrs_{metadata_probe,reshape_diagnostics,weight_zero_probe}.json`, dropping HRS from
`incident_personperiod.SPECS`, re-keying `incident_horizon_counts.json` and re-running every
downstream script produces a three-panel study; `std_MHAS.csv` behaves the same way for Mexico. This
is recorded so that a withdrawn attestation costs a rerun rather than a scramble.

### A2. Ethics approvals — four per-cohort [AUTHOR-SPECIFIC] fields plus the institutional exemption determination

`## Ethics` currently asserts that each cohort "was approved by its national ethical review bodies"
and that this is a secondary analysis of de-identified releases. The first half is a claim about four
studies conducted by four institutions and the second is a claim about this analysis. Both must come
from documents, not from inference:

- HRS: the institutional review approvals recorded by the University of Michigan / the survey
  contractor for the years actually used, and RAND's position on secondary use.
- CHARLS: the ethical approval statement in the CHARLS protocol/review papers and the Peking
  University Human Ethics Committee reference it carries.
- KLoSA: the Korean Institutional Review Board approval associated with the KLoSA waves used.
- MHAS: the University of Manchester / UCLA and Mexican partner IRB statements carried by MHAS
  documentation.
- **This analysis**: whether the authors' institution requires (or has granted) a waiver or an approval
  for secondary analysis of de-identified public files. If none was sought and none was required, say
  that in the institution's own words rather than writing "not applicable".

Do not invent, estimate or back-fill an approval number. `SELF_AUDIT.md` treats an unverified ethics
line as a blocking item for exactly this reason.

### A3. Authorship, CRediT initials and the AI-tool statement (structured [AUTHOR-SPECIFIC: initials] placeholders now present)

- The author list, affiliations and ORCIDs are not in this repository and cannot be inferred.
- `Author contributions` must be CRediT-classified with real names, and every named author must have
  seen and approved the submitted version. The analysis in this repo was produced with an automated
  agent (see `deliverables/README_reproducibility.md`); the agent cannot be an author and cannot carry
  accountability, so the statement must name which human verified which outputs. This is not a
  formality here: 23 defects in the analysis were found by checking machine-produced numbers against
  each other, and a reviewer will ask who did the checking.
- Nature Portfolio / npj Digital Medicine require a generative-AI disclosure in the Methods or
  Acknowledgements stating the tool, the version, and what it was and was not used for. Copy the
  wording from the journal's current editorial policy at submission time — it moves — and do not
  describe AI use as "software assistance" if it wrote analysis code.
- `Funding`: grant numbers or an explicit "no specific funding" statement, from the authors.
- `Competing interests`: from the authors; the current text is a placeholder.

### A4. The code package a reviewer can run

`deliverables/README_reproducibility.md` lists the run order and every script, and
`intl/publish_incident_tables.py` plus the `analysis/output/make_*_rows.py` printers mean no
manuscript number is hand-transcribed. What is missing for review:

- a dependency lock (Python version and `requirements.txt`/`environment.yml`) — the pipeline depends on
  sklearn, statsmodels, scipy, pandas, `pyreadstat`;
- one command that runs the whole chain from the raw releases, which cannot be published in the
  repository because the raw cohorts are gated (state this, and ship the intermediate
  `personperiod_pooled.csv` schema instead — see `deliverables/data_dictionary.md`);
- the superseded outputs kept as they are kept now (`results/superseded/`, with the README that says why
  each file is dead), because an unlabeled stale table one glob away is how defect 19 happened.

---

## B. Author decisions that change published numbers

### B1. Refit the primary model at a fixed tight tolerance, or keep the disclosure (defect 21)

The published logistic model is `LogisticRegression(C=1.0)` at sklearn's default `tol=1e-4` and stops
after ~10 iterations. Solved to `tol=1e-10`, US predicted/observed is 1.1698 where Table 8 says 1.1606,
and US AUROC 0.72664 against 0.72628. Every rounded claim survives; the third decimal does not. The
pre-submission review's position is that the final manuscript should be regenerated from a converged fit
rather than carry a tolerance footnote. That is a defensible editorial judgement with a cost: it moves
roughly 40 published rows at their third decimal and requires re-running every downstream arm, figure
and table of this paper. The primary competing-risks arm of Table 9 already converges at
`ftol=1e-14, gtol=1e-10` (20–25 L-BFGS-B iterations, recorded per fit), so the inconsistency is between
arms, and the reviewers will notice it. **Decide before submission, not after the first review.**

### B2. Whether Table 9's arm becomes the headline model

The absolute-risk analysis in the Results is now the duration-consistent, competing-mortality arm
(`intl/incident_cr_primary.py`, V4), and the nine-classifier transport comparison keeps the published
logistic hazard because a tree ensemble cannot be given a log-exposure offset. That split is written into
the manuscript. What has *not* been done is carrying the classifier comparison onto the corrected
estimand: if a reviewer asks which algorithm transfers best under V4, the answer is not computed.

### B3. Deferred analyses the pre-submission review asked for, with the reason each is deferred

| Item | Status | Reason |
|---|---|---|
| P1-5 core-variable model + variable-definition ablation | **DONE 2026-11-03.** | `intl/incident_cr_definition.py` refits both cause-specific hazards, both compositions and the local repair from scratch on three nested feature tiers, and the answer strengthens the paper rather than weakening it: Mexico's four-year predicted/observed ratio is 3.004 (19 columns, the published arm) -> 3.171 (17, cardiac and alcohol removed because their *questions* differ) -> 3.106 (11, hypertension and marital removed too because their availability differs), with every interval starting above 2.7, and the repair gain does not shrink (+0.00365 -> +0.00454 -> +0.00430). The tier named `common` is the published arm refitted through this script's own code path and reproduces all eight frozen cells to within 1e-6, so the three rows are comparable by construction. Published as Table 11 with its own printer (`make_definition_rows.py`) and a per-panel missingness table that justifies each tier by measured values rather than by prose. What the arm does *not* claim: discrimination falls as columns leave (Mexico 0.610 -> 0.571), so the strict tier is a stress test, not a preferred model. |
| P1-4 clinical threshold rationale | **Partly done, still weak.** | 5% four-year risk is used because it is the mid-range of the decision curves and sits above the panels' own observed incidence, and the paper says the curves are hypothetical. It is not a validated action threshold, and no stroke-prevention or primary-care contributor has reviewed it. An external opinion, or an explicit statement that the threshold is illustrative, is needed before a reviewer accepts the DCA panels as clinical content. |
| P1-6 age subgroups in the main text | **DONE 2026-11-03.** | Promoted to main-text Table 12 with a dedicated Results subsection, printed by `analysis/output/make_subgroup_rows.py`, which also re-checks the eight age-band numbers quoted in the Limitations (six match; two sat on the rounding boundary of the 4-decimal published table and now carry the published digits - see `docs/SELF_AUDIT.md` defect 26). The subsection reads the previously unopened `pred_over_obs_offset` column, which quantifies what one panel-wide intercept does inside a country: Mexico's 20-59 band moves from 2.383 to 0.728. |
| P1-7 positioning against existing stroke risk scores | **Not done.** | Requires a literature pass the authors should own (which scores, which populations, which variables are even available in these four panels). The manuscript currently states that this study does not claim to beat existing tools; that sentence needs citations behind it. |
| P1-1 flexible calibration curves | **DONE 2026-11-03.** | `intl/incident_calibration_smooth.py` draws the continuous object the decile table approximates: a spline calibration fit of observed risk on the frozen linear predictor with a 200-draw person-clustered bootstrap band, for the frozen and the 5%-intercept-repaired model, one panel per facet (Figure 9b). It sharpens the shape-vs-level point: Mexico's high-risk tail (predicted 0.13 -> observed 0.065, band 0.014-0.178) is over-predicted roughly twofold and the intercept moves the curve without bending the tail onto the diagonal. |
| P0-1 competing-risks composition audit | **DONE 2026-11-03.** | `intl/incident_cr_exact.py` proves the reviewer's survival-factor charge wrong (`(1-p_s)(1-p_d)=exp(-(lambda_s+lambda_d)D)` to 1e-16) but concedes a real, different exclusivity error in the step event factor (`1+p_s*p_d>1`); `intl/incident_cr_joint.py` fits the principled joint multinomial likelihood (gradient self-tested to 1.5e-9, interval probabilities conserved to 2e-16, ladder flat at 1.000000); `intl/incident_cr_simulation.py` shows with a known truth why neither marginal-fit arm is unbiased. Across V4/V5/joint Mexico spans 2.93-3.00 and every panel moves by <=3.4%, so the headline is invariant (Table 9b). |
| Age-aware recalibration (was declared out of scope) | **DONE 2026-11-03.** | `intl/incident_age_recalibration.py` fits population-intercept / per-band / intercept+age / shrunk-band updates on local data and scores them on independent persons. Finding (Table 13): the population intercept fixes the panel average but leaves a ~2.2-fold age-band error; naive per-band intercepts are unstable; the smooth intercept+age update cuts the worst-band error to ~1.2-fold with the lowest net-benefit variance, and none of it lifts Mexico's net benefit above treat-none. |
| Round 9: honest allocation relabel + structural trim | **DONE 2026-11-04.** | Table 19 relabelled as a uniform-within-interval allocation (distribution assumption stated) and a third, joint-model-based conditional (truncated-exponential) allocation added (`incident_cr_alloc_variants.py`): China 0.80 under midpoint/uniform/model-based, Mexico the only move 2.98->2.18->2.14, so 'only Mexico' is robust to the allocation rule; abstract 'China barely moved' scoped to the allocation check; 'flagged Mexico alone' -> 'only country regularly selected'; clinical value framed as re-evaluate-before-deployment (8/40 splits, <1 net person); SHAP + cross-sectional/V4 physically moved to `Supplementary_technical.md` (Notes S-C/S-D); residual dev-history recast; front-matter author/affiliation/corresponding skeleton added; audit_consistency_round9.py 64 PASS. |
| Round 8: post-review reconciliation | **DONE 2026-11-04.** | Competing-risk identity corrected (p_s - alpha_s = P(death-first in step); total double-count p_s*p_d = (p_s-alpha_s)+(p_d-alpha_d)) in text + scripts; 'fully nonparametric' overclaim renamed; Finding A resolved - pooled-hazard MLE China 0.40-0.47 (Table 18, shape-robust) is an estimand re-specification, estimand-matched IC leaves China invariant and flags only Mexico (Tables 19); clinical baseline (Table 20); 2-D unreported-stroke grid (Table S6); age gate unified to >=20; Results restructured to six named subsections; Methods given ### subheadings; dev-history + reference verification notes stripped; audit_consistency_round8.py 127 PASS. |
| Round 7: submission-hardening pass | **DONE 2026-11-04.** | Seventh-round P0/P1 closed against disk. **P0-1** cohort flow reconciles: the 2-person gap was real (2 MHAS adults never gave a determinable dated baseline stroke answer, removed before the risk set), now `107,898 − 2 − 3,775 = 104,121` in prose, Table 1 (new "Baseline stroke status not determinable" row), Methods and Figure 10; `incident_sample_flow.py` emits a `no_determinable_stroke` column and every node reconciles. **P0-6** the selective-updating policy is re-run on the **joint** model (`incident_update_policy_joint.py`, 200 reps) and replaces logistic Table 10 (MX 70% trigger / +0.00261 paired at 2%, 100% / +0.00370 at 5%; CN/KR/US barely fire); the honest change is that promoting the estimator *removed* the logistic arm's "rule misses Korea" failure mode (Korea's joint P/O is already 1.15, so recalibration costs NB and the rule correctly declines). **P0-3** interval-censored midpoint-free observed risk (`incident_cr_interval_eval.py`) → Table 15: MX P/O 2.98 → **2.10** (bracket 1.22/2.94), so the headline is stated as the ascertained-estimand value, not measurement-free. **P0-2** outcome-observation mapping (Table 16) + synthetic unreported-fatal-stroke sweep (`incident_cr_unreported_stroke_sim.py`) → Table S6: uniform under-ascertainment barely moves P/O, differential could take MX toward ~1.0. **P0-4** KLoSA reworded to "incomplete mortality ascertainment limits identification of the competing-risk estimand" (no lower-bound/bias-direction conflict). **P0-5** consolidated weight-disclosure Table 17. **P0-7** "prespecified" tiered to analysis-plan-specified, no prospective-registration claim. **P1** events-based sizing, "every evaluated split" (not 40 independent validations), predefined-candidate framing, per-band detail. **Format**: Funding folded into Acknowledgments; Limitations label folded; **References expanded 5 → 15**, every entry resolved against EuropePMC (PMID/DOI/title/authors/pages) and cited in first-appearance order. **TRIPOD+AI item-by-item checklist** added as `deliverables/TRIPODAI_checklist.md`. Gates: `analysis/output/audit_consistency_round7.py` (86 assertions, PASS) alongside `audit_consistency_round6.py` (53, PASS). |
| Round 6: joint model promoted to the single PRIMARY arm + Results 15→6 | **DONE 2026-11-03.** | Sixth-round P0: stop mixing old-V4 and new-joint headline numbers. The joint multinomial estimator is now declared primary everywhere (abstract, Results, Discussion, Table 9b with Joint as the primary column, age subgroups, calibration curves, decision analysis), the V4/Aalen–Johansen composition relabelled the separately-fitted sensitivity arm, and `intl/incident_cr_joint_primary.py` regenerates every joint sub-analysis (age bands, deciles, smooth curve, five age-aware strategies, DCA) from the shared per-person joint CIF, cross-reconciled to Mexico panel P/O 2.975. Editorial: Results condensed from 15 `###` to 6 by demoting detail blocks to `####` in place (bodies not moved, so cross-references survive; a full physical reorder + table renumber was judged a bigger integrity risk than its benefit); the section-ordering meta-paragraph and the round-by-round audit narration removed/restated neutrally; the composition derivation marked for Supplementary Methods; the Table 7 "positive at 5% or more" claim corrected (repaired NB dips negative again at 10%); a seven-element primary-estimand definition added to Methods; outcome relabelled survey-ascertained; SHAP scope note added (explains the classifier arm on log-odds, not the joint CIF); a three-level deployability Table 14 added; abstract retuned to 131 words. Gate: `analysis/output/audit_consistency_round6.py` (53 assertions, PASS). |

---

## C. Journal compliance, recorded with its verification state

| Requirement | What is in the manuscript | Verified from |
|---|---|---|
| Article abstract: unstructured, ≤150 words | Unstructured, now **131 words** counted as whitespace-separated tokens containing at least one alphanumeric character (the sixth-round retune put it in the 130-140 band the reviewer recommended, with headroom under 150, and re-cited the joint-model headline: Mexico 0.0283 vs 0.0095, 2.98-fold, 8/40 treat-none). The count is printed by the snippet in `deliverables/README_reproducibility.md` and asserted `<= 150` and in-window by `analysis/output/audit_consistency_round6.py`. | The word count is machine-checked; the **150-word ceiling itself is NOT verified** — nature.com returned HTTP 303 to every fetch attempt from this machine, so 150 comes from the reviewer's transcription of the live page and third-party summaries. A human must still read the live submission guidelines. |
| Data availability statement | Present, with the gated-access routes named per cohort. | Journal requirement is known; the wording must be re-checked against the current policy page at submission. |
| Code availability statement | Present, naming every script including the fifth-round additions, the sixth-round joint-primary arm (`incident_cr_joint_primary.py`, printer `make_joint_primary_rows.py`, audit `audit_consistency_round6.py`) and the round-7 additions (`incident_update_policy_joint.py`, `incident_cr_interval_eval.py`, `incident_cr_unreported_stroke_sim.py`, printer `make_round7_rows.py`, audit `audit_consistency_round7.py`). | Same caveat. |
| TRIPOD+AI / PROBAST+AI | **Item-by-item checklist FILLED 2026-11-04** as `deliverables/TRIPODAI_checklist.md`, mapped to this manuscript's sections/tables/figures. Honest remaining gaps are flagged there, not hidden: funding/author-contributions/ethics items need author input; outcome/predictor blinding items are NA (self-reported survey outcome). | The checklist is aligned to the TRIPOD+AI statement (ref [5]); a human should confirm the mapping against the released PDF checklist. |
| References / literature positioning | **Expanded 5 → 15 (2026-11-04)** across the six under-covered areas (stroke burden, prediction-model validation & performance, model updating, competing-risk methodology, self-report stroke validity incl. a Korea-specific study, decision-curve net benefit, TRIPOD/TRIPOD+AI). Every entry resolved against its EuropePMC record (PMID + DOI + title + authors + journal + volume/pages); none written from memory; cited in-text in first-appearance order [1]-[15], machine-checked by `audit_consistency_round7.py`. | Journal citation *style* (numbering, author-count truncation) still needs a human pass against the live author guidelines. |
| Reporting of AI assistance in code development | Disclosed in the reproducibility README and in the Ethics/Contributions placeholders. | Must be aligned with the journal's policy text at submission. |

---

## D. What is *not* a blocker, stated so it is not re-litigated

- The MHAS/RAND HRS **harmonised** variable mappings, the KLoSA reshape corrections, the BMI plausibility
  filter and the interview-status coding rules are all machine-checked and documented; they were the
  subject of earlier rounds and do not need re-verification.
- The interval-censored likelihood, the event-time allocation arms, the competing-risks composition and
  the adaptation-independence audit are complete and published under dated filenames in
  `results/tables/`, with their gates and disclosures in
  `results/tables/incident_cr_primary_diagnostics_2026-11-03.json` and
  `incident_adaptation_leakage_audit_2026-11-03.csv`.
- Korea's absent vital-status field is a property of the released KLoSA wave files, not of the pipeline;
  it is disclosed wherever it bites, including inside the primary arm's own output. The exit-module
  files that would fix it are not on disk and are not obtainable from here.
- The four-country design remains *n* = 4 for any statement about "how models travel in general". Every
  transportability statistic is reported per country, and the pooled averages are labelled descriptive.

---

## E. Suggested order of closure

1. A1 + A2 — licences and ethics, by the authors, from documents. Nothing else matters if these fail.
2. B1 — the convergence decision, before any further table work, because it changes which numbers are
   final.
3. ~~P1-5 (B3) — the definition-ablation arm~~ **done 2026-11-03** (Table 11: Mexico 3.004 → 3.171 →
   3.106 across feature tiers, so the level error is risk and not measurement), together with P1-6
   (Table 12) and P0/P1 items B3's other entries; what remains of B3 is P1-4 (external threshold opinion)
   and P1-7 (literature positioning).
4. C — the live journal rules, the checklists, and the abstract trim.
5. A3 + A4 — authorship text, AI disclosure, environment lock.
6. Only then the cover letter (`deliverables/cover_letter.md`), which currently describes the audit
   trail in first-person-plural terms that need to become the authors' own.


## Z. Complete list of remaining author-only items (34 [AUTHOR-SPECIFIC] placeholders in manuscript.md)

These are facts the analysis cannot produce and must NEVER be invented by it. Each is a required author action:

- Front matter: **author list, order, numbered affiliations and corresponding authors SUPPLIED by the authors on
  2026-11-04** (Jianhuang Huang¹ # *, Yangyang Lin² #, Qixiu Wang³ #, Jianning Chen¹ *; Affiliated Hospital of Putian
  University / Chinese People's Armed Police Force Fujian Provincial Corps Hospital / Affiliated Hospital of Liaoning
  University of Traditional Chinese Medicine; correspondence Jianhuang Huang teamhuang@sina.com and Jianning Chen
  cjn2006@sohu.com). **Remaining front-matter gap: ORCIDs** — not supplied, still a placeholder.
- Ethics: the submitting institution's named exemption/approval determination (the study is a secondary analysis of
  de-identified public releases, but the exempt/not-exempt call is the authors' institution's to make, not inferable
  from de-identification), and, per cohort (HRS/CHARLS/KLoSA/MHAS), the parent-study ethics body, protocol/approval
  identifier, consent procedure and secondary-use authorisation, read from each study's own documentation.
- Data-use terms: confirm each cohort's licence permits automated/AI-assisted processing and describes this analysis
  as used; if a cohort's terms prohibit it, that cohort must be removed from the four-country comparison (KLoSA needs
  registration + a study creation code; MHAS/ELES terms must be read individually).
- Code availability: the release repository URL, version tag and archived version DOI (e.g. Zenodo) for the versioned
  snapshot; nothing here should be filled with a placeholder DOI.
- Author contributions: CRediT roles assigned by author initials; approval of the final version; accountability.
- Competing interests and funding: all-author confirmation; declare any grant numbers and any data-use restriction
  limiting redistribution of harmonised files.

Until these are supplied and every author signs off, the file is a complete, audited scientific draft but NOT an
uploadable submission (journal policy: authorship, ethics and data/code access statements must be real and complete).

### Round-10 closure note (2026-11-04)

The tenth-round "final comprehensive review" (verdict: Major revision before submission) was closed against disk,
not by assertion:

- **Model identity unified (P0-1, P0-4).** The joint multinomial competing-risks model is now the primary estimator
  everywhere it is formally reported: the appendix Table 3 is the joint model's four-country calibration /
  discrimination / decision-utility results, Table 4 is the joint-model local update, the Methods probability
  construction leads with the joint likelihood and its exclusive first-event probability α_s,j (the separately-fitted
  two-hazard Aalen-Johansen composition is demoted to a labelled sensitivity arm), and the main Figures 1-6 are the
  joint model's own output. The classifier grid and the logistic update grid moved to Supplementary Tables S7/S8; the
  old logistic / XGBoost adaptation, fitting-scale, ranking-vs-level, complexity, class-weight, specification-grid and
  logistic-calibration figures moved to Supplementary Figures S1-S8, each labelled with the model it actually plots.
- **Partial-strict contradiction closed with a real refit (P0-2).** The false "permissive is the only frame retaining
  competing death" claim was deleted from both Methods and Results (partial-strict and permissive both retain all
  23,347 death intervals; only full-strict deletes them). A genuine joint-model partial-strict refit was run
  (`incident_cr_joint_strict_refit.py`, 40 splits) and added as Table 7b: Mexico stays the only >2 over-prediction
  (2.54) and its repair beats frozen in 100% of splits, so the primary estimator's headline survives stricter coverage.
- **Supplementary Information completed as a standalone booklet (P0-3).** `Supplementary_technical.md` is now a full
  SI: Supplementary Methods S-A (known-truth competing-risks simulation, real numbers from
  `incident_cr_simulation.csv`), S-B (exclusivity identity + probability-conservation ladder), S-C (interval-censored
  likelihood + the three observed-risk allocation rules); Notes S-D (cross-sectional arm) and S-E (SHAP); and all
  Supplementary Tables S1-S8 and Figures S1-S8 that the main text cites. The main article keeps only pointers.
- **Reference-4 corrected (P1-1).** The TRIPOD citation was fixed to Ann Intern Med. 2015;162(1):55-63,
  doi:10.7326/M14-0697, PMID 25560714, verified against EuropePMC (PMID 25560714) before writing.
- **Other P1/P2.** Korea now carries a single unified predict-side / observe-side footnote; the China pooled-hazard
  reading is reworded as "not reproduced under estimand-matched allocation; different observation/censoring
  structures" rather than an "artefact"; split ranges are labelled "2.5th-97.5th percentile range across N splits"
  (not CIs); the abstract opens with the research question/design and closes with a pre-deployment-validation
  statement; the Methods heading drops the pre-registration-sounding "declared before any model was fitted".

**Author-only items and current count.** The real authors subsequently supplied the author list, order, numbered
affiliations and corresponding authors, so the **[AUTHOR-SPECIFIC] count dropped from 36 to 34** (only ORCIDs remain
among the front-matter items). The remaining 34 - ethics determinations, per-cohort data-use/AI-assisted-processing
licence terms, CRediT initials, funding and the code-release DOI - must be supplied by the real authors and never
auto-filled. In particular the **MHAS AI-assisted-processing attestation** (currently recorded as the data
holder's statement, not an independently verified licence reading) and the **KLoSA registration / licence terms**
require the authors to read the actual licence text and retain proof; if any cohort's terms prohibit automated
processing, that cohort must be dropped and the design re-run on the remaining panels.
