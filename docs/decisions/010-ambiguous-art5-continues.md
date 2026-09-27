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
