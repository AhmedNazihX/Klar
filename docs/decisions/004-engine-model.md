# 004 · Engine model: GPT-6 Luna or Gemini 3.1 Flash-Lite

- **Date:** 2026-10-01
- **Story:** X2 (docs/BACKLOG.md); protocol in decision 023
- **Status:** proposed (results filled in from the stored runs on 2026-10-01; waiting for the user to accept)

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
- **Late generation records (deferred check, added after the first paid run).** In the first paid run on
  2026-10-01 (Luna run `d33c31fa-6183-45f1-bee0-0e86606e2ef8`, Gemini run `62fb71eb-b738-4ba6-a81e-3c50a8f0325b`),
  16 Luna and 9 Gemini probes were stored as failed although the model had replied in full: their generation
  record didn't show up within the ~18 s lookup (`not_pinned` = "generation … not found after 12 attempts").
  Under a real run's load, OpenRouter writes the records later than that. So a record that isn't found in time,
  or a lookup that fails in transport or with a server error (5xx), no longer fails the probe during the run. The
  probe is stored as *pending* (`scores.pending_verification`), with its kind (answered or broken) and its
  correctness kept. Once every probe of a model has run, and before its run is marked finished, the pending
  records are looked up again, all together, with a much longer window: one request per missing record per
  round, with waits of 5, 10, 20, 40 and then 60 s between rounds. A record not there yet, a transport error, a
  5xx or a rate limit (429) is tried again in a later round; a 429 also ends the round early. Each round asks
  first for the records not asked yet, so a round cut short never starves the rest; a record that never got
  asked before the time ran out says so ("not looked up within 300 s (budget spent)"). No request starts
  after 5 minutes (`DEFERRED_BUDGET_SECONDS`), and each request still times out after 5 s, so the check takes at
  most 5 minutes and 5 seconds per run. Any other failure (another 4xx, a record that names no provider) is
  final at once. If every call of the
  probe is shown to come from the pinned provider, the probe keeps its score. If one came from another provider,
  or a record still isn't there, the probe becomes failed (no answer), as before. Each settled row says what was
  found in `predicted.smoke.deferred_check`. A row still pending (only a run that stopped before the check
  leaves one) counts as failed, and such a run isn't compared anyway.
- **Recheck of stored runs (`aiact evaluate smoke-recheck <run id> …`).** The same longer lookup, for runs stored
  before the deferred check existed. It makes no model call, only the free generation-record lookups, and
  `--dry-run` prints what would change without writing anything. It takes only completed runs, and it reads and
  checks every run it is given before it looks anything up or writes anything, so one bad run id stops the
  command with nothing written; each run's summary is printed as soon as that run is stored. It looks again only
  at failed probes whose one fault was a lookup a later try may settle (a record not found in time or never
  looked up, a transport error, a 5xx or a 429): no `provider_error`, and a reply the run kept. It reads the reply from the
  stored row the way the run classed it. A stored `error` from the node's schema or the result contract is a
  broken answer; a reply cut off by the output cap raised one of those, so it stays broken. A transport,
  provider or database error was never an answer, and such a probe is never rescored. With no `error`, the
  stored outcome is the answer: it is read back and scored with the same matchers against the case's label, the
  case loaded from `eval/cases/own` by its id. The recheck refuses a case that changed since the run. If every
  call is confirmed on the pinned provider (the same exact name check: `Azure` for Luna, `Google` for Gemini),
  the row gets that score (`failed: false`, `served_as_pinned: true`), and `predicted.smoke.recheck` keeps the
  audit trail: when, the original `not_pinned`, the provider found, and `by: smoke-recheck`. If another provider
  served it, the row stays failed and names that provider. If the record still isn't there, the row is left as
  it is. The run's `config.rechecks` records each recheck (date, probes rechecked, confirmed, found served by
  another provider, still failing),
  and the run's status is never touched. Running it again changes nothing that is already settled. It then
  prints each run's summary and the comparison below, still computed only from the stored rows. Under the
  comparison's table, a line for each recheck that confirmed at least one probe says that the run's rows were
  rescored ("luna: rechecked on <date>: N probes confirmed late (smoke-recheck)", with ", M found served by
  another provider" added when it found any); a recheck that confirmed none gets no line.
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
| `openai/gpt-6-luna-20260922` | `d33c31fa-6183-45f1-bee0-0e86606e2ef8` | 2/82 (2.4%): facts 2 | 0/82 (0.0%) | 38/41 (92.7%) |
| `google/gemini-3.1-flash-lite` | `62fb71eb-b738-4ba6-a81e-3c50a8f0325b` | 0/82 (0.0%) | 0/82 (0.0%) | 35/41 (85.4%) |

Source: `uv run aiact evaluate smoke-recheck d33c31fa-6183-45f1-bee0-0e86606e2ef8 62fb71eb-b738-4ba6-a81e-3c50a8f0325b`
(2026-10-01), which prints the comparison from the stored rows. Both runs were made at commit 409bd4e. As first
stored, 16 Luna and 9 Gemini probes counted as "no answer" (19.5% and 11.0%, so the verdict was `inconclusive`). In
every one the model had replied in full, and only the served-provider record arrived after the lookup window. The
recheck confirmed all 25 on the pinned provider (16 Azure, 9 Google) and rescored the stored replies; each row keeps
the audit trail in `predicted.smoke.recheck`, and each run lists the recheck in `config.rechecks`.

Per node (broken / correct of scored):

| Node | Luna | Gemini |
| --- | --- | --- |
| facts (41) | 2 broken (one cut off by the output cap, `finish_reason: length`) / not scored | 0 broken / not scored |
| scope (13) | 0 / 12 of 13 | 0 / 12 of 13 |
| high_risk (15) | 0 / 14 of 15 | 0 / 11 of 15 |
| role_obligations (13) | 0 / 12 of 13 | 0 / 12 of 13 |

Spend (stored `eval_runs.cost_usd`, chat calls only; embeddings excluded, as above): $0.1128 (Luna), $0.1726
(Gemini), $0.2854 in total, against the dry run's cold-price estimate of $0.38. The recheck itself cost nothing.

## Decision
`keep_luna`. Under decision 023's rule: Luna's broken share is 2 of 82 answers (2.4%), under the 10% limit, and
its accuracy on the 41 probes both models answered is 92.7% against Gemini's 85.4%, 7.3 points **above** Gemini, so
the accuracy rule (10 or more points below) doesn't apply. No probe got no answer, so the run is conclusive (023
part 4). The engine model stays GPT-6 Luna, `openai/gpt-6-luna-20260922` on `azure/eu`.

## Consequences
- The engine model is GPT-6 Luna: `ENGINE_MODEL=openai/gpt-6-luna-20260922`, `ENGINE_PROVIDER=azure/eu` in
  `backend/.env` (unchanged, it was already Luna) and named in `backend/.env.example`.
- The E2, E3, E5 and E7 recordings were made with Luna, so none needs recording again; E8 records its nodes with
  Luna.
- Two broken facts answers: one hit the facts node's output cap (`finish_reason: length`). E8 should check the facts
  node's `MAX_OUTPUT_TOKENS` (4000) against Luna's reasoning, as E5 had to for the high-risk node.
- Own cases are development cases (decision 018): this settles the model, not the reported accuracy.
