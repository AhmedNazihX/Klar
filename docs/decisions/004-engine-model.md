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
  `google-vertex/eu`. Both pinned with fallbacks off, `zdr: true`, `data_collection: "deny"` (decision 005).
  The smoke models' OpenRouter SDK client is built with a `strategy="none"` retry config, so each call is exactly
  one HTTP attempt and every billed attempt is one the probe counts (ChatOpenRouter's own `max_retries=0` alone
  leaves the SDK on its default retries of 5XX and network errors; a mock-transport test pins one attempt on a
  503). Each probe stores the provider that served each call, read from OpenRouter's generation record
  (`predicted.smoke.served_by`, with the generation ids; the lookup client also never retries and times out
  after 5 s, and the lookup tries at most 12 times, 1.5 s apart, on a 404 or 429). A reply counts as failed if
  it isn't shown to come from the pinned provider: another provider (`served_as_pinned: false`), or no
  generation id or an unreadable record (`served_as_pinned: null`). The pinned names are `Azure` for Luna and
  `Google` for Gemini on Vertex, where Google AI Studio, which isn't ZDR, would show as `Google AI Studio`. The
  record names the provider, not the region: the EU region rests on the pinned endpoint with fallbacks off.
- **Broken** means the model answered but the answer didn't fit the node's JSON schema or the result contract
  (cross-field rules aren't in the schema, so contract failures count: decision 010 addendum). A reply cut off
  by the output cap (`finish_reason: "length"`) is broken too (decision 023 addendum, part 7). The nodes make no
  tool calls: retrieval is code, so structured output is the models' only interface.
- **Failed** means no usable answer: a transport, provider or database error, a reply not shown to come from
  the pinned provider, or a reply the provider broke off (`finish_reason: "error"`, which counts as no answer
  under decision 023 addendum, part 7). In within-cap checks on 2026-10-01, two of five Gemini role probes on
  own-d-01 broke off with a cut JSON at $0 cost; the other three were fine. A broken-off call is not looked up in
  OpenRouter's generation records (`predicted.smoke.lookup_skipped`), since an unbilled generation may have
  none and the wait would hold a slot for ~18 s. Failed probes count as neither broken nor wrong. Any other error
  stops the run, including a provision the corpus lacks: neither check lets the model name a provision, so that
  is a corpus gap, never the model's fault.
- **Accuracy** is over the labelled probes both models replied to, with a broken answer counted wrong; the
  broken share is over each model's replies.
- **Per-call evidence** (part 7): every probe stores each call's billed cost, tokens, generation id, OpenRouter's
  `finish_reason` and the provider's own `native_finish_reason` in `predicted.smoke.calls`, so each failed or
  broken probe can be checked from its row.
- **Inconclusive** (decision 023 addendum, parts 4-6, accepted by the user on 2026-10-01): if more than 10% of
  either model's probes got no usable answer, or no probe was scored for both, neither rule is applied and the
  run is repeated; it is not a verdict.
- **Stored runs.** One `eval_runs` row per model (`config.experiment = x2_engine_smoke`), one `eval_case_results`
  row per probe (`case_id = <node>:<case id>`). The verdict is recomputed from those rows by run id, and only from
  two completed runs that planned the same probes.
- **Cost.** Per call, OpenRouter's `usage.cost`; the token-price estimate when it's missing; the probe's worst
  case when the usage is missing too (`predicted.smoke.cost_is_estimated`). The cap is checked before each probe:
  a probe starts only while the spend plus the worst case of every probe in flight and of this one (the largest
  recorded prompt × 1.5 and the full output cap) stays within `--max-cost-usd`. The spend excludes the embedding calls retrieval makes (a few hundred
  tokens per search at $0.01/M, the same for both models).
- **Cost estimate** (`aiact evaluate smoke --dry-run`, cold prices, from the mean tokens of the 47 committed Luna
  node recordings, the role ones re-recorded by C7b with the Art. 111(2) section): Luna ~$0.099, Gemini ~$0.283,
  total ~$0.38.
- **Within-cap checks on 2026-10-01** (nothing stored): three single probes (Gemini role and high_risk on the
  worked example, Luna role) all fitted and matched the label, $0.0058, so Gemini accepts the engine's JSON schemas
  on `google-vertex/eu`. Two one-line calls and one role probe per model through the full probe path confirmed the
  generation records name `Azure` (Luna) and `Google` (Gemini), $0.0025. After C7b's role change, the high-risk
  role probe on own-d-01 ran once on Luna (fitted, matched) and five times on Gemini (three fitted and matched,
  two broken off with `finish_reason: "error"`), $0.0052; the no-retry client ran in all of them.

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
