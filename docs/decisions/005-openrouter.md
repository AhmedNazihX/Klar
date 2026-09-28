# 005 · OpenRouter routes, prompt caching and cost per classification

- **Date:** 2026-09-28
- **Story:** X3 (docs/BACKLOG.md)
- **Status:** proposed (waiting for the user: confirm the spending cap, see Consequences)

## Question
INIT › Open questions (Implementation decisions still open) asks whether OpenRouter passes prompt caching through
for the chosen models, whether it offers EU routes, and what GPT-6 Luna's context window is. INIT › Tech stack
(Budget rules) asks for the real token use of one classification in week one, and INIT › Risks names a hard spending
cap on the OpenRouter key as the budget guard. The answers decide how every model call is routed and whether the
€50 budget holds.

## How it was measured
- **Endpoint facts** (context window, prices, ZDR, supported parameters): `GET /api/v1/models`,
  `GET /api/v1/models/<slug>/endpoints` and `GET /api/v1/endpoints/zdr` on 2026-09-28. These calls are free.
- **One sample classification**: a single chat call per model. The system prompt holds the fixed-order instructions
  (scope → Art. 5 → Art. 6/Annex III → Art. 50 → role) plus Articles 5, 6, 50 and Annex III as retrieved context,
  cut from the consolidated English text in `data/raw/ai-act-consolidated.en.html` (31,243 characters). The user
  message is an invented CV-ranking product (not a benchmark case; `eval/` was not read). The output is JSON with
  `risk_class`, `steps` and `follow_up_questions`. Every call sent `zdr: true`, `data_collection: "deny"`,
  `allow_fallbacks: false` and pinned one EU endpoint in `provider.order`. The same request was sent twice, 3 s apart,
  to see whether the second call reads from the cache. Each row cites the OpenRouter generation id, which can be
  looked up with `GET /api/v1/generation?id=<id>`.
- Total live spend of X3: **$0.037319** (six classification calls $0.037315, one Jev probe $0.0000038).

## Answers to the open questions

### Prompt caching: works for every chosen chat model on its EU ZDR route
| Model (EU ZDR endpoint) | Call | Prompt tokens | Cached read | Cache write | Output (reasoning) | Cost (USD) | Generation id |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `openai/gpt-6-luna` (`azure/eu`) | 1 | 6,026 | 0 | 6,023 | 1,854 (1,015) | 0.0018482 | gen-1790588216-Nvstw7Ptv77dnfoKEBEh |
| `openai/gpt-6-luna` (`azure/eu`) | 2 | 6,026 | 6,023 | 0 | 1,563 (709) | 0.0009262 | gen-1790588231-fUibmDa5tPycN094aFE2 |
| `google/gemini-3.1-flash-lite` (`google-vertex/eu`) | 1 | 6,054 | 0 | 0 | 541 (0) | 0.0025575 | gen-1790588244-lASbA7G0r6NNhzJ3xnRM |
| `google/gemini-3.1-flash-lite` (`google-vertex/eu`) | 2 | 6,054 | 6,042 | 0 | 493 (0) | 0.0009829 | gen-1790588250-SdKXtZbOt977Re43hNOg |
| `anthropic/claude-haiku-4.5` (`google-vertex/europe`) | 1 | 6,463 | 0 | 6,460 | 1,999 (0) | 0.0198803 | gen-1790588288-2MyVJaxyBgnSeYRb8Hrv |
| `anthropic/claude-haiku-4.5` (`google-vertex/europe`) | 2 | 6,463 | 6,460 | 0 | 1,892 (0) | 0.0111199 | gen-1790588314-3STVC9h4QMSRxaWuqOkT |

- **GPT-6 Luna** caches automatically (no request flag). The first call pays the cache-write price ($0.1375/M, 1.25×
  input); a repeat of the same prefix reads at $0.011/M (0.1× input). The prompt part of the cost fell from
  $0.00082849 to $0.00006658. OpenRouter's `supports_implicit_caching` flag says `false` for every Luna endpoint,
  yet the usage shows cache writes and reads, so the flag is not a reliable signal.
- **Gemini 3.1 Flash-Lite** caches implicitly with no write charge; the cached read is 0.1× input. Prompt cost fell
  from $0.00166485 to $0.00016946.
- **Claude Haiku 4.5** caches only when asked: the request sets top-level `cache_control: {"type": "ephemeral"}`.
  Prompt cost fell from $0.0088858 to $0.0007139. The same holds for Claude Sonnet 5 (same provider mechanism; not
  called, to save budget).
- Caching needs an identical prefix: static instructions and retrieved provisions first, the user's description last.
  With one pinned endpoint the second call hit the cache without a `session_id`.
- The Vertex Haiku endpoints reject `response_format: json_object` (routing error "Filter by Parameters removed
  google-vertex/global, google-vertex/europe"). They list `structured_outputs` as supported, so V4 and B8 should
  use a JSON schema, not JSON mode, on that route.

### Token use of one sample classification
- One single-prompt classification with Articles 5, 6, 50 and Annex III as context costs about **6,000 prompt
  tokens and 1,500–1,900 output tokens** on Luna, of which 700–1,000 are reasoning tokens (rows above).
- On Luna via `azure/eu` that is **$0.0018 cold and $0.0009 with a warm cache**. Output tokens are most of the cost
  once the prefix is cached ($0.00086 of $0.00093 on call 2).
- Arithmetic projection, not a measurement: the staged engine makes several model calls per case. At six calls per
  case at the cold price, one case costs 6 × $0.0018 = $0.011, and a 100-case headline run about $1.1. The real
  figure comes from E-stories' LangSmith traces.

### EU routes and ZDR options per chosen model
Context and prices are per endpoint from `GET /api/v1/models/<slug>/endpoints`; ZDR is membership in
`GET /api/v1/endpoints/zdr`. Prices are USD per million tokens (input / output / cache read).

| Role (INIT › Tech stack) | Slug | Context window (max output) | EU endpoint(s) that are ZDR | EU price | Notes |
| --- | --- | --- | --- | --- | --- |
| Engine | `openai/gpt-6-luna` (pinned `openai/gpt-6-luna-20260922`) | 1,050,000 (128,000); OpenAI endpoints cap the prompt at 922,000; long-context price above 272,000 prompt tokens | `azure/eu` | 0.11 / 0.55 / 0.011 | ZDR endpoints: `azure`, `azure/us`, `azure/eu`. The `openai` endpoints (incl. `openai/flex`, `openai/fast`) are not ZDR. Supports tools, `response_format`, `structured_outputs`, `reasoning` |
| Fallback engine, RAGAS | `google/gemini-3.1-flash-lite` | 1,048,576 (65,536) | `google-vertex/eu` | 0.275 / 1.65 / 0.0275 | Google AI Studio endpoints are not ZDR; all five Vertex endpoints are |
| Judge backup, label filter | `anthropic/claude-haiku-4.5` | 200,000 (64,000) | `amazon-bedrock/eu-west-1`, `google-vertex/europe` | 1.10 / 5.50 / 0.11 | `anthropic` and `azure/global` are removed by `data_collection: deny` + `zdr`. Vertex: no `response_format`, has `structured_outputs` |
| Premium comparison | `anthropic/claude-sonnet-5` | 1,000,000 (128,000) | `amazon-bedrock/eu-west-1`, `google-vertex/europe` | 2.20 / 11.00 / 0.22 | Bedrock endpoints do not list `structured_outputs`; use `google-vertex/europe` |
| Judge (first pass) | `typesafe/jev-router`, `typesafe/jev-1.13` | router: 1,000,000; jev-1.13: 32,000 | none with an EU tag | jev-1.13: 0.042 input | See Jev below |
| Embeddings | `qwen/qwen3-embedding-8b` | Nebius 32,000 | `nebius` (ZDR) | 0.01 input | Nebius is the EU host named in INIT; OpenRouter gives no region tag for it. `deepinfra/us` and `siliconflow/fp8` are also ZDR but not EU |
| Embedding comparison arm | `openai/text-embedding-3-large` | 8,192 | none (`azure` is ZDR, no EU tag) | 0.13 input | Evaluation only: embeds corpus text and benchmark queries, never user input |

- **Regional endpoints must be pinned by full slug.** On the global domain, OpenRouter's default routing skips
  endpoints with a regional surcharge whenever a standard-priced endpoint exists ("Filter by Regional Surcharge" in
  the routing error above). A request reaches `azure/eu`, `google-vertex/eu`, `google-vertex/europe` or
  `amazon-bedrock/eu-west-1` only when that slug is in `provider.order` or `provider.only`; a bare `azure` or
  `google-vertex` does not select them (OpenRouter docs, guides/features/in-region-routing). The EU surcharge is 10%
  over the standard price for every model above.
- **In-region processing at OpenRouter itself** (`https://eu.openrouter.ai`, requests decrypted and handled in the
  EU) exists only on Business and Enterprise plans (OpenRouter docs, guides/features/sovereign-ai). This key reports
  `allowed_data_regions: ["global"]`, so OpenRouter's own hop stays global; only the model provider is pinned to the
  EU. The privacy notice (P-stories) must say so.
- **ZDR and no-training** are enforced per request by `provider: {zdr: true, data_collection: "deny"}`, which F6's
  `aiact.llm.routing.provider_preferences` already sends on every call.

### Jev (judge) through OpenRouter
- `typesafe/jev-1.13` is a "decisions model": chat completions returns HTTP 400 "cannot be used with the
  chat/completions endpoint. Use the /api/alpha/decisions endpoint instead." Its endpoint lists no tools, no
  `response_format` and no `structured_outputs`.
- `typesafe/jev-router` has no endpoints of its own; it forwards to another model. A 13-token probe with ZDR on was
  answered by **`openai/gpt-6-luna` on Azure** (gen-1790588362-uGhjGTHL0j4rf7zDjLLI, $0.0000038). A judge on the
  router can therefore be the engine model itself, which breaks INIT's rule that engine and judges come from
  different companies.

### Spending cap
- `GET /api/v1/key` for the project key reports `limit: 35` (USD), `limit_reset: null` (a one-off cap, not
  monthly), `usage: 25.051323419` and `limit_remaining: 9.948676581` after X3's calls (read 2026-09-28). A cap is
  therefore set on the key. The key's lifetime usage is already $25.05 of it.

## Options
| Option | What was measured | Result | Source |
| --- | --- | --- | --- |
| A. Default routing with ZDR + no-training only | Where requests land | Luna goes to `azure` (global ZDR); EU endpoints are skipped as surcharge endpoints | endpoints listing; OpenRouter in-region routing docs |
| B. Pin each chat model's EU ZDR endpoint in `provider.order`, fallbacks off | Cost, caching, availability | Works for Luna, Flash-Lite, Haiku; +10% price; caching hits on the second call | generation ids above |
| C. `eu.openrouter.ai` in-region routing | Plan requirement | Needs Business/Enterprise; key is `global` | `GET /api/v1/key`; sovereign-ai docs |

## Decision
Option B: every model call pins its EU ZDR endpoint (`azure/eu` for Luna, `google-vertex/eu` for Flash-Lite,
`google-vertex/europe` for Haiku 4.5 and Sonnet 5, `nebius` for embeddings) with `zdr`, `data_collection: deny`, and
static-prefix-first prompts so caching applies. The rule that decided it is INIT › Ethical considerations (confidential company information:
"model providers and OpenRouter configured not to train on or retain inputs where possible") together with the EU host already
chosen for embeddings; the 10% surcharge is small against the per-case cost measured above.

## Consequences
- **Settings (not applied; X3's DoD doesn't ask for it).** `ENGINE_MODEL=openai/gpt-6-luna-20260922` is X2's call.
  The chat factory needs a provider-order setting per role (for example `ENGINE_PROVIDER=azure/eu`), passed as
  `provider_order` with `allow_fallbacks=False`, the way embeddings already pin `EMBEDDING_PROVIDER=nebius`.
- **Anthropic caching** needs top-level `cache_control: {"type": "ephemeral"}` in the request body. Whoever builds
  the Haiku calls (B8 label filter, V4 judge backup) must check that `langchain-openrouter` passes it through.
- **Prompt layout.** E-stories put instructions and retrieved provisions before the user's description, so the
  prefix is cacheable across checks and cases.
- **Jev (V4).** Don't use `typesafe/jev-router` as the judge: it can route to Luna. `typesafe/jev-1.13` needs the
  `/api/alpha/decisions` endpoint, not chat completions, so V4 must check whether that API can act as a judge at all,
  or fall back to Claude Haiku 4.5.
- **Budget.** The key has $9.95 of its $35 cap left. That covers X1, X2 and early E-stories at the measured cost,
  but not the full plan (INIT estimates €20–30 in total). The user decides whether to raise the cap.
- **Privacy notice (P-stories).** Name OpenRouter (global processing on this plan), Microsoft Azure (EU) for Luna,
  Google Vertex (EU) for Gemini and Claude, and Nebius for embeddings.
- **Revisit** if a pinned EU endpoint goes down for long (Option A as a fallback keeps ZDR but leaves the EU), if
  the project moves to a Business plan (Option C), or if the E-stories' traced cost per case is more than twice the
  projection above.
