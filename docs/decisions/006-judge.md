# 006 · The judge: Jev first, an LLM judge for unsure items, and the unsure margin

- **Date:** 2026-10-13
- **Story:** V4 (docs/BACKLOG.md)
- **Status:** proposed (waiting for the user: the hand labels, the validation run, then the margin)

## Question
INIT › Evaluation › Judge: the checks that need judgement (citation support, evidence tags, Q&A
support, no invented content) go first to Jev, which returns yes/no with a probability; unsure
cases go to an LLM judge with a written reason. Before use, the judge is validated on about 50
hand-labelled English and German cases, comparing Jev with the LLM judge on agreement and
calibration. Three things are open: whether Jev can act as a judge at all on OpenRouter (decision
005 ruled out `typesafe/jev-router`), which model is the LLM judge (the user picked Claude Haiku
5.5 as the candidate on 2026-10-10, subject to zero data retention on its route), and the unsure
margin.

## What is settled by measurement (2026-10-13)

### Jev answers yes/no questions through the Decisions API
- `typesafe/jev-1.13` answers a `noul` question (a yes/no question) with the probability of yes
  (OpenRouter docs, guides/community/jev and the Decisions API reference). The judge asks each
  check as one `noul` question with named fields as state (`aiact/eval/judge.py`, `CHECKS`).
- Live probe on two committed cases (`aiact.eval.judge_validation.judge_case`, not the validation
  run): jv-en-02 probability of yes 0.02 ($0.00002037), jv-de-08 0.19 ($0.000018228).
- Its only endpoint is `typesafe` (TypeSafe), on the ZDR list, $0.042 per million input tokens,
  output free, context 64,000 (`GET /api/v1/models/typesafe/jev-1.13/endpoints` and
  `GET /api/v1/endpoints/zdr`). V3's recorded call shows `"provider":"TypeSafe"`
  (`backend/tests/recordings/eval/test_baselines/test_jev_baseline_roundtrip.yaml`). So
  `jev-1.13` is not the engine model: the different-company rule of INIT › Tech stack holds. It has
  no EU endpoint; the judge only reads benchmark cases, Act text and the engine's answers to
  benchmark cases, never a user's description. This is an exception to decision 005's EU rule
  for model calls, limited to benchmark material: `judge.py` and `JevJudge` say so, and a test
  (`test_no_serving_code_imports_the_eval_package`) holds that nothing serving users
  (`aiact.api`, `aiact.engine`, `aiact.drafting`, `aiact.mcp`) imports `aiact.eval`.

### The LLM judge's route
| Model | EU ZDR endpoint | Price (in / out per M tokens) | JSON schema output | Source |
| --- | --- | --- | --- | --- |
| `anthropic/claude-haiku-5.5` (snapshot `-20261007`) | `google-vertex/europe` (also `amazon-bedrock/eu-west-1`, which lists no structured outputs) | $0.11 / $0.55 | yes (`structured_outputs` and `response_format`) | endpoints listing and ZDR list, 2026-10-13 |
| `anthropic/claude-haiku-4.5` | `google-vertex/europe`, `amazon-bedrock/eu-west-1` | $1.10 / $5.50 | `structured_outputs` only on Vertex | same; decision 005 |

- Zero data retention on Haiku 5.5's `google-vertex/europe` route is **confirmed** (it is on the
  ZDR list), as the user's 2026-10-10 decision required.
- A live call to Haiku 5.5 on that route was refused before reaching the model: "0 endpoints out
  of 3 requested are available matching your guardrail restrictions and data policy … Model
  blocked by guardrail: 3 endpoints excluded" (OpenRouter workspace guardrail). The same request
  to Haiku 4.5 on `google-vertex/europe` answered in the expected JSON ($0.0009405). Haiku 5.5
  needs the model allowed in the workspace guardrail.
- Prompt caching is not used: the judge's fixed instructions are a few hundred tokens, below what
  Anthropic caches.

## Options
| Option | What it means | Cost of the validation run (48 cases, both judges each) | Source |
| --- | --- | --- | --- |
| A. Jev first, Haiku 5.5 for unsure items (INIT's design) | the margin from the report decides how many items go to Haiku | at most $0.038 (`judge_validation.estimate_usd(48)`: every prompt at 3,000 tokens and every answer at 600) | estimate constants in `judge.py` |
| B. Haiku 5.5 alone | margin 0.5 in effect, Jev dropped | the same run measures it (the report's "Backup judge" column) | |
| C. Jev first, Haiku 4.5 for unsure items | no guardrail change; ten times Haiku 5.5's price | at most $0.32 by the same bound (the CLI gives no estimate for a backup model other than Haiku 5.5, and warns); the probe call cost $0.00094, so about $0.05 in practice | prices above; probe |

The validation numbers (agreement with the labels, Cohen's kappa, Jev's Brier score and
calibration error, and the margin table) come from `eval/judge_validation/report.md` after the
run. They are not here yet: the 48 cases await the user's labels.

## Decision (proposed)
Keep option A, the INIT design, with the margin `report.md` recommends: the smallest margin with
the highest agreement with the hand labels. If the backup judge alone (margin 0.5) agrees more
often than every smaller margin, Jev adds nothing and option B applies. The code ships with a
provisional margin of 0.3 (`UNSURE_MARGIN`), to be replaced by the measured one.

The report recommends no margin while any labelled case has no combined answer at some margin
(the judge that had to answer failed): such a case drops out of the larger margins only, so their
rates would rest on fewer cases than the smaller margins' and the rows couldn't be compared. An
unmeasured case is counted apart, never as a miss; the failed cases are rerun first (a run asks
them again). Accepting this record also accepts Jev's non-EU route for benchmark material only
(above).

## Consequences
- Settings (applied, with defaults, `.env.example` lists them): `JUDGE_MODEL=typesafe/jev-1.13`,
  `JUDGE_BACKUP_MODEL=anthropic/claude-haiku-5.5`, `JUDGE_BACKUP_PROVIDER=google-vertex/europe`,
  pinned with fallbacks off and one attempt per call.
- Before the run: allow `anthropic/claude-haiku-5.5` in the OpenRouter workspace guardrail, or set
  `JUDGE_BACKUP_MODEL=anthropic/claude-haiku-4.5` (option C). While the route is blocked, a run
  stops at the first case whose backup call reaches no model, so it pays Jev for one case only.
- A case is asked again when anything either judge reads changes: its texts, the check's
  question or criteria, or the backup judge's instructions (`input_sha256`).
- After the run: record the numbers and the chosen margin here, set `UNSURE_MARGIN` to it, and
  mark this record accepted. V5 (judged metrics) builds on `Judge.judge`.
- V6's RAGAS faithfulness stays the independent cross-check on Jev's verdicts (INIT; V6's note).
- Revisit when Jev's version changes (thresholds don't transfer between models), or when V5's
  manual sample disagrees with the judge noticeably more often than the validation did.
