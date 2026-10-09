# 033 · Refused requests: a second pinned EU model, measured before it is adopted

- **Date:** 2026-10-09 (draft); rule, privacy wording, decision date and paid run approved by the user 2026-10-10;
  measured 2026-10-10
- **Story:** X2b (docs/BACKLOG.md); revisits decision 004 for refused requests only; builds on 023, 029, 030
- **Status:** accepted (user, 2026-10-10). Verdict under the rule fixed before the run: **adopt** Gemini 3.1
  Flash-Lite for refused requests (13 of 13 answered, 7 of 7 labelled answers matching; see Results). The route
  itself is built by a later story (X2c).

## Question
GPT-6 Luna on `azure/eu` stays the engine model (decision 004). Azure's content filter refuses some descriptions
before the model runs: `finish_reason: content_filter`, "I'm sorry, but I cannot assist with that request.",
`prompt_tokens: 0`, cost 0. Since decision 030 such a check gives no risk class, only "a person must review it". The
systems refused are mostly the ones Art. 5(1)(ba) and (bb) exist for, so the product can't classify exactly those.
Should a second pinned EU model answer the requests Luna's provider refuses, and does one work?

What the committed recordings show (no new call made):

| Node | Cases | Refused by Azure | Source |
| --- | --- | --- | --- |
| prohibited (E4, `own/c`) | 17 | 8: own-c-01, 02, 04, 05, 06, 07, 14, 16 | `backend/tests/recordings/engine/nodes/test_prohibited/` (E10's re-record) |
| facts (E13, every own case) | 78 answered + 5 refused | 5: own-c-01, 02, 03, 05, 07 | `backend/tests/recordings/engine/nodes/test_facts/` |
| transparency (E6, `own/a`) | 16 | 0 | `test_transparency/` (2026-10-06) |
| scope, high_risk, role | 13, 17, 14 calls | 0 | their recordings |

The rate varies from run to run: own-c-06, 14 and 16 were answered in E4's run and refused in E10's; own-c-03 was
answered in E4's and E10's prohibited runs but refused twice under the original text (E11) and in E13's facts run.
So the measurement reads several Luna runs together.

## The rule (fixed before the run; approved by the user 2026-10-10, rule 2 at 4 in 5)
Implemented in `backend/aiact/eval/experiments/smoke_refusals.py` (`ANSWERED_SHARE`, `MATCHED_SHARE`), in integers.

- **M** is the set of probes (node and case) Luna's provider refused in at least one of the Luna runs below.
- The second model is **adopted** for refused requests if, on the M probes:
  1. it **answers at least N of the M**, with N = ⌈4M/5⌉ (4 in 5): an answer is not refused, not broken (the node's
     schema or the result contract) and not failed; and
  2. it **matches the label on at least 4 in 5 of the labelled probes it answers**, scored with
     `aiact/eval/experiments/matchers.py`, the rules the replay tests import.
  The facts node is scored for refusals and broken outputs only: an answered facts probe counts for rule 1, never for
  rule 2 (facts has no label, decision 023).
- **Inconclusive**, and neither rule applied, when Luna refused nothing in these runs, or when more than 1 in 10 of
  the M probes got no answer from the second model (a transport or provider error, a reply not shown to come from
  its pinned provider, a probe its run didn't plan; decision 023 addendum, part 4). An inconclusive run is repeated.
- **Rejected** when rule 1 fails, or rule 2 fails on at least one labelled answer; the own-Azure fallback below is
  then decided.
- **Inconclusive** too when rule 1 holds but none of the second model's answers carries a label (only facts probes
  were refused, say): rule 2 has nothing to read, and "0 of 0 matching" proves nothing. The run is repeated with
  refused check probes, or the user decides on rule 1 alone.

Example with the recordings' numbers: if M is 13 (8 prohibited, 5 facts), N is 11; with 8 prohibited answers, at
least 7 must match their label (7 × 5 ≥ 8 × 4).

**Where this differs from the DoD's wording (for the user to choose).** The DoD reads "matches the label on those it
answers": taken literally, every answered labelled probe must match (N of N). Rule 2 above asks for 4 in 5 instead,
the same tolerance as rule 1, because one model-to-model disagreement on a legally hard case (Art. 5(1)(ba)/(bb)
descriptions are near the line by design) would otherwise reject a model that answers everything. With the
recordings' 8 prohibited probes the difference is one probe: 4 in 5 accepts 7 of 8 matching, "all of them" needs
8 of 8. The user chose 4 in 5 (2026-10-10, before the run); `MATCHED_SHARE` stays (4, 5).

## How it is measured
`aiact evaluate smoke` (X2's harness), with the node and case subset X2b adds (`--node`, `--case`): the engine's own
nodes, prompts, retrieval and output caps, each model pinned with fallbacks off, `zdr: true`,
`data_collection: "deny"`, no retries (decision 005), and every reply checked against OpenRouter's generation record
for its pinned provider. X2b adds the prohibited node (E4) on `own/c` and the transparency node (E6) on `own/a`, and a
fourth probe outcome, **refused** (the node's refusal outcome, decisions 029 and 030), which is neither answered nor
broken. `aiact evaluate smoke-refusals` prints the table per node and the verdict from the stored rows.

Run plan (dry runs, `--dry-run`, no call made; cold prices from `smoke.TYPICAL_TOKENS`, an upper bound; X2's real
spend was about three quarters of its cold estimate, decision 004; refused calls cost $0):

| Run | Model | Nodes and cases | Probes | Estimate |
| --- | --- | --- | --- | --- |
| 1 | Luna | facts on every own case (77: the 74 below and the 3 too thin to start, `own/thin`, E13), scope `own/b` (13), prohibited `own/c` (17), high_risk `own/e` and the worked example (15), transparency `own/a` (16), role `own/d` with a role (13) | 151 | ≤ $0.236 |
| 2, 3 | Luna | facts and prohibited on `own/c` (17 + 17), again, for the run-to-run rate | 34 each | ≤ $0.065 each |
| 4 | Gemini 3.1 Flash-Lite | the nodes with a refusal, on the cases Luna refused in runs 1–3 (from the recordings: facts and prohibited on 9 cases) | ~18 | ≤ $0.097 |
| | | **Total** | ~237 | **≤ $0.47** ($0.463) |

Facts runs on the thin cases only when every check is planned (run 1) or facts runs alone: X2's own plan is unchanged.
`--case` takes a case's full id (`own-c-01-undress-photo-app`, as `--dry-run` prints them), repeated per case.

Commands (each run is capped with `--max-cost-usd`; the Gemini case list comes from runs 1–3, shown here with the
nine cases the recordings saw refused):

```
uv run aiact evaluate smoke --model luna --node facts --node scope --node prohibited --node high_risk --node transparency --node role_obligations --max-cost-usd 0.30
uv run aiact evaluate smoke --model luna --node facts --node prohibited --max-cost-usd 0.10
uv run aiact evaluate smoke --model luna --node facts --node prohibited --max-cost-usd 0.10
uv run aiact evaluate smoke --model gemini --node facts --node prohibited --case own-c-01-undress-photo-app --case own-c-02-undress-app-before-december --case own-c-03-image-tool-with-safeguards --case own-c-04-studio-digital-doubles-consent --case own-c-05-gossip-site-fake-nudes --case own-c-06-dating-app-nudity-blur --case own-c-07-unfiltered-image-generator --case own-c-14-kids-game-sad-pet-offers --case own-c-16-police-live-search-missing-child --max-cost-usd 0.15
uv run aiact evaluate smoke-refusals --engine-run <run 1> --engine-run <run 2> --engine-run <run 3> --second-run <run 4>
```

## Results
Measured 2026-10-10 on story branch `story/X2b-refusal-route-measure-decide` at 8e955a0, printed by
`aiact evaluate smoke-refusals` from the stored `eval_runs` rows. Run 4 was given the 8 cases Luna refused in runs 1–3
(own-c-16 was answered in all three, so it was left out of the command above).

| Node | Cases run | Refused by Luna | Answered by the second model | Matching the label | Refused by both | Broken | No answer |
| --- | --- | --- | --- | --- | --- | --- | --- |
| facts | 77 | 6 | 6 | - | 0 | 0 | 0 |
| scope | 13 | 0 | 0 | 0/0 | 0 | 0 | 0 |
| prohibited | 17 | 7 | 7 | 7/7 | 0 | 0 | 0 |
| high_risk | 15 | 0 | 0 | 0/0 | 0 | 0 | 0 |
| transparency | 16 | 0 | 0 | 0/0 | 0 | 0 | 0 |
| role_obligations | 13 | 0 | 0 | 0/0 | 0 | 0 | 0 |

| Run | Model | Probes | Cost (USD) |
| --- | --- | --- | --- |
| 9bca1781-5620-466a-929e-69d0eb1ea26f | luna (run 1, every node) | 151 | 0.1934 |
| 311613fb-9f91-498f-9f22-a63551ee6e9f | luna (run 2, facts and prohibited on own/c) | 34 | 0.0310 |
| 4ccd0883-8e4e-4101-b1fc-23e3f52088a1 | luna (run 3, the same) | 34 | 0.0333 |
| c5ceecfe-afcb-403f-b413-bf42be1bda60 | gemini (run 4, facts and prohibited on the 8 refused cases) | 16 | 0.0607 |
| | | **Total** | **0.3184** |

M = 13 refused probes (12 per Luna run, varying between runs: facts on own-c-04 only in runs 1 and 3, prohibited
on own-c-06 only in runs 2 and 3, on own-c-14 only in runs 1 and 2), all on the image-abuse and manipulation cases
of `own/c` (c-01 to c-07, c-14). N = ⌈4·13/5⌉ = 11. Rule 1: 13 of 13 answered. Rule 2: 7 of 7 labelled answers
match, which also meets the DoD's literal "all of them". No other node was refused. **Verdict: adopt.**

## The route, if the second model is adopted
- **The only exception to decision 004's no-fallback pin.** Every other call stays pinned to one model on one
  endpoint with `allow_fallbacks: false`. The route is not an OpenRouter fallback: the engine makes a second call,
  itself pinned.
- **It fires only on a provider refusal**: `finish_reason == "content_filter"` with no parseable answer (what
  `aiact.llm.structured.parse_reply` raises as `ProviderRefusalError`). A `content_filter` reply with a usable answer
  (own-c-16 in E4's run) is used as it is; a broken answer, a transport error or any other finish reason never
  triggers it. A model-level refusal (`message.refusal` set, `finish_reason: stop`, empty content; E8's question) is
  not a provider refusal and stays a broken output: it hasn't been seen on Luna. Revisit if it is.
- **Full slugs.** Engine model: `openai/gpt-6-luna-20260922` on `azure/eu`. Second model:
  `google/gemini-3.1-flash-lite` on `google-vertex/eu`. Both with `zdr: true`, `data_collection: "deny"`,
  `allow_fallbacks: false`, and the second model's reply checked against its pinned provider like the first's.
- **When both refuse**, decision 030 applies: the check is not assessed and the result carries no class.

## Privacy wording (accepted by the user 2026-10-10; INIT › Data policy, Ethical considerations › Choice of model providers)
Adopting the route adds a second processor for the refused requests only: Google, through OpenRouter, on Vertex
AI in the EU. The "Who processes it" panel already names Google Vertex AI next to Microsoft Azure
(`frontend/src/i18n/locales/*.json`, `privacy.who.modelsDetail`); the proposed sentence says what goes there and
when. A refused check's request is more than the description: it carries the facts extracted from it (facts from
the user's answers to follow-up questions included) and the law text retrieved for the check, and it is sent once
for each check the filter blocked, not once per description.

- EN: "If Microsoft Azure's content filter blocks a check, that check's request (the description and the facts and
  answers taken from it) is sent once more to Gemini 3.1 Flash-Lite on Google Vertex AI in the EU (zero data
  retention, no training), for each check the filter blocked. This happens only when the filter blocks it."
- DE: "Blockiert der Inhaltsfilter von Microsoft Azure eine Prüfung, wird die Anfrage dieser Prüfung (die
  Beschreibung sowie die daraus gewonnenen Fakten und Antworten) noch einmal an Gemini 3.1 Flash-Lite bei Google
  Vertex AI in der EU gesendet (keine Datenspeicherung beim Anbieter, kein Training), für jede blockierte Prüfung.
  Das geschieht nur, wenn der Filter sie blockiert."

The privacy notice names Google as a processor for these requests, reached through OpenRouter.

## If the second model also refuses
The fallback is an own Azure deployment with modified content filters (off OpenRouter; it needs Microsoft's approval;
user, 2026-10-02, BACKLOG › X2b "From E4"). Decision date: **2026-10-16** (accepted by the user 2026-10-10), one week
after the run, before the build freezes when W1 starts (decision 024). With the verdict "adopt", this applies only if
the built route's own tests or a later run show Gemini refusing too.

## Consequences (once accepted and measured)
- **Adopted:** a story implements the route in `aiact/llm` and the six model-calling nodes (one place:
  `common.refused_check`'s callers), with tests that it fires only on a refusal and stays pinned; E11's
  `test_replay_original_text_reads_no_december_point` (own-c-03) and the refused own-c and facts cases are recorded
  on it, and their `KNOWN_GAPS` entries go.
- **Rejected:** the own-Azure decision is taken by the date above; until then decision 030's class-less result stands.
- **Either way:** the run's numbers go into this record from the stored rows (run ids, `smoke-refusals`).
