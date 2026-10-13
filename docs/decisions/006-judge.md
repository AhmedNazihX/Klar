# 006 · The judge: Jev first, an LLM judge for unsure items, and the unsure margin

- **Date:** 2026-10-13
- **Story:** V4 (docs/BACKLOG.md)
- **Status:** accepted (2026-10-13, the user: margin 0.1; backup judge Haiku 5.5 once allowed in the guardrail, validated on both 4.5 and 5.5)

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
  (`test_nothing_outside_the_benchmark_package_imports_it`) imports every `aiact` module but
  `aiact.eval` and the CLI in a fresh interpreter and finds no `aiact.eval` module loaded, so no
  code serving users (API, engine, drafting, MCP, Q&A, reports) reaches the judge, by any import.

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
calibration error, and the margin table) come from `eval/judge_validation/report.md`.

## Validation result (2026-10-13)
- **Run:** Jev (`typesafe/jev-1.13`) and Claude Haiku 4.5 on `google-vertex/europe` answered all
  48 cases, none failed; $0.0529 OpenRouter. Haiku 5.5 is blocked in the OpenRouter workspace
  guardrail, so the user chose option C through `JUDGE_BACKUP_MODEL=anthropic/claude-haiku-4.5`
  in `backend/.env`, keeping 5.5 as the code default (the label filter's zero-retention route,
  decision 005). `test_backup_judge_roundtrip` stays recording-pending until 5.5 is allowed.
- **Labels (48: 21 yes, 27 no).** At the user's request a fresh Claude Opus agent drafted them,
  reading only `cases.yaml` and the README, never the judges' answers; its 36 clear cases were
  taken as drafted. The user labelled jv-en-01 to -04 (en-02 and en-03 corrected to no on review)
  and decided the 8 cases the agent marked hard (en-11 no, en-13 yes, en-24 no, de-02 yes, de-06
  yes, de-07 no, de-09 yes, de-18 no). Rules applied: an evidence tag is stated only when the text
  says it (a likely reading is no); a left-out detail makes an answer no only when it changes what
  the answer tells the asker; a point of Art. 5(1) cited without the list's opening sentence
  supports "prohibited". Caveat: the labels are Claude's reading checked by the user, not an
  independent human reference; Haiku (a Claude model) still agreed less with them than Jev.

| Judge | Agreement with the labels | Cohen's kappa |
| --- | --- | --- |
| Jev alone (margin 0) | 45/48 (94%) | 0.87 |
| Haiku 4.5 alone (margin 0.5) | 39/48 (81%) | 0.62 |
| Jev, Haiku 4.5 when unsure (margin 0.1, 1 case sent) | 46/48 (96%) | 0.92 |
| margin 0.2 (4 sent) / 0.3 (12 sent) | 43/48 (90%) / 41/48 (85%) | 0.79 / 0.71 |

Jev's calibration over the 48 labelled cases: Brier score 0.052, expected calibration error
0.089 (all 22 cases below 0.2 labelled no, all 14 at 0.8 or above labelled yes). By check, Jev
was 12/12 on citation support and invented content; Haiku 4.5 was 8/12 on invented content.
0.1 beats 0.0 by one case (jv-de-09), within noise on 48 cases.

**Re-run with Haiku 5.5 (same day).** The user then allowed `anthropic/claude-haiku-5.5` in the
guardrail and removed the 4.5 line, so the backup judge is the code default again; the 48 cases
were asked again ($0.0090 OpenRouter) and `test_backup_judge_roundtrip` recorded. Haiku 5.5 alone
agrees 45/48 (94%, κ 0.88), as often as Jev (45/48, κ 0.87; Brier 0.053, calibration error
0.087 on this run); by check 12/12 citation support, 11/12 evidence tags, 11/12 Q&A, 11/12
invented content. Combined: margin 0.1 sends 1 case and agrees 46/48 (κ 0.92); every margin
from 0.2 to 0.5 agrees 45/48. Margin 0.1 stays the choice. `report.md` and `answers.jsonl` hold
this run.

## Decision
Option A, the INIT design: Jev first, Claude Haiku 5.5 (the code default) for unsure items,
and the unsure margin 0.1 (`UNSURE_MARGIN`), the report's smallest margin with the highest
agreement with the hand labels (user, 2026-10-13). Option C (Haiku 4.5) was measured first while
5.5 was blocked; it chose the same margin. The rule as first proposed:
the margin `report.md` recommends, the smallest margin with
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
