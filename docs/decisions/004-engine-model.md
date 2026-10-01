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
below** Gemini's on the same cases. `aiact.eval.experiments.smoke_verdict.compare` applies it in integer arithmetic, so
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
  no answers, no exclusions), and is scored with the same rules, which the replay tests import from
  `aiact/eval/experiments/matchers.py` (class, route, Annex point, status, missing fact, role; the worked example
  must also cite Art. 6(3)). So Luna's numbers can be checked against the committed recordings.
- **Endpoints.** Luna `openai/gpt-6-luna-20260922` on `azure/eu`; Gemini `google/gemini-3.1-flash-lite` on
  `google-vertex/eu`. Both pinned with fallbacks off, `zdr: true`, `data_collection: "deny"` (decision 005), and
  with no client retries, so every billed attempt is one the probe counts. Each probe stores the provider that
  served each call, read from OpenRouter's generation record (`predicted.smoke.served_by`, with the generation
  ids), and counts as failed if it isn't the pinned one (`Azure` for Luna; `Google` for Gemini on Vertex, where
  Google AI Studio, which isn't ZDR, would show as `Google AI Studio`). The record names the provider, not the
  region: the EU region rests on the pinned endpoint with fallbacks off.
- **Broken** means the model answered but the answer didn't fit the node's JSON schema or the result contract
  (cross-field rules aren't in the schema, so contract failures count: decision 010 addendum), or named a
  provision the corpus doesn't have. A reply cut off by the output cap is broken too. The nodes make no tool
  calls: retrieval is code, so structured output is the models' only interface. **Failed** means no usable
  answer: a transport, provider or database error, or a reply from another provider than the pinned one. Failed
  probes count as neither broken nor wrong. Any other error stops the run. **Accuracy** is over the labelled probes
  both models replied to, with a broken answer counted wrong; the broken share is over each model's replies.
- **Inconclusive** (not part of decision 023; the user is asked to confirm it): if more than 10% of either model's
  probes got no usable answer, or no probe was scored for both, the rule isn't applied and the runs are repeated.
- **Stored runs.** One `eval_runs` row per model (`config.experiment = x2_engine_smoke`), one `eval_case_results`
  row per probe (`case_id = <node>:<case id>`). The verdict is recomputed from those rows by run id, and only from
  two completed runs that planned the same probes.
- **Cost.** Per call, OpenRouter's `usage.cost`, or the token-price estimate when it's missing
  (`predicted.smoke.cost_is_estimated`). The cap is checked before each probe: a probe starts only while the spend
  plus the worst case of every probe in flight and of this one (the largest recorded prompt × 1.5 and the full
  output cap) stays within `--max-cost-usd`. The spend excludes the embedding calls retrieval makes (a few hundred
  tokens per search at $0.01/M, the same for both models).
- **Cost estimate** (`aiact evaluate smoke --dry-run`, cold prices, from the mean tokens of the 47 committed Luna
  node recordings): Luna ~$0.096, Gemini ~$0.275, total ~$0.37.
- **Within-cap checks on 2026-10-01** (nothing stored): three single probes (Gemini role and high_risk on the
  worked example, Luna role) all fitted and matched the label, $0.0058, so Gemini accepts the engine's JSON schemas
  on `google-vertex/eu`. Two one-line calls and one role probe per model through the full probe path confirmed the
  generation records name `Azure` (Luna) and `Google` (Gemini), $0.0025.

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
