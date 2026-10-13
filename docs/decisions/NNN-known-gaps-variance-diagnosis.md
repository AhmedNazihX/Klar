# NNN · The engine's known gaps after E19: variance, rule or label

- **Date:** 2026-10-13
- **Story:** E14 (docs/BACKLOG.md); affects E17's deferred items, the high-risk and role prompts, and the own-a-14 label
- **Status:** proposed (waiting for the user): the diagnoses are final; the worked-example runs wait for the
  go-ahead on their cost, and the three follow-ups below are the user's to choose

## Question
After E19 the node replays still have five known gaps, and E19's recording showed two cases that flipped once
(own-e-09, own-c-15). The engine runs at temperature 0, but the pinned model reasons before it answers, so it is
not deterministic. For each one: is the miss run-to-run variance, a weakness of a prompt or a rule (fixable in
general, without tuning to the case), or a label question? The worked example's scope step wavered in the user's
live check (2026-10-07: one run asked, one decided), so it is diagnosed here too.

## How it was measured
Every committed recording of a replay is a recorded run. The replies were read from each version of the cassette in
git history (`git log -- <cassette>`, then the model's JSON reply in each version), with no new paid call. A run
counts as on the same prompt only when the node's prompt didn't change in between. The worked example also gets
five fresh runs of the scope step on one request (`tests/engine/nodes/test_scope_variance.py`), recorded once the
user agrees to the cost.

## Results
| Case (node) | Recorded runs: what wavers | Diagnosis | Kept as |
| --- | --- | --- | --- |
| own-b-05-regression-loan-scorecard (scope) | 5 of 5 (e8ba4f1, e0f4535, be9fda1, 66e3ae6, 710f1f1): `ai_system` yes, `guidance_excludes_technique` no, because guide-definition para 42 concerns optimisation and the scorecard predicts default | Not variance: a stable reading. The label holds the definition contested; the model reads para 42 the way the label's own reading A does. A rule that flags every named technique as contested would widen the scope prompt, against E18 and E19's work on over-strictness | Known gap (user, 2026-09-30) |
| own-d-03-assistant-repurposed-hiring (role) | Base `role` deployer in 4 of 5 (bd88a5b, 9c6b648, 1de2c6f, eb3f9b4), provider in 1 (be9fda1, the current one). eb3f9b4 (E8) and be9fda1 (E10) are on the same prompt in substance: the only change between them is the sentence about the user's answers | Variance. A deployer base with `builds_on_gpai` yes passes (provider through 25(1)(c), deployer kept); a provider base loses the deployer role. The prompt's role definition ("before any switch") doesn't say which role a company has when it builds its own system on another provider's model and uses it itself, so the model can read either one | Known gap; follow-up 1 |
| own-e-10-in-house-nodule-finder (high-risk) | `annex_i.third_party_assessment` unknown in 5 of 7 (9ea543b, 5abcc58, be9fda1, 710f1f1, c2a81f3), no in 2 (cc2962a, 69ec0a0); `settled_in_law` yes in all 7. On the current prompt, E19's two recordings split: 69ec0a0 "no" (decided not high-risk on the Annex I route) and c2a81f3 "unknown" (asks; the current one) | Variance between asking and a lenient "no", and a prompt weakness: nothing in high_risk.md covers an exemption from the sector law's conformity procedure (the MDR's in-house exemption). The model never reads it as open in law, which the label does. The Annex I guidelines (paras 27-30) don't address exemptions | Known gap; follow-up 2. A re-record can read "no" again, and the replay then fails |
| own-a-14-practice-phone-agent (transparency) | `deep_fake`: no (6f15db0, the passing B5a recording), unknown (be9fda1, 710f1f1), covered and open in law (69ec0a0, the current one); 4 runs across 3 prompt versions | Not variance: a label question. guide-art50 para 113 counts "realistic AI-generated human avatars or personas, and personal characteristics or expressions, such as image, voice" as persons, and a subject that "can plausibly exist" is enough. That supports the deep-fake reading the label leaves out | Known gap; follow-up 3 |
| own-a-15-intranet-assistant-in-house (transparency) | `interaction.exception`: yes before E18's T3 rule (6f15db0, be9fda1), open in law (710f1f1) and no (69ec0a0) after it. Both later runs say the mandatory training on AI tools isn't shown to be about this assistant | Not variance: a reading of T3's wording ("training on the AI system itself … can show all three together") against guide-art50 para 45's example (staff who are properly trained, AI literate and aware that they use AI systems). This is over-strictness, so it is E18 and E19's area | Known gap; E19's follow-up |
| own-e-09-ropeway-wear-forecast (high-risk, passes) | `annex_i.settled_in_law` no in 6 of 7 runs, yes in 1 (69ec0a0). On the current prompt: 69ec0a0 decided, c2a81f3 open (the current one, which passes) | Variance: the safety-component question is open in law in all the other runs | Passes; no entry |
| own-c-15-debt-collection-chat-pressure (prohibited, passes) | On the current prompt: 69ec0a0 `social_scoring` yes with `disproportionate_treatment` yes (point (c) decided), 4126434 the same with `disproportionate_treatment` no (the current one, which passes). Earlier: no and no (be9fda1, 7f02474), and open in law (2df6387) | Variance: 69ec0a0 counts the deceptive deadlines, which every debtor gets, as treatment resulting from a score. The prompt already says "the score leads to worse treatment", so no rule is missing | Passes; no entry |
| INIT worked example (scope) | `ai_system` unknown in all 6 whole-run recordings (7f02474, 5033d93, 66e3ae6, 710f1f1, cc2962a, 69ec0a0; the last three on the current scope prompt). The only scope answer that pauses the step is `ai_system`, and every other answer was the same in all 6. The user's live "decided" run must have read it yes | Variance on `ai_system` only, between the two readings INIT › Worked example accepts ("the engine may ask … or assume it is an AI system; either is accepted"). The prompt is clear: "unknown" when the answer depends on how the system works and the description doesn't say, which this one doesn't. No fix | Five fresh runs pending (see below) |

## Decision
No prompt or node change in E14. Each gap stays with its diagnosis in its `KNOWN_GAPS` reason. Two of the gaps
(own-d-03 and own-e-10) come from a general weakness, and each has a candidate fix. They are left to the user,
because E14 is the variance diagnosis only (user, 2026-10-12), and each fix changes a prompt every replay of its node
reads. own-a-14 is a label question.

The worked example's five runs are measured by `test_worked_example_scope_varies_only_between_inits_readings`. Every
run must be one of INIT's two readings, and nothing else may waver. Estimated cost: the scope call in the
worked-example cassette cost $0.00114 (OpenRouter `usage.cost`, 4,431 prompt and 965 completion tokens), so five runs
cost about $0.006, plus five embedding calls under $0.00001.

## Follow-ups (the user's to choose)
1. **Role prompt (own-d-03).** One sentence in role_obligations.md's `role`: when the company builds its own system on
   another provider's model, answer "deployer" when it also uses that system itself under its own authority, and
   "provider" when only others use it. The application already makes it the provider, and guide-art50 para 15 says
   one operator can be both. Cost: a re-record of every role replay. Risk: own-d-06 (a shop's website chat, labelled
   provider only) could gain a deployer role.
2. **High-risk prompt (own-e-10).** One rule for `third_party_assessment`: an exemption from the sector law's
   conformity procedure that the company relies on is never a "no" by itself. The answer is "unknown" while the
   description doesn't show the exemption's conditions are met. Once it does, whether Art. 6(1)(b) still applies is
   open in law (`open_on` "third_party_assessment"), because the Act's "is required to undergo" fits both readings and
   the Annex I guidelines don't reach it. Cost: a re-record of every high-risk replay. Benefit: it removes a
   false-low-risk reading seen in 2 of 7 runs.
3. **Label (own-a-14).** Should Art. 50(4) stay out of the label for a generic, very human-sounding synthetic phone
   voice? guide-art50 para 113 points the other way. A label change goes through eval/LABEL_CHANGES.md.

## Consequences
- `tests/engine/nodes/test_scope_variance.py`: the five-run replay, a strict "recording pending" xfail until it is
  recorded (`uv run pytest tests/engine/nodes/test_scope_variance.py --record-mode=once`, then drop the mark).
  Once recorded, the count of runs that ask (`ai_system` unknown) goes into the worked example's row above.
- The KNOWN_GAPS reasons in test_scope.py, test_role_obligations.py, test_high_risk.py and test_transparency.py name
  their E14 diagnosis.
- Revisit when a prompt named above changes, or when a re-record flips a gap the other way.
