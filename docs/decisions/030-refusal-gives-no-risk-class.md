# 030 · A provider refusal gives no risk class, only an explanation

- **Date:** 2026-10-07
- **Story:** X2b (docs/BACKLOG.md), found while recording E11's replays
- **Status:** accepted (user, 2026-10-07). Supersedes the "prohibited assumed" part of decision 029.

## Question
Decision 029 made a provider content-filter refusal return an honest "needs review" step instead of a schema error,
and kept **prohibited as the working assumption** (INIT › Risk classes: the stricter reading). Recording E11's
original-text replay for own-c-03 showed what that means for a user. The provider refused twice in a row, and the
result read: "The model provider's content filter blocked … None of the Art. 5 prohibitions can be ruled out:
prohibited is assumed until a person has reviewed it." Under the original text, the expected answer for that case is
"not prohibited". Should a refused check still put a risk class on the result?

| Run | Case | Response | Source |
| --- | --- | --- | --- |
| E11 replay recording, 1st try | own-c-03, law_version original | `content_filter`, the step assumed prohibited, status `needs_more_information` | `tests/engine/nodes/test_prohibited.py::test_replay_original_text_reads_no_december_point`, 2026-10-07 |
| E11 replay recording, retry | same | refused again | same test, 2026-10-07 |
| E4 first B5c run | own-c-01, 02, 03, 04, 05, 07 | `content_filter`, no answer | decision 029 |
| E10 re-record | 8 of 17 prohibited own cases | refused (the rate varies from run to run) | BACKLOG › X2b, "From E10" |

## Options
| Option | What it means | Result | Source |
| --- | --- | --- | --- |
| Keep 029 | A refusal shows an explanation and assumes prohibited | A harmless system that trips the filter is shown as prohibited: a false result the user can't tell apart from a real one | user, 2026-10-07: "they shouldn't get a false result" |
| **No risk class on a refusal** | A refusal shows only the explanation: the provider blocked the automatic check, so it couldn't be assessed and a person must review it. The result carries no risk class | Honest about what the tool doesn't know. Still never shown as a schema error (029's main point stands) | user, 2026-10-07 |

## Decision
A provider refusal never produces a risk class. The step and the result say plainly that the model provider blocked
the automatic check, so this system could not be assessed automatically and a person must review it. 029's other
rules stay: a refusal is detected (`content_filter` with no parseable answer), is never a schema error, and is never
treated as an answer. INIT's "stricter reading" rule is for legal ambiguity, where the law can be read two ways. A
refusal gives no reading at all, so the rule doesn't apply.

## Consequences
- **X2b** carries the engine change alongside its measurement. Today a refused node's step assumes prohibited; it
  must instead return a "not assessed" outcome with no risk class (a status or outcome the schema can express
  without a class), and the aggregated result must carry no class and say which step was refused. If X2b adopts a
  second model for refused requests, this outcome applies only when both models refuse.
- **E4 / E8 / E10 (merged):** the six nodes share `common.refused_check`, so the change lands in one place. The
  prohibited node's "prohibited assumed" text and the tests that pin it change with it. The own-c `KNOWN_GAPS` keep
  their reason, now "provider content filter (decisions 029, 030)".
- **E11:** the original-text replay for own-c-03 can't pass while the provider refuses it. No other case can test
  that point: Art. 5(1)(ba) is about undressing and fake-nude apps, which is the content the filter blocks. The
  replay stays `xfail` with the reason "provider refusal (decision 030); passes once X2b answers refused requests",
  and its refused cassette is not committed.
- **P5 / P21:** the result screens show the refusal explanation with no risk pill and no duty list. P21 (Prohibited
  result) must not show the prohibited screen for a refusal.
- **Benchmark (V8, W1):** a refused case scores as "not assessed", not as a prohibited prediction. The run report
  counts refusals separately.
- **Revisit** if the provider offers a filter setting for this use, or X2b's second model answers every refused case.
