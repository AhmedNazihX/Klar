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
Draw the cases by a committed seed (stratified by risk class, at least 2 per engine step, a positive among the
Annex I and Annex III ones, decided English labels only), run them through the Commission checker, map each answer
to one `RiskClass` with a fixed table, and keep the answers in a YAML file from which a command writes
`eval/reports/pile_b/head_to_head.md`.

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
  `eval/reports/pile_b/head_to_head/`), the validation, and the rendering with an empty engine column. The user then
  runs the checker (about 25 questionnaires; my estimate is 2–4 hours).
- V10b fills the engine column from a stored run and scores both columns with the same code.
- Role and Annex point aren't compared. The checker is beta: the report gives each run's date, and notes it as a
  limitation if the checker doesn't cover the 2025–26 amendments (for example the December 2026 prohibitions in
  the own cases).
- Revisit if the Commission checker is withdrawn or changes its outcomes during the runs.

## Implementation (V10a; accepted by the user 2026-10-14: placement A, even split A, positive Annex case B)
- **Where the files live.** The draw, the answer sheet, the report and the screenshots are in
  `eval/reports/pile_b/` (`head_to_head_draw.json`, `head_to_head.yaml`, `head_to_head.md`, `head_to_head/`),
  not `eval/reports/`: they name Pile B cases with their labels, and the user's answers retell each case, so they
  go where the Engine lane can't read them (docs/LAYOUT.md: no cb-* id above `pile_b/`).
- **The draw.** Seed 20261014, 25 cases from the cases as tagged `labels-v1` (be072f0), read from the tag itself.
  "Stratified by risk class" is an even split: five per class, since the pool has all five. Each engine step is
  served first (two cases each, within the class shares), then each class is filled by a seeded sample. For
  Annex I and Annex III, at least one of the step's cases is a positive (a `high_risk` label reached through that
  Annex) when the pool has one (it has six for Annex I): the step's picks are among its positives until one is
  drawn. A case exercises a step by its own category (a–f) or Commission Annex area, by a class only one step
  gives (out of scope, prohibited, limited risk), and Art. 6(3) when its basis is the filter or it cites a
  lettered condition. `aiact evaluate head-to-head draw` reproduces it and refuses a different one. The first
  draw had no positive Annex I case; the rule was changed and the case set re-drawn before any checker run.
- **Scoring.** The checker's class is scored against the current labels (a later change has its LABEL_CHANGES
  row), with `metrics.class_match` and `metrics.class_too_low`, the bare-class forms of `risk_class_match` and
  `false_low_risk`; V10b scores the engine column with the same code.

## Amendment 2026-10-14: an agent answers the checker, the user spot-checks (user, option A)
- **Question.** The checker can be driven by a browser agent (Playwright: no login, no captcha; one radio-button
  question per step, the page names its question release, "6.5.1" on 2026-10-14). Who interprets each description to
  answer the checker's questions: an agent, or the user by hand as INIT › Evaluation › Head-to-head says?
- **Options.** A: a blind agent per case answers all 25, the user re-runs a seeded 5 by hand (about 40–60 min of the
  user's time; OpenRouter $0; Claude Code tokens a few million, mostly cached, an estimate). B: the user answers all
  25 by hand (2–4 h). The user knows the labels (they wrote or reviewed many of the cases), which can pull answers
  towards the right class; the agent never sees them, but is from the same project as the engine.
- **Decision: A.** One fresh agent per case gets only that case's description (no id, label, notes, engine output)
  and a fixed answering rule: answer from the description only; where it doesn't settle a question, pick the
  reading the description most directly supports (never a "don't know"-style option) and list that question as
  uncertain. The user's hand runs follow the same rule. It records every question and answer, the result and its headings verbatim,
  and the checker's question release.
- **Spot-check.** Seed 20261015: for each risk class in the order out_of_scope, prohibited, high_risk, limited_risk,
  minimal_risk, `random.Random(20261015).choice` over the sorted ids of the drawn cases of that class (one call per
  class, in that order), fixed before any agent run. The user runs these 5 by hand, blind to the agent's answers; the
  report shows both classes per spot-check case and every answer that differs. The scored column is the agent's.
- **Consequences.** The sheet records who answered each run, the question release and the uncertain questions, and
  holds the user's spot-check runs apart from the scored ones; the report states that an agent answered, instead of
  "by hand" (a V10a follow-up). V10a is done when the 25 agent runs and the 5 spot-checks pass `check --complete`.
  A spot-check disagreement on the class is discussed with the user case by case before the report is committed.
- **Answering rule changed 2026-10-14 (user, option B), after case-02.** The first rule picked a "don't know"-style
  option where the description didn't settle a question. A side review noted that this tilts against the checker:
  the engine always commits to a class (flagging "needs more information"), while a "don't know" can lead the checker
  to "can't determine", a miss. Rule B gives both the same footing; case-02 was re-run under it, and the report
  counts the uncertain answers per run.
- **Runs and spot-check outcome (2026-10-14).** All 25 cases were answered by blind agents on question release
  6.5.1 (Claude Code tokens: 1,738,158 for the 25 kept runs, plus 73,829 for case-02's run under the first rule,
  kept aside, not scored; OpenRouter $0). The result sentences were mapped to classes by the user's confirmed
  `headings` table (the "Risk level assessment" sentences, plus the prohibited, Art. 2 exclusion and Art. 50
  sentences, which the checker prints under "Your obligations"). The user's 5 hand runs agree with the agent's on
  the class in 3 of 5. Both disagreements were reviewed with the user one at a time:
  - the high-risk spot-check case (border screening): the hand run's "exclusively military, defence or national
    security" answer (Art. 2(3)) was a slip; the agent's Annex III point 7(b) route is right (user).
  - the minimal-risk spot-check case (job-ad wording tool): the hand run's "interacts directly with natural
    persons" tick (Art. 50(1)) was a slip; the agent's "not an AI system" is a judgement call it flagged as
    uncertain (expert-written pattern lists), which differs from the label (user). On borderline descriptions the
    checker's result turns on how the answerer reads "is it an AI system?" and "does it interact with people?".
  - Copy slips in the hand runs were corrected with the user's agreement (option labels' case and spelling, one
    question title, the role question's section title replaced by its question text, a lower-case "it"); the
    scored agent runs are unchanged.
