# 036 · Head-to-head method: Commission checker, stratified draw, class-only scoring, YAML input

- **Date:** 2026-10-14
- **Story:** V10a (docs/BACKLOG.md); feeds V10b
- **Status:** accepted 2026-10-14 (all four choices the user's)

## Question
INIT › Evaluation › Head-to-head: "20–30 cases from the headline benchmark are run by hand through the FLI or
Commission checker, and both scores are reported, whichever way they fall." The INIT doesn't say which checker,
how the cases are picked, how a checker's answer becomes a score, or what the user fills in. The checkers are
questionnaires, so the user answers their questions from each case's description.

## Options
| Choice | Options compared | Chosen | Source |
| --- | --- | --- | --- |
| 1. Case selection | A stratified random draw with a fixed seed · B hand-picked per engine step · C random from Commission Pile B only | **A**, with at least 2 cases per engine step (scope, prohibited, Annex III, Annex I, Art. 6(3), transparency, roles), English cases with a decided label only | `risk_class_match` (`backend/aiact/eval/metrics.py`) skips `legally_ambiguous` and thin labels, so those would score nothing |
| 2. Checker | A Commission AI Act Service Desk checker · B FLI Compliance Checker · C both | **A** | Commission page: "currently in its beta version… an ongoing project" (https://ai-act-service-desk.ec.europa.eu/en/eu-ai-act-compliance-checker); FLI changelog last entry 3 July 2025, Official Journal text of 13 June 2024 (https://artificialintelligenceact.eu/assessment/eu-ai-act-compliance-checker/) |
| 3. Scoring | A one risk class per answer, class only · B class + role · C no score | **A**, scored with the engine's own `risk_class_match` and false-low-risk count | INIT asks for "both scores" |
| 4. Input format | A a hand-filled Markdown table · B a YAML file the user fills, validated, with the report generated from it | **B** | — |

## Decision
Draw the cases by a committed seed (stratified by risk class, at least 2 per engine step, decided English labels
only), run them through the Commission checker, map each answer to one `RiskClass` with a fixed table, and keep
the answers in a YAML file from which a command writes `eval/reports/head_to_head.md`.

The class table, by meaning; when several apply, the strictest wins, as in the engine:

| Checker outcome | Class |
| --- | --- |
| a prohibited practice | `prohibited` |
| high-risk (Annex I or III), with or without transparency duties | `high_risk` |
| Art. 50 transparency duties only | `limited_risk` |
| AI literacy only, or no specific duties | `minimal_risk` |
| the Act does not apply | `out_of_scope` |
| can't determine | no class (a miss, as for the engine) |

On the first case the user notes the checker's exact result headings. A heading the table doesn't fit gets a row
then, before any case is scored.

## Consequences
- V10a becomes `mixed`. An agent builds the draw (the seed and the rule are committed before any checker run), the
  YAML template (per case: `date`, `result_text` verbatim, `answers`, optional screenshot under
  `eval/reports/head_to_head/`), the validation, and the rendering with an empty engine column. The user then
  runs the checker (about 25 questionnaires; my estimate is 2–4 hours).
- V10b fills the engine column from a stored run and scores both columns with the same code.
- Role and Annex point aren't compared. The checker is beta: the report gives each run's date, and notes it as a
  limitation if the checker doesn't cover the 2025–26 amendments (for example the December 2026 prohibitions in
  the own cases).
- Revisit if the Commission checker is withdrawn or changes its outcomes during the runs.

## Implementation (V10a, for the user to confirm)
- **Where the files live.** The draw, the answer sheet, the report and the screenshots are in
  `eval/reports/pile_b/` (`head_to_head_draw.json`, `head_to_head.yaml`, `head_to_head.md`, `head_to_head/`),
  not `eval/reports/`: they name Pile B cases with their labels, and the user's answers retell each case, so they
  go where the Engine lane can't read them (docs/LAYOUT.md: no cb-* id above `pile_b/`).
- **The draw.** Seed 20261014, 25 cases from the cases as tagged `labels-v1` (be072f0), read from the tag itself.
  "Stratified by risk class" is an even split: five per class, since the pool has all five. Each engine step is
  served first (two cases each, within the class shares), then each class is filled by a seeded sample. A case
  exercises a step by its own category (a–f) or Commission Annex area, by a class only one step gives (out of
  scope, prohibited, limited risk), and Art. 6(3) when its basis is the filter or it cites a lettered condition.
  `aiact evaluate head-to-head draw` reproduces it and refuses a different one.
- **Scoring.** The checker's class is scored against the current labels (a later change has its LABEL_CHANGES
  row), with `metrics.class_match` and `metrics.class_too_low`, the bare-class forms of `risk_class_match` and
  `false_low_risk`; V10b scores the engine column with the same code.
