# 010 · An ambiguous Art. 5 step keeps the run going

- **Date:** 2026-09-27
- **Story:** F3 (docs/BACKLOG.md)
- **Status:** accepted (approved by the user during the F3 review, as relayed by the orchestrator)

## Question
A `prohibited` result stops the run after the Art. 5 check (INIT > How it works, Risk classes). When the Art. 5
step is `legally_ambiguous`, should the run still stop there? The answer decides what the result contract lets
through and how E1 routes the graph. INIT asks for both readings of an ambiguous question to be shown, with the
stricter one as the labelled working assumption (INIT > How it works, Outcomes).

## Options
| Option | What was measured | Result | Source |
| --- | --- | --- | --- |
| A. Stop after Art. 5 whenever `risk_class=prohibited` | Contract fit | The lenient reading (not prohibited) has no class, role or obligations, so it can't be shown | INIT > How it works, Outcomes |
| B. Stop only when the Art. 5 step is `decided`; when it's ambiguous, run the remaining checks | Contract fit | Both readings exist; `risk_class=prohibited` stays the stricter working assumption | INIT > How it works, Outcomes |

No numbers were measured. This is a design choice about the contract.

## Decision
Option B. A `prohibited` result ends after the Art. 5 step only when that step's status is `decided`. When the
Art. 5 step is `legally_ambiguous`, the result keeps `risk_class=prohibited` as the stricter working assumption,
and the steps must include every remaining check, as for any other class. The rule that decided it is INIT's
requirement to show both readings.

## Consequences
- `ClassificationResult` (backend/aiact/schemas/result.py) enforces the rule: early ends are allowed only for
  `out_of_scope` after the scope step, and for `prohibited` with a decided Art. 5 step. Any other result must list
  all five steps, in order.
- E1 (graph skeleton) routes to the end after the prohibited node only on a decided match. An ambiguous match goes
  on to high_risk, transparency and role_obligations. E4 marks an unsettled match as `legally_ambiguous` and never
  as a decided `prohibited`.
- E8 (finalize) keeps `prohibited` as the working assumption and uses the later steps' outcome as the lenient
  reading. Role and obligations are therefore present on an ambiguous prohibited result.
- Revisit this if legal review says an ambiguous Art. 5 match must never show obligations for the lenient reading.

## Addendum (F3 second review)
These rules extend the decision and follow INIT > How it works, Outcomes (the stricter reading is the working
assumption).
- **Which stopping steps may end the run.** An early end (`out_of_scope` after scope, `prohibited` after Art. 5) is
  allowed only when the stopping step is `decided`, or is `needs_more_information` with `error` set and no
  `missing_fact`. The second case is a verification failure that E9 marks after routing; E9 does not re-route.
  A `legally_ambiguous` stopping step, or one missing a real fact, means the remaining checks run and all five steps
  are present.
- **Scope follows the same rule.** `out_of_scope` needs a decided (or error-only) scope step. An uncertain scope
  question has "in scope" as its stricter reading, so the engine goes on and the class comes from the later steps.
- **An out_of_scope result has no obligations, annex_point or transparency_duties.**
- **The status is derived from the steps:** `legally_ambiguous` if any step is, otherwise `needs_more_information`
  if any step is, otherwise `decided`. The contract requires this equality, so V2 can't under-report uncertain
  outcomes.
- **Every step's `missing_fact` appears, by id and with the same text, in `follow_up_questions`.**
- **JSON Schema limits.** These cross-field rules can't be expressed in JSON Schema. A model's structured output can
  match the schema and still fail validation, so X2 and V3 count a contract failure as a broken output.
  `OpenQuestion.readings` is an array with exactly two items (minItems/maxItems, not prefixItems), which structured
  output modes support more widely.

## Addendum (2026-10-01, decision 026 item 10)
A third early end: when the facts step finds the description too thin to start (what the tool decides or who it
affects is missing), the engine stops before the four checks with a "needs a description" outcome. It is a case of
`needs_more_information` and carries the three prompts (what it decides, who it affects, bought or built) as
follow-up questions; no class is predicted. The contract rule above ("any other result must list all five steps")
gains this exception. E13 sets the exact contract shape (which fields are empty, how the class is represented) and
how the metrics score the outcome, in its own decision record.
