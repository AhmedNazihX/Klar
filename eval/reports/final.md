# Final evaluation (W1)

Numbers below are quoted from stored runs (`eval_runs` / `eval_case_results`) by run_id, via
`aiact evaluate report`, `gap`, `breakdown`, `held-out-hits`, `tool-calls` and
`head-to-head render`, whose outputs are pasted in full under *Stored outputs*. Classifications are
guidance, not legal advice.

- **Build:** frozen when W1 started (decision 024), at commit `6f5fa5024bb48d8e491c2f7642782a865fd0b445`;
  every run below records that commit and no uncommitted changes. Law: the 19 May 2026 draft
  high-risk guidelines (decision 007, W0 run 2).
- **Runs:** full run 1 and full run 2, both started 2026-10-15. Run 1 holds every set, classifier and
  mode INIT › Metrics needs; run 2 repeats the sets whose numbers vary from run to run (user,
  2026-10-15). The gap runs, appliedAI, the academic set, the baselines, the head-to-head draw and the
  retrieval check ran once, in run 1.
- **Engine:** `openai/gpt-6-luna-20260922` on `azure/eu`. Requests the engine model's provider refuses
  go to a second model, `google/gemini-3.1-flash-lite` on `google-vertex/eu` (decision 033); the
  share it answered is given per run below.
- **Own cases are development cases:** the engine's nodes were developed against them, so Commission
  Pile B carries the headline (decision 018).
- **Contaminated cases (decision 016):** the headline is given with and without the two contaminated
  cases listed in decision 016 (`eval/isolation/contaminated.json`). Decision 016 is revisited if they
  score clearly better than the rest: they scored 2 of 2 in run 1 and 1 of 2 in run 2 (from the
  accuracy with and without them below), so they did not, and nothing is revisited.

## Headline figures (landing and Method pages, P27)

| Figure | Run 1 | Run 2 |
| --- | --- | --- |
| Risk-class accuracy, Commission Pile B held out | 65.8% (100/152), run `31baa80c-f3bc-4eaf-93d0-4280b5fa14e7` | 60.5% (92/152), run `3ed735c1-b796-421b-a01e-5d36faa93851` |
| … without the contaminated cases | 65.3% (98/150) | 60.7% (91/150) |
| False-low-risk rate, Commission Pile B | 0.0% (0/56) | 1.7% (1/59) |
| Citations that exist (at run time), Commission Pile B | 100.0% (147/147) | 100.0% (149/149) |
| Results the second model answered (the engine model's provider refused), Commission Pile B | 3 of 147 (2.0%) | 4 of 149 (2.7%) |
| Results refused by both models (not assessed), Commission Pile B | 0 of 147 (0.0%) | 0 of 149 (0.0%) |

Run date: 2026-10-15 for both. Head-to-head against the Commission's AI Act Service Desk checker
(decision 036; quoted from `eval/reports/pile_b/head_to_head.md`, re-rendered from run
`592089b8-1585-4f8f-a108-9d4ebbe8f38a` on the frozen build): Commission checker 84.0% (21/25),
engine 76.0% (19/25) risk-class accuracy over the same 25 drawn cases; false-low-risk rate 0.0% (0/10)
for both. Both columns are given as they fall.

## Every INIT metric

Every value is quoted from the run whose id is in its cell or in its column header. "Run 1 / Run 2"
give the two full runs side by side; their spread is the difference between the two values shown,
quoted as is.

### Risk-class accuracy, per benchmark

| Benchmark | Run 1 | Run 2 |
| --- | --- | --- |
| Commission Pile B, held out (headline) | 65.8% (100/152) `31baa80c-f3bc-4eaf-93d0-4280b5fa14e7` | 60.5% (92/152) `3ed735c1-b796-421b-a01e-5d36faa93851` |
| Own cases (development cases) | 84.6% (66/78) `d520e689-5c8b-463c-9155-42b2d7a2ab02` | 84.6% (66/78) `f5d98467-29ab-42c0-9d18-ecf3c4164939` |
| Soft-wording pairs | 66.7% (16/24) `c1746ef0-d8bf-4caa-84a0-b93a552dc99f` | 62.5% (15/24) `3539d1b0-b22d-403d-9c62-e08961b00384` |
| Consistency set | 90.0% (27/30) `76a3d43e-5f0e-4e17-9e65-8d5534cd85e2` | 86.7% (26/30) `acf079e8-cab4-4b24-b61f-101f7d6d0fa5` |
| Annex matching | 87.5% (42/48) `983fda65-4fdf-4afb-b553-bc0280c9ff49` | 87.5% (42/48) `918a061a-333b-41a3-aeae-26e24971bd45` |
| appliedAI (second benchmark, reported separately) | 62.7% (52/83) `f0e004fa-8f79-4c51-a9c7-6655a4529479` | not repeated |
| Academic benchmark (extra check, reported separately) | 87.2% (293/336) `a6de7ccb-1324-45ff-8eb0-52682e5677a5` | not repeated |
| Head-to-head draw (own and Pile B cases mixed) | 76.0% (19/25) `592089b8-1585-4f8f-a108-9d4ebbe8f38a` | not repeated |

appliedAI: the reviewed figures stay those of `eval/reports/appliedai_review.md` by run
`9908ac9d-3c8c-4e91-be8f-ccdb8b89eb03`: 63.0% (51/81) before excluding the labels marked outdated or
wrong, 78.5% (51/65) after. The verdicts came from one proposing agent, a blind adversarial agent and the
user's confirmation; 21 of the 29 excluded labels were wrong when made, not outdated (V9). That run
predates E21; run `f0e004fa-8f79-4c51-a9c7-6655a4529479` above is the frozen build's unreviewed figure
(its report counts 55 cases for the disagreement review, which was not redone).

### Baselines (same cases, run 1)

| Classifier | Commission Pile B | Own cases (development cases) |
| --- | --- | --- |
| Engine (staged, cited) | 65.8% (100/152) `31baa80c-f3bc-4eaf-93d0-4280b5fa14e7` | 84.6% (66/78) `d520e689-5c8b-463c-9155-42b2d7a2ab02` |
| `baseline_luna`: same model, one prompt, no retrieval | 60.5% (92/152) `b2b88c38-5f2d-438e-8741-7e234ebb6cc5` | 75.6% (59/78) `1e490e70-6606-436a-902a-a92157456f06` |
| `baseline_jev`: Jev classifying the description | 51.3% (78/152) `bc908149-1726-49e2-ae14-67ffe7efae3a` | 74.4% (58/78) `dadf2f5a-32fd-4c14-9b2d-9ebbc4b33e06` |
| Baseline false-low-risk rate, `baseline_luna` / `baseline_jev` | 0.0% (0/61) / 13.1% (8/61) | 0.0% (0/31) / 17.6% (6/34) |

### Held-out vs in-corpus gap (run 1)

From `aiact evaluate gap` (pasted in full below):

| Set | Held-out run | Gap run | Gap |
| --- | --- | --- | --- |
| Commission Pile B | 65.8% (100/152) `31baa80c-f3bc-4eaf-93d0-4280b5fa14e7` | 71.1% (108/152) `2d0ad2ce-6ef3-4ffb-b928-f441e17a7fe2` | -5.3 pp |
| … without the contaminated cases | 65.3% (98/150) | 70.7% (106/150) | -5.3 pp |
| Own cases | 84.6% (66/78) `d520e689-5c8b-463c-9155-42b2d7a2ab02` | 84.6% (66/78) `22bf99b1-0e18-42d9-b558-2a401b66415b` | +0.0 pp |

Isolation check on the traces (`aiact evaluate held-out-hits`): the held-out runs' traces retrieved no
held-out row (Commission Pile B 0 of 147 (0.0%), own cases 0 of 88 (0.0%)); the gap runs' did
(Commission Pile B 88 of 146 (60.3%), 112 distinct held-out rows; own cases 9 of 88 (10.2%), 11
distinct rows). Run 2's held-out runs retrieved none either (Commission Pile B 0 of 148 (0.0%), own
cases 0 of 86 (0.0%)). In run 2's Pile B run (`3ed735c1-b796-421b-a01e-5d36faa93851`) one search had
no recorded hit ids and was left out of that check (the output's label reads "traced before V8 recorded
them", but the run is later than V8); why is not visible in the stored run, so it is unexplained.

### The other metrics

Runs: Commission Pile B `31baa80c-f3bc-4eaf-93d0-4280b5fa14e7` / `3ed735c1-b796-421b-a01e-5d36faa93851`;
own cases `d520e689-5c8b-463c-9155-42b2d7a2ab02` / `f5d98467-29ab-42c0-9d18-ecf3c4164939`; the other
sets' runs are named in their cells by the first part of their id (full ids in the per-run table).

| Metric | Commission Pile B, `31baa80c` / `3ed735c1` | Own cases, `d520e689` / `f5d98467` | Other sets |
| --- | --- | --- | --- |
| False-low-risk rate | 0.0% (0/56) / 1.7% (1/59) | 0.0% (0/34) / 0.0% (0/34) | appliedAI 45.0% (9/20) `f0e004fa`; academic 11.3% (17/151) `a6de7ccb`; soft pairs 16.7% (4/24) `c1746ef0` / 18.2% (4/22) `3539d1b0`; soft pairs with key-fact answers 4.3% (1/23) `1ff04bc9` / 8.7% (2/23) `79e16006`; Annex matching 0.0% (0/48) `983fda65` / 2.1% (1/47) `918a061a`; consistency set 0.0% (0/18) `76a3d43e` / 0.0% (0/18) `acf079e8` |
| Annex point accuracy | 93.3% (42/45) / 95.7% (44/46) | 100.0% (21/21) / 90.5% (19/21) | Annex matching 97.6% (41/42) `983fda65` / 100.0% (42/42) `918a061a` |
| Role accuracy | 92.1% (140/152) / 92.1% (140/152) | 82.9% (63/76) / 77.6% (59/76) | academic 90.0% (305/339) `a6de7ccb` |
| Legally ambiguous: precision | 0.0% (0/6) / 7.1% (1/14) | 16.7% (1/6) / 40.0% (2/5) | appliedAI 25.0% (1/4) `f0e004fa` |
| Legally ambiguous: recall | n/a (0/0) / 100.0% (1/1) | 50.0% (1/2) / 40.0% (2/5) | appliedAI 5.3% (1/19) `f0e004fa` |
| Needs more information: precision (reported separately) | 0.0% (0/84) / 0.0% (0/79) | 12.9% (4/31) / 11.8% (4/34) | |
| Needs more information: recall | n/a (0/0) / n/a (0/0) | 80.0% (4/5) / 80.0% (4/5) | |
| Citation existence (at run time; hard rule 100%) | 100.0% (147/147) / 100.0% (149/149) | 100.0% (84/84) / 100.0% (82/82) | 100.0% in every other engine run (reports below) |
| Citation support (judged) | 14.5% (97/669) / 15.5% (102/660) | 16.4% (52/318) / 21.6% (65/301) | |
| Evidence-tag accuracy (judged) | 99.6% (708/711) / 99.6% (709/712) | 99.3% (428/431) / 99.3% (412/415) | |
| No invented content (code-checked documents, P8a) | 100.0%, 196/196 / 100.0%, 226/226 | 100.0%, 85/85 / 100.0%, 98/98 | |

The engine's false-low-risk rate counts only cases with a result: failed cases are left out, which is
why its Commission Pile B counts are 0/56 and 1/59 where the baselines' are 0/61.

| Metric | Run 1 | Run 2 |
| --- | --- | --- |
| Downgrade rate, soft wording, without key-fact answers | 25.0% (3/12) `c1746ef0-d8bf-4caa-84a0-b93a552dc99f` | 40.0% (4/10) `3539d1b0-b22d-403d-9c62-e08961b00384` |
| Downgrade rate, with the key-fact answers (decision 019) | 8.3% (1/12) `1ff04bc9-4425-4898-b81b-43f2bdcc1325` | 9.1% (1/11) `79e16006-8663-4e52-9f4b-d248a9404a13` |
| Consistency (same class across a triple's three descriptions) | 100.0% (10/10) `76a3d43e-5f0e-4e17-9e65-8d5534cd85e2` | 90.0% (9/10) `acf079e8-cab4-4b24-b61f-101f7d6d0fa5` |
| Q&A support (judged) | 100.0% (25/25) `6b05eb02-df86-4cbd-af1f-0d5caa0b33ce` | 100.0% (24/24) `fffeb510-2aaa-4ff8-b619-125a4af2eb70` |

Judged metrics: Jev `typesafe/jev-1.13` first, the backup `anthropic/claude-haiku-5.5` on
`google-vertex/europe` for items within the unsure margin 0.1 (decision 006); items the judge couldn't
answer are counted as not measured, never as fails (counts in each report).

**Obligations and documents** are covered by ordinary code tests (the backend suite at the freeze
commit, run in CI) and by the code check of invented content above.

**Retrieval and Q&A quality (RAGAS, Q&A set).** The report command does not render a RAGAS table yet
(V6), so the means are quoted from `eval_runs.config.outcome.means`:

| Mean | Run 1 `6b05eb02-df86-4cbd-af1f-0d5caa0b33ce` | Run 2 `fffeb510-2aaa-4ff8-b619-125a4af2eb70` |
| --- | --- | --- |
| context_precision | 0.8828703703357113 | 0.8828703703372545 |
| context_recall | 0.9413580246913581 | 0.9413580246913581 |
| faithfulness | 0.7937389770723103 | 0.8106407995296884 |
| provision_recall | 0.8395061728395062 | 0.8765432098765432 |

Each run scored 27 of 29 items (2 failed, from the runner's summary line).

**Retrieval on Annex matching and Q&A (model-free, run 1, arm `qwen3-1536`):** means from
`eval_runs.config.outcome.means`.

| Mean | Annex matching `7e25cc5a-ba56-4311-a28f-e28762cc8f27` | Q&A `a3ae0b4a-9055-4bf3-acb9-2b43df4c38da` |
| --- | --- | --- |
| context_precision | 0.4666666666666666 | 0.7482758620689655 |
| context_recall | 0.5833333333333334 | 0.8505747126436782 |
| annex_recall_lenient | 0.5833333333333334 | n/a |
| reciprocal_rank | 0.48989621489621493 | 0.7626436781609196 |
| best_similarity | 0.72134516193739 | 0.8059788737738048 |

**Tool-call correctness** (LangSmith traces, `aiact evaluate tool-calls`; each step's share of traces
that called the lookups it should have):

| Run | Step | Correct | Count | Missed |
| --- | --- | ---: | ---: | --- |
| `d520e689-5c8b-463c-9155-42b2d7a2ab02` | scope | 100.0% | 84/84 |  |
| `d520e689-5c8b-463c-9155-42b2d7a2ab02` | prohibited | 100.0% | 76/76 |  |
| `d520e689-5c8b-463c-9155-42b2d7a2ab02` | high_risk | 100.0% | 66/66 |  |
| `d520e689-5c8b-463c-9155-42b2d7a2ab02` | transparency | 100.0% | 66/66 |  |
| `d520e689-5c8b-463c-9155-42b2d7a2ab02` | role_obligations | 100.0% | 66/66 |  |
| `f5d98467-29ab-42c0-9d18-ecf3c4164939` | scope | 100.0% | 82/82 |  |
| `f5d98467-29ab-42c0-9d18-ecf3c4164939` | prohibited | 100.0% | 74/74 |  |
| `f5d98467-29ab-42c0-9d18-ecf3c4164939` | high_risk | 98.4% | 62/63 | every Annex III point fetched (1) |
| `f5d98467-29ab-42c0-9d18-ecf3c4164939` | transparency | 100.0% | 63/63 |  |
| `f5d98467-29ab-42c0-9d18-ecf3c4164939` | role_obligations | 100.0% | 63/63 |  |

Not read: `31baa80c-f3bc-4eaf-93d0-4280b5fa14e7`, `3ed735c1-b796-421b-a01e-5d36faa93851` (the LangSmith reads of these runs did not finish; `aiact evaluate tool-calls <run_id>` gives them). Both are Pile B runs; the rows above are own-case runs (development cases).

## Per language, business function and Commission area

From `aiact evaluate breakdown` (W1; decision 024's 2026-10-15 amendment). Own cases are grouped by
business function (sales, education and research have few cases: read each rate with its count;
the 3 thin cases have none), Commission cases by their `area:` tag. Full tables under *Stored outputs*.

## Failures, cut-offs and refusals per run

"Failed" is the runner's count of cases with no result; a reply cut off at the output cap is asked
once more (E20), and a reply cut off twice can become a failed case. Cut-offs are counted from the
runs' logs (lines "the reply was cut off at the output cap; asking once more"); the logs themselves
are not quoted, as they name cases.

| Run | Set, classifier, mode | Cases (failed) | Cut-offs | Answered by the second model | Cost |
| --- | --- | --- | ---: | --- | ---: |
| `31baa80c-f3bc-4eaf-93d0-4280b5fa14e7` (r1-01) | commission_b, engine, heldout | 153 (6 failed) | 24 | 3 of 147 (2.0%) | $1.2788 |
| `2d0ad2ce-6ef3-4ffb-b928-f441e17a7fe2` (r1-02) | commission_b, engine, all (gap run) | 153 (7 failed) | 15 | 4 of 146 (2.7%) | $1.2650 |
| `d520e689-5c8b-463c-9155-42b2d7a2ab02` (r1-03) | own, engine, heldout | 88 (0 failed) | 3 | 8 of 88 (9.1%) | $0.6555 |
| `22bf99b1-0e18-42d9-b558-2a401b66415b` (r1-04) | own, engine, all (gap run) | 88 (0 failed) | 4 | 7 of 88 (8.0%) | $0.6406 |
| `c1746ef0-d8bf-4caa-84a0-b93a552dc99f` (r1-05) | soft_pairs, engine | 24 (0 failed) | 0 | 0 of 24 (0.0%) | $0.2020 |
| `1ff04bc9-4425-4898-b81b-43f2bdcc1325` (r1-17) | soft_pairs, engine, answers from r1-05 | 24 (1 failed) | 1 | 1 of 23 (4.3%) | $0.2184 |
| `76a3d43e-5f0e-4e17-9e65-8d5534cd85e2` (r1-06) | consistency, engine | 30 (0 failed) | 0 | 1 of 30 (3.3%) | $0.2006 |
| `983fda65-4fdf-4afb-b553-bc0280c9ff49` (r1-07) | annex_match, engine | 48 (0 failed) | 3 | 1 of 48 (2.1%) | $0.4191 |
| `592089b8-1585-4f8f-a108-9d4ebbe8f38a` (r1-08) | head-to-head draw, engine | 25 (0 failed) | 1 | 6 of 25 (24.0%) | $0.1834 |
| `f0e004fa-8f79-4c51-a9c7-6655a4529479` (r1-09) | appliedai, engine | 106 (0 failed) | 3 | 2 of 106 (1.9%) | $0.8937 |
| `a6de7ccb-1324-45ff-8eb0-52682e5677a5` (r1-10) | academic, engine | 339 (0 failed) | 10 | 3 of 339 (0.9%) | $2.2177 |
| `b2b88c38-5f2d-438e-8741-7e234ebb6cc5` (r1-11) | commission_b, baseline_luna | 153 (2 failed) | 0 | 0 of 151 (0.0%) | $0.1358 |
| `1e490e70-6606-436a-902a-a92157456f06` (r1-12) | own, baseline_luna | 88 (7 failed) | 0 | 0 of 81 (0.0%) | $0.0608 |
| `bc908149-1726-49e2-ae14-67ffe7efae3a` (r1-13) | commission_b, baseline_jev | 153 (0 failed) | 0 | 0 of 153 (0.0%) | $0.0071 |
| `dadf2f5a-32fd-4c14-9b2d-9ebbc4b33e06` (r1-14) | own, baseline_jev | 88 (0 failed) | 0 | 0 of 88 (0.0%) | $0.0041 |
| `3ed735c1-b796-421b-a01e-5d36faa93851` (r2-01) | commission_b, engine, heldout | 153 (4 failed) | 29 | 4 of 149 (2.7%) | $1.3204 |
| `f5d98467-29ab-42c0-9d18-ecf3c4164939` (r2-03) | own, engine, heldout | 88 (2 failed) | 6 | 9 of 86 (10.5%) | $0.6417 |
| `3539d1b0-b22d-403d-9c62-e08961b00384` (r2-05) | soft_pairs, engine | 24 (1 failed) | 1 | 1 of 23 (4.3%) | $0.2018 |
| `79e16006-8663-4e52-9f4b-d248a9404a13` (r2-17) | soft_pairs, engine, answers from r2-05 | 24 (0 failed) | 0 | 2 of 24 (8.3%) | $0.2181 |
| `acf079e8-cab4-4b24-b61f-101f7d6d0fa5` (r2-06) | consistency, engine | 30 (0 failed) | 0 | 0 of 30 (0.0%) | $0.2035 |
| `918a061a-333b-41a3-aeae-26e24971bd45` (r2-07) | annex_match, engine | 48 (1 failed) | 3 | 1 of 47 (2.1%) | $0.4141 |
| `6b05eb02-df86-4cbd-af1f-0d5caa0b33ce` (r1-15) | qa, RAGAS | 27/29 items (2 failed) | 0 | n/a | $0.1752 |
| `fffeb510-2aaa-4ff8-b619-125a4af2eb70` (r2-15) | qa, RAGAS | 27/29 items (2 failed) | 0 | n/a | $0.1775 |
| `7e25cc5a-ba56-4311-a28f-e28762cc8f27`, `a3ae0b4a-9055-4bf3-acb9-2b43df4c38da` (r1-16) | embeddings, Annex matching and Q&A | 48/48, 29/29 | 0 | n/a | $0.000092, $0.000029 |

No run stopped at its cost cap; every command exited 0, and no log held a top-level error.

## Cost

| Item | Cost |
| --- | --- |
| Stored run costs (`eval_runs.cost_usd`), the 25 runs above | $11.735008 |
| Judged passes (each report's "Judge cost" line): r1-01 $0.0985, r1-03 $0.0605, r1-15 $0.0021, r2-01 $0.1032, r2-03 $0.0613, r2-15 $0.0021 | $0.3277 |
| Total, the two lines above | $12.0627 |

The OpenRouter account showed $8.56 after run 1 and $3.50 for the judged passes and run 2 (user,
2026-10-15): $12.06, within the user's $15 cap for both full runs (approved 2026-10-15). Free dry
runs with the dummy classifier, used to check the commands, cost nothing.

## Limitations

A later read-only analysis of run 1's Pile B misses, made after W1, is at the end of this report (*Later
analysis*); it is not one of the stored outputs.

- **No hand-reviewed sample of the judge's verdicts.** Citation support and evidence tags are judged by
  Jev with the backup LLM judge for unsure items, validated in V4 against hand-labelled items
  (decision 006). INIT's manual sample of the W1 runs' verdicts is not done (user, 2026-10-15): the
  judged rates are not checked by hand on these runs.
- **Citation support is low** (from 14.5% (97/669) to 21.6% (65/301) above). It is quoted as judged;
  this report does not analyse why, and without the hand-review sample the judge's share of wrong
  "not supported" verdicts on these runs is unknown.
- **Output-cap cut-offs.** A reply cut off at the output cap is asked once more (E20), and one cut off
  twice can become a failed case. The counted log lines are first cut-offs, so they don't show how
  many of the failed cases came from them.
- **False low risks on repeated sets.** Run 2 had false low risks where run 1 had none on the same
  sets: Commission Pile B 1.7% (1/59) and Annex matching 2.1% (1/47); on the soft pairs with key-fact
  answers it had 8.7% (2/23) against run 1's 4.3% (1/23).
- **Tool-call correctness** was read for 2 of the 4 planned runs, both own-case runs (development
  cases: `d520e689-5c8b-463c-9155-42b2d7a2ab02`, `f5d98467-29ab-42c0-9d18-ecf3c4164939`); the LangSmith
  reads of the Pile B headline runs did not finish, so there is no figure on them.
- **RAGAS faithfulness about 0.80** on the Q&A set (0.7937389770723103 and 0.8106407995296884), below its
  context recall: some answers state more than the retrieved text supports, by RAGAS's own measure.
- **Run-to-run spread.** Run 2 repeats the varying sets on the same build; differences between the
  two columns (for example the headline 65.8% and 60.5%, and one false low risk in run 2's 1.7%
  (1/59)) come from run-to-run variance: same build, same cases, same settings. Known gaps own-e-09, own-f-07 (variance) and own-e-10
  were kept by the user (E20); none is a false low risk in these runs' own-case figures.
- **Own cases are development cases** (decision 018); the academic set and appliedAI are reported
  separately (INIT › Test sets); the appliedAI disagreement review covers run
  `9908ac9d-3c8c-4e91-be8f-ccdb8b89eb03`, which predates E21.
- **Gap.** The gap's known limits are printed with it (under *Stored outputs*). Isolation n-gram
  numbers beyond those are not quoted: B4a's tie-break between rows with equal coverage depends on
  hash order, so its n-gram report can differ between runs (the gate result does not).
- **Head-to-head.** The checker is a beta answered by agents with a hand spot-check (decision 036);
  the engine column now comes from a new engine run on the frozen build
  (`592089b8-1585-4f8f-a108-9d4ebbe8f38a`, build `6f5fa5024bb4`), not a rescore of the earlier one
  (`d74843dc-52f0-48c6-95ce-775fbf1610b6`, build `9f945cf01bf6`, 2026-10-14, before E21). Against that
  earlier run the commission_b cases went from 37.5% (3/8) to 50.0% (4/8) and the own cases from
  94.1% (16/17) to 88.2% (15/17); the total is 76.0% (19/25) in both. Full limits in `eval/reports/pile_b/head_to_head.md`.
- **No external legal review of the labels** (INIT › Label rules).

## Commands

Run from `backend/` at the freeze commit, each with `--seed 0` and the default concurrency 4; stderr
went to logs outside the repository (they name cases).

| Run | Command (`aiact evaluate …`) | Cap |
| --- | --- | ---: |
| r1-01, r2-01 | `run --set commission_b --classifier engine --exclude-mode heldout` | $1.50, $1.45 |
| r1-02 | `run --set commission_b --classifier engine --exclude-mode all` | $1.50 |
| r1-03, r2-03 | `run --set own --classifier engine --exclude-mode heldout` | $0.75 |
| r1-04 | `run --set own --classifier engine --exclude-mode all` | $0.75 |
| r1-05, r2-05 | `run --set soft_pairs --classifier engine --exclude-mode heldout` | $0.25 |
| r1-17, r2-17 | `run --set soft_pairs --classifier engine --exclude-mode heldout --answers-from <r1-05 / r2-05>` | $0.25, $0.26 |
| r1-06, r2-06 | `run --set consistency --classifier engine --exclude-mode heldout` | $0.30, $0.25 |
| r1-07, r2-07 | `run --set annex_match --classifier engine --exclude-mode heldout` | $0.50, $0.48 |
| r1-08 | `run --cases-from-draw --classifier engine --exclude-mode heldout` | $0.25 |
| r1-09 | `run --set appliedai --classifier engine --exclude-mode heldout` | $1.05 |
| r1-10 | `run --set academic --classifier engine --exclude-mode heldout` | $3.00 |
| r1-11, r1-12 | `run --set commission_b` / `--set own --classifier baseline_luna` | $0.17, $0.07 |
| r1-13, r1-14 | `run --set commission_b` / `--set own --classifier baseline_jev` | $0.01, $0.01 |
| r1-15, r2-15 | `ragas` | $0.25, $0.22 |
| r1-16 | `embeddings --arm qwen3-1536 --set annex_match --set qa` | $0.01 |
| judged | `judged <run_id>`, a dry run first: r1-03 small pass, r1-03, r1-01, r1-15, r2-01, r2-03, r2-15 | $0.03, $0.40, $0.72, $0.03, $0.72, $0.40, $0.03 |
| head-to-head | `head-to-head render --run-id 592089b8-1585-4f8f-a108-9d4ebbe8f38a` (free; re-reads the stored run) | n/a |

## Stored outputs

Pasted unchanged, except that each heading is moved down two levels.

### Gap

#### Held-out vs in-corpus gap: `commission_b`

- Held-out run (the reported number): 31baa80c-f3bc-4eaf-93d0-4280b5fa14e7, status completed
- Gap run (every example retrievable): 2d0ad2ce-6ef3-4ffb-b928-f441e17a7fe2, status completed

| Risk-class accuracy | Held-out run | Gap run | Gap (held-out minus gap run) |
| --- | ---: | ---: | ---: |
| Every case | 65.8% (100/152) | 71.1% (108/152) | -5.3 pp |
| Without the contaminated cases (docs/decisions/016-contaminated-pile-b-cases.md) | 65.3% (98/150) | 70.7% (106/150) | -5.3 pp |

Known limits of this comparison:
- Pile A example rows are judged by 6-gram coverage only (threshold 0.8, B13), since sibling examples share long reasoning sentences; a Pile B example quoted inside a Pile A example row below that coverage would not be caught.
- Some Pile A examples are near-twins of Pile B ones (for example hr-ex-024, -067, -124, -187 share 50-58% of their 8-word runs with a Pile B example; C4's audit). They stay retrievable in both runs (decision 012), so the gap understates how much the engine leans on memorised examples.
- The guideline search returns Pile A examples whose stock phrasing shares 8-word runs with their Pile B siblings, and the high-risk prompt carries the Act's full Annex III text (E5's isolation audit); both are allowed under decision 012 and present in both runs.
- Searching alone is weak for softly worded German descriptions: own-e-14 brought no Annex III row into a top-50 law search (E5), so the high-risk step lists every Annex III point instead.

#### Held-out vs in-corpus gap: `own`

- Held-out run (the reported number): d520e689-5c8b-463c-9155-42b2d7a2ab02, status completed
- Gap run (every example retrievable): 22bf99b1-0e18-42d9-b558-2a401b66415b, status completed

| Risk-class accuracy | Held-out run | Gap run | Gap (held-out minus gap run) |
| --- | ---: | ---: | ---: |
| Every case | 84.6% (66/78) | 84.6% (66/78) | +0.0 pp |
| Without the contaminated cases (docs/decisions/016-contaminated-pile-b-cases.md) | 84.6% (66/78) | 84.6% (66/78) | +0.0 pp |

Known limits of this comparison:
- Pile A example rows are judged by 6-gram coverage only (threshold 0.8, B13), since sibling examples share long reasoning sentences; a Pile B example quoted inside a Pile A example row below that coverage would not be caught.
- Some Pile A examples are near-twins of Pile B ones (for example hr-ex-024, -067, -124, -187 share 50-58% of their 8-word runs with a Pile B example; C4's audit). They stay retrievable in both runs (decision 012), so the gap understates how much the engine leans on memorised examples.
- The guideline search returns Pile A examples whose stock phrasing shares 8-word runs with their Pile B siblings, and the high-risk prompt carries the Act's full Annex III text (E5's isolation audit); both are allowed under decision 012 and present in both runs.
- Searching alone is weak for softly worded German descriptions: own-e-14 brought no Annex III row into a top-50 law search (E5), so the high-risk step lists every Annex III point instead.


### Held-out rows retrieved

#### Held-out rows retrieved, run 31baa80c-f3bc-4eaf-93d0-4280b5fa14e7

- Traces checked: 147
- Traces that retrieved a held-out row: 0 of 147 (0.0%)
- Distinct held-out rows retrieved: 0
- Left out, a search without recorded hit ids: 0 (traced before V8 recorded them)
- Left out, still being ingested: 0
- Left out, no runs returned: 0 (expired, another workspace, or not yet ingested)
- Cases without a trace: 6

#### Held-out rows retrieved, run 2d0ad2ce-6ef3-4ffb-b928-f441e17a7fe2

- Traces checked: 146
- Traces that retrieved a held-out row: 88 of 146 (60.3%)
- Distinct held-out rows retrieved: 112
- Left out, a search without recorded hit ids: 0 (traced before V8 recorded them)
- Left out, still being ingested: 0
- Left out, no runs returned: 0 (expired, another workspace, or not yet ingested)
- Cases without a trace: 7

#### Held-out rows retrieved, run d520e689-5c8b-463c-9155-42b2d7a2ab02

- Traces checked: 88
- Traces that retrieved a held-out row: 0 of 88 (0.0%)
- Distinct held-out rows retrieved: 0
- Left out, a search without recorded hit ids: 0 (traced before V8 recorded them)
- Left out, still being ingested: 0
- Left out, no runs returned: 0 (expired, another workspace, or not yet ingested)
- Cases without a trace: 0

#### Held-out rows retrieved, run 22bf99b1-0e18-42d9-b558-2a401b66415b

- Traces checked: 88
- Traces that retrieved a held-out row: 9 of 88 (10.2%)
- Distinct held-out rows retrieved: 11
- Left out, a search without recorded hit ids: 0 (traced before V8 recorded them)
- Left out, still being ingested: 0
- Left out, no runs returned: 0 (expired, another workspace, or not yet ingested)
- Cases without a trace: 0

#### Held-out rows retrieved, run 3ed735c1-b796-421b-a01e-5d36faa93851

- Traces checked: 148
- Traces that retrieved a held-out row: 0 of 148 (0.0%)
- Distinct held-out rows retrieved: 0
- Left out, a search without recorded hit ids: 1 (traced before V8 recorded them)
- Left out, still being ingested: 0
- Left out, no runs returned: 0 (expired, another workspace, or not yet ingested)
- Cases without a trace: 4

#### Held-out rows retrieved, run f5d98467-29ab-42c0-9d18-ecf3c4164939

- Traces checked: 86
- Traces that retrieved a held-out row: 0 of 86 (0.0%)
- Distinct held-out rows retrieved: 0
- Left out, a search without recorded hit ids: 0 (traced before V8 recorded them)
- Left out, still being ingested: 0
- Left out, no runs returned: 0 (expired, another workspace, or not yet ingested)
- Cases without a trace: 2


### Tool-call correctness

#### Tool-call correctness, run d520e689-5c8b-463c-9155-42b2d7a2ab02

- Traces scored: 84
- Left out, no lookup run: 4 (recorded before lookups were traced, or not fully ingested)
- Left out, still being ingested: 0 (a lookup run has no end yet)
- Left out, no runs returned: 0 (expired, another workspace, or not yet ingested)
- Cases without a trace: 0

| Step | Correct | Count | Missed |
| --- | ---: | ---: | --- |
| scope | 100.0% | 84/84 |  |
| prohibited | 100.0% | 76/76 |  |
| high_risk | 100.0% | 66/66 |  |
| transparency | 100.0% | 66/66 |  |
| role_obligations | 100.0% | 66/66 |  |

#### Tool-call correctness, run f5d98467-29ab-42c0-9d18-ecf3c4164939

- Traces scored: 82
- Left out, no lookup run: 4 (recorded before lookups were traced, or not fully ingested)
- Left out, still being ingested: 0 (a lookup run has no end yet)
- Left out, no runs returned: 0 (expired, another workspace, or not yet ingested)
- Cases without a trace: 2

| Step | Correct | Count | Missed |
| --- | ---: | ---: | --- |
| scope | 100.0% | 82/82 |  |
| prohibited | 100.0% | 74/74 |  |
| high_risk | 98.4% | 62/63 | every Annex III point fetched (1) |
| transparency | 100.0% | 63/63 |  |
| role_obligations | 100.0% | 63/63 |  |


### Breakdowns of the headline runs

#### Run 31baa80c-f3bc-4eaf-93d0-4280b5fa14e7 by area

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
- Groups with few cases are noisy: read each rate with its count.

| area | Cases | Risk-class accuracy | False-low-risk rate | Annex point accuracy | Role accuracy |
| --- | ---: | ---: | ---: | ---: | ---: |
| annex_i | 6 | 100.0% (6/6) | 0.0% (0/4) | 100.0% (4/4) | 100.0% (6/6) |
| annex_iii_1 | 20 | 65.0% (13/20) | 0.0% (0/6) | 100.0% (4/4) | 95.0% (19/20) |
| annex_iii_2 | 13 | 69.2% (9/13) | 0.0% (0/5) | 100.0% (5/5) | 100.0% (13/13) |
| annex_iii_3 | 15 | 40.0% (6/15) | 0.0% (0/6) | 100.0% (4/4) | 93.3% (14/15) |
| annex_iii_4 | 16 | 56.2% (9/16) | 0.0% (0/6) | 100.0% (3/3) | 87.5% (14/16) |
| annex_iii_5 | 24 | 62.5% (15/24) | 0.0% (0/11) | 100.0% (8/8) | 95.8% (23/24) |
| annex_iii_6 | 24 | 66.7% (16/24) | 0.0% (0/7) | 50.0% (3/6) | 91.7% (22/24) |
| annex_iii_7 | 22 | 77.3% (17/22) | 0.0% (0/8) | 100.0% (8/8) | 86.4% (19/22) |
| annex_iii_8 | 13 | 75.0% (9/12) | 0.0% (0/3) | 100.0% (3/3) | 83.3% (10/12) |

#### Run 31baa80c-f3bc-4eaf-93d0-4280b5fa14e7 by language

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
- Groups with few cases are noisy: read each rate with its count.

| language | Cases | Risk-class accuracy | False-low-risk rate | Annex point accuracy | Role accuracy |
| --- | ---: | ---: | ---: | ---: | ---: |
| de | 54 | 74.1% (40/54) | 0.0% (0/24) | 95.0% (19/20) | 92.6% (50/54) |
| en | 99 | 61.2% (60/98) | 0.0% (0/32) | 92.0% (23/25) | 91.8% (90/98) |

#### Run 3ed735c1-b796-421b-a01e-5d36faa93851 by area

- Benchmark: `commission_b`
- Commit: `6f5fa5024bb48d8e491c2f7642782a865fd0b445`
- Status: completed
- Classifier: `engine`: `openai/gpt-6-luna-20260922` on `azure/eu`
- Cases run: every case of the set
- Second model for refused requests (decision 033): `google/gemini-3.1-flash-lite` on `google-vertex/eu`
- Exclude mode: `heldout` (held-out examples kept out of retrieval: the reported number)
- Started: 2026-10-15T08:35:42.503011+00:00
- Model: openai/gpt-6-luna-20260922
- Cost: $1.3204, 7509895 tokens
- Groups with few cases are noisy: read each rate with its count.

| area | Cases | Risk-class accuracy | False-low-risk rate | Annex point accuracy | Role accuracy |
| --- | ---: | ---: | ---: | ---: | ---: |
| annex_i | 6 | 83.3% (5/6) | 0.0% (0/4) | 100.0% (4/4) | 100.0% (6/6) |
| annex_iii_1 | 20 | 60.0% (12/20) | 0.0% (0/6) | 100.0% (4/4) | 90.0% (18/20) |
| annex_iii_2 | 13 | 76.9% (10/13) | 0.0% (0/5) | 100.0% (5/5) | 92.3% (12/13) |
| annex_iii_3 | 15 | 40.0% (6/15) | 0.0% (0/6) | 100.0% (4/4) | 93.3% (14/15) |
| annex_iii_4 | 16 | 56.2% (9/16) | 0.0% (0/7) | 100.0% (5/5) | 93.8% (15/16) |
| annex_iii_5 | 24 | 54.2% (13/24) | 0.0% (0/10) | 100.0% (8/8) | 91.7% (22/24) |
| annex_iii_6 | 24 | 58.3% (14/24) | 0.0% (0/8) | 66.7% (4/6) | 95.8% (23/24) |
| annex_iii_7 | 22 | 68.2% (15/22) | 0.0% (0/10) | 100.0% (8/8) | 90.9% (20/22) |
| annex_iii_8 | 13 | 66.7% (8/12) | 33.3% (1/3) | 100.0% (2/2) | 83.3% (10/12) |

#### Run 3ed735c1-b796-421b-a01e-5d36faa93851 by language

- Benchmark: `commission_b`
- Commit: `6f5fa5024bb48d8e491c2f7642782a865fd0b445`
- Status: completed
- Classifier: `engine`: `openai/gpt-6-luna-20260922` on `azure/eu`
- Cases run: every case of the set
- Second model for refused requests (decision 033): `google/gemini-3.1-flash-lite` on `google-vertex/eu`
- Exclude mode: `heldout` (held-out examples kept out of retrieval: the reported number)
- Started: 2026-10-15T08:35:42.503011+00:00
- Model: openai/gpt-6-luna-20260922
- Cost: $1.3204, 7509895 tokens
- Groups with few cases are noisy: read each rate with its count.

| language | Cases | Risk-class accuracy | False-low-risk rate | Annex point accuracy | Role accuracy |
| --- | ---: | ---: | ---: | ---: | ---: |
| de | 54 | 66.7% (36/54) | 4.3% (1/23) | 94.4% (17/18) | 87.0% (47/54) |
| en | 99 | 57.1% (56/98) | 0.0% (0/36) | 96.4% (27/28) | 94.9% (93/98) |

#### Run d520e689-5c8b-463c-9155-42b2d7a2ab02 by business_function

- Benchmark: `own` (development cases: the engine's nodes were developed against them, so Commission Pile B carries the headline (decision 018))
- Commit: `6f5fa5024bb48d8e491c2f7642782a865fd0b445`
- Status: completed
- Classifier: `engine`: `openai/gpt-6-luna-20260922` on `azure/eu`
- Cases run: every case of the set
- Second model for refused requests (decision 033): `google/gemini-3.1-flash-lite` on `google-vertex/eu`
- Exclude mode: `heldout` (held-out examples kept out of retrieval: the reported number)
- Started: 2026-10-15T02:43:33.856824+00:00
- Model: openai/gpt-6-luna-20260922
- Cost: $0.6555, 3713749 tokens
- Groups with few cases are noisy: read each rate with its count.

| business_function | Cases | Risk-class accuracy | False-low-risk rate | Annex point accuracy | Role accuracy |
| --- | ---: | ---: | ---: | ---: | ---: |
| consumer_product | 8 | 62.5% (5/8) | 0.0% (0/1) | n/a (0/0) | 83.3% (5/6) |
| content | 9 | 88.9% (8/9) | 0.0% (0/3) | n/a (0/0) | 66.7% (6/9) |
| customer_service | 7 | 100.0% (6/6) | 0.0% (0/1) | 100.0% (1/1) | 100.0% (6/6) |
| education | 3 | 100.0% (3/3) | 0.0% (0/2) | 100.0% (2/2) | 100.0% (3/3) |
| finance | 7 | 75.0% (3/4) | 0.0% (0/2) | 100.0% (1/1) | 66.7% (4/6) |
| healthcare | 5 | 100.0% (4/4) | 0.0% (0/4) | 100.0% (4/4) | 100.0% (5/5) |
| hr | 12 | 75.0% (9/12) | 0.0% (0/8) | 100.0% (5/5) | 90.0% (9/10) |
| marketing | 5 | 75.0% (3/4) | 0.0% (0/1) | n/a (0/0) | 80.0% (4/5) |
| operations | 7 | 83.3% (5/6) | 0.0% (0/1) | 100.0% (1/1) | 83.3% (5/6) |
| product_safety | 5 | 80.0% (4/5) | 0.0% (0/4) | 100.0% (4/4) | 100.0% (5/5) |
| productivity | 6 | 83.3% (5/6) | n/a (0/0) | n/a (0/0) | 83.3% (5/6) |
| public_services | 4 | 100.0% (4/4) | 0.0% (0/2) | 100.0% (1/1) | 75.0% (3/4) |
| research | 1 | 100.0% (1/1) | n/a (0/0) | n/a (0/0) | n/a (0/0) |
| sales | 2 | 100.0% (2/2) | 0.0% (0/2) | n/a (0/0) | 0.0% (0/2) |
| security | 4 | 100.0% (4/4) | 0.0% (0/3) | 100.0% (2/2) | 100.0% (3/3) |
| (none) | 3 | n/a (0/0) | n/a (0/0) | n/a (0/0) | n/a (0/0) |

#### Run d520e689-5c8b-463c-9155-42b2d7a2ab02 by language

- Benchmark: `own` (development cases: the engine's nodes were developed against them, so Commission Pile B carries the headline (decision 018))
- Commit: `6f5fa5024bb48d8e491c2f7642782a865fd0b445`
- Status: completed
- Classifier: `engine`: `openai/gpt-6-luna-20260922` on `azure/eu`
- Cases run: every case of the set
- Second model for refused requests (decision 033): `google/gemini-3.1-flash-lite` on `google-vertex/eu`
- Exclude mode: `heldout` (held-out examples kept out of retrieval: the reported number)
- Started: 2026-10-15T02:43:33.856824+00:00
- Model: openai/gpt-6-luna-20260922
- Cost: $0.6555, 3713749 tokens
- Groups with few cases are noisy: read each rate with its count.

| language | Cases | Risk-class accuracy | False-low-risk rate | Annex point accuracy | Role accuracy |
| --- | ---: | ---: | ---: | ---: | ---: |
| de | 44 | 82.5% (33/40) | 0.0% (0/20) | 100.0% (12/12) | 82.5% (33/40) |
| en | 44 | 86.8% (33/38) | 0.0% (0/14) | 100.0% (9/9) | 83.3% (30/36) |

#### Run f5d98467-29ab-42c0-9d18-ecf3c4164939 by business_function

- Benchmark: `own` (development cases: the engine's nodes were developed against them, so Commission Pile B carries the headline (decision 018))
- Commit: `6f5fa5024bb48d8e491c2f7642782a865fd0b445`
- Status: completed
- Classifier: `engine`: `openai/gpt-6-luna-20260922` on `azure/eu`
- Cases run: every case of the set
- Second model for refused requests (decision 033): `google/gemini-3.1-flash-lite` on `google-vertex/eu`
- Exclude mode: `heldout` (held-out examples kept out of retrieval: the reported number)
- Started: 2026-10-15T09:53:49.189556+00:00
- Model: openai/gpt-6-luna-20260922
- Cost: $0.6417, 3642373 tokens
- Groups with few cases are noisy: read each rate with its count.

| business_function | Cases | Risk-class accuracy | False-low-risk rate | Annex point accuracy | Role accuracy |
| --- | ---: | ---: | ---: | ---: | ---: |
| consumer_product | 8 | 75.0% (6/8) | 0.0% (0/1) | n/a (0/0) | 66.7% (4/6) |
| content | 9 | 88.9% (8/9) | 0.0% (0/3) | n/a (0/0) | 66.7% (6/9) |
| customer_service | 7 | 100.0% (6/6) | 0.0% (0/1) | 100.0% (1/1) | 100.0% (6/6) |
| education | 3 | 100.0% (3/3) | 0.0% (0/2) | 100.0% (2/2) | 100.0% (3/3) |
| finance | 7 | 75.0% (3/4) | 0.0% (0/2) | 100.0% (1/1) | 66.7% (4/6) |
| healthcare | 5 | 100.0% (4/4) | 0.0% (0/4) | 75.0% (3/4) | 80.0% (4/5) |
| hr | 12 | 75.0% (9/12) | 0.0% (0/8) | 100.0% (6/6) | 80.0% (8/10) |
| marketing | 5 | 75.0% (3/4) | 0.0% (0/1) | n/a (0/0) | 80.0% (4/5) |
| operations | 7 | 83.3% (5/6) | 0.0% (0/1) | 100.0% (1/1) | 100.0% (6/6) |
| product_safety | 5 | 100.0% (5/5) | 0.0% (0/4) | 75.0% (3/4) | 100.0% (5/5) |
| productivity | 6 | 66.7% (4/6) | n/a (0/0) | n/a (0/0) | 66.7% (4/6) |
| public_services | 4 | 100.0% (4/4) | 0.0% (0/2) | 100.0% (1/1) | 75.0% (3/4) |
| research | 1 | 100.0% (1/1) | n/a (0/0) | n/a (0/0) | n/a (0/0) |
| sales | 2 | 100.0% (2/2) | 0.0% (0/2) | n/a (0/0) | 0.0% (0/2) |
| security | 4 | 75.0% (3/4) | 0.0% (0/3) | 100.0% (1/1) | 66.7% (2/3) |
| (none) | 3 | n/a (0/0) | n/a (0/0) | n/a (0/0) | n/a (0/0) |

#### Run f5d98467-29ab-42c0-9d18-ecf3c4164939 by language

- Benchmark: `own` (development cases: the engine's nodes were developed against them, so Commission Pile B carries the headline (decision 018))
- Commit: `6f5fa5024bb48d8e491c2f7642782a865fd0b445`
- Status: completed
- Classifier: `engine`: `openai/gpt-6-luna-20260922` on `azure/eu`
- Cases run: every case of the set
- Second model for refused requests (decision 033): `google/gemini-3.1-flash-lite` on `google-vertex/eu`
- Exclude mode: `heldout` (held-out examples kept out of retrieval: the reported number)
- Started: 2026-10-15T09:53:49.189556+00:00
- Model: openai/gpt-6-luna-20260922
- Cost: $0.6417, 3642373 tokens
- Groups with few cases are noisy: read each rate with its count.

| language | Cases | Risk-class accuracy | False-low-risk rate | Annex point accuracy | Role accuracy |
| --- | ---: | ---: | ---: | ---: | ---: |
| de | 44 | 87.5% (35/40) | 0.0% (0/20) | 92.3% (12/13) | 80.0% (32/40) |
| en | 44 | 81.6% (31/38) | 0.0% (0/14) | 87.5% (7/8) | 75.0% (27/36) |


### Breakdowns of the other runs, by language

#### Run c1746ef0-d8bf-4caa-84a0-b93a552dc99f by language

- Benchmark: `soft_pairs`
- Commit: `6f5fa5024bb48d8e491c2f7642782a865fd0b445`
- Status: completed
- Classifier: `engine`: `openai/gpt-6-luna-20260922` on `azure/eu`
- Cases run: every case of the set
- Second model for refused requests (decision 033): `google/gemini-3.1-flash-lite` on `google-vertex/eu`
- Exclude mode: `heldout` (held-out examples kept out of retrieval: the reported number)
- Started: 2026-10-15T03:43:00.348920+00:00
- Model: openai/gpt-6-luna-20260922
- Cost: $0.2020, 1206419 tokens
- Groups with few cases are noisy: read each rate with its count.

| language | Cases | Risk-class accuracy | False-low-risk rate | Annex point accuracy | Role accuracy |
| --- | ---: | ---: | ---: | ---: | ---: |
| de | 10 | 50.0% (5/10) | 20.0% (2/10) | 100.0% (5/5) | 100.0% (10/10) |
| en | 14 | 78.6% (11/14) | 14.3% (2/14) | 100.0% (11/11) | 100.0% (14/14) |

#### Run 1ff04bc9-4425-4898-b81b-43f2bdcc1325 by language

- Benchmark: `soft_pairs`
- Commit: `6f5fa5024bb48d8e491c2f7642782a865fd0b445`
- Status: completed
- Classifier: `engine`: `openai/gpt-6-luna-20260922` on `azure/eu`
- Cases run: every case of the set
- Second model for refused requests (decision 033): `google/gemini-3.1-flash-lite` on `google-vertex/eu`
- Exclude mode: `heldout` (held-out examples kept out of retrieval: the reported number)
- Answers: the stored key-fact answers to the questions run `c1746ef0-d8bf-4caa-84a0-b93a552dc99f` asked, any other question answered "don't know" (decision 019)
- Started: 2026-10-15T04:27:14.433811+00:00
- Model: openai/gpt-6-luna-20260922
- Cost: $0.2184, 1285274 tokens
- Groups with few cases are noisy: read each rate with its count.

| language | Cases | Risk-class accuracy | False-low-risk rate | Annex point accuracy | Role accuracy |
| --- | ---: | ---: | ---: | ---: | ---: |
| de | 10 | 50.0% (5/10) | 0.0% (0/10) | 100.0% (5/5) | 100.0% (10/10) |
| en | 14 | 71.4% (10/14) | 7.7% (1/13) | 100.0% (10/10) | 92.9% (13/14) |

#### Run 3539d1b0-b22d-403d-9c62-e08961b00384 by language

- Benchmark: `soft_pairs`
- Commit: `6f5fa5024bb48d8e491c2f7642782a865fd0b445`
- Status: completed
- Classifier: `engine`: `openai/gpt-6-luna-20260922` on `azure/eu`
- Cases run: every case of the set
- Second model for refused requests (decision 033): `google/gemini-3.1-flash-lite` on `google-vertex/eu`
- Exclude mode: `heldout` (held-out examples kept out of retrieval: the reported number)
- Started: 2026-10-15T10:29:02.461987+00:00
- Model: openai/gpt-6-luna-20260922
- Cost: $0.2018, 1175987 tokens
- Groups with few cases are noisy: read each rate with its count.

| language | Cases | Risk-class accuracy | False-low-risk rate | Annex point accuracy | Role accuracy |
| --- | ---: | ---: | ---: | ---: | ---: |
| de | 10 | 50.0% (5/10) | 30.0% (3/10) | 100.0% (5/5) | 100.0% (10/10) |
| en | 14 | 71.4% (10/14) | 8.3% (1/12) | 100.0% (10/10) | 85.7% (12/14) |

#### Run 79e16006-8663-4e52-9f4b-d248a9404a13 by language

- Benchmark: `soft_pairs`
- Commit: `6f5fa5024bb48d8e491c2f7642782a865fd0b445`
- Status: completed
- Classifier: `engine`: `openai/gpt-6-luna-20260922` on `azure/eu`
- Cases run: every case of the set
- Second model for refused requests (decision 033): `google/gemini-3.1-flash-lite` on `google-vertex/eu`
- Exclude mode: `heldout` (held-out examples kept out of retrieval: the reported number)
- Answers: the stored key-fact answers to the questions run `3539d1b0-b22d-403d-9c62-e08961b00384` asked, any other question answered "don't know" (decision 019)
- Started: 2026-10-15T11:35:28.972793+00:00
- Model: openai/gpt-6-luna-20260922
- Cost: $0.2181, 1233248 tokens
- Groups with few cases are noisy: read each rate with its count.

| language | Cases | Risk-class accuracy | False-low-risk rate | Annex point accuracy | Role accuracy |
| --- | ---: | ---: | ---: | ---: | ---: |
| de | 10 | 70.0% (7/10) | 0.0% (0/10) | 100.0% (7/7) | 100.0% (10/10) |
| en | 14 | 64.3% (9/14) | 15.4% (2/13) | 100.0% (9/9) | 92.9% (13/14) |

#### Run 76a3d43e-5f0e-4e17-9e65-8d5534cd85e2 by language

- Benchmark: `consistency`
- Commit: `6f5fa5024bb48d8e491c2f7642782a865fd0b445`
- Status: completed
- Classifier: `engine`: `openai/gpt-6-luna-20260922` on `azure/eu`
- Cases run: every case of the set
- Second model for refused requests (decision 033): `google/gemini-3.1-flash-lite` on `google-vertex/eu`
- Exclude mode: `heldout` (held-out examples kept out of retrieval: the reported number)
- Started: 2026-10-15T03:52:25.940070+00:00
- Model: openai/gpt-6-luna-20260922
- Cost: $0.2006, 1260509 tokens
- Groups with few cases are noisy: read each rate with its count.

| language | Cases | Risk-class accuracy | False-low-risk rate | Annex point accuracy | Role accuracy |
| --- | ---: | ---: | ---: | ---: | ---: |
| de | 9 | 100.0% (9/9) | 0.0% (0/3) | 100.0% (3/3) | 100.0% (9/9) |
| en | 21 | 85.7% (18/21) | 0.0% (0/15) | 100.0% (9/9) | 83.3% (15/18) |

#### Run acf079e8-cab4-4b24-b61f-101f7d6d0fa5 by language

- Benchmark: `consistency`
- Commit: `6f5fa5024bb48d8e491c2f7642782a865fd0b445`
- Status: completed
- Classifier: `engine`: `openai/gpt-6-luna-20260922` on `azure/eu`
- Cases run: every case of the set
- Second model for refused requests (decision 033): `google/gemini-3.1-flash-lite` on `google-vertex/eu`
- Exclude mode: `heldout` (held-out examples kept out of retrieval: the reported number)
- Started: 2026-10-15T10:40:29.692575+00:00
- Model: openai/gpt-6-luna-20260922
- Cost: $0.2035, 1269663 tokens
- Groups with few cases are noisy: read each rate with its count.

| language | Cases | Risk-class accuracy | False-low-risk rate | Annex point accuracy | Role accuracy |
| --- | ---: | ---: | ---: | ---: | ---: |
| de | 9 | 100.0% (9/9) | 0.0% (0/3) | 100.0% (3/3) | 100.0% (9/9) |
| en | 21 | 81.0% (17/21) | 0.0% (0/15) | 100.0% (8/8) | 77.8% (14/18) |

#### Run 983fda65-4fdf-4afb-b553-bc0280c9ff49 by language

- Benchmark: `annex_match`
- Commit: `6f5fa5024bb48d8e491c2f7642782a865fd0b445`
- Status: completed
- Classifier: `engine`: `openai/gpt-6-luna-20260922` on `azure/eu`
- Cases run: every case of the set
- Second model for refused requests (decision 033): `google/gemini-3.1-flash-lite` on `google-vertex/eu`
- Exclude mode: `heldout` (held-out examples kept out of retrieval: the reported number)
- Started: 2026-10-15T04:00:59.617638+00:00
- Model: openai/gpt-6-luna-20260922
- Cost: $0.4191, 2447061 tokens
- Groups with few cases are noisy: read each rate with its count.

| language | Cases | Risk-class accuracy | False-low-risk rate | Annex point accuracy | Role accuracy |
| --- | ---: | ---: | ---: | ---: | ---: |
| de | 21 | 95.2% (20/21) | 0.0% (0/21) | 100.0% (20/20) | 100.0% (21/21) |
| en | 27 | 81.5% (22/27) | 0.0% (0/27) | 95.5% (21/22) | 96.3% (26/27) |

#### Run 918a061a-333b-41a3-aeae-26e24971bd45 by language

- Benchmark: `annex_match`
- Commit: `6f5fa5024bb48d8e491c2f7642782a865fd0b445`
- Status: completed
- Classifier: `engine`: `openai/gpt-6-luna-20260922` on `azure/eu`
- Cases run: every case of the set
- Second model for refused requests (decision 033): `google/gemini-3.1-flash-lite` on `google-vertex/eu`
- Exclude mode: `heldout` (held-out examples kept out of retrieval: the reported number)
- Started: 2026-10-15T10:54:34.082508+00:00
- Model: openai/gpt-6-luna-20260922
- Cost: $0.4141, 2426742 tokens
- Groups with few cases are noisy: read each rate with its count.

| language | Cases | Risk-class accuracy | False-low-risk rate | Annex point accuracy | Role accuracy |
| --- | ---: | ---: | ---: | ---: | ---: |
| de | 21 | 95.2% (20/21) | 0.0% (0/21) | 100.0% (20/20) | 100.0% (21/21) |
| en | 27 | 81.5% (22/27) | 3.8% (1/26) | 100.0% (22/22) | 92.6% (25/27) |

#### Run f0e004fa-8f79-4c51-a9c7-6655a4529479 by language

- Benchmark: `appliedai`
- Commit: `6f5fa5024bb48d8e491c2f7642782a865fd0b445`
- Status: completed
- Classifier: `engine`: `openai/gpt-6-luna-20260922` on `azure/eu`
- Cases run: every case of the set
- Second model for refused requests (decision 033): `google/gemini-3.1-flash-lite` on `google-vertex/eu`
- Exclude mode: `heldout` (held-out examples kept out of retrieval: the reported number)
- Started: 2026-10-15T04:36:38.259839+00:00
- Model: openai/gpt-6-luna-20260922
- Cost: $0.8937, 5931283 tokens
- Groups with few cases are noisy: read each rate with its count.

| language | Cases | Risk-class accuracy | False-low-risk rate | Annex point accuracy | Role accuracy |
| --- | ---: | ---: | ---: | ---: | ---: |
| de | 106 | 62.7% (52/83) | 45.0% (9/20) | n/a (0/0) | n/a (0/0) |

#### Run a6de7ccb-1324-45ff-8eb0-52682e5677a5 by language

- Benchmark: `academic`
- Commit: `6f5fa5024bb48d8e491c2f7642782a865fd0b445`
- Status: completed
- Classifier: `engine`: `openai/gpt-6-luna-20260922` on `azure/eu`
- Cases run: every case of the set
- Second model for refused requests (decision 033): `google/gemini-3.1-flash-lite` on `google-vertex/eu`
- Exclude mode: `heldout` (held-out examples kept out of retrieval: the reported number)
- Started: 2026-10-15T05:10:51.832483+00:00
- Model: openai/gpt-6-luna-20260922
- Cost: $2.2177, 14453670 tokens
- Groups with few cases are noisy: read each rate with its count.

| language | Cases | Risk-class accuracy | False-low-risk rate | Annex point accuracy | Role accuracy |
| --- | ---: | ---: | ---: | ---: | ---: |
| en | 339 | 87.2% (293/336) | 11.3% (17/151) | n/a (0/0) | 90.0% (305/339) |


### Breakdowns of the baselines

#### Run b2b88c38-5f2d-438e-8741-7e234ebb6cc5 by area

- Benchmark: `commission_b`
- Commit: `6f5fa5024bb48d8e491c2f7642782a865fd0b445`
- Status: completed
- Classifier: `baseline_luna`: `openai/gpt-6-luna-20260922` on `azure/eu`
- Cases run: every case of the set
- Exclude mode: `heldout` (held-out examples kept out of retrieval: the reported number)
- Started: 2026-10-15T06:48:58.718299+00:00
- Model: openai/gpt-6-luna-20260922
- Cost: $0.1358, 375880 tokens
- Groups with few cases are noisy: read each rate with its count.

| area | Cases | Risk-class accuracy | False-low-risk rate | Annex point accuracy | Role accuracy |
| --- | ---: | ---: | ---: | ---: | ---: |
| annex_i | 6 | 83.3% (5/6) | 0.0% (0/4) | 25.0% (1/4) | 100.0% (6/6) |
| annex_iii_1 | 20 | 45.0% (9/20) | 0.0% (0/7) | 100.0% (5/5) | 95.0% (19/20) |
| annex_iii_2 | 13 | 53.8% (7/13) | 0.0% (0/5) | 100.0% (5/5) | 100.0% (13/13) |
| annex_iii_3 | 15 | 46.7% (7/15) | 0.0% (0/6) | 83.3% (5/6) | 100.0% (15/15) |
| annex_iii_4 | 16 | 62.5% (10/16) | 0.0% (0/7) | 100.0% (7/7) | 87.5% (14/16) |
| annex_iii_5 | 24 | 62.5% (15/24) | 0.0% (0/11) | 100.0% (11/11) | 100.0% (24/24) |
| annex_iii_6 | 24 | 66.7% (16/24) | 0.0% (0/8) | 71.4% (5/7) | 91.7% (22/24) |
| annex_iii_7 | 22 | 59.1% (13/22) | 0.0% (0/10) | 55.6% (5/9) | 100.0% (22/22) |
| annex_iii_8 | 13 | 83.3% (10/12) | 0.0% (0/3) | 100.0% (3/3) | 100.0% (12/12) |

#### Run bc908149-1726-49e2-ae14-67ffe7efae3a by area

- Benchmark: `commission_b`
- Commit: `6f5fa5024bb48d8e491c2f7642782a865fd0b445`
- Status: completed
- Classifier: `baseline_jev`: `typesafe/jev-1.13`
- Cases run: every case of the set
- Exclude mode: `heldout` (held-out examples kept out of retrieval: the reported number)
- Started: 2026-10-15T07:07:19.421730+00:00
- Model: typesafe/jev-1.13
- Cost: $0.0071, 197775 tokens
- Groups with few cases are noisy: read each rate with its count.

| area | Cases | Risk-class accuracy | False-low-risk rate | Annex point accuracy | Role accuracy |
| --- | ---: | ---: | ---: | ---: | ---: |
| annex_i | 6 | 100.0% (6/6) | 0.0% (0/4) | 0.0% (0/4) | 100.0% (6/6) |
| annex_iii_1 | 20 | 25.0% (5/20) | 57.1% (4/7) | 0.0% (0/2) | 90.0% (18/20) |
| annex_iii_2 | 13 | 61.5% (8/13) | 20.0% (1/5) | 0.0% (0/4) | 100.0% (13/13) |
| annex_iii_3 | 15 | 46.7% (7/15) | 16.7% (1/6) | 0.0% (0/5) | 93.3% (14/15) |
| annex_iii_4 | 16 | 75.0% (12/16) | 14.3% (1/7) | 0.0% (0/6) | 100.0% (16/16) |
| annex_iii_5 | 24 | 50.0% (12/24) | 0.0% (0/11) | 0.0% (0/11) | 91.7% (22/24) |
| annex_iii_6 | 24 | 37.5% (9/24) | 0.0% (0/8) | 0.0% (0/8) | 83.3% (20/24) |
| annex_iii_7 | 22 | 54.5% (12/22) | 10.0% (1/10) | 0.0% (0/9) | 95.5% (21/22) |
| annex_iii_8 | 13 | 58.3% (7/12) | 0.0% (0/3) | 0.0% (0/3) | 91.7% (11/12) |

#### Run 1e490e70-6606-436a-902a-a92157456f06 by business_function

- Benchmark: `own` (development cases: the engine's nodes were developed against them, so Commission Pile B carries the headline (decision 018))
- Commit: `6f5fa5024bb48d8e491c2f7642782a865fd0b445`
- Status: completed
- Classifier: `baseline_luna`: `openai/gpt-6-luna-20260922` on `azure/eu`
- Cases run: every case of the set
- Exclude mode: `heldout` (held-out examples kept out of retrieval: the reported number)
- Started: 2026-10-15T06:59:00.889103+00:00
- Model: openai/gpt-6-luna-20260922
- Cost: $0.0608, 180225 tokens
- Groups with few cases are noisy: read each rate with its count.

| business_function | Cases | Risk-class accuracy | False-low-risk rate | Annex point accuracy | Role accuracy |
| --- | ---: | ---: | ---: | ---: | ---: |
| consumer_product | 8 | 50.0% (4/8) | 0.0% (0/1) | n/a (0/0) | 83.3% (5/6) |
| content | 9 | 33.3% (3/9) | n/a (0/0) | n/a (0/0) | 44.4% (4/9) |
| customer_service | 7 | 100.0% (6/6) | 0.0% (0/1) | 100.0% (1/1) | 100.0% (6/6) |
| education | 3 | 100.0% (3/3) | 0.0% (0/2) | 100.0% (2/2) | 100.0% (3/3) |
| finance | 7 | 75.0% (3/4) | 0.0% (0/2) | 100.0% (2/2) | 100.0% (6/6) |
| healthcare | 5 | 100.0% (4/4) | 0.0% (0/4) | 75.0% (3/4) | 100.0% (5/5) |
| hr | 12 | 91.7% (11/12) | 0.0% (0/8) | 85.7% (6/7) | 90.0% (9/10) |
| marketing | 5 | 75.0% (3/4) | 0.0% (0/1) | n/a (0/0) | 60.0% (3/5) |
| operations | 7 | 50.0% (3/6) | 0.0% (0/1) | 0.0% (0/1) | 100.0% (6/6) |
| product_safety | 5 | 80.0% (4/5) | 0.0% (0/4) | 0.0% (0/4) | 80.0% (4/5) |
| productivity | 6 | 66.7% (4/6) | n/a (0/0) | n/a (0/0) | 83.3% (5/6) |
| public_services | 4 | 100.0% (4/4) | 0.0% (0/2) | 100.0% (1/1) | 100.0% (4/4) |
| research | 1 | 100.0% (1/1) | n/a (0/0) | n/a (0/0) | n/a (0/0) |
| sales | 2 | 100.0% (2/2) | 0.0% (0/2) | n/a (0/0) | 50.0% (1/2) |
| security | 4 | 100.0% (4/4) | 0.0% (0/3) | 100.0% (2/2) | 66.7% (2/3) |
| (none) | 3 | n/a (0/0) | n/a (0/0) | n/a (0/0) | n/a (0/0) |

#### Run dadf2f5a-32fd-4c14-9b2d-9ebbc4b33e06 by business_function

- Benchmark: `own` (development cases: the engine's nodes were developed against them, so Commission Pile B carries the headline (decision 018))
- Commit: `6f5fa5024bb48d8e491c2f7642782a865fd0b445`
- Status: completed
- Classifier: `baseline_jev`: `typesafe/jev-1.13`
- Cases run: every case of the set
- Exclude mode: `heldout` (held-out examples kept out of retrieval: the reported number)
- Started: 2026-10-15T07:07:35.213651+00:00
- Model: typesafe/jev-1.13
- Cost: $0.0041, 114489 tokens
- Groups with few cases are noisy: read each rate with its count.

| business_function | Cases | Risk-class accuracy | False-low-risk rate | Annex point accuracy | Role accuracy |
| --- | ---: | ---: | ---: | ---: | ---: |
| consumer_product | 8 | 50.0% (4/8) | 0.0% (0/1) | n/a (0/0) | 83.3% (5/6) |
| content | 9 | 88.9% (8/9) | 0.0% (0/3) | n/a (0/0) | 55.6% (5/9) |
| customer_service | 7 | 66.7% (4/6) | 100.0% (1/1) | n/a (0/0) | 100.0% (6/6) |
| education | 3 | 66.7% (2/3) | 0.0% (0/2) | 0.0% (0/2) | 66.7% (2/3) |
| finance | 7 | 75.0% (3/4) | 0.0% (0/2) | 0.0% (0/2) | 83.3% (5/6) |
| healthcare | 5 | 100.0% (4/4) | 0.0% (0/4) | 0.0% (0/4) | 100.0% (5/5) |
| hr | 12 | 83.3% (10/12) | 12.5% (1/8) | 0.0% (0/7) | 80.0% (8/10) |
| marketing | 5 | 75.0% (3/4) | 100.0% (1/1) | n/a (0/0) | 80.0% (4/5) |
| operations | 7 | 66.7% (4/6) | 100.0% (1/1) | n/a (0/0) | 100.0% (6/6) |
| product_safety | 5 | 80.0% (4/5) | 0.0% (0/4) | 0.0% (0/4) | 100.0% (5/5) |
| productivity | 6 | 83.3% (5/6) | n/a (0/0) | n/a (0/0) | 100.0% (6/6) |
| public_services | 4 | 50.0% (2/4) | 50.0% (1/2) | 0.0% (0/1) | 75.0% (3/4) |
| research | 1 | 100.0% (1/1) | n/a (0/0) | n/a (0/0) | n/a (0/0) |
| sales | 2 | 100.0% (2/2) | 0.0% (0/2) | n/a (0/0) | 0.0% (0/2) |
| security | 4 | 50.0% (2/4) | 33.3% (1/3) | 0.0% (0/1) | 33.3% (1/3) |
| (none) | 3 | n/a (0/0) | n/a (0/0) | n/a (0/0) | n/a (0/0) |


### Run reports (`aiact evaluate report`)

#### Run 31baa80c-f3bc-4eaf-93d0-4280b5fa14e7

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
- Case ids and expected labels: `eval/reports/pile_b/run-31baa80c-f3bc-4eaf-93d0-4280b5fa14e7.md` (Pile B's, kept out of this text: the Engine lane can't read that folder, V11)

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

Contaminated cases, flagged by docs/decisions/016-contaminated-pile-b-cases.md: 2 (named in the Pile B file)

| Metric | Value | Count |
| --- | ---: | ---: |
| Risk-class accuracy without the contaminated cases | 65.3% | 98/150 |

##### Provider refusals (decisions 029, 030, 033)

- Second model for refused requests: `google/gemini-3.1-flash-lite`
- Refused by the engine model: 3 of 147 (2.0%) (named in the Pile B file)
- Answered by the second model: 3 of 147 (2.0%) (named in the Pile B file)
- Refused by both (not assessed): 0 of 147 (0.0%)
- Second model's refusal rate: 0 of 3 (0.0%)
- Risk-class accuracy without the cases the second model answered: 65.1% (97/149)

Calls by the model that served them: `openai/gpt-6-luna` 899, `qwen/qwen3-embedding-8b` 634, `google/gemini-3.1-flash-lite` 3

##### Failures by step

- **scope** (4) (named in the Pile B file)
- **prohibited** (13) (named in the Pile B file)
- **high_risk** (16) (named in the Pile B file)
- **transparency** (16) (named in the Pile B file)
- **role_obligations** (1) (named in the Pile B file)
- **no result (the classifier failed)** (6) (named in the Pile B file)

##### Model-written texts

- Longest fact or question: 240 characters (cap 600)
- Facts: 912 over 147 results
- Follow-up questions: 1031 over 147 results

##### Judged metrics

- Judge: Jev `typesafe/jev-1.13`, backup `anthropic/claude-haiku-5.5` on `google-vertex/europe`, unsure margin 0.1 (decision 006)
- Cases judged: 147 of 147
- Judge cost: $0.0985, 1540396 tokens (not in the run's cost above)

| Metric | Value | Count | Not measured | Backup decided | Cost | Cost per item |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Citation support | 14.5% | 97/669 | 46 | 32 | $0.0819 | $0.000115 |
| Evidence-tag accuracy | 99.6% | 708/711 | 0 | 3 | $0.0166 | $0.000023 |

Not measured: the judge's reply was refused or broken, or the item was too long to send; never counted as a fail.

- No invented content: checked by code (P8a's `check_nothing_invented` on each document the results call for), not judged: 100.0%, 196/196 documents

#### Run 2d0ad2ce-6ef3-4ffb-b928-f441e17a7fe2

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
- Case ids and expected labels: `eval/reports/pile_b/run-2d0ad2ce-6ef3-4ffb-b928-f441e17a7fe2.md` (Pile B's, kept out of this text: the Engine lane can't read that folder, V11)

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

Contaminated cases, flagged by docs/decisions/016-contaminated-pile-b-cases.md: 2 (named in the Pile B file)

| Metric | Value | Count |
| --- | ---: | ---: |
| Risk-class accuracy without the contaminated cases | 70.7% | 106/150 |

##### Provider refusals (decisions 029, 030, 033)

- Second model for refused requests: `google/gemini-3.1-flash-lite`
- Refused by the engine model: 4 of 146 (2.7%) (named in the Pile B file)
- Answered by the second model: 4 of 146 (2.7%) (named in the Pile B file)
- Refused by both (not assessed): 0 of 146 (0.0%)
- Second model's refusal rate: 0 of 4 (0.0%)
- Risk-class accuracy without the cases the second model answered: 71.6% (106/148)

Calls by the model that served them: `openai/gpt-6-luna` 886, `qwen/qwen3-embedding-8b` 629, `google/gemini-3.1-flash-lite` 4

##### Failures by step

- **scope** (2) (named in the Pile B file)
- **prohibited** (12) (named in the Pile B file)
- **high_risk** (8) (named in the Pile B file)
- **transparency** (16) (named in the Pile B file)
- **no result (the classifier failed)** (7) (named in the Pile B file)

##### Model-written texts

- Longest fact or question: 288 characters (cap 600)
- Facts: 914 over 146 results
- Follow-up questions: 1021 over 146 results

Judged metrics: not judged yet (`aiact evaluate judged <run_id>`).

- No invented content: checked by code (P8a's `check_nothing_invented` on each document the results call for), not judged: 100.0%, 183/183 documents

#### Run d520e689-5c8b-463c-9155-42b2d7a2ab02

- Benchmark: `own` (development cases: the engine's nodes were developed against them, so Commission Pile B carries the headline (decision 018))
- Commit: `6f5fa5024bb48d8e491c2f7642782a865fd0b445`
- Status: completed
- Classifier: `engine`: `openai/gpt-6-luna-20260922` on `azure/eu`
- Cases run: every case of the set
- Second model for refused requests (decision 033): `google/gemini-3.1-flash-lite` on `google-vertex/eu`
- Exclude mode: `heldout` (held-out examples kept out of retrieval: the reported number)
- Started: 2026-10-15T02:43:33.856824+00:00
- Model: openai/gpt-6-luna-20260922
- Cost: $0.6555, 3713749 tokens
- Cases: 88 (0 failed)

| Metric | Value | Count |
| --- | ---: | ---: |
| Risk-class accuracy (development cases) | 84.6% | 66/78 |
| Not assessed (provider refused a check, decision 030) | 0 | |
| Risk-class accuracy, not-assessed cases counted as misses | 84.6% | 66/78 |
| False-low-risk rate | 0.0% | 0/34 |
| Annex point accuracy | 100.0% | 21/21 |
| Role accuracy | 82.9% | 63/76 |
| Legally ambiguous: precision | 16.7% | 1/6 |
| Legally ambiguous: recall | 50.0% | 1/2 |
| Ambiguous answered needs-more-information | 5 | |
| Needs more information: precision | 12.9% | 4/31 |
| Needs more information: recall | 80.0% | 4/5 |
| Downgrade rate (soft wording) | n/a | 0/0 |
| Basis accuracy (Commission cases) | n/a | 0/0 |
| Flip variant asked or flagged | n/a | 0/0 |
| Label citation cited (any of) | 96.5% | 82/85 |
| Needs a description: asked (thin cases) | 100.0% | 3/3 |
| Needs a description: asked wrongly (other cases) | 1.2% | 1/85 |
| Consistency | n/a | 0/0 |
| Citation existence (at run time) | 100.0% | 84/84 |
| appliedAI disagreement review | 0 | |
| Academic out-of-scope review | 0 | |

##### Provider refusals (decisions 029, 030, 033)

- Second model for refused requests: `google/gemini-3.1-flash-lite`
- Refused by the engine model: 8 of 88 (9.1%): own-c-01-undress-photo-app, own-c-02-undress-app-before-december, own-c-03-image-tool-with-safeguards, own-c-04-studio-digital-doubles-consent, own-c-05-gossip-site-fake-nudes, own-c-07-unfiltered-image-generator, own-c-14-kids-game-sad-pet-offers, own-e-03-talking-plush-toy
- Answered by the second model: 8 of 88 (9.1%): own-c-01-undress-photo-app, own-c-02-undress-app-before-december, own-c-03-image-tool-with-safeguards, own-c-04-studio-digital-doubles-consent, own-c-05-gossip-site-fake-nudes, own-c-07-unfiltered-image-generator, own-c-14-kids-game-sad-pet-offers, own-e-03-talking-plush-toy
- Refused by both (not assessed): 0 of 88 (0.0%)
- Second model's refusal rate: 0 of 8 (0.0%)
- Risk-class accuracy without the cases the second model answered: 84.3% (59/70)

Calls by the model that served them: `openai/gpt-6-luna` 449, `qwen/qwen3-embedding-8b` 327, `google/gemini-3.1-flash-lite` 14

##### Failures by step

- **facts** (1): own-c-03-image-tool-with-safeguards (answered with a description request)
- **scope** (1): own-b-04-card-game-opponent (expected out_of_scope, got limited_risk (legally_ambiguous))
- **prohibited** (6): own-a-05-vacuum-ad-synthetic-customers (expected limited_risk, got prohibited (needs_more_information)); own-a-06-satire-minister-sketches (expected limited_risk, got prohibited (needs_more_information)); own-c-18-car-sharing-driving-score (expected minimal_risk, got prohibited (needs_more_information)); own-d-02-retrained-credit-score (expected high_risk, got prohibited (needs_more_information)); own-d-04-warehouse-task-allocation (expected high_risk, got prohibited (needs_more_information)); own-f-06-pflegedienst-leistungsprofil (expected high_risk, got prohibited (needs_more_information))
- **high_risk** (1): own-f-07-water-mains-renewal-plan (expected minimal_risk, got high_risk (needs_more_information))
- **transparency** (3): own-c-06-dating-app-nudity-blur (expected minimal_risk, got limited_risk (legally_ambiguous)); own-e-13-wheelchair-obstacle-stop (expected minimal_risk, got limited_risk (decided)); own-f-04-gehaltsrunde-auswertung (expected minimal_risk, got limited_risk (needs_more_information))
- **role_obligations** (12): own-c-01-undress-photo-app (expected role provider, got none); own-c-05-gossip-site-fake-nudes (expected role deployer, got none); own-c-07-unfiltered-image-generator (expected role provider, got none); own-c-08-agent-voice-mood-scores (expected role deployer, got none); own-c-10-town-resident-points (expected role deployer, got none); own-c-12-face-search-crawler (expected role provider, got none); own-c-13-store-camera-lifestyle-segments (expected role provider, got none); own-c-14-kids-game-sad-pet-offers (expected role provider, got none); own-c-15-debt-collection-chat-pressure (expected role deployer, got none); own-c-20-fitnessclub-vertraeglichkeitswert (expected role deployer, got none); own-d-12-lender-extra-input (expected role provider, got deployer); own-e-02-lift-maintenance-forecast (expected role provider, got deployer)

##### Model-written texts

- Longest fact or question: 344 characters (cap 600)
- Facts: 588 over 88 results
- Follow-up questions: 484 over 88 results

##### Judged metrics

- Judge: Jev `typesafe/jev-1.13`, backup `anthropic/claude-haiku-5.5` on `google-vertex/europe`, unsure margin 0.1 (decision 006)
- Cases judged: 88 of 88
- Judge cost: $0.0605, 858197 tokens (not in the run's cost above)

| Metric | Value | Count | Not measured | Backup decided | Cost | Cost per item |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Citation support | 16.4% | 52/318 | 40 | 16 | $0.0496 | $0.000138 |
| Evidence-tag accuracy | 99.3% | 428/431 | 1 | 3 | $0.0109 | $0.000025 |

Not measured: the judge's reply was refused or broken, or the item was too long to send; never counted as a fail.

- No invented content: checked by code (P8a's `check_nothing_invented` on each document the results call for), not judged: 100.0%, 85/85 documents

#### Run 22bf99b1-0e18-42d9-b558-2a401b66415b

- Benchmark: `own` (development cases: the engine's nodes were developed against them, so Commission Pile B carries the headline (decision 018))
- Commit: `6f5fa5024bb48d8e491c2f7642782a865fd0b445`
- Status: completed
- Classifier: `engine`: `openai/gpt-6-luna-20260922` on `azure/eu`
- Cases run: every case of the set
- Second model for refused requests (decision 033): `google/gemini-3.1-flash-lite` on `google-vertex/eu`
- Exclude mode: `all` (the gap run: held-out examples retrievable, never the reported number; decision 012)
- Started: 2026-10-15T03:15:12.264872+00:00
- Model: openai/gpt-6-luna-20260922
- Cost: $0.6406, 3641139 tokens
- Cases: 88 (0 failed)

| Metric | Value | Count |
| --- | ---: | ---: |
| Risk-class accuracy (development cases) | 84.6% | 66/78 |
| Not assessed (provider refused a check, decision 030) | 0 | |
| Risk-class accuracy, not-assessed cases counted as misses | 84.6% | 66/78 |
| False-low-risk rate | 2.9% | 1/34 |
| Annex point accuracy | 95.0% | 19/20 |
| Role accuracy | 81.6% | 62/76 |
| Legally ambiguous: precision | 33.3% | 2/6 |
| Legally ambiguous: recall | 50.0% | 2/4 |
| Ambiguous answered needs-more-information | 3 | |
| Needs more information: precision | 12.9% | 4/31 |
| Needs more information: recall | 80.0% | 4/5 |
| Downgrade rate (soft wording) | n/a | 0/0 |
| Basis accuracy (Commission cases) | n/a | 0/0 |
| Flip variant asked or flagged | n/a | 0/0 |
| Label citation cited (any of) | 96.5% | 82/85 |
| Needs a description: asked (thin cases) | 100.0% | 3/3 |
| Needs a description: asked wrongly (other cases) | 1.2% | 1/85 |
| Consistency | n/a | 0/0 |
| Citation existence (at run time) | 100.0% | 84/84 |
| appliedAI disagreement review | 0 | |
| Academic out-of-scope review | 0 | |

##### Provider refusals (decisions 029, 030, 033)

- Second model for refused requests: `google/gemini-3.1-flash-lite`
- Refused by the engine model: 7 of 88 (8.0%): own-c-01-undress-photo-app, own-c-02-undress-app-before-december, own-c-03-image-tool-with-safeguards, own-c-04-studio-digital-doubles-consent, own-c-05-gossip-site-fake-nudes, own-c-07-unfiltered-image-generator, own-f-04-gehaltsrunde-auswertung
- Answered by the second model: 7 of 88 (8.0%): own-c-01-undress-photo-app, own-c-02-undress-app-before-december, own-c-03-image-tool-with-safeguards, own-c-04-studio-digital-doubles-consent, own-c-05-gossip-site-fake-nudes, own-c-07-unfiltered-image-generator, own-f-04-gehaltsrunde-auswertung
- Refused by both (not assessed): 0 of 88 (0.0%)
- Second model's refusal rate: 0 of 7 (0.0%)
- Risk-class accuracy without the cases the second model answered: 85.9% (61/71)

Calls by the model that served them: `openai/gpt-6-luna` 441, `qwen/qwen3-embedding-8b` 319, `google/gemini-3.1-flash-lite` 12

##### Failures by step

- **facts** (1): own-c-03-image-tool-with-safeguards (answered with a description request)
- **scope** (2): own-d-04-warehouse-task-allocation (expected high_risk, got out_of_scope (decided)); own-f-02-tafel-kundenausweis (expected minimal_risk, got out_of_scope (decided))
- **prohibited** (6): own-a-05-vacuum-ad-synthetic-customers (expected limited_risk, got prohibited (needs_more_information)); own-a-06-satire-minister-sketches (expected limited_risk, got prohibited (needs_more_information)); own-c-16-police-live-search-missing-child (expected high_risk, got prohibited (needs_more_information)); own-c-18-car-sharing-driving-score (expected minimal_risk, got prohibited (needs_more_information)); own-d-10-rebranded-health-pricing (expected high_risk, got prohibited (needs_more_information)); own-f-06-pflegedienst-leistungsprofil (expected high_risk, got prohibited (needs_more_information))
- **high_risk** (2): own-e-08-heart-rhythm-app (Annex point annex:III:1:b); own-f-07-water-mains-renewal-plan (expected minimal_risk, got high_risk (needs_more_information))
- **transparency** (2): own-c-06-dating-app-nudity-blur (expected minimal_risk, got limited_risk (legally_ambiguous)); own-f-04-gehaltsrunde-auswertung (expected minimal_risk, got limited_risk (needs_more_information))
- **role_obligations** (10): own-a-09-newsroom-reviewed-drafts (expected role deployer, got provider); own-c-01-undress-photo-app (expected role provider, got none); own-c-05-gossip-site-fake-nudes (expected role deployer, got none); own-c-07-unfiltered-image-generator (expected role provider, got none); own-c-08-agent-voice-mood-scores (expected role deployer, got none); own-c-10-town-resident-points (expected role deployer, got none); own-c-11-police-burglary-risk-list (expected role deployer, got none); own-c-12-face-search-crawler (expected role provider, got none); own-c-14-kids-game-sad-pet-offers (expected role provider, got none); own-c-20-fitnessclub-vertraeglichkeitswert (expected role deployer, got none)

##### Model-written texts

- Longest fact or question: 560 characters (cap 600)
- Facts: 564 over 88 results
- Follow-up questions: 482 over 88 results

Judged metrics: not judged yet (`aiact evaluate judged <run_id>`).

- No invented content: checked by code (P8a's `check_nothing_invented` on each document the results call for), not judged: 100.0%, 97/97 documents

#### Run c1746ef0-d8bf-4caa-84a0-b93a552dc99f

- Benchmark: `soft_pairs`
- Commit: `6f5fa5024bb48d8e491c2f7642782a865fd0b445`
- Status: completed
- Classifier: `engine`: `openai/gpt-6-luna-20260922` on `azure/eu`
- Cases run: every case of the set
- Second model for refused requests (decision 033): `google/gemini-3.1-flash-lite` on `google-vertex/eu`
- Exclude mode: `heldout` (held-out examples kept out of retrieval: the reported number)
- Started: 2026-10-15T03:43:00.348920+00:00
- Model: openai/gpt-6-luna-20260922
- Cost: $0.2020, 1206419 tokens
- Cases: 24 (0 failed)

| Metric | Value | Count |
| --- | ---: | ---: |
| Risk-class accuracy | 66.7% | 16/24 |
| Not assessed (provider refused a check, decision 030) | 0 | |
| Risk-class accuracy, not-assessed cases counted as misses | 66.7% | 16/24 |
| False-low-risk rate | 16.7% | 4/24 |
| Annex point accuracy | 100.0% | 16/16 |
| Role accuracy | 100.0% | 24/24 |
| Legally ambiguous: precision | 0.0% | 0/3 |
| Legally ambiguous: recall | n/a | 0/0 |
| Ambiguous answered needs-more-information | 0 | |
| Needs more information: precision | 0.0% | 0/14 |
| Needs more information: recall | n/a | 0/0 |
| Downgrade rate (soft wording) | 25.0% | 3/12 |
| Basis accuracy (Commission cases) | n/a | 0/0 |
| Flip variant asked or flagged | n/a | 0/0 |
| Label citation cited (any of) | 100.0% | 24/24 |
| Needs a description: asked (thin cases) | n/a | 0/0 |
| Needs a description: asked wrongly (other cases) | 0.0% | 0/24 |
| Consistency | n/a | 0/0 |
| Citation existence (at run time) | 100.0% | 24/24 |
| appliedAI disagreement review | 0 | |
| Academic out-of-scope review | 0 | |

##### Provider refusals (decisions 029, 030, 033)

- Second model for refused requests: `google/gemini-3.1-flash-lite`
- Refused by the engine model: 0 of 24 (0.0%)
- Answered by the second model: 0 of 24 (0.0%)
- Refused by both (not assessed): 0 of 24 (0.0%)
- Second model's refusal rate: 0 of 0 (n/a)
- Risk-class accuracy without the cases the second model answered: 66.7% (16/24)

Calls by the model that served them: `openai/gpt-6-luna` 144, `qwen/qwen3-embedding-8b` 106

##### Failures by step

- **prohibited** (4): soft-02-cleaning-staff-scores-plain (expected high_risk, got prohibited (legally_ambiguous)); soft-08-spedition-fahrstil-noten-plain (expected high_risk, got prohibited (needs_more_information)); soft-08-spedition-fahrstil-noten-soft (expected high_risk, got prohibited (needs_more_information)); soft-12-mobilfunk-ratenkauf-plain (expected high_risk, got prohibited (legally_ambiguous))
- **high_risk** (4): soft-07-insurance-ombudsman-drafts-plain (expected high_risk, got limited_risk (decided)); soft-07-insurance-ombudsman-drafts-soft (expected high_risk, got limited_risk (needs_more_information)); soft-09-zahnzusatz-wartezeiten-soft (expected high_risk, got minimal_risk (needs_more_information)); soft-11-klinikverbund-pflege-bewerbungen-soft (expected high_risk, got limited_risk (needs_more_information))

##### Model-written texts

- Longest fact or question: 286 characters (cap 600)
- Facts: 133 over 24 results
- Follow-up questions: 197 over 24 results

Judged metrics: not judged yet (`aiact evaluate judged <run_id>`).

- No invented content: checked by code (P8a's `check_nothing_invented` on each document the results call for), not judged: 100.0%, 53/53 documents

#### Run 1ff04bc9-4425-4898-b81b-43f2bdcc1325

- Benchmark: `soft_pairs`
- Commit: `6f5fa5024bb48d8e491c2f7642782a865fd0b445`
- Status: completed
- Classifier: `engine`: `openai/gpt-6-luna-20260922` on `azure/eu`
- Cases run: every case of the set
- Second model for refused requests (decision 033): `google/gemini-3.1-flash-lite` on `google-vertex/eu`
- Exclude mode: `heldout` (held-out examples kept out of retrieval: the reported number)
- Answers: the stored key-fact answers to the questions run `c1746ef0-d8bf-4caa-84a0-b93a552dc99f` asked, any other question answered "don't know" (decision 019)
- Started: 2026-10-15T04:27:14.433811+00:00
- Model: openai/gpt-6-luna-20260922
- Cost: $0.2184, 1285274 tokens
- Cases: 24 (1 failed)

| Metric | Value | Count |
| --- | ---: | ---: |
| Risk-class accuracy | 62.5% | 15/24 |
| Not assessed (provider refused a check, decision 030) | 0 | |
| Risk-class accuracy, not-assessed cases counted as misses | 62.5% | 15/24 |
| False-low-risk rate | 4.3% | 1/23 |
| Annex point accuracy | 100.0% | 15/15 |
| Role accuracy | 95.8% | 23/24 |
| Legally ambiguous: precision | 0.0% | 0/1 |
| Legally ambiguous: recall | n/a | 0/0 |
| Ambiguous answered needs-more-information | 0 | |
| Needs more information: precision | 0.0% | 0/15 |
| Needs more information: recall | n/a | 0/0 |
| Downgrade rate (soft wording) | 8.3% | 1/12 |
| Basis accuracy (Commission cases) | n/a | 0/0 |
| Flip variant asked or flagged | n/a | 0/0 |
| Label citation cited (any of) | 100.0% | 23/23 |
| Needs a description: asked (thin cases) | n/a | 0/0 |
| Needs a description: asked wrongly (other cases) | 0.0% | 0/23 |
| Consistency | n/a | 0/0 |
| Citation existence (at run time) | 100.0% | 23/23 |
| appliedAI disagreement review | 0 | |
| Academic out-of-scope review | 0 | |

##### Provider refusals (decisions 029, 030, 033)

- Second model for refused requests: `google/gemini-3.1-flash-lite`
- Refused by the engine model: 1 of 23 (4.3%): soft-01-garden-centre-applications-soft
- Answered by the second model: 1 of 23 (4.3%): soft-01-garden-centre-applications-soft
- Refused by both (not assessed): 0 of 23 (0.0%)
- Second model's refusal rate: 0 of 1 (0.0%)
- Risk-class accuracy without the cases the second model answered: 60.9% (14/23)

Calls by the model that served them: `openai/gpt-6-luna` 144, `qwen/qwen3-embedding-8b` 106, `google/gemini-3.1-flash-lite` 1

##### Failures by step

- **prohibited** (7): soft-02-cleaning-staff-scores-plain (expected high_risk, got prohibited (legally_ambiguous)); soft-05-conservatory-pre-auditions-soft (expected high_risk, got prohibited (needs_more_information)); soft-08-spedition-fahrstil-noten-plain (expected high_risk, got prohibited (needs_more_information)); soft-08-spedition-fahrstil-noten-soft (expected high_risk, got prohibited (needs_more_information)); soft-09-zahnzusatz-wartezeiten-plain (expected high_risk, got prohibited (needs_more_information)); soft-10-elterngeld-rueckforderung-soft (expected high_risk, got prohibited (needs_more_information)); soft-11-klinikverbund-pflege-bewerbungen-plain (expected high_risk, got prohibited (needs_more_information))
- **high_risk** (1): soft-07-insurance-ombudsman-drafts-soft (expected high_risk, got limited_risk (needs_more_information))
- **no result (the classifier failed)** (1): soft-03-car-leasing-scores-plain (no result)

##### Model-written texts

- Longest fact or question: 287 characters (cap 600)
- Facts: 147 over 23 results
- Follow-up questions: 203 over 23 results

Judged metrics: not judged yet (`aiact evaluate judged <run_id>`).

- No invented content: checked by code (P8a's `check_nothing_invented` on each document the results call for), not judged: 100.0%, 51/51 documents

#### Run 76a3d43e-5f0e-4e17-9e65-8d5534cd85e2

- Benchmark: `consistency`
- Commit: `6f5fa5024bb48d8e491c2f7642782a865fd0b445`
- Status: completed
- Classifier: `engine`: `openai/gpt-6-luna-20260922` on `azure/eu`
- Cases run: every case of the set
- Second model for refused requests (decision 033): `google/gemini-3.1-flash-lite` on `google-vertex/eu`
- Exclude mode: `heldout` (held-out examples kept out of retrieval: the reported number)
- Started: 2026-10-15T03:52:25.940070+00:00
- Model: openai/gpt-6-luna-20260922
- Cost: $0.2006, 1260509 tokens
- Cases: 30 (0 failed)

| Metric | Value | Count |
| --- | ---: | ---: |
| Risk-class accuracy | 90.0% | 27/30 |
| Not assessed (provider refused a check, decision 030) | 0 | |
| Risk-class accuracy, not-assessed cases counted as misses | 90.0% | 27/30 |
| False-low-risk rate | 0.0% | 0/18 |
| Annex point accuracy | 100.0% | 12/12 |
| Role accuracy | 88.9% | 24/27 |
| Legally ambiguous: precision | n/a | 0/0 |
| Legally ambiguous: recall | n/a | 0/0 |
| Ambiguous answered needs-more-information | 0 | |
| Needs more information: precision | 0.0% | 0/5 |
| Needs more information: recall | n/a | 0/0 |
| Downgrade rate (soft wording) | n/a | 0/0 |
| Basis accuracy (Commission cases) | n/a | 0/0 |
| Flip variant asked or flagged | n/a | 0/0 |
| Label citation cited (any of) | 100.0% | 30/30 |
| Needs a description: asked (thin cases) | n/a | 0/0 |
| Needs a description: asked wrongly (other cases) | 0.0% | 0/30 |
| Consistency | 100.0% | 10/10 |
| Citation existence (at run time) | 100.0% | 30/30 |
| appliedAI disagreement review | 0 | |
| Academic out-of-scope review | 0 | |

##### Provider refusals (decisions 029, 030, 033)

- Second model for refused requests: `google/gemini-3.1-flash-lite`
- Refused by the engine model: 1 of 30 (3.3%): cons-09-stadthotels-zimmerpreise-c
- Answered by the second model: 1 of 30 (3.3%): cons-09-stadthotels-zimmerpreise-c
- Refused by both (not assessed): 0 of 30 (0.0%)
- Second model's refusal rate: 0 of 1 (0.0%)
- Risk-class accuracy without the cases the second model answered: 89.7% (26/29)

Calls by the model that served them: `openai/gpt-6-luna` 159, `qwen/qwen3-embedding-8b` 114, `google/gemini-3.1-flash-lite` 1

##### Failures by step

- **prohibited** (3): cons-06-courier-offboarding-scores-a (expected high_risk, got prohibited (needs_more_information)); cons-06-courier-offboarding-scores-b (expected high_risk, got prohibited (needs_more_information)); cons-06-courier-offboarding-scores-c (expected high_risk, got prohibited (needs_more_information))
- **role_obligations** (3): cons-03-meeting-webcam-moods-a (expected role deployer, got none); cons-03-meeting-webcam-moods-b (expected role deployer, got none); cons-03-meeting-webcam-moods-c (expected role deployer, got none)

##### Model-written texts

- Longest fact or question: 169 characters (cap 600)
- Facts: 220 over 30 results
- Follow-up questions: 129 over 30 results

Judged metrics: not judged yet (`aiact evaluate judged <run_id>`).

- No invented content: checked by code (P8a's `check_nothing_invented` on each document the results call for), not judged: 100.0%, 41/41 documents

#### Run 983fda65-4fdf-4afb-b553-bc0280c9ff49

- Benchmark: `annex_match`
- Commit: `6f5fa5024bb48d8e491c2f7642782a865fd0b445`
- Status: completed
- Classifier: `engine`: `openai/gpt-6-luna-20260922` on `azure/eu`
- Cases run: every case of the set
- Second model for refused requests (decision 033): `google/gemini-3.1-flash-lite` on `google-vertex/eu`
- Exclude mode: `heldout` (held-out examples kept out of retrieval: the reported number)
- Started: 2026-10-15T04:00:59.617638+00:00
- Model: openai/gpt-6-luna-20260922
- Cost: $0.4191, 2447061 tokens
- Cases: 48 (0 failed)

| Metric | Value | Count |
| --- | ---: | ---: |
| Risk-class accuracy | 87.5% | 42/48 |
| Not assessed (provider refused a check, decision 030) | 0 | |
| Risk-class accuracy, not-assessed cases counted as misses | 87.5% | 42/48 |
| False-low-risk rate | 0.0% | 0/48 |
| Annex point accuracy | 97.6% | 41/42 |
| Role accuracy | 97.9% | 47/48 |
| Legally ambiguous: precision | 0.0% | 0/2 |
| Legally ambiguous: recall | n/a | 0/0 |
| Ambiguous answered needs-more-information | 0 | |
| Needs more information: precision | 0.0% | 0/12 |
| Needs more information: recall | n/a | 0/0 |
| Downgrade rate (soft wording) | n/a | 0/0 |
| Basis accuracy (Commission cases) | n/a | 0/0 |
| Flip variant asked or flagged | n/a | 0/0 |
| Label citation cited (any of) | 100.0% | 48/48 |
| Needs a description: asked (thin cases) | n/a | 0/0 |
| Needs a description: asked wrongly (other cases) | 0.0% | 0/48 |
| Consistency | n/a | 0/0 |
| Citation existence (at run time) | 100.0% | 48/48 |
| appliedAI disagreement review | 0 | |
| Academic out-of-scope review | 0 | |

##### Provider refusals (decisions 029, 030, 033)

- Second model for refused requests: `google/gemini-3.1-flash-lite`
- Refused by the engine model: 1 of 48 (2.1%): annex-match-01-police-footage-face-search
- Answered by the second model: 1 of 48 (2.1%): annex-match-01-police-footage-face-search
- Refused by both (not assessed): 0 of 48 (0.0%)
- Second model's refusal rate: 0 of 1 (0.0%)
- Risk-class accuracy without the cases the second model answered: 87.2% (41/47)

Calls by the model that served them: `openai/gpt-6-luna` 291, `qwen/qwen3-embedding-8b` 213, `google/gemini-3.1-flash-lite` 1

##### Failures by step

- **prohibited** (6): annex-match-07-business-school-admissions (expected high_risk, got prohibited (needs_more_information)); annex-match-13-lager-bewerbungen-punkte (expected high_risk, got prohibited (needs_more_information)); annex-match-14-job-ad-audience-targeting (expected high_risk, got prohibited (legally_ambiguous)); annex-match-15-restructuring-redundancy-list (expected high_risk, got prohibited (needs_more_information)); annex-match-21-online-health-premium (expected high_risk, got prohibited (needs_more_information)); annex-match-28-football-match-offending-risk (expected high_risk, got prohibited (legally_ambiguous))
- **high_risk** (1): annex-match-27-dna-mixture-likelihood (Annex point annex:III:6:e)
- **role_obligations** (1): annex-match-35-court-draft-judgments (expected role deployer, got provider)

##### Model-written texts

- Longest fact or question: 234 characters (cap 600)
- Facts: 319 over 48 results
- Follow-up questions: 390 over 48 results

Judged metrics: not judged yet (`aiact evaluate judged <run_id>`).

- No invented content: checked by code (P8a's `check_nothing_invented` on each document the results call for), not judged: 100.0%, 124/124 documents

#### Run 592089b8-1585-4f8f-a108-9d4ebbe8f38a

- Benchmark: `head_to_head` (the head-to-head draw: own development cases and Commission Pile B cases together, so this accuracy mixes the two; the per-set scores are in `eval/reports/pile_b/head_to_head.md`)
- Commit: `6f5fa5024bb48d8e491c2f7642782a865fd0b445`
- Status: completed
- Classifier: `engine`: `openai/gpt-6-luna-20260922` on `azure/eu`
- Cases run: every case of the set
- Second model for refused requests (decision 033): `google/gemini-3.1-flash-lite` on `google-vertex/eu`
- Exclude mode: `heldout` (held-out examples kept out of retrieval: the reported number)
- Started: 2026-10-15T04:19:59.071344+00:00
- Model: openai/gpt-6-luna-20260922
- Cost: $0.1834, 897298 tokens
- Cases: 25 (0 failed)
- Case ids and expected labels: `eval/reports/pile_b/run-592089b8-1585-4f8f-a108-9d4ebbe8f38a.md` (Pile B's, kept out of this text: the Engine lane can't read that folder, V11)

| Metric | Value | Count |
| --- | ---: | ---: |
| Risk-class accuracy | 76.0% | 19/25 |
| Not assessed (provider refused a check, decision 030) | 0 | |
| Risk-class accuracy, not-assessed cases counted as misses | 76.0% | 19/25 |
| False-low-risk rate | 0.0% | 0/10 |
| Annex point accuracy | 100.0% | 5/5 |
| Role accuracy | 65.0% | 13/20 |
| Legally ambiguous: precision | 0.0% | 0/1 |
| Legally ambiguous: recall | n/a | 0/0 |
| Ambiguous answered needs-more-information | 0 | |
| Needs more information: precision | 0.0% | 0/8 |
| Needs more information: recall | n/a | 0/0 |
| Downgrade rate (soft wording) | n/a | 0/0 |
| Basis accuracy (Commission cases) | 100.0% | 6/6 |
| Flip variant asked or flagged | n/a | 0/0 |
| Label citation cited (any of) | 88.0% | 22/25 |
| Needs a description: asked (thin cases) | n/a | 0/0 |
| Needs a description: asked wrongly (other cases) | 0.0% | 0/25 |
| Consistency | n/a | 0/0 |
| Citation existence (at run time) | 100.0% | 25/25 |
| appliedAI disagreement review | 0 | |
| Academic out-of-scope review | 0 | |

##### Provider refusals (decisions 029, 030, 033)

- Second model for refused requests: `google/gemini-3.1-flash-lite`
- Refused by the engine model: 6 of 25 (24.0%) (named in the Pile B file)
- Answered by the second model: 6 of 25 (24.0%) (named in the Pile B file)
- Refused by both (not assessed): 0 of 25 (0.0%)
- Second model's refusal rate: 0 of 6 (0.0%)
- Risk-class accuracy without the cases the second model answered: 73.7% (14/19)

Calls by the model that served them: `openai/gpt-6-luna` 112, `qwen/qwen3-embedding-8b` 72, `google/gemini-3.1-flash-lite` 10

##### Failures by step

- **scope** (3) (named in the Pile B file)
- **prohibited** (1) (named in the Pile B file)
- **transparency** (2) (named in the Pile B file)
- **role_obligations** (5) (named in the Pile B file)

##### Model-written texts

- Longest fact or question: 229 characters (cap 600)
- Facts: 164 over 25 results
- Follow-up questions: 147 over 25 results

Judged metrics: not judged yet (`aiact evaluate judged <run_id>`).

- No invented content: checked by code (P8a's `check_nothing_invented` on each document the results call for), not judged: 100.0%, 26/26 documents

#### Run f0e004fa-8f79-4c51-a9c7-6655a4529479

- Benchmark: `appliedai`
- Commit: `6f5fa5024bb48d8e491c2f7642782a865fd0b445`
- Status: completed
- Classifier: `engine`: `openai/gpt-6-luna-20260922` on `azure/eu`
- Cases run: every case of the set
- Second model for refused requests (decision 033): `google/gemini-3.1-flash-lite` on `google-vertex/eu`
- Exclude mode: `heldout` (held-out examples kept out of retrieval: the reported number)
- Started: 2026-10-15T04:36:38.259839+00:00
- Model: openai/gpt-6-luna-20260922
- Cost: $0.8937, 5931283 tokens
- Cases: 106 (0 failed)

| Metric | Value | Count |
| --- | ---: | ---: |
| Risk-class accuracy | 62.7% | 52/83 |
| Not assessed (provider refused a check, decision 030) | 0 | |
| Risk-class accuracy, not-assessed cases counted as misses | 62.7% | 52/83 |
| False-low-risk rate | 45.0% | 9/20 |
| Annex point accuracy | n/a | 0/0 |
| Role accuracy | n/a | 0/0 |
| Legally ambiguous: precision | 25.0% | 1/4 |
| Legally ambiguous: recall | 5.3% | 1/19 |
| Ambiguous answered needs-more-information | 23 | |
| Needs more information: precision | 0.0% | 0/27 |
| Needs more information: recall | n/a | 0/0 |
| Downgrade rate (soft wording) | n/a | 0/0 |
| Basis accuracy (Commission cases) | n/a | 0/0 |
| Flip variant asked or flagged | n/a | 0/0 |
| Label citation cited (any of) | n/a | 0/0 |
| Needs a description: asked (thin cases) | n/a | 0/0 |
| Needs a description: asked wrongly (other cases) | 0.0% | 0/106 |
| Consistency | n/a | 0/0 |
| Citation existence (at run time) | 100.0% | 106/106 |
| appliedAI disagreement review | 55 | |
| Academic out-of-scope review | 0 | |

##### Provider refusals (decisions 029, 030, 033)

- Second model for refused requests: `google/gemini-3.1-flash-lite`
- Refused by the engine model: 2 of 106 (1.9%): aai-004, aai-094
- Answered by the second model: 2 of 106 (1.9%): aai-004, aai-094
- Refused by both (not assessed): 0 of 106 (0.0%)
- Second model's refusal rate: 0 of 2 (0.0%)
- Risk-class accuracy without the cases the second model answered: 63.0% (51/81)

Calls by the model that served them: `openai/gpt-6-luna` 635, `qwen/qwen3-embedding-8b` 526, `google/gemini-3.1-flash-lite` 2

##### Failures by step

- **prohibited** (2): aai-010 (expected high_risk, got prohibited (needs_more_information)); aai-093 (expected prohibited, got high_risk (needs_more_information))
- **high_risk** (11): aai-007 (expected high_risk, got minimal_risk (needs_more_information)); aai-013 (expected minimal_risk, got high_risk (needs_more_information)); aai-019 (expected minimal_risk, got high_risk (needs_more_information)); aai-035 (expected high_risk, got minimal_risk (needs_more_information)); aai-042 (expected high_risk, got minimal_risk (needs_more_information)); aai-046 (expected high_risk, got minimal_risk (decided)); aai-055 (expected high_risk, got limited_risk (needs_more_information)); aai-088 (expected high_risk, got minimal_risk (decided)); aai-091 (expected minimal_risk, got high_risk (needs_more_information)); aai-092 (expected high_risk, got minimal_risk (decided)); aai-107 (expected high_risk, got minimal_risk (decided))
- **uncertain status (appliedAI unclear)** (18): aai-008 (expected none, got limited_risk (decided)); aai-017 (expected none, got minimal_risk (decided)); aai-020 (expected none, got limited_risk (decided)); aai-024 (expected none, got minimal_risk (decided)); aai-025 (expected none, got minimal_risk (decided)); aai-044 (expected none, got limited_risk (decided)); aai-054 (expected none, got minimal_risk (decided)); aai-057 (expected none, got minimal_risk (decided)); aai-058 (expected none, got minimal_risk (decided)); aai-074 (expected none, got minimal_risk (decided)); aai-084 (expected none, got minimal_risk (decided)); aai-087 (expected none, got minimal_risk (decided)); aai-089 (expected none, got minimal_risk (decided)); aai-090 (expected none, got minimal_risk (decided)); aai-094 (expected none, got minimal_risk (decided)); aai-101 (expected none, got minimal_risk (decided)); aai-109 (expected none, got minimal_risk (decided)); aai-112 (expected none, got minimal_risk (decided))

##### Model-written texts

- Longest fact or question: 343 characters (cap 600)
- Facts: 599 over 106 results
- Follow-up questions: 855 over 106 results

Judged metrics: not judged yet (`aiact evaluate judged <run_id>`).

- No invented content: checked by code (P8a's `check_nothing_invented` on each document the results call for), not judged: 100.0%, 71/71 documents

#### Run a6de7ccb-1324-45ff-8eb0-52682e5677a5

- Benchmark: `academic`
- Commit: `6f5fa5024bb48d8e491c2f7642782a865fd0b445`
- Status: completed
- Classifier: `engine`: `openai/gpt-6-luna-20260922` on `azure/eu`
- Cases run: every case of the set
- Second model for refused requests (decision 033): `google/gemini-3.1-flash-lite` on `google-vertex/eu`
- Exclude mode: `heldout` (held-out examples kept out of retrieval: the reported number)
- Started: 2026-10-15T05:10:51.832483+00:00
- Model: openai/gpt-6-luna-20260922
- Cost: $2.2177, 14453670 tokens
- Cases: 339 (0 failed)

| Metric | Value | Count |
| --- | ---: | ---: |
| Risk-class accuracy | 87.2% | 293/336 |
| Not assessed (provider refused a check, decision 030) | 0 | |
| Risk-class accuracy, not-assessed cases counted as misses | 87.2% | 293/336 |
| False-low-risk rate | 11.3% | 17/151 |
| Annex point accuracy | n/a | 0/0 |
| Role accuracy | 90.0% | 305/339 |
| Legally ambiguous: precision | 0.0% | 0/29 |
| Legally ambiguous: recall | n/a | 0/0 |
| Ambiguous answered needs-more-information | 3 | |
| Needs more information: precision | 0.0% | 0/167 |
| Needs more information: recall | n/a | 0/0 |
| Downgrade rate (soft wording) | n/a | 0/0 |
| Basis accuracy (Commission cases) | n/a | 0/0 |
| Flip variant asked or flagged | n/a | 0/0 |
| Label citation cited (any of) | 100.0% | 4/4 |
| Needs a description: asked (thin cases) | n/a | 0/0 |
| Needs a description: asked wrongly (other cases) | 0.9% | 3/339 |
| Consistency | n/a | 0/0 |
| Citation existence (at run time) | 100.0% | 336/336 |
| appliedAI disagreement review | 0 | |
| Academic out-of-scope review | 4 | |

##### Provider refusals (decisions 029, 030, 033)

- Second model for refused requests: `google/gemini-3.1-flash-lite`
- Refused by the engine model: 3 of 339 (0.9%): academic-0135, academic-0329, academic-0339
- Answered by the second model: 3 of 339 (0.9%): academic-0135, academic-0329, academic-0339
- Refused by both (not assessed): 0 of 339 (0.0%)
- Second model's refusal rate: 0 of 3 (0.0%)
- Risk-class accuracy without the cases the second model answered: 87.1% (290/333)

Calls by the model that served them: `openai/gpt-6-luna` 1930, `qwen/qwen3-embedding-8b` 1276, `google/gemini-3.1-flash-lite` 3

##### Failures by step

- **facts** (3): academic-0131 (answered with a description request); academic-0139 (answered with a description request); academic-0260 (answered with a description request)
- **scope** (2): academic-0185 (expected limited_risk, got out_of_scope (decided)); academic-0209 (expected limited_risk, got out_of_scope (decided))
- **prohibited** (32): academic-0040 (expected prohibited, got minimal_risk (decided)); academic-0043 (expected prohibited, got minimal_risk (decided)); academic-0044 (expected prohibited, got minimal_risk (needs_more_information)); academic-0047 (expected prohibited, got high_risk (decided)); academic-0052 (expected prohibited, got high_risk (decided)); academic-0059 (expected prohibited, got high_risk (needs_more_information)); academic-0060 (expected prohibited, got high_risk (decided)); academic-0061 (expected prohibited, got high_risk (decided)); academic-0062 (expected prohibited, got high_risk (decided)); academic-0063 (expected prohibited, got high_risk (decided)); academic-0065 (expected prohibited, got high_risk (decided)); academic-0067 (expected prohibited, got limited_risk (needs_more_information)); academic-0069 (expected prohibited, got high_risk (decided)); academic-0070 (expected prohibited, got high_risk (decided)); academic-0072 (expected high_risk, got prohibited (needs_more_information)); academic-0075 (expected high_risk, got prohibited (needs_more_information)); academic-0080 (expected high_risk, got prohibited (needs_more_information)); academic-0085 (expected high_risk, got prohibited (needs_more_information)); academic-0089 (expected high_risk, got prohibited (needs_more_information)); academic-0091 (expected high_risk, got prohibited (needs_more_information)); academic-0094 (expected high_risk, got prohibited (needs_more_information)); academic-0096 (expected high_risk, got prohibited (needs_more_information)); academic-0097 (expected high_risk, got prohibited (needs_more_information)); academic-0099 (expected high_risk, got prohibited (needs_more_information)); academic-0106 (expected high_risk, got prohibited (needs_more_information)); academic-0107 (expected high_risk, got prohibited (needs_more_information)); academic-0110 (expected high_risk, got prohibited (needs_more_information)); academic-0112 (expected high_risk, got prohibited (needs_more_information)); academic-0122 (expected high_risk, got prohibited (needs_more_information)); academic-0140 (expected high_risk, got prohibited (needs_more_information)); academic-0146 (expected high_risk, got prohibited (needs_more_information)); academic-0154 (expected high_risk, got prohibited (needs_more_information))
- **high_risk** (6): academic-0108 (expected high_risk, got minimal_risk (decided)); academic-0142 (expected high_risk, got minimal_risk (decided)); academic-0147 (expected high_risk, got minimal_risk (decided)); academic-0162 (expected limited_risk, got high_risk (needs_more_information)); academic-0224 (expected limited_risk, got high_risk (needs_more_information)); academic-0237 (expected limited_risk, got high_risk (needs_more_information))
- **role_obligations** (29): academic-0019 (expected role provider, got none); academic-0020 (expected role deployer, got none); academic-0021 (expected role provider, got none); academic-0022 (expected role deployer, got none); academic-0026 (expected role deployer, got none); academic-0027 (expected role provider, got none); academic-0028 (expected role deployer, got none); academic-0029 (expected role provider, got none); academic-0033 (expected role provider, got none); academic-0034 (expected role deployer, got none); academic-0036 (expected role deployer, got none); academic-0037 (expected role provider, got none); academic-0038 (expected role deployer, got none); academic-0039 (expected role provider, got none); academic-0045 (expected role provider, got none); academic-0046 (expected role deployer, got none); academic-0049 (expected role provider, got none); academic-0050 (expected role deployer, got none); academic-0053 (expected role provider, got none); academic-0054 (expected role deployer, got none); academic-0055 (expected role provider, got none); academic-0056 (expected role deployer, got none); academic-0057 (expected role provider, got none); academic-0058 (expected role deployer, got none); academic-0068 (expected role deployer, got none); academic-0269 (expected role deployer, got none); academic-0273 (expected role deployer, got none); academic-0303 (expected role deployer, got none); academic-0317 (expected role deployer, got none)

##### Model-written texts

- Longest fact or question: 307 characters (cap 600)
- Facts: 1844 over 339 results
- Follow-up questions: 2977 over 339 results

Judged metrics: not judged yet (`aiact evaluate judged <run_id>`).

- No invented content: checked by code (P8a's `check_nothing_invented` on each document the results call for), not judged: 100.0%, 312/312 documents

#### Run b2b88c38-5f2d-438e-8741-7e234ebb6cc5

- Benchmark: `commission_b`
- Commit: `6f5fa5024bb48d8e491c2f7642782a865fd0b445`
- Status: completed
- Classifier: `baseline_luna`: `openai/gpt-6-luna-20260922` on `azure/eu`
- Cases run: every case of the set
- Exclude mode: `heldout` (held-out examples kept out of retrieval: the reported number)
- Started: 2026-10-15T06:48:58.718299+00:00
- Model: openai/gpt-6-luna-20260922
- Cost: $0.1358, 375880 tokens
- Cases: 153 (2 failed)
- Case ids and expected labels: `eval/reports/pile_b/run-b2b88c38-5f2d-438e-8741-7e234ebb6cc5.md` (Pile B's, kept out of this text: the Engine lane can't read that folder, V11)

| Metric | Value | Count |
| --- | ---: | ---: |
| Risk-class accuracy | 60.5% | 92/152 |
| Not assessed (provider refused a check, decision 030) | 0 | |
| Risk-class accuracy, not-assessed cases counted as misses | 60.5% | 92/152 |
| False-low-risk rate | 0.0% | 0/61 |
| Annex point accuracy | 82.5% | 47/57 |
| Role accuracy | 96.7% | 147/152 |
| Legally ambiguous: precision | 3.8% | 1/26 |
| Legally ambiguous: recall | 100.0% | 1/1 |
| Ambiguous answered needs-more-information | 0 | |
| Needs more information: precision | 0.0% | 0/28 |
| Needs more information: recall | n/a | 0/0 |
| Downgrade rate (soft wording) | n/a | 0/0 |
| Basis accuracy (Commission cases) | 64.4% | 94/146 |
| Flip variant asked or flagged | 0.0% | 0/5 |
| Label citation cited (any of) | 0.0% | 0/151 |
| Needs a description: asked (thin cases) | n/a | 0/0 |
| Needs a description: asked wrongly (other cases) | 0.0% | 0/151 |
| Consistency | n/a | 0/0 |
| Citation existence (at run time) | n/a | 0/0 |
| appliedAI disagreement review | 0 | |
| Academic out-of-scope review | 0 | |

Contaminated cases, flagged by docs/decisions/016-contaminated-pile-b-cases.md: 2 (named in the Pile B file)

| Metric | Value | Count |
| --- | ---: | ---: |
| Risk-class accuracy without the contaminated cases | 60.7% | 91/150 |

##### Provider refusals (decisions 029, 030, 033)

- Second model: not recorded for this run (refusals can't be told apart).
- Refused by the engine model: 0 of 151 (0.0%)
- Answered by the second model: 0 of 151 (0.0%)
- Refused by both (not assessed): 0 of 151 (0.0%)
- Second model's refusal rate: 0 of 0 (n/a)
- Risk-class accuracy without the cases the second model answered: 60.5% (92/152)

Calls by the model that served them: none recorded

##### Failures by step

- **scope** (1) (named in the Pile B file)
- **prohibited** (4) (named in the Pile B file)
- **high_risk** (47) (named in the Pile B file)
- **transparency** (16) (named in the Pile B file)
- **no result (the classifier failed)** (2) (named in the Pile B file)

##### Model-written texts

- Longest fact or question: 284 characters (cap 600)
- Facts: 0 over 151 results
- Follow-up questions: 28 over 151 results

Judged metrics: not judged yet (`aiact evaluate judged <run_id>`).

- No invented content: checked by code (P8a's `check_nothing_invented` on each document the results call for), not judged: 100.0%, 30/30 documents

#### Run 1e490e70-6606-436a-902a-a92157456f06

- Benchmark: `own` (development cases: the engine's nodes were developed against them, so Commission Pile B carries the headline (decision 018))
- Commit: `6f5fa5024bb48d8e491c2f7642782a865fd0b445`
- Status: completed
- Classifier: `baseline_luna`: `openai/gpt-6-luna-20260922` on `azure/eu`
- Cases run: every case of the set
- Exclude mode: `heldout` (held-out examples kept out of retrieval: the reported number)
- Started: 2026-10-15T06:59:00.889103+00:00
- Model: openai/gpt-6-luna-20260922
- Cost: $0.0608, 180225 tokens
- Cases: 88 (7 failed)

| Metric | Value | Count |
| --- | ---: | ---: |
| Risk-class accuracy (development cases) | 75.6% | 59/78 |
| Not assessed (provider refused a check, decision 030) | 0 | |
| Risk-class accuracy, not-assessed cases counted as misses | 75.6% | 59/78 |
| False-low-risk rate | 0.0% | 0/31 |
| Annex point accuracy | 70.8% | 17/24 |
| Role accuracy | 82.9% | 63/76 |
| Legally ambiguous: precision | 12.5% | 1/8 |
| Legally ambiguous: recall | 20.0% | 1/5 |
| Ambiguous answered needs-more-information | 2 | |
| Needs more information: precision | 41.7% | 5/12 |
| Needs more information: recall | 100.0% | 5/5 |
| Downgrade rate (soft wording) | n/a | 0/0 |
| Basis accuracy (Commission cases) | n/a | 0/0 |
| Flip variant asked or flagged | n/a | 0/0 |
| Label citation cited (any of) | 0.0% | 0/78 |
| Needs a description: asked (thin cases) | 0.0% | 0/3 |
| Needs a description: asked wrongly (other cases) | 0.0% | 0/78 |
| Consistency | n/a | 0/0 |
| Citation existence (at run time) | n/a | 0/0 |
| appliedAI disagreement review | 0 | |
| Academic out-of-scope review | 0 | |

##### Provider refusals (decisions 029, 030, 033)

- Second model: not recorded for this run (refusals can't be told apart).
- Refused by the engine model: 0 of 81 (0.0%)
- Answered by the second model: 0 of 81 (0.0%)
- Refused by both (not assessed): 0 of 81 (0.0%)
- Second model's refusal rate: 0 of 0 (n/a)
- Risk-class accuracy without the cases the second model answered: 75.6% (59/78)

Calls by the model that served them: none recorded

##### Failures by step

- **facts** (3): own-t-01-ai-for-hr (answered with a class); own-t-02-sales-team-ai-tool (answered with a class); own-t-03-ki-im-kundenservice (answered with a class)
- **scope** (4): own-b-03-bakery-weekday-average (expected out_of_scope, got minimal_risk (decided)); own-b-04-card-game-opponent (expected out_of_scope, got minimal_risk (decided)); own-b-10-open-source-plant-app (expected out_of_scope, got limited_risk (legally_ambiguous)); own-b-13-private-trading-app (expected out_of_scope, got minimal_risk (decided))
- **high_risk** (10): own-c-09-crane-operator-stress-alarm (Annex point annex:I:1); own-e-02-lift-maintenance-forecast (expected minimal_risk, got high_risk (needs_more_information)); own-e-04-loader-crane-tip-guard (Annex point annex:I:1); own-e-05-emergency-braking-supplier (Annex point annex:I:section:A:2018/858); own-e-07-grinder-burst-kit (Annex point annex:I:1); own-e-11-boiler-flame-module (Annex point annex:I:section:A:9); own-e-12-hospital-xray-triage (Annex point annex:I:10); own-f-04-gehaltsrunde-auswertung (expected minimal_risk, got high_risk (needs_more_information)); own-f-06-pflegedienst-leistungsprofil (Annex point annex:III:4:a); own-f-07-water-mains-renewal-plan (expected minimal_risk, got high_risk (legally_ambiguous))
- **transparency** (5): own-a-07-surfing-cows-ad (expected limited_risk, got minimal_risk (decided)); own-a-09-newsroom-reviewed-drafts (expected limited_risk, got minimal_risk (decided)); own-a-12-coffee-machine-voice (expected minimal_risk, got limited_risk (decided)); own-a-13-code-autocomplete-plugin (expected minimal_risk, got limited_risk (legally_ambiguous)); own-c-18-car-sharing-driving-score (expected minimal_risk, got limited_risk (legally_ambiguous))
- **role_obligations** (6): own-c-08-agent-voice-mood-scores (expected role deployer, got none); own-c-11-police-burglary-risk-list (expected role deployer, got none); own-c-12-face-search-crawler (expected role provider, got none); own-c-13-store-camera-lifestyle-segments (expected role provider, got none); own-c-20-fitnessclub-vertraeglichkeitswert (expected role deployer, got none); own-d-05-white-label-captions (expected role provider, got distributor)
- **no result (the classifier failed)** (7): own-c-01-undress-photo-app (no result); own-c-02-undress-app-before-december (no result); own-c-03-image-tool-with-safeguards (no result); own-c-04-studio-digital-doubles-consent (no result); own-c-05-gossip-site-fake-nudes (no result); own-c-07-unfiltered-image-generator (no result); own-e-13-wheelchair-obstacle-stop (no result)

##### Model-written texts

- Longest fact or question: 300 characters (cap 600)
- Facts: 0 over 81 results
- Follow-up questions: 14 over 81 results

Judged metrics: not judged yet (`aiact evaluate judged <run_id>`).

- No invented content: checked by code (P8a's `check_nothing_invented` on each document the results call for), not judged: 100.0%, 12/12 documents

#### Run bc908149-1726-49e2-ae14-67ffe7efae3a

- Benchmark: `commission_b`
- Commit: `6f5fa5024bb48d8e491c2f7642782a865fd0b445`
- Status: completed
- Classifier: `baseline_jev`: `typesafe/jev-1.13`
- Cases run: every case of the set
- Exclude mode: `heldout` (held-out examples kept out of retrieval: the reported number)
- Started: 2026-10-15T07:07:19.421730+00:00
- Model: typesafe/jev-1.13
- Cost: $0.0071, 197775 tokens
- Cases: 153 (0 failed)
- Case ids and expected labels: `eval/reports/pile_b/run-bc908149-1726-49e2-ae14-67ffe7efae3a.md` (Pile B's, kept out of this text: the Engine lane can't read that folder, V11)

| Metric | Value | Count |
| --- | ---: | ---: |
| Risk-class accuracy | 51.3% | 78/152 |
| Not assessed (provider refused a check, decision 030) | 0 | |
| Risk-class accuracy, not-assessed cases counted as misses | 51.3% | 78/152 |
| False-low-risk rate | 13.1% | 8/61 |
| Annex point accuracy | 0.0% | 0/52 |
| Role accuracy | 92.8% | 141/152 |
| Legally ambiguous: precision | n/a | 0/0 |
| Legally ambiguous: recall | 0.0% | 0/1 |
| Ambiguous answered needs-more-information | 0 | |
| Needs more information: precision | n/a | 0/0 |
| Needs more information: recall | n/a | 0/0 |
| Downgrade rate (soft wording) | n/a | 0/0 |
| Basis accuracy (Commission cases) | 57.5% | 84/146 |
| Flip variant asked or flagged | 0.0% | 0/6 |
| Label citation cited (any of) | 0.0% | 0/153 |
| Needs a description: asked (thin cases) | n/a | 0/0 |
| Needs a description: asked wrongly (other cases) | 0.0% | 0/153 |
| Consistency | n/a | 0/0 |
| Citation existence (at run time) | n/a | 0/0 |
| appliedAI disagreement review | 0 | |
| Academic out-of-scope review | 0 | |

Contaminated cases, flagged by docs/decisions/016-contaminated-pile-b-cases.md: 2 (named in the Pile B file)

| Metric | Value | Count |
| --- | ---: | ---: |
| Risk-class accuracy without the contaminated cases | 52.0% | 78/150 |

##### Provider refusals (decisions 029, 030, 033)

- Second model: not recorded for this run (refusals can't be told apart).
- Refused by the engine model: 0 of 153 (0.0%)
- Answered by the second model: 0 of 153 (0.0%)
- Refused by both (not assessed): 0 of 153 (0.0%)
- Second model's refusal rate: 0 of 0 (n/a)
- Risk-class accuracy without the cases the second model answered: 51.3% (78/152)

Calls by the model that served them: none recorded

##### Failures by step

- **scope** (4) (named in the Pile B file)
- **prohibited** (1) (named in the Pile B file)
- **high_risk** (104) (named in the Pile B file)
- **transparency** (17) (named in the Pile B file)

##### Model-written texts

- Longest fact or question: 0 characters (cap 600)
- Facts: 0 over 153 results
- Follow-up questions: 0 over 153 results

Judged metrics: not judged yet (`aiact evaluate judged <run_id>`).

- No invented content: checked by code (P8a's `check_nothing_invented` on each document the results call for), not judged: 100.0%, 3/3 documents

#### Run dadf2f5a-32fd-4c14-9b2d-9ebbc4b33e06

- Benchmark: `own` (development cases: the engine's nodes were developed against them, so Commission Pile B carries the headline (decision 018))
- Commit: `6f5fa5024bb48d8e491c2f7642782a865fd0b445`
- Status: completed
- Classifier: `baseline_jev`: `typesafe/jev-1.13`
- Cases run: every case of the set
- Exclude mode: `heldout` (held-out examples kept out of retrieval: the reported number)
- Started: 2026-10-15T07:07:35.213651+00:00
- Model: typesafe/jev-1.13
- Cost: $0.0041, 114489 tokens
- Cases: 88 (0 failed)

| Metric | Value | Count |
| --- | ---: | ---: |
| Risk-class accuracy (development cases) | 74.4% | 58/78 |
| Not assessed (provider refused a check, decision 030) | 0 | |
| Risk-class accuracy, not-assessed cases counted as misses | 74.4% | 58/78 |
| False-low-risk rate | 17.6% | 6/34 |
| Annex point accuracy | 0.0% | 0/21 |
| Role accuracy | 80.3% | 61/76 |
| Legally ambiguous: precision | n/a | 0/0 |
| Legally ambiguous: recall | 0.0% | 0/7 |
| Ambiguous answered needs-more-information | 0 | |
| Needs more information: precision | n/a | 0/0 |
| Needs more information: recall | 0.0% | 0/5 |
| Downgrade rate (soft wording) | n/a | 0/0 |
| Basis accuracy (Commission cases) | n/a | 0/0 |
| Flip variant asked or flagged | n/a | 0/0 |
| Label citation cited (any of) | 0.0% | 0/85 |
| Needs a description: asked (thin cases) | 0.0% | 0/3 |
| Needs a description: asked wrongly (other cases) | 0.0% | 0/85 |
| Consistency | n/a | 0/0 |
| Citation existence (at run time) | n/a | 0/0 |
| appliedAI disagreement review | 0 | |
| Academic out-of-scope review | 0 | |

##### Provider refusals (decisions 029, 030, 033)

- Second model: not recorded for this run (refusals can't be told apart).
- Refused by the engine model: 0 of 88 (0.0%)
- Answered by the second model: 0 of 88 (0.0%)
- Refused by both (not assessed): 0 of 88 (0.0%)
- Second model's refusal rate: 0 of 0 (n/a)
- Risk-class accuracy without the cases the second model answered: 74.4% (58/78)

Calls by the model that served them: none recorded

##### Failures by step

- **facts** (3): own-t-01-ai-for-hr (answered with a class); own-t-02-sales-team-ai-tool (answered with a class); own-t-03-ki-im-kundenservice (answered with a class)
- **scope** (5): own-b-04-card-game-opponent (expected out_of_scope, got minimal_risk (decided)); own-b-10-open-source-plant-app (expected out_of_scope, got minimal_risk (decided)); own-b-12-texas-booking-chat (expected out_of_scope, got limited_risk (decided)); own-b-13-private-trading-app (expected out_of_scope, got high_risk (decided)); own-f-03-exam-booklet-matching (expected minimal_risk, got out_of_scope (decided))
- **prohibited** (6): own-c-02-undress-app-before-december (expected limited_risk, got prohibited (decided)); own-c-08-agent-voice-mood-scores (expected prohibited, got limited_risk (decided)); own-c-10-town-resident-points (expected prohibited, got high_risk (decided)); own-c-11-police-burglary-risk-list (expected prohibited, got high_risk (decided)); own-c-13-store-camera-lifestyle-segments (expected prohibited, got limited_risk (decided)); own-c-17-supermarket-ban-list-cameras (expected high_risk, got prohibited (decided))
- **high_risk** (28): own-a-16-applicant-screening-chatbot (Annex point None); own-b-07-satellite-dual-use (expected minimal_risk, got high_risk (decided)); own-b-09-voice-mood-prototype (expected high_risk, got limited_risk (decided)); own-b-11-open-source-cv-ranking (Annex point None); own-c-09-crane-operator-stress-alarm (expected high_risk, got limited_risk (decided)); own-c-16-police-live-search-missing-child (Annex point None); own-c-18-car-sharing-driving-score (expected minimal_risk, got high_risk (decided)); own-c-19-physio-master-auswahl (Annex point None); own-d-01-own-brand-screening (Annex point None); own-d-02-retrained-credit-score (Annex point None); own-d-03-assistant-repurposed-hiring (Annex point None); own-d-04-warehouse-task-allocation (Annex point None); own-d-08-importer-essay-marking (Annex point None); own-d-09-reseller-applicant-ranking (Annex point None); own-d-10-rebranded-health-pricing (Annex point None); own-d-13-mailroom-tool-benefits (Annex point None); own-e-01-skin-lesion-app (Annex point None); own-e-04-loader-crane-tip-guard (Annex point None); own-e-05-emergency-braking-supplier (Annex point None); own-e-07-grinder-burst-kit (Annex point None); own-e-08-heart-rhythm-app (Annex point None); own-e-11-boiler-flame-module (Annex point None); own-e-12-hospital-xray-triage (Annex point None); own-e-13-wheelchair-obstacle-stop (expected minimal_risk, got high_risk (decided)); own-e-14-emergency-triage-module (Annex point None); own-f-04-gehaltsrunde-auswertung (expected minimal_risk, got high_risk (decided)); own-f-06-pflegedienst-leistungsprofil (Annex point None); own-f-07-water-mains-renewal-plan (expected minimal_risk, got high_risk (decided))
- **transparency** (2): own-a-12-coffee-machine-voice (expected minimal_risk, got limited_risk (decided)); own-a-13-code-autocomplete-plugin (expected minimal_risk, got limited_risk (decided))
- **role_obligations** (8): own-c-01-undress-photo-app (expected role provider, got none); own-c-05-gossip-site-fake-nudes (expected role deployer, got none); own-c-07-unfiltered-image-generator (expected role provider, got none); own-c-12-face-search-crawler (expected role provider, got none); own-c-14-kids-game-sad-pet-offers (expected role provider, got none); own-c-20-fitnessclub-vertraeglichkeitswert (expected role deployer, got none); own-d-05-white-label-captions (expected role provider, got distributor); own-d-12-lender-extra-input (expected role provider, got deployer)

##### Model-written texts

- Longest fact or question: 0 characters (cap 600)
- Facts: 0 over 88 results
- Follow-up questions: 0 over 88 results

Judged metrics: not judged yet (`aiact evaluate judged <run_id>`).

- No invented content: checked by code (P8a's `check_nothing_invented` on each document the results call for), not judged: 100.0%, 4/4 documents

#### Run 6b05eb02-df86-4cbd-af1f-0d5caa0b33ce

- Benchmark: `qa`
- Commit: `6f5fa5024bb48d8e491c2f7642782a865fd0b445`
- Status: completed
- Started: 2026-10-15T07:07:45.904979+00:00
- Cost: $0.1752, 495774 tokens
- Items: 29, 26 with an answer drawn from the sources

##### Judged metrics

- Judge: Jev `typesafe/jev-1.13`, backup `anthropic/claude-haiku-5.5` on `google-vertex/europe`, unsure margin 0.1 (decision 006)
- Cases judged: 26 of 26
- Judge cost: $0.0021, 51064 tokens (not in the run's cost above)

| Metric | Value | Count | Not measured | Backup decided | Cost | Cost per item |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Q&A support | 100.0% | 25/25 | 1 | 0 | $0.0021 | $0.000082 |

Not measured: the judge's reply was refused or broken, or the item was too long to send; never counted as a fail.

#### Run 3ed735c1-b796-421b-a01e-5d36faa93851

- Benchmark: `commission_b`
- Commit: `6f5fa5024bb48d8e491c2f7642782a865fd0b445`
- Status: completed
- Classifier: `engine`: `openai/gpt-6-luna-20260922` on `azure/eu`
- Cases run: every case of the set
- Second model for refused requests (decision 033): `google/gemini-3.1-flash-lite` on `google-vertex/eu`
- Exclude mode: `heldout` (held-out examples kept out of retrieval: the reported number)
- Started: 2026-10-15T08:35:42.503011+00:00
- Model: openai/gpt-6-luna-20260922
- Cost: $1.3204, 7509895 tokens
- Cases: 153 (4 failed)
- Case ids and expected labels: `eval/reports/pile_b/run-3ed735c1-b796-421b-a01e-5d36faa93851.md` (Pile B's, kept out of this text: the Engine lane can't read that folder, V11)

| Metric | Value | Count |
| --- | ---: | ---: |
| Risk-class accuracy | 60.5% | 92/152 |
| Not assessed (provider refused a check, decision 030) | 0 | |
| Risk-class accuracy, not-assessed cases counted as misses | 60.5% | 92/152 |
| False-low-risk rate | 1.7% | 1/59 |
| Annex point accuracy | 95.7% | 44/46 |
| Role accuracy | 92.1% | 140/152 |
| Legally ambiguous: precision | 7.1% | 1/14 |
| Legally ambiguous: recall | 100.0% | 1/1 |
| Ambiguous answered needs-more-information | 0 | |
| Needs more information: precision | 0.0% | 0/79 |
| Needs more information: recall | n/a | 0/0 |
| Downgrade rate (soft wording) | n/a | 0/0 |
| Basis accuracy (Commission cases) | 75.2% | 106/141 |
| Flip variant asked or flagged | 16.7% | 1/6 |
| Label citation cited (any of) | 60.4% | 90/149 |
| Needs a description: asked (thin cases) | n/a | 0/0 |
| Needs a description: asked wrongly (other cases) | 0.0% | 0/149 |
| Consistency | n/a | 0/0 |
| Citation existence (at run time) | 100.0% | 149/149 |
| appliedAI disagreement review | 0 | |
| Academic out-of-scope review | 0 | |

Contaminated cases, flagged by docs/decisions/016-contaminated-pile-b-cases.md: 2 (named in the Pile B file)

| Metric | Value | Count |
| --- | ---: | ---: |
| Risk-class accuracy without the contaminated cases | 60.7% | 91/150 |

##### Provider refusals (decisions 029, 030, 033)

- Second model for refused requests: `google/gemini-3.1-flash-lite`
- Refused by the engine model: 4 of 149 (2.7%) (named in the Pile B file)
- Answered by the second model: 4 of 149 (2.7%) (named in the Pile B file)
- Refused by both (not assessed): 0 of 149 (0.0%)
- Second model's refusal rate: 0 of 4 (0.0%)
- Risk-class accuracy without the cases the second model answered: 60.1% (89/148)

Calls by the model that served them: `openai/gpt-6-luna` 907, `qwen/qwen3-embedding-8b` 632, `google/gemini-3.1-flash-lite` 4

##### Failures by step

- **scope** (5) (named in the Pile B file)
- **prohibited** (15) (named in the Pile B file)
- **high_risk** (22) (named in the Pile B file)
- **transparency** (16) (named in the Pile B file)
- **role_obligations** (1) (named in the Pile B file)
- **no result (the classifier failed)** (4) (named in the Pile B file)

##### Model-written texts

- Longest fact or question: 303 characters (cap 600)
- Facts: 946 over 149 results
- Follow-up questions: 1066 over 149 results

##### Judged metrics

- Judge: Jev `typesafe/jev-1.13`, backup `anthropic/claude-haiku-5.5` on `google-vertex/europe`, unsure margin 0.1 (decision 006)
- Cases judged: 149 of 149
- Judge cost: $0.1032, 1555461 tokens (not in the run's cost above)

| Metric | Value | Count | Not measured | Backup decided | Cost | Cost per item |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Citation support | 15.5% | 102/660 | 58 | 26 | $0.0870 | $0.000121 |
| Evidence-tag accuracy | 99.6% | 709/712 | 1 | 1 | $0.0162 | $0.000023 |

Not measured: the judge's reply was refused or broken, or the item was too long to send; never counted as a fail.

- No invented content: checked by code (P8a's `check_nothing_invented` on each document the results call for), not judged: 100.0%, 226/226 documents

#### Run f5d98467-29ab-42c0-9d18-ecf3c4164939

- Benchmark: `own` (development cases: the engine's nodes were developed against them, so Commission Pile B carries the headline (decision 018))
- Commit: `6f5fa5024bb48d8e491c2f7642782a865fd0b445`
- Status: completed
- Classifier: `engine`: `openai/gpt-6-luna-20260922` on `azure/eu`
- Cases run: every case of the set
- Second model for refused requests (decision 033): `google/gemini-3.1-flash-lite` on `google-vertex/eu`
- Exclude mode: `heldout` (held-out examples kept out of retrieval: the reported number)
- Started: 2026-10-15T09:53:49.189556+00:00
- Model: openai/gpt-6-luna-20260922
- Cost: $0.6417, 3642373 tokens
- Cases: 88 (2 failed)

| Metric | Value | Count |
| --- | ---: | ---: |
| Risk-class accuracy (development cases) | 84.6% | 66/78 |
| Not assessed (provider refused a check, decision 030) | 0 | |
| Risk-class accuracy, not-assessed cases counted as misses | 84.6% | 66/78 |
| False-low-risk rate | 0.0% | 0/34 |
| Annex point accuracy | 90.5% | 19/21 |
| Role accuracy | 77.6% | 59/76 |
| Legally ambiguous: precision | 40.0% | 2/5 |
| Legally ambiguous: recall | 40.0% | 2/5 |
| Ambiguous answered needs-more-information | 2 | |
| Needs more information: precision | 11.8% | 4/34 |
| Needs more information: recall | 80.0% | 4/5 |
| Downgrade rate (soft wording) | n/a | 0/0 |
| Basis accuracy (Commission cases) | n/a | 0/0 |
| Flip variant asked or flagged | n/a | 0/0 |
| Label citation cited (any of) | 97.6% | 81/83 |
| Needs a description: asked (thin cases) | 100.0% | 3/3 |
| Needs a description: asked wrongly (other cases) | 1.2% | 1/83 |
| Consistency | n/a | 0/0 |
| Citation existence (at run time) | 100.0% | 82/82 |
| appliedAI disagreement review | 0 | |
| Academic out-of-scope review | 0 | |

##### Provider refusals (decisions 029, 030, 033)

- Second model for refused requests: `google/gemini-3.1-flash-lite`
- Refused by the engine model: 9 of 86 (10.5%): own-a-12-coffee-machine-voice, own-c-01-undress-photo-app, own-c-02-undress-app-before-december, own-c-03-image-tool-with-safeguards, own-c-04-studio-digital-doubles-consent, own-c-05-gossip-site-fake-nudes, own-c-07-unfiltered-image-generator, own-c-14-kids-game-sad-pet-offers, own-e-03-talking-plush-toy
- Answered by the second model: 9 of 86 (10.5%): own-a-12-coffee-machine-voice, own-c-01-undress-photo-app, own-c-02-undress-app-before-december, own-c-03-image-tool-with-safeguards, own-c-04-studio-digital-doubles-consent, own-c-05-gossip-site-fake-nudes, own-c-07-unfiltered-image-generator, own-c-14-kids-game-sad-pet-offers, own-e-03-talking-plush-toy
- Refused by both (not assessed): 0 of 86 (0.0%)
- Second model's refusal rate: 0 of 9 (0.0%)
- Risk-class accuracy without the cases the second model answered: 84.1% (58/69)

Calls by the model that served them: `openai/gpt-6-luna` 443, `qwen/qwen3-embedding-8b` 321, `google/gemini-3.1-flash-lite` 14

##### Failures by step

- **facts** (1): own-c-03-image-tool-with-safeguards (answered with a description request)
- **scope** (1): own-b-04-card-game-opponent (expected out_of_scope, got limited_risk (legally_ambiguous))
- **prohibited** (6): own-a-05-vacuum-ad-synthetic-customers (expected limited_risk, got prohibited (needs_more_information)); own-a-06-satire-minister-sketches (expected limited_risk, got prohibited (needs_more_information)); own-c-16-police-live-search-missing-child (expected high_risk, got prohibited (needs_more_information)); own-c-18-car-sharing-driving-score (expected minimal_risk, got prohibited (needs_more_information)); own-d-02-retrained-credit-score (expected high_risk, got prohibited (needs_more_information)); own-f-06-pflegedienst-leistungsprofil (expected high_risk, got prohibited (needs_more_information))
- **high_risk** (4): own-e-05-emergency-braking-supplier (Annex point annex:III:2); own-e-08-heart-rhythm-app (Annex point annex:III:1:b); own-f-01-depot-headcount-forecast (expected minimal_risk, got high_risk (needs_more_information)); own-f-07-water-mains-renewal-plan (expected minimal_risk, got high_risk (needs_more_information))
- **transparency** (1): own-f-04-gehaltsrunde-auswertung (expected minimal_risk, got limited_risk (needs_more_information))
- **role_obligations** (11): own-c-01-undress-photo-app (expected role provider, got none); own-c-05-gossip-site-fake-nudes (expected role deployer, got none); own-c-07-unfiltered-image-generator (expected role provider, got none); own-c-08-agent-voice-mood-scores (expected role deployer, got none); own-c-10-town-resident-points (expected role deployer, got none); own-c-11-police-burglary-risk-list (expected role deployer, got none); own-c-12-face-search-crawler (expected role provider, got none); own-c-13-store-camera-lifestyle-segments (expected role provider, got none); own-c-14-kids-game-sad-pet-offers (expected role provider, got none); own-c-15-debt-collection-chat-pressure (expected role deployer, got none); own-c-20-fitnessclub-vertraeglichkeitswert (expected role deployer, got none)
- **no result (the classifier failed)** (1): own-a-11-email-tone-rewrite (no result)

##### Model-written texts

- Longest fact or question: 535 characters (cap 600)
- Facts: 554 over 86 results
- Follow-up questions: 489 over 86 results

##### Judged metrics

- Judge: Jev `typesafe/jev-1.13`, backup `anthropic/claude-haiku-5.5` on `google-vertex/europe`, unsure margin 0.1 (decision 006)
- Cases judged: 86 of 86
- Judge cost: $0.0613, 866312 tokens (not in the run's cost above)

| Metric | Value | Count | Not measured | Backup decided | Cost | Cost per item |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Citation support | 21.6% | 65/301 | 44 | 13 | $0.0516 | $0.000150 |
| Evidence-tag accuracy | 99.3% | 412/415 | 0 | 3 | $0.0097 | $0.000023 |

Not measured: the judge's reply was refused or broken, or the item was too long to send; never counted as a fail.

- No invented content: checked by code (P8a's `check_nothing_invented` on each document the results call for), not judged: 100.0%, 98/98 documents

#### Run 3539d1b0-b22d-403d-9c62-e08961b00384

- Benchmark: `soft_pairs`
- Commit: `6f5fa5024bb48d8e491c2f7642782a865fd0b445`
- Status: completed
- Classifier: `engine`: `openai/gpt-6-luna-20260922` on `azure/eu`
- Cases run: every case of the set
- Second model for refused requests (decision 033): `google/gemini-3.1-flash-lite` on `google-vertex/eu`
- Exclude mode: `heldout` (held-out examples kept out of retrieval: the reported number)
- Started: 2026-10-15T10:29:02.461987+00:00
- Model: openai/gpt-6-luna-20260922
- Cost: $0.2018, 1175987 tokens
- Cases: 24 (1 failed)

| Metric | Value | Count |
| --- | ---: | ---: |
| Risk-class accuracy | 62.5% | 15/24 |
| Not assessed (provider refused a check, decision 030) | 0 | |
| Risk-class accuracy, not-assessed cases counted as misses | 62.5% | 15/24 |
| False-low-risk rate | 18.2% | 4/22 |
| Annex point accuracy | 100.0% | 15/15 |
| Role accuracy | 91.7% | 22/24 |
| Legally ambiguous: precision | n/a | 0/0 |
| Legally ambiguous: recall | n/a | 0/0 |
| Ambiguous answered needs-more-information | 0 | |
| Needs more information: precision | 0.0% | 0/15 |
| Needs more information: recall | n/a | 0/0 |
| Downgrade rate (soft wording) | 40.0% | 4/10 |
| Basis accuracy (Commission cases) | n/a | 0/0 |
| Flip variant asked or flagged | n/a | 0/0 |
| Label citation cited (any of) | 95.7% | 22/23 |
| Needs a description: asked (thin cases) | n/a | 0/0 |
| Needs a description: asked wrongly (other cases) | 4.3% | 1/23 |
| Consistency | n/a | 0/0 |
| Citation existence (at run time) | 100.0% | 22/22 |
| appliedAI disagreement review | 0 | |
| Academic out-of-scope review | 0 | |

##### Provider refusals (decisions 029, 030, 033)

- Second model for refused requests: `google/gemini-3.1-flash-lite`
- Refused by the engine model: 1 of 23 (4.3%): soft-03-car-leasing-scores-plain
- Answered by the second model: 1 of 23 (4.3%): soft-03-car-leasing-scores-plain
- Refused by both (not assessed): 0 of 23 (0.0%)
- Second model's refusal rate: 0 of 1 (0.0%)
- Risk-class accuracy without the cases the second model answered: 60.9% (14/23)

Calls by the model that served them: `openai/gpt-6-luna` 139, `qwen/qwen3-embedding-8b` 102, `google/gemini-3.1-flash-lite` 1

##### Failures by step

- **facts** (1): soft-05-conservatory-pre-auditions-soft (answered with a description request)
- **prohibited** (3): soft-02-cleaning-staff-scores-plain (expected high_risk, got prohibited (needs_more_information)); soft-08-spedition-fahrstil-noten-plain (expected high_risk, got prohibited (needs_more_information)); soft-08-spedition-fahrstil-noten-soft (expected high_risk, got prohibited (needs_more_information))
- **high_risk** (4): soft-07-insurance-ombudsman-drafts-soft (expected high_risk, got limited_risk (needs_more_information)); soft-09-zahnzusatz-wartezeiten-soft (expected high_risk, got minimal_risk (needs_more_information)); soft-10-elterngeld-rueckforderung-soft (expected high_risk, got limited_risk (needs_more_information)); soft-11-klinikverbund-pflege-bewerbungen-soft (expected high_risk, got limited_risk (needs_more_information))
- **no result (the classifier failed)** (1): soft-02-cleaning-staff-scores-soft (no result)

##### Model-written texts

- Longest fact or question: 229 characters (cap 600)
- Facts: 140 over 23 results
- Follow-up questions: 179 over 23 results

Judged metrics: not judged yet (`aiact evaluate judged <run_id>`).

- No invented content: checked by code (P8a's `check_nothing_invented` on each document the results call for), not judged: 100.0%, 47/47 documents

#### Run 79e16006-8663-4e52-9f4b-d248a9404a13

- Benchmark: `soft_pairs`
- Commit: `6f5fa5024bb48d8e491c2f7642782a865fd0b445`
- Status: completed
- Classifier: `engine`: `openai/gpt-6-luna-20260922` on `azure/eu`
- Cases run: every case of the set
- Second model for refused requests (decision 033): `google/gemini-3.1-flash-lite` on `google-vertex/eu`
- Exclude mode: `heldout` (held-out examples kept out of retrieval: the reported number)
- Answers: the stored key-fact answers to the questions run `3539d1b0-b22d-403d-9c62-e08961b00384` asked, any other question answered "don't know" (decision 019)
- Started: 2026-10-15T11:35:28.972793+00:00
- Model: openai/gpt-6-luna-20260922
- Cost: $0.2181, 1233248 tokens
- Cases: 24 (0 failed)

| Metric | Value | Count |
| --- | ---: | ---: |
| Risk-class accuracy | 66.7% | 16/24 |
| Not assessed (provider refused a check, decision 030) | 0 | |
| Risk-class accuracy, not-assessed cases counted as misses | 66.7% | 16/24 |
| False-low-risk rate | 8.7% | 2/23 |
| Annex point accuracy | 100.0% | 16/16 |
| Role accuracy | 95.8% | 23/24 |
| Legally ambiguous: precision | n/a | 0/0 |
| Legally ambiguous: recall | n/a | 0/0 |
| Ambiguous answered needs-more-information | 0 | |
| Needs more information: precision | 0.0% | 0/16 |
| Needs more information: recall | n/a | 0/0 |
| Downgrade rate (soft wording) | 9.1% | 1/11 |
| Basis accuracy (Commission cases) | n/a | 0/0 |
| Flip variant asked or flagged | n/a | 0/0 |
| Label citation cited (any of) | 95.8% | 23/24 |
| Needs a description: asked (thin cases) | n/a | 0/0 |
| Needs a description: asked wrongly (other cases) | 4.2% | 1/24 |
| Consistency | n/a | 0/0 |
| Citation existence (at run time) | 100.0% | 23/23 |
| appliedAI disagreement review | 0 | |
| Academic out-of-scope review | 0 | |

##### Provider refusals (decisions 029, 030, 033)

- Second model for refused requests: `google/gemini-3.1-flash-lite`
- Refused by the engine model: 2 of 24 (8.3%): soft-01-garden-centre-applications-soft, soft-04-retraining-project-grades-soft
- Answered by the second model: 2 of 24 (8.3%): soft-01-garden-centre-applications-soft, soft-04-retraining-project-grades-soft
- Refused by both (not assessed): 0 of 24 (0.0%)
- Second model's refusal rate: 0 of 2 (0.0%)
- Risk-class accuracy without the cases the second model answered: 63.6% (14/22)

Calls by the model that served them: `openai/gpt-6-luna` 139, `qwen/qwen3-embedding-8b` 102, `google/gemini-3.1-flash-lite` 2

##### Failures by step

- **facts** (1): soft-05-conservatory-pre-auditions-soft (answered with a description request)
- **prohibited** (5): soft-02-cleaning-staff-scores-plain (expected high_risk, got prohibited (needs_more_information)); soft-02-cleaning-staff-scores-soft (expected high_risk, got prohibited (needs_more_information)); soft-08-spedition-fahrstil-noten-plain (expected high_risk, got prohibited (needs_more_information)); soft-08-spedition-fahrstil-noten-soft (expected high_risk, got prohibited (needs_more_information)); soft-11-klinikverbund-pflege-bewerbungen-plain (expected high_risk, got prohibited (needs_more_information))
- **high_risk** (2): soft-07-insurance-ombudsman-drafts-plain (expected high_risk, got limited_risk (decided)); soft-07-insurance-ombudsman-drafts-soft (expected high_risk, got limited_risk (needs_more_information))

##### Model-written texts

- Longest fact or question: 301 characters (cap 600)
- Facts: 160 over 24 results
- Follow-up questions: 190 over 24 results

Judged metrics: not judged yet (`aiact evaluate judged <run_id>`).

- No invented content: checked by code (P8a's `check_nothing_invented` on each document the results call for), not judged: 100.0%, 50/50 documents

#### Run acf079e8-cab4-4b24-b61f-101f7d6d0fa5

- Benchmark: `consistency`
- Commit: `6f5fa5024bb48d8e491c2f7642782a865fd0b445`
- Status: completed
- Classifier: `engine`: `openai/gpt-6-luna-20260922` on `azure/eu`
- Cases run: every case of the set
- Second model for refused requests (decision 033): `google/gemini-3.1-flash-lite` on `google-vertex/eu`
- Exclude mode: `heldout` (held-out examples kept out of retrieval: the reported number)
- Started: 2026-10-15T10:40:29.692575+00:00
- Model: openai/gpt-6-luna-20260922
- Cost: $0.2035, 1269663 tokens
- Cases: 30 (0 failed)

| Metric | Value | Count |
| --- | ---: | ---: |
| Risk-class accuracy | 86.7% | 26/30 |
| Not assessed (provider refused a check, decision 030) | 0 | |
| Risk-class accuracy, not-assessed cases counted as misses | 86.7% | 26/30 |
| False-low-risk rate | 0.0% | 0/18 |
| Annex point accuracy | 100.0% | 11/11 |
| Role accuracy | 85.2% | 23/27 |
| Legally ambiguous: precision | 0.0% | 0/1 |
| Legally ambiguous: recall | n/a | 0/0 |
| Ambiguous answered needs-more-information | 0 | |
| Needs more information: precision | 0.0% | 0/8 |
| Needs more information: recall | n/a | 0/0 |
| Downgrade rate (soft wording) | n/a | 0/0 |
| Basis accuracy (Commission cases) | n/a | 0/0 |
| Flip variant asked or flagged | n/a | 0/0 |
| Label citation cited (any of) | 100.0% | 30/30 |
| Needs a description: asked (thin cases) | n/a | 0/0 |
| Needs a description: asked wrongly (other cases) | 0.0% | 0/30 |
| Consistency | 90.0% | 9/10 |
| Citation existence (at run time) | 100.0% | 30/30 |
| appliedAI disagreement review | 0 | |
| Academic out-of-scope review | 0 | |

##### Provider refusals (decisions 029, 030, 033)

- Second model for refused requests: `google/gemini-3.1-flash-lite`
- Refused by the engine model: 0 of 30 (0.0%)
- Answered by the second model: 0 of 30 (0.0%)
- Refused by both (not assessed): 0 of 30 (0.0%)
- Second model's refusal rate: 0 of 0 (n/a)
- Risk-class accuracy without the cases the second model answered: 86.7% (26/30)

Calls by the model that served them: `openai/gpt-6-luna` 159, `qwen/qwen3-embedding-8b` 114

##### Failures by step

- **prohibited** (4): cons-06-courier-offboarding-scores-a (expected high_risk, got prohibited (needs_more_information)); cons-06-courier-offboarding-scores-b (expected high_risk, got prohibited (needs_more_information)); cons-06-courier-offboarding-scores-c (expected high_risk, got prohibited (needs_more_information)); cons-07-rebranded-loan-scoring-a (expected high_risk, got prohibited (needs_more_information))
- **role_obligations** (3): cons-03-meeting-webcam-moods-a (expected role deployer, got none); cons-03-meeting-webcam-moods-b (expected role deployer, got none); cons-03-meeting-webcam-moods-c (expected role deployer, got none)

##### Model-written texts

- Longest fact or question: 171 characters (cap 600)
- Facts: 216 over 30 results
- Follow-up questions: 149 over 30 results

Judged metrics: not judged yet (`aiact evaluate judged <run_id>`).

- No invented content: checked by code (P8a's `check_nothing_invented` on each document the results call for), not judged: 100.0%, 38/38 documents

#### Run 918a061a-333b-41a3-aeae-26e24971bd45

- Benchmark: `annex_match`
- Commit: `6f5fa5024bb48d8e491c2f7642782a865fd0b445`
- Status: completed
- Classifier: `engine`: `openai/gpt-6-luna-20260922` on `azure/eu`
- Cases run: every case of the set
- Second model for refused requests (decision 033): `google/gemini-3.1-flash-lite` on `google-vertex/eu`
- Exclude mode: `heldout` (held-out examples kept out of retrieval: the reported number)
- Started: 2026-10-15T10:54:34.082508+00:00
- Model: openai/gpt-6-luna-20260922
- Cost: $0.4141, 2426742 tokens
- Cases: 48 (1 failed)

| Metric | Value | Count |
| --- | ---: | ---: |
| Risk-class accuracy | 87.5% | 42/48 |
| Not assessed (provider refused a check, decision 030) | 0 | |
| Risk-class accuracy, not-assessed cases counted as misses | 87.5% | 42/48 |
| False-low-risk rate | 2.1% | 1/47 |
| Annex point accuracy | 100.0% | 42/42 |
| Role accuracy | 95.8% | 46/48 |
| Legally ambiguous: precision | 0.0% | 0/3 |
| Legally ambiguous: recall | n/a | 0/0 |
| Ambiguous answered needs-more-information | 0 | |
| Needs more information: precision | 0.0% | 0/10 |
| Needs more information: recall | n/a | 0/0 |
| Downgrade rate (soft wording) | n/a | 0/0 |
| Basis accuracy (Commission cases) | n/a | 0/0 |
| Flip variant asked or flagged | n/a | 0/0 |
| Label citation cited (any of) | 97.9% | 46/47 |
| Needs a description: asked (thin cases) | n/a | 0/0 |
| Needs a description: asked wrongly (other cases) | 0.0% | 0/47 |
| Consistency | n/a | 0/0 |
| Citation existence (at run time) | 100.0% | 47/47 |
| appliedAI disagreement review | 0 | |
| Academic out-of-scope review | 0 | |

##### Provider refusals (decisions 029, 030, 033)

- Second model for refused requests: `google/gemini-3.1-flash-lite`
- Refused by the engine model: 1 of 47 (2.1%): annex-match-19-checkout-pay-later
- Answered by the second model: 1 of 47 (2.1%): annex-match-19-checkout-pay-later
- Refused by both (not assessed): 0 of 47 (0.0%)
- Second model's refusal rate: 0 of 1 (0.0%)
- Risk-class accuracy without the cases the second model answered: 87.2% (41/47)

Calls by the model that served them: `openai/gpt-6-luna` 287, `qwen/qwen3-embedding-8b` 211, `google/gemini-3.1-flash-lite` 1

##### Failures by step

- **prohibited** (4): annex-match-07-business-school-admissions (expected high_risk, got prohibited (needs_more_information)); annex-match-13-lager-bewerbungen-punkte (expected high_risk, got prohibited (needs_more_information)); annex-match-14-job-ad-audience-targeting (expected high_risk, got prohibited (needs_more_information)); annex-match-21-online-health-premium (expected high_risk, got prohibited (needs_more_information))
- **high_risk** (1): annex-match-28-football-match-offending-risk (expected high_risk, got minimal_risk (legally_ambiguous))
- **no result (the classifier failed)** (1): annex-match-25-senior-fraud-prevention-visits (no result)

##### Model-written texts

- Longest fact or question: 213 characters (cap 600)
- Facts: 317 over 47 results
- Follow-up questions: 360 over 47 results

Judged metrics: not judged yet (`aiact evaluate judged <run_id>`).

- No invented content: checked by code (P8a's `check_nothing_invented` on each document the results call for), not judged: 100.0%, 129/129 documents

#### Run fffeb510-2aaa-4ff8-b619-125a4af2eb70

- Benchmark: `qa`
- Commit: `6f5fa5024bb48d8e491c2f7642782a865fd0b445`
- Status: completed
- Started: 2026-10-15T11:25:16.137330+00:00
- Cost: $0.1775, 503283 tokens
- Items: 29, 25 with an answer drawn from the sources

##### Judged metrics

- Judge: Jev `typesafe/jev-1.13`, backup `anthropic/claude-haiku-5.5` on `google-vertex/europe`, unsure margin 0.1 (decision 006)
- Cases judged: 25 of 25
- Judge cost: $0.0021, 51341 tokens (not in the run's cost above)

| Metric | Value | Count | Not measured | Backup decided | Cost | Cost per item |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Q&A support | 100.0% | 24/24 | 1 | 0 | $0.0021 | $0.000085 |

Not measured: the judge's reply was refused or broken, or the item was too long to send; never counted as a fail.


## Later analysis (2026-10-15): why run 1 missed 52 of 152 Pile B cases

A read-only analysis of stored run `31baa80c-f3bc-4eaf-93d0-4280b5fa14e7`, made after W1 and cross-checked
with run 2 (`3ed735c1-b796-421b-a01e-5d36faa93851`) and the plain-prompt baseline
(`b2b88c38-5f2d-438e-8741-7e234ebb6cc5`). The failure types were assigned by an AI agent reading each case's
stored steps; the user did not review them case by case. Counts only: no case ids and no Pile B text.

**None of the 46 misses with a result put a high-risk or prohibited system lower.** 42 were too strict; 4
answered "not an AI system" where the label is minimal (the same duties). The other 6 were failed cases.

| Failure type | Misses | Too strict | Baseline right |
| --- | ---: | ---: | ---: |
| Art. 50 duty assumed where minimal | 16 | 16 | 7 |
| Wrongly prohibited (Art. 5) | 13 | 13 | 9 |
| Wrong Annex III point or area, or Annex I route | 12 | 12 | 1 |
| No result (a step failed) | 6 | n/a | 4 |
| "Not an AI system" where minimal | 4 | 0 (4 too lenient, no practical effect) | 3 |
| Art. 6(3) exception missed | 1 | 1 | 0 |
| Total | 52 | 42 | 24 |

**The cross-cutting cause.** 27 of the 52 misses came from a step returning "needs more information" or
"legally ambiguous"; the engine then put the stricter reading as the headline class (decision 010's working
assumption). That covers 13 of the 13 prohibited, 6 of the 12 wrong-area and 8 of the 16 transparency misses.

**Top areas:** education 9 of 15; essential services and credit 9 of 24; law enforcement 8 of 24.

**Stability.** 46 of the 52 were missed in run 2 too; 6 flipped, 3 of them failed cases that ran fine the second
time. The baseline got 24 of the engine's misses right; the engine got 32 right that the baseline missed.

**Three patterns:**

- Art. 5(1)(c) is flagged when a description doesn't state whether worse treatment is unjustified or
  disproportionate.
- Art. 50(2) "synthetic content" is read as covering analytic or structured outputs (forecasts, reports, rosters).
- "Profiling" is read broadly, which blocks the Art. 6(3) exception.

**Label doubts, flagged only; nothing was changed:** 1 case where "not an AI system" looks right; 2–3 arguable
out-of-scope versus minimal cases; 1 arguable credit case.

**Suggested fix, not applied:** when a step is unsure, keep the class the engine can establish as the headline
and show the stricter reading as an open question. The estimate is up to about 27 cases; it is untested.
