# 032 · "Needs a description": the contract shape and how the benchmark scores it

- **Date:** 2026-10-08
- **Story:** E13 (docs/BACKLOG.md); also affects P20, B10c, V8, W1
- **Status:** proposed: the contract shape follows decision 010's addendum; the scoring rule (option A below) waits
  for the user's agreement, and the metrics carry it as a draft until then

## Question
Decision 010's addendum (2026-10-01, decision 026 item 10) adds a third early end: when the facts step finds the
description too thin to start (what the tool decides or who it affects is missing), the engine stops before the four
checks with a "needs a description" outcome, a case of `needs_more_information` that carries three prompts (what it
decides, who it affects, bought or built), and predicts no class. It left two things to E13: the exact contract shape,
and how the benchmark scores the outcome. INIT › Users and positioning: "The evaluation scores the engine directly, so
the measured accuracy describes what every user gets", so the outcome can't be left out of the metrics.

## The contract shape (follows the addendum)
| Field | A needs-a-description result | Source |
| --- | --- | --- |
| `steps` | empty; it is the only result with no steps | addendum: "stops before the four checks" |
| `risk_class` | `null`; a result has no class exactly when it has no steps | addendum: "no class is predicted" |
| `status` | `needs_more_information` | addendum |
| `follow_up_questions` | includes `what_it_decides`, `who_it_affects`, `bought_or_built` (`DESCRIPTION_QUESTION_IDS`), in the result's language, worded as artboard `ClassifyVague`, each with its example line as `hint` | addendum; artboard `ClassifyVague` |
| `facts` | the facts the description does give | E13 |
| `role`, `annex_point`, `transparency_duties`, `deciding_facts`, `obligations`, `legal_review`, `not_assessed` | empty | E13 |

The facts node decides it: the engine model's facts answer gains two booleans, `says_what_it_decides` and
`says_who_it_affects`; when either is false the graph goes from facts straight to finalize. A refused facts call
(decision 029) is not a thin description: the checks run, as before.

Every other result keeps the rules of decision 010: all five steps, or an early end after a decided scope or Art. 5
step. A schema test pins that every shorter list is still rejected.

## Options for the scoring
A needs-a-description result can meet two kinds of case: a thin-description case, whose label expects no class
(`risk_class: null`, `status: needs_more_information`, tag `thin-description`, written in B10c), or any other case,
which the engine should have classified.

| Option | Thin case answered "needs a description" | Thin case answered with a class | Other case answered "needs a description" | Pros | Cons |
| --- | --- | --- | --- | --- | --- |
| **A. Two rows of its own (proposed)** | hit in "Needs a description: asked" | miss there | counts in "Needs a description: asked wrongly"; a miss in risk-class and role accuracy; left out of false-low-risk and the downgrade rate | Risk-class accuracy keeps meaning "the right class"; the false-flag rate is visible on its own; a needless "tell us more" still costs accuracy | Two more rows in the report |
| B. Fold into risk-class accuracy | a hit in risk-class accuracy ("no class" counts as the right answer) | a miss there | a miss in risk-class accuracy only | One headline number | Mixes "no class" into a class metric; 2-5 thin cases among about 200 barely move it, so a false-flag problem stays hidden |
| C. Count a false flag apart, like a failed run | hit | miss | left out of every accuracy, counted only in its own row | Accuracy measures only the classified cases | Hides a real failure: the user got no class for a describable system |

Every option scores the status the same way: a needs-a-description result is `needs_more_information`, so it counts
in that status's precision and recall like any other (a thin case answered so is a true positive). A consistency
group with a needs-a-description member is not consistent (its classes differ).

Why false-low-risk leaves it out in A: the measure is "a high-risk or prohibited system shown a lower class", and
no class is shown; the user is asked to describe the tool. The false-flag row counts it instead.

## Decision
Proposed: option A. Waiting for the user.

## Consequences
- `backend/aiact/eval/metrics.py`: `description_asked` and `description_asked_wrongly` (keys in
  `eval_case_results.scores`), two rows in `RunMetrics` and the report; risk-class accuracy leaves thin cases out.
  Switching to B or C changes those two scorers and `risk_class_match` only.
- `backend/aiact/eval/cases.py`: `CaseLabel.risk_class` may be null, only with `needs_more_information` and no role
  or Annex point; such a label needs `notes` saying what is missing instead of a `label_citation` (no provision
  settles "too thin").
- **B10c** writes the thin-description cases with the `/case` skill; the user approves them.
- **P20** shows the outcome; until then the classify screen ends such a run like an unfinished one (no class, nothing
  saved).
- **Re-recording:** the facts prompt and its answer schema changed, so every facts recording and the worked example's
  end-to-end replay are re-recorded once (cost logged in the E13 hand-over).
