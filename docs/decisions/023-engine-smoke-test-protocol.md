# 023 · Engine model smoke test: staged nodes, a fixed threshold, own cases

- **Date:** 2026-09-30
- **Story:** X2 (docs/BACKLOG.md); also affects E8
- **Status:** accepted (the user agreed to all three parts on 2026-09-30)

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

## Consequences
- X2 writes the result to `docs/decisions/004-engine-model.md` (reserved).
- Own cases are development cases (decision 018), which suits a model comparison.
