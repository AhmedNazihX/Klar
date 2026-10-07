# 019 · Follow-up answers are appended to the description; the eval uses fixed answers

- **Date:** 2026-09-30
- **Story:** E10 (docs/BACKLOG.md); also affects B6, V8, P5
- **Status:** accepted (the user agreed on 2026-09-30)

## Question
INIT › Metrics asks for the downgrade rate "with and without key-fact questions", but `EngineInput.answers`
(`backend/aiact/engine/state.py`) is unused, a fact from an answer can't be `stated`, and no case carries answers.

## Options
| Question | Options | Source |
| --- | --- | --- |
| How answers enter | Append them to the description as text (INIT › How it works: "The interface asks them, adds the answers to the description, and runs the engine again"), or a separate structured channel | INIT l.37; E10 note from E2 |
| Who answers in the eval | Fixed answers stored in each B6 case, or a simulated answerer model over a hidden full description | backlog review finding A3 |

## Decision
Answers are appended to the description (a fact from an answer is `stated`, with a span in the extended text),
and each B6 soft-wording case stores fixed answers to its likely key-fact questions; a question with no stored
answer is answered "don't know". Fixed answers are free and reproducible; appending follows INIT.

## Consequences
- E10: `classify_system` appends the answers and drops the separate `answers` path; a test shows an answer turning a fact into `stated`.
- B6: the case format gains `key_fact_answers`.
- V8: two stored run_ids for the downgrade rate, without and with the answers.
- P5's follow-up loop uses the same append rule.
- Amended 2026-10-07 (user, at B6 review): V8 appends only the stored answers whose key is the id of a question the engine asked in that run; any other question is answered "don't know". Keys are fixed-question ids (`annex_iii_use`, `ai_system`, …); model-written questions (`about: high_risk`) get no stored answer.
