# Pile B run 31baa80c-f3bc-4eaf-93d0-4280b5fa14e7: every case named

Written by `aiact evaluate report 31baa80c-f3bc-4eaf-93d0-4280b5fa14e7`: the full report, with the case ids and expected labels its printed text leaves out. The Engine lane denies this folder (V11). Classifications are guidance, not legal advice.

## Run 31baa80c-f3bc-4eaf-93d0-4280b5fa14e7

- Benchmark: `commission_b`
- Commit: `6f5fa5024bb48d8e491c2f7642782a865fd0b445`
- Status: completed
- Classifier: `engine`: `openai/gpt-6-luna-20260922` on `azure/eu`
- Cases run: every case of the set
- Second model for refused requests (decision 033): `google/gemini-3.1-flash-lite` on `google-vertex/eu`
- Exclude mode: `heldout` (held-out examples kept out of retrieval: the reported number)
- Started: 2026-10-15T00:45:13.646378+00:00
- Model: openai/gpt-6-luna-20260922
- Cost: $1.2788, 7376463 tokens
- Cases: 153 (6 failed)

| Metric | Value | Count |
| --- | ---: | ---: |
| Risk-class accuracy | 65.8% | 100/152 |
| Not assessed (provider refused a check, decision 030) | 0 | |
| Risk-class accuracy, not-assessed cases counted as misses | 65.8% | 100/152 |
| False-low-risk rate | 0.0% | 0/56 |
| Annex point accuracy | 93.3% | 42/45 |
| Role accuracy | 92.1% | 140/152 |
| Legally ambiguous: precision | 0.0% | 0/6 |
| Legally ambiguous: recall | n/a | 0/0 |
| Ambiguous answered needs-more-information | 1 | |
| Needs more information: precision | 0.0% | 0/84 |
| Needs more information: recall | n/a | 0/0 |
| Downgrade rate (soft wording) | n/a | 0/0 |
| Basis accuracy (Commission cases) | 79.4% | 112/141 |
| Flip variant asked or flagged | 0.0% | 0/6 |
| Label citation cited (any of) | 57.1% | 84/147 |
| Needs a description: asked (thin cases) | n/a | 0/0 |
| Needs a description: asked wrongly (other cases) | 0.0% | 0/147 |
| Consistency | n/a | 0/0 |
| Citation existence (at run time) | 100.0% | 147/147 |
| appliedAI disagreement review | 0 | |
| Academic out-of-scope review | 0 | |

Contaminated cases, flagged by docs/decisions/016-contaminated-pile-b-cases.md: cb-031-incident-footage-timeline (from hr-ex-031), cb-269-asylum-decision-quality-review (from hr-ex-269)

| Metric | Value | Count |
| --- | ---: | ---: |
| Risk-class accuracy without the contaminated cases | 65.3% | 98/150 |

### Provider refusals (decisions 029, 030, 033)

- Second model for refused requests: `google/gemini-3.1-flash-lite`
- Refused by the engine model: 3 of 147 (2.0%): cb-080-city-school-place-allocation, cb-098-special-needs-placement-classifier, cb-210-abuse-material-triage-sorting
- Answered by the second model: 3 of 147 (2.0%): cb-080-city-school-place-allocation, cb-098-special-needs-placement-classifier, cb-210-abuse-material-triage-sorting
- Refused by both (not assessed): 0 of 147 (0.0%)
- Second model's refusal rate: 0 of 3 (0.0%)
- Risk-class accuracy without the cases the second model answered: 65.1% (97/149)

Calls by the model that served them: `openai/gpt-6-luna` 899, `qwen/qwen3-embedding-8b` 634, `google/gemini-3.1-flash-lite` 3

### Failures by step

- **scope** (4): cb-100-school-leaver-pathway-trends (expected minimal_risk, got out_of_scope (decided)); cb-119-job-ad-wording-check (expected minimal_risk, got out_of_scope (decided)); cb-262-visa-file-completeness-sorting (expected minimal_risk, got out_of_scope (decided)); cb-303-polling-institute-dashboards (expected minimal_risk, got out_of_scope (decided))
- **prohibited** (13): cb-041-airport-walkway-passenger-categories (expected high_risk, got prohibited (legally_ambiguous)); cb-046-bodycam-agitation-alert (expected high_risk, got prohibited (needs_more_information)); cb-091-neurodivergent-learning-companion (expected minimal_risk, got prohibited (needs_more_information)); cb-103-certification-exam-proctoring (expected high_risk, got prohibited (needs_more_information)); cb-104-online-exam-cheating-patterns (expected high_risk, got prohibited (needs_more_information)); cb-108-proctor-second-opinion (expected minimal_risk, got prohibited (needs_more_information)); cb-115-apprentice-application-screening (expected high_risk, got prohibited (needs_more_information)); cb-116-social-job-ad-audiences (expected high_risk, got prohibited (needs_more_information)); cb-130-performance-based-shift-allocation (expected high_risk, got prohibited (needs_more_information)); cb-144-housing-benefit-risk-score (expected high_risk, got prohibited (needs_more_information)); cb-148-sickness-claim-fraud-flags (expected high_risk, got prohibited (needs_more_information)); cb-161-bureau-score-for-landlords (expected high_risk, got prohibited (needs_more_information)); cb-217-prison-reoffending-forecast (expected high_risk, got prohibited (needs_more_information))
- **high_risk** (16): cb-020-stadium-gate-ban-list (expected minimal_risk, got high_risk (legally_ambiguous)); cb-042-border-lane-age-sex-estimates (expected limited_risk, got high_risk (needs_more_information)); cb-069-heating-plant-patrol-robot (expected minimal_risk, got high_risk (needs_more_information)); cb-099-next-year-course-suggestions (expected minimal_risk, got high_risk (decided)); cb-125-bar-membership-check (expected minimal_risk, got high_risk (decided)); cb-136-voluntary-course-progress-feedback (expected minimal_risk, got high_risk (needs_more_information)); cb-164-loan-form-inline-help (expected minimal_risk, got high_risk (decided)); cb-168-securities-lending-limit (expected minimal_risk, got high_risk (decided)); cb-185-emergency-line-traffic-monitor (expected minimal_risk, got high_risk (needs_more_information)); cb-191-partner-violence-risk-court (Annex point annex:III:8:a); cb-198-interview-room-credibility-cues (Annex point annex:III:6:c); cb-199-officer-fatigue-wearables (expected minimal_risk, got high_risk (needs_more_information)); cb-218-sentencing-recidivism-score (Annex point annex:III:8:a); cb-232-customs-object-detection (expected minimal_risk, got high_risk (needs_more_information)); cb-233-station-cctv-unusual-movement (expected minimal_risk, got high_risk (legally_ambiguous)); cb-275-sea-rescue-person-detection (expected minimal_risk, got high_risk (decided))
- **transparency** (16): cb-030-seized-media-presort (expected minimal_risk, got limited_risk (needs_more_information)); cb-051-dashcam-drowsiness-warning (expected minimal_risk, got limited_risk (decided)); cb-054-decoy-server-attack-learning (expected minimal_risk, got limited_risk (decided)); cb-056-datacentre-mail-and-leak-watch (expected minimal_risk, got limited_risk (needs_more_information)); cb-077-regional-demand-forecast (expected minimal_risk, got limited_risk (decided)); cb-086-admissions-round-pattern-audit (expected minimal_risk, got limited_risk (needs_more_information)); cb-093-teacher-exam-proofreader (expected minimal_risk, got limited_risk (needs_more_information)); cb-102-tutor-advice-method-review (expected minimal_risk, got limited_risk (needs_more_information)); cb-172-life-cover-product-design (expected minimal_risk, got limited_risk (needs_more_information)); cb-183-responder-exercise-simulator (expected minimal_risk, got limited_risk (decided)); cb-188-flood-fire-prepositioning-brief (expected minimal_risk, got limited_risk (decided)); cb-206-device-data-recovery (expected minimal_risk, got limited_risk (legally_ambiguous)); cb-207-crime-scene-3d-model (expected minimal_risk, got limited_risk (needs_more_information)); cb-228-police-back-office-automation (expected minimal_risk, got limited_risk (needs_more_information)); cb-254-risk-record-dedup (expected minimal_risk, got limited_risk (needs_more_information)); cb-290-judgment-redaction-and-fee-check (expected minimal_risk, got limited_risk (needs_more_information))
- **role_obligations** (1): cb-160-bank-consumer-credit-score (expected role provider, got deployer)
- **no result (the classifier failed)** (6): cb-017-abuse-material-offender-matching (no result); cb-117-staffing-vacancy-matching (no result); cb-222-missing-child-suspect-filter (no result); cb-247-route-duration-traveller-alert (no result); cb-271-land-border-presence-alerts (no result); cb-305-ballot-scan-tally (no result)

### Model-written texts

- Longest fact or question: 240 characters (cap 600)
- Facts: 912 over 147 results
- Follow-up questions: 1031 over 147 results

### Judged metrics

- Judge: Jev `typesafe/jev-1.13`, backup `anthropic/claude-haiku-5.5` on `google-vertex/europe`, unsure margin 0.1 (decision 006)
- Cases judged: 147 of 147
- Judge cost: $0.0985, 1540396 tokens (not in the run's cost above)

| Metric | Value | Count | Not measured | Backup decided | Cost | Cost per item |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Citation support | 14.5% | 97/669 | 46 | 32 | $0.0819 | $0.000115 |
| Evidence-tag accuracy | 99.6% | 708/711 | 0 | 3 | $0.0166 | $0.000023 |

Not measured: the judge's reply was refused or broken, or the item was too long to send; never counted as a fail.

- No invented content: checked by code (P8a's `check_nothing_invented` on each document the results call for), not judged: 100.0%, 196/196 documents
