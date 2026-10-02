# 029 · A provider refusal gives an honest "needs review" step, not an error

- **Date:** 2026-10-02
- **Story:** E4 (docs/BACKLOG.md)
- **Status:** accepted (user, 2026-10-02, option A)

## Question
E4's first B5c recording sent all 17 category-c cases to the pinned engine model (decision 004,
`openai/gpt-6-luna-20260922` on `azure/eu`, no fallbacks). For 6 cases the provider's content filter blocked the
input before the model ran, so the node failed with a misleading "Invalid JSON" schema error. Those cases are exactly
the ones the Art. 5(1)(ba)/(bb) check exists for, so a user describing such a system would get an error from the
check meant to flag it. What should a node do when the provider refuses?

| Case | Response | Source |
| --- | --- | --- |
| own-c-01, 02, 03, 04, 05, 07 (undressing apps, fake nudes, abuse material) | `finish_reason: content_filter`, content "I'm sorry, but I cannot assist with that request.", `prompt_tokens: 0`, `cost: 0` | `backend/tests/recordings/engine/nodes/test_prohibited/test_b5c_case_replay[own-c-0{1,2,3,4,5,7}-*].yaml` |
| own-c-16 (police live search) | `finish_reason: content_filter` but a usable answer; the replay passes | same folder, `own-c-16-*` |
| The other 10 cases | `finish_reason: stop` | same folder |

The whole recording cost $0.022531981 (the sum of the `usage.cost` fields in the 17 cassettes).

## Options
| Option | What it means | Result | Source |
| --- | --- | --- | --- |
| **A. Detect the refusal; return a code-decided step** | The node recognises `content_filter` with no usable answer and returns "could not be assessed automatically; Art. 5(1)(ba)/(bb) may apply; have a person review it", status `needs_more_information`, prohibited assumed (INIT › Risk classes: the stricter reading) | Keeps E4 on schedule; the 6 cases are known gaps with that reason | user, 2026-10-02 |
| B. Route refused descriptions to a second, unfiltered model | Changes decision 004's pin | Needs a measured comparison first, so it delays E4 | — |
| C. Leave the error | The product shows an error for these systems | Not chosen | — |

## Decision
Option A. A provider refusal is never shown as a schema error or treated as an answer: the node returns an explicit,
code-decided step that says the system could not be assessed automatically and needs a person's review, keeps
prohibited as the working assumption, and cites the provisions the node always fetches.

## Consequences
- **E4:** the prohibited node detects the refusal (`finish_reason` `content_filter` with no parseable answer) and
  returns that step. own-c-01, 02, 03, 04, 05 and 07 go into `KNOWN_GAPS` with the reason "provider content
  filter (decision 029)".
- **E8 / E10:** every node that calls the engine model handles a refusal the same way, and the aggregated result
  says which step was not assessed. The scope and high-risk nodes are likely to meet the same filter on these
  descriptions.
- **Follow-up:** measure the refusal rate over the benchmark (V8) and compare a second model for refused inputs in a
  new decision that revisits 004 (a paid comparison, which needs the user's go-ahead).
- **Revisit** if the refusal rate on the benchmark is high enough to move the headline numbers, or if the provider
  offers a filter setting for this use.
