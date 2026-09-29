# 015 · The flip-feature product rule uses only Pile A and the Act's own conditions

- **Date:** 2026-09-29
- **Story:** E2 (docs/BACKLOG.md)
- **Status:** accepted (user, 2026-09-29, option A)

## Question
Decision 001's product rule says the engine must ask about a "however / if" feature that would flip a guideline
example's verdict, because a user may describe the base version of a system that really has the feature. E2's
first facts prompt (`backend/aiact/engine/prompts/facts.md`) listed those features. The isolation audit found that
three of its bullets closely paraphrased the deciding feature of held-out Pile B examples, so the engine would see
part of their answer key on every run (INIT › Benchmark isolation):

| Bullet (first version) | Mirrors |
| --- | --- |
| Fraud or money laundering: "does it enrich the data with other personal data or build profiles of individuals?" | hr-ex-226 |
| Faces, voices or behaviour: "does it infer emotions, stress, truthfulness or deception?" | hr-ex-241 |
| Political campaigns: "does it generate new content, or target or profile voters?" | hr-ex-307 (its recorded flip feature) |

## Options
| Option | What was measured | Result | Source |
| --- | --- | --- | --- |
| **A. Rewrite** the three bullets as conditions stated in the Act, with no guideline example as their source | 5-word runs shared with any Pile B row's `text`, `lead_in`, `use_case` or `flip_variants` (153 rows) | 0 for every flip bullet and for the whole prompt; 0 in the 5 re-recorded replays | 5-word-run check over `eval/split.json` `pile_b` and `eval/commission_examples/examples.jsonl`, run in the E2 worktree |
| B. Keep the bullets and report hr-ex-226, 241 and 307 separately as contaminated | Nothing measured | Not chosen: it shrinks the held-out set and leaves the leak in the product | — |
| C. Remove the flip-feature list from the prompt | Nothing measured | Not chosen: drops the product rule for every system, including the Pile A variants | — |

The rewritten lines, as they now stand in the prompt:
- "Checking payments or customers for fraud or money laundering: is it only detecting financial fraud, or does it
  also assess creditworthiness or build profiles of individuals?" (Annex III 5(b) and its financial-fraud exception;
  Art. 6(3), where profiling of natural persons always stays high-risk)
- "Analysing faces, voices or behaviour (for example in interviews, exams, border checks or at work): is it used as a
  polygraph or similar tool, or does it infer emotions?" (Annex III 6(b) and 7(a), "polygraphs or similar tools";
  Art. 5(1)(f), inferring emotions in the workplace and education institutions)
- "Supporting political campaigns or public debate: is it meant to sway how people vote, or the result of an election
  or referendum?" (Annex III 8(b)). The coordinator's first wording, "intended to influence the outcome of an election
  or referendum", follows the Act word for word. It still shared 5-word runs with hr-ex-304 and hr-ex-307, which quote
  the Act, so it was reworded to keep the condition without the shared runs.

The other five bullets (court or dispute support, social scoring or crime prediction, workplace or education
emotion inference, public benefits, scholarships) come from Pile A rows or the user's backlog rules (B12). None of
them shares a 5-word run with Pile B, and they were left as they are.

## Decision
Option A. Decision 001's product rule is limited to Pile A examples and to conditions stated in the Act: a prompt
must never paraphrase a Pile B example's deciding feature, and no prompt line may share a 5-word run with a Pile B
row's text or `flip_variants`.

## Consequences
- `backend/aiact/engine/prompts/facts.md` carries the three rewritten lines. The five E2 replays were re-recorded
  against it (about $0.0055). Three required question ids follow the model's new wording: `fraud_only`,
  `machinery_safety_function` and `emotions_or_polygraph`.
- **Every later engine prompt (E3–E8)** follows the same rule. Before merging, the isolation audit should run the
  5-word-run check on any changed prompt file.
- **E8 / V2:** scoring whether the engine asked about a row's flip feature still works for hr-ex-226, 241 and 307.
  The engine now asks about the Act's condition, not the example's wording, so a question that covers the condition
  counts.
- **Revisit** if the audit finds a looser paraphrase than a 5-word run, or if the Pile B size or membership changes.
