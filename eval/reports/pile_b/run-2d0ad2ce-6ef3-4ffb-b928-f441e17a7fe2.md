# Pile B run 2d0ad2ce-6ef3-4ffb-b928-f441e17a7fe2: every case named

Written by `aiact evaluate report 2d0ad2ce-6ef3-4ffb-b928-f441e17a7fe2`: the full report, with the case ids and expected labels its printed text leaves out. The Engine lane denies this folder (V11). Classifications are guidance, not legal advice.

## Run 2d0ad2ce-6ef3-4ffb-b928-f441e17a7fe2

- Benchmark: `commission_b`
- Commit: `6f5fa5024bb48d8e491c2f7642782a865fd0b445`
- Status: completed
- Classifier: `engine`: `openai/gpt-6-luna-20260922` on `azure/eu`
- Cases run: every case of the set
- Second model for refused requests (decision 033): `google/gemini-3.1-flash-lite` on `google-vertex/eu`
- Exclude mode: `all` (the gap run: held-out examples retrievable, never the reported number; decision 012)
- Started: 2026-10-15T01:43:06.258513+00:00
- Model: openai/gpt-6-luna-20260922
- Cost: $1.2650, 7283865 tokens
- Cases: 153 (7 failed)

| Metric | Value | Count |
| --- | ---: | ---: |
| Risk-class accuracy | 71.1% | 108/152 |
| Not assessed (provider refused a check, decision 030) | 0 | |
| Risk-class accuracy, not-assessed cases counted as misses | 71.1% | 108/152 |
| False-low-risk rate | 0.0% | 0/60 |
| Annex point accuracy | 97.9% | 47/48 |
| Role accuracy | 92.8% | 141/152 |
| Legally ambiguous: precision | 0.0% | 0/4 |
| Legally ambiguous: recall | 0.0% | 0/1 |
| Ambiguous answered needs-more-information | 0 | |
| Needs more information: precision | 0.0% | 0/82 |
| Needs more information: recall | n/a | 0/0 |
| Downgrade rate (soft wording) | n/a | 0/0 |
| Basis accuracy (Commission cases) | 90.7% | 127/140 |
| Flip variant asked or flagged | 0.0% | 0/6 |
| Label citation cited (any of) | 58.2% | 85/146 |
| Needs a description: asked (thin cases) | n/a | 0/0 |
| Needs a description: asked wrongly (other cases) | 0.0% | 0/146 |
| Consistency | n/a | 0/0 |
| Citation existence (at run time) | 100.0% | 146/146 |
| appliedAI disagreement review | 0 | |
| Academic out-of-scope review | 0 | |

Contaminated cases, flagged by docs/decisions/016-contaminated-pile-b-cases.md: cb-031-incident-footage-timeline (from hr-ex-031), cb-269-asylum-decision-quality-review (from hr-ex-269)

| Metric | Value | Count |
| --- | ---: | ---: |
| Risk-class accuracy without the contaminated cases | 70.7% | 106/150 |

### Provider refusals (decisions 029, 030, 033)

- Second model for refused requests: `google/gemini-3.1-flash-lite`
- Refused by the engine model: 4 of 146 (2.7%): cb-030-seized-media-presort, cb-044-cigarette-machine-age-camera, cb-091-neurodivergent-learning-companion, cb-210-abuse-material-triage-sorting
- Answered by the second model: 4 of 146 (2.7%): cb-030-seized-media-presort, cb-044-cigarette-machine-age-camera, cb-091-neurodivergent-learning-companion, cb-210-abuse-material-triage-sorting
- Refused by both (not assessed): 0 of 146 (0.0%)
- Second model's refusal rate: 0 of 4 (0.0%)
- Risk-class accuracy without the cases the second model answered: 71.6% (106/148)

Calls by the model that served them: `openai/gpt-6-luna` 886, `qwen/qwen3-embedding-8b` 629, `google/gemini-3.1-flash-lite` 4

### Failures by step

- **scope** (2): cb-100-school-leaver-pathway-trends (expected minimal_risk, got out_of_scope (decided)); cb-119-job-ad-wording-check (expected minimal_risk, got out_of_scope (decided))
- **prohibited** (12): cb-041-airport-walkway-passenger-categories (expected high_risk, got prohibited (decided)); cb-046-bodycam-agitation-alert (expected high_risk, got prohibited (needs_more_information)); cb-104-online-exam-cheating-patterns (expected high_risk, got prohibited (needs_more_information)); cb-111-agency-profile-sourcing (expected high_risk, got prohibited (needs_more_information)); cb-116-social-job-ad-audiences (expected high_risk, got prohibited (needs_more_information)); cb-130-performance-based-shift-allocation (expected high_risk, got prohibited (legally_ambiguous)); cb-144-housing-benefit-risk-score (expected high_risk, got prohibited (needs_more_information)); cb-161-bureau-score-for-landlords (expected high_risk, got prohibited (needs_more_information)); cb-217-prison-reoffending-forecast (expected high_risk, got prohibited (legally_ambiguous)); cb-218-sentencing-recidivism-score (expected high_risk, got prohibited (needs_more_information)); cb-222-missing-child-suspect-filter (expected high_risk, got prohibited (needs_more_information)); cb-248-overstay-indicator-flags (expected high_risk, got prohibited (needs_more_information))
- **high_risk** (8): cb-042-border-lane-age-sex-estimates (expected limited_risk, got high_risk (decided)); cb-091-neurodivergent-learning-companion (expected minimal_risk, got high_risk (needs_more_information)); cb-108-proctor-second-opinion (expected minimal_risk, got high_risk (decided)); cb-136-voluntary-course-progress-feedback (expected minimal_risk, got high_risk (legally_ambiguous)); cb-189-incident-site-casualty-map (expected minimal_risk, got high_risk (needs_more_information)); cb-191-partner-violence-risk-court (Annex point annex:III:8:a); cb-233-station-cctv-unusual-movement (expected minimal_risk, got high_risk (needs_more_information)); cb-264-visa-fee-routing (expected minimal_risk, got high_risk (decided))
- **transparency** (16): cb-020-stadium-gate-ban-list (expected minimal_risk, got limited_risk (decided)); cb-030-seized-media-presort (expected minimal_risk, got limited_risk (needs_more_information)); cb-054-decoy-server-attack-learning (expected minimal_risk, got limited_risk (decided)); cb-077-regional-demand-forecast (expected minimal_risk, got limited_risk (needs_more_information)); cb-086-admissions-round-pattern-audit (expected minimal_risk, got limited_risk (needs_more_information)); cb-093-teacher-exam-proofreader (expected minimal_risk, got limited_risk (decided)); cb-102-tutor-advice-method-review (expected minimal_risk, got limited_risk (needs_more_information)); cb-141-promotion-report-polishing (expected minimal_risk, got limited_risk (legally_ambiguous)); cb-156-caseworker-fact-lookup (expected minimal_risk, got limited_risk (needs_more_information)); cb-183-responder-exercise-simulator (expected minimal_risk, got limited_risk (needs_more_information)); cb-188-flood-fire-prepositioning-brief (expected minimal_risk, got limited_risk (decided)); cb-199-officer-fatigue-wearables (expected minimal_risk, got limited_risk (needs_more_information)); cb-206-device-data-recovery (expected minimal_risk, got limited_risk (needs_more_information)); cb-207-crime-scene-3d-model (expected minimal_risk, got limited_risk (needs_more_information)); cb-228-police-back-office-automation (expected minimal_risk, got limited_risk (needs_more_information)); cb-290-judgment-redaction-and-fee-check (expected minimal_risk, got limited_risk (needs_more_information))
- **no result (the classifier failed)** (7): cb-007-lift-door-controller (no result); cb-039-burglary-series-image-links (no result); cb-051-dashcam-drowsiness-warning (no result); cb-125-bar-membership-check (no result); cb-214-financial-document-tagging (no result); cb-262-visa-file-completeness-sorting (no result); cb-275-sea-rescue-person-detection (no result)

### Model-written texts

- Longest fact or question: 288 characters (cap 600)
- Facts: 914 over 146 results
- Follow-up questions: 1021 over 146 results

Judged metrics: not judged yet (`aiact evaluate judged <run_id>`).

- No invented content: checked by code (P8a's `check_nothing_invented` on each document the results call for), not judged: 100.0%, 183/183 documents
