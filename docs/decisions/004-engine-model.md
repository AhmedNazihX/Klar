# 004 · Engine model: GPT-6 Luna or Gemini 3.1 Flash-Lite

- **Date:** 2026-10-01 (draft; the numbers come from the paid run)
- **Story:** X2 (docs/BACKLOG.md); protocol in decision 023
- **Status:** DRAFT: the two-model run has not been made. Fill in the `TBD` cells from the output of
  `aiact evaluate smoke` (or `aiact evaluate smoke-compare <luna run> <gemini run>`), then ask the user to accept.

## Question
INIT › Engine safety net: GPT-6 Luna was released on 22 September 2026 and has no track record. Does it produce
usable outputs on the staged engine, or does the engine switch to Gemini 3.1 Flash-Lite?

## The rule (fixed before the run, decision 023)
Luna is dropped if **more than 10%** of its outputs are broken, or its accuracy is **10 or more percentage points
below** Gemini's on the same cases. `aiact.eval.experiments.smoke.compare` applies it in integer arithmetic, so
exactly 10% broken keeps Luna and exactly 10 points below drops it.

## How it was measured
- **Nodes and cases.** `aiact evaluate smoke` runs the merged engine nodes, with their own prompts, retrieval and
  output caps, under each model:
  - facts (E2) on every case below: broken outputs only (facts have no label);
  - scope (E3) on the 13 B5b cases (`eval/cases/own/b`);
  - high_risk (E5) on INIT's worked example and the 14 B5e cases (`own/e`);
  - role_obligations (E7) on the 13 B5d cases (`own/d`), given the class the label settles (the role-only replay
    the user chose on 2026-09-29).

  That is 82 probes on 41 descriptions per model. Every probe sees the state its node's replay test uses (no facts,
  no answers, no exclusions), and is scored with the same rule as that replay (class, route, Annex point, status,
  missing fact, role), so Luna's numbers can be checked against the committed recordings.
- **Endpoints.** Luna `openai/gpt-6-luna-20260922` on `azure/eu`; Gemini `google/gemini-3.1-flash-lite` on
  `google-vertex/eu`. Both pinned with fallbacks off, `zdr: true`, `data_collection: "deny"` (decision 005).
- **Broken** means the model answered but the answer didn't fit the node's JSON schema or the result contract
  (cross-field rules aren't in the schema, so contract failures count: decision 010 addendum). A reply cut off by
  the output cap is broken too. The nodes make no tool calls: retrieval is code, so structured output is the
  models' only interface. **Failed** means no answer came back (network, provider or database error); failed
  probes count as neither broken nor wrong, and more than 10% of them for either model makes the verdict
  inconclusive. **Accuracy** is over the labelled probes both models answered, with a broken answer counted wrong.
- **Stored runs.** One `eval_runs` row per model (`config.experiment = x2_engine_smoke`), one `eval_case_results`
  row per probe (`case_id = <node>:<case id>`). The verdict is recomputed from those rows by run id.
- **Cost estimate** (`aiact evaluate smoke --dry-run`, cold prices, from the mean tokens of the 47 committed Luna
  node recordings): Luna ~$0.096, Gemini ~$0.275, total ~$0.37. A within-cap check on 2026-10-01 ran three single
  probes (Gemini role and high_risk on the worked example, Luna role): all three fitted and matched the label,
  $0.0058 in total, so Gemini accepts the engine's JSON schemas on `google-vertex/eu`. Nothing from that check
  was stored.

## Results
| Model | Run id | Broken answers | No answer | Accuracy (same probes) |
| --- | --- | --- | --- | --- |
| `openai/gpt-6-luna-20260922` | TBD | TBD | TBD | TBD |
| `google/gemini-3.1-flash-lite` | TBD | TBD | TBD | TBD |

Per node (broken / accuracy): TBD. Spend: TBD (Luna), TBD (Gemini).

## Decision
TBD: `keep_luna` or `drop_luna`, as the rule gives it.

## Consequences
- The engine model is set in `backend/.env` (`ENGINE_MODEL`, `ENGINE_PROVIDER`) and named in
  `backend/.env.example`: Luna `openai/gpt-6-luna-20260922` on `azure/eu`, or Gemini
  `google/gemini-3.1-flash-lite` on `google-vertex/eu`.
- If Gemini: the E2, E3, E5 and E7 replays are recorded again under Gemini before E8 records its nodes.
- Own cases are development cases (decision 018): this settles the model, not the reported accuracy.
