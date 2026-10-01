# 023 · Engine model smoke test: staged nodes, a fixed threshold, own cases

- **Date:** 2026-09-30
- **Story:** X2 (docs/BACKLOG.md); also affects E8
- **Status:** accepted (the user agreed to all three parts on 2026-09-30; inconclusive addendum accepted on 2026-10-01)

## Question
INIT › Engine safety net: a first-week smoke test of GPT-6 Luna against Gemini 3.1 Flash-Lite on 20 headline
cases; switch if more than 10% of Luna's outputs or tool calls are broken, "or its accuracy is clearly worse". X2
planned a single-prompt classifier (the engine is now staged), had no number for "clearly worse", and waited on B4
(not started), so the week-one check would land after V8.

## Decision
1. X2 replays the merged staged nodes (E2, E3, E7, and E5 once merged) under both models on their approved own
   cases (B5a–e), about 50 cases at roughly $0.002 each on Luna (decision 005).
2. Luna is dropped if more than 10% of its outputs are broken, or its accuracy is 10 or more percentage points
   below Gemini's on the same cases. The threshold is fixed before the run.
3. X2 no longer depends on B4, and E8 depends on X2, so the model is settled before the remaining nodes are recorded.

## Addendum (2026-10-01): an inconclusive outcome
Accepted by the user on 2026-10-01, before the run (option A of three: accept it; remove it; or count a missing
answer as broken).

4. The run ends **inconclusive**, and neither rule in part 2 is applied, when more than 10% of either model's
   probes got no answer (a transport, provider or database error, or a reply not served by the pinned provider),
   or when no probe was scored for both models. An inconclusive run is repeated. It is not a verdict.
5. A broken answer still counts against the model (part 2). Only a missing answer leads to inconclusive.
6. If repeated runs stay inconclusive because one model's endpoint keeps failing, that is a separate reason to
   drop it, and the user decides it then.
7. (user, 2026-10-01, option A of two) A call the provider breaks off, reported as `finish_reason: "error"`,
   counts as **no answer** (a provider error under part 4), not as a broken answer. A reply cut off by the model's
   output cap (`finish_reason: "length"`) stays **broken** (part 5). Each probe stores the provider's own finish
   reason and the call's cost, so the classification can be checked from the stored rows. The case that raised
   it: in X2's within-cap check, 2 of 5 Gemini role probes broke off with a cut JSON at a cost of $0.

Why: without it, an outage would produce a keep or drop verdict from part of the cases. The 10% broken rule
doesn't see missing answers, and the accuracy would be taken over whatever came back. Implemented as
`FAILED_SHARE_LIMIT = (1, 10)` in `backend/aiact/eval/experiments/smoke_verdict.py` (story X2).

## Consequences
- X2 writes the result to `docs/decisions/004-engine-model.md` (reserved).
- Own cases are development cases (decision 018), which suits a model comparison.
