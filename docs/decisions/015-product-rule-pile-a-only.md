# 015 · The flip-feature product rule uses only Pile A and the Act's own conditions

- **Date:** 2026-09-29
- **Story:** E2 (docs/BACKLOG.md)
- **Status:** accepted (user, 2026-09-29, option A); leak check amended by 028 (runs that are the Act's own wording are exempt)

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
| **A. Rewrite** the three bullets as conditions stated in the Act, with no guideline example as their source | 5-word runs the prompt shares with any Pile B row's `text`, `lead_in`, `use_case` or `flip_variants` (153 rows) | 0 for the final prompt | The leak-check command below, run from the repo root on commit of this record |
| B. Keep the bullets and report hr-ex-226, 241 and 307 separately as contaminated | Nothing measured | Not chosen: it shrinks the held-out set and leaves the leak in the product | — |
| C. Remove the flip-feature list from the prompt | Nothing measured | Not chosen: drops the product rule for every system, including the Pile A variants | — |

Leak check (prints `153 Pile B rows; no shared 5-word runs`, or each shared run with the example it matches):

```bash
uv run --project backend python -c 'import json,re
W=lambda t:re.findall(r"[a-z0-9]+",re.sub("[’\x27]","",t.lower()))
G=lambda w:{tuple(w[i:i+5]) for i in range(len(w)-4)}
pb=set(json.load(open("eval/split.json"))["pile_b"])
rows=[r for r in map(json.loads,open("eval/commission_examples/examples.jsonl")) if r["example_id"] in pb]
B={g:r["example_id"] for r in rows for t in (r["text"],r["lead_in"] or "",r["use_case"] or "",json.dumps(r["flip_variants"])) for g in G(W(t))}
P=G(W(open("backend/aiact/engine/prompts/facts.md").read()))
print(len(rows),"Pile B rows;",sorted((" ".join(g),B[g]) for g in P&B.keys()) or "no shared 5-word runs")'
```

The rewritten lines, as they now stand in the prompt:
- **Fraud or money laundering:** "Checking payments or customers for fraud or money laundering: does it also assess
  creditworthiness or set credit scores for individuals?" This is Annex III 5(b)'s own question ("evaluate the
  creditworthiness of natural persons or establish their credit score"), whose exception takes systems used only to
  detect financial fraud out of 5(b). hr-ex-226's enrichment and profiling feature is no longer asked about here,
  and no Annex III 6(e) or law-enforcement probe replaces it: those belong to the high-risk and prohibited checks.
- **Faces, voices or behaviour:** "Analysing faces, voices or behaviour (for example in interviews, exams, border
  checks or at work): is it used as a polygraph or similar tool, or does it infer emotions?" (Annex III 6(b) and 7(a),
  "polygraphs or similar tools"; Art. 5(1)(f), inferring emotions in the workplace and education institutions.)
- **Political campaigns:** "Supporting political campaigns: do voters see its output directly, or is it only used to
  organise or run the campaign?" This asks Annex III 8(b)'s own exclusion: it "does not include AI systems to the
  output of which natural persons are not directly exposed, such as tools used to organise, optimise or structure
  political campaigns from an administrative or logistical point of view". A question about whether the tool aims to
  influence votes was dropped, because nearly every campaign tool would answer yes.

The other five bullets (court or dispute support, social scoring or crime prediction, workplace or education
emotion inference, public benefits, scholarships) come from Pile A rows or the user's backlog rules (B12). None of
them shares a 5-word run with Pile B, and they were left as they are.

## Decision
Option A. Decision 001's product rule is limited to Pile A examples and to conditions stated in the Act: a prompt
must never paraphrase a Pile B example's deciding feature, and no prompt line may share a 5-word run with a Pile B
row's text or `flip_variants`.

## Consequences
- `backend/aiact/engine/prompts/facts.md` carries the three rewritten lines. The five E2 replays were re-recorded
  against it for $0.0052638575 in total: the sum of the `usage.cost` fields OpenRouter returned, stored in
  `backend/tests/recordings/engine/nodes/test_facts/*.yaml`. The replay test checks each required question by its id
  and by a word in its text: `creditworthiness` ("credit"), `safety_function` ("safety") and `emotion_inference`
  ("emotion").
- **Every later engine prompt (E3–E8)** follows the same rule. Before merging, the isolation audit runs the leak
  check above on any changed prompt file.
- **E8 / V2:** scoring whether the engine asked about a row's flip feature is limited by this rule. For hr-ex-226 the
  facts node no longer asks about enrichment, so that row's variant is caught, or not, by the high-risk check alone.
  For hr-ex-241 and 307 the engine asks the Act's condition, not the example's wording.
- **Revisit** if the audit finds a looser paraphrase than a 5-word run, or if the Pile B size or membership changes.
