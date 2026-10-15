# Architecture

The detail behind the README's Architecture section. One Python backend holds all the logic; the web app and the
MCP server are its clients.

## The engine

`backend/aiact/engine/` is a LangGraph graph with a fixed check order that no path can skip:

```
facts → scope → prohibited → high_risk → transparency → role_obligations → finalize
```

- `facts` extracts the facts and their evidence tags. A description too thin to start (for example "We use AI in
  our shop.") goes straight to `finalize` with a "needs a description" outcome, and no check runs.
- `scope` (Art. 2–3) and `prohibited` (Art. 5) may end the run early, but only when they matched and decided; an
  uncertain match goes on with the stricter reading as the working assumption (decision 010).
- `high_risk` (Art. 6, Annex III, Annex I flagged), `transparency` (Art. 50) and `role_obligations` (Art. 16,
  23–26, the Art. 25 switch, the Art. 111(2) rules for systems already on the market) follow.
- **Citation check** (`engine/citations.py`): every check node is wrapped by a validator. Each citation a step
  makes must resolve in the corpus, in the language it quotes, under the run's law version and, for the amended
  text and guidance, on the run's date; a citation that resolves is rebuilt from the corpus row, so its quote is
  the corpus's own. A step citing something that doesn't resolve is run once more (a refused step is not). If a
  citation still doesn't resolve, the step keeps the citations that do and says a person must verify it, and a
  decided step becomes `needs_more_information`.
- `finalize` calls no model. It sets the class and status and collects the deciding facts and follow-up
  questions.
- If the model provider's content filter refuses a check, the request goes once to a second pinned EU model
  (decision 033). If that also fails, the result gives no class and says a person must review it (decisions 029,
  030).

## Retrieval over the AI Act corpus

The corpus holds only official texts and Commission guidance, in English and German where official: the AI Act
(original and consolidated), the Digital Omnibus, and the guidelines on the AI system definition, prohibited
practices, high-risk classification (draft, May 2026) and Art. 50, plus the transparency Code of Practice
(`data/manifest.yaml`; parsed texts in `data/parsed/`). Where the law says where to look, the engine fetches the
provision by its ID. Otherwise it searches by meaning (pgvector, Qwen3-Embedding-8B at 1,536 dimensions), with a
lightly weighted keyword arm (Postgres full-text search) fused in to break ties (decision 003): to match a
description to Annex III or Annex I points, to find similar Commission guideline examples, and to answer
questions. The half of the Commission's worked examples that forms the benchmark is filtered out of every search
by default (decision 012).

## Models

All through OpenRouter, each pinned to its EU zero-data-retention endpoint with fallbacks off (decision 005): the
engine runs on GPT-6 Luna (`openai/gpt-6-luna-20260922` on `azure/eu`, decision 004); refused requests go to
Gemini 3.1 Flash-Lite on `google-vertex/eu` (decision 033); embeddings come from Qwen3-Embedding-8B on Nebius
(decision 003). The evaluation uses Claude Haiku 4.5 as the label filter and Gemini 3.1 Flash-Lite for RAGAS
(decision 005).

## Databases

Decision 034 and its amendment.

- **Hosted** (Supabase Free plan, Frankfurt `eu-central-1`): the app, the benchmark runs and their stored results.
  - `backend/.env` (from `backend/.env.example`): `DATABASE_URL` is the session pooler's connection string with
    `?sslmode=require`, `SUPABASE_URL` and `SUPABASE_SERVICE_KEY` the project URL and secret key. Turn on the
    dashboard's Database settings > SSL Configuration > "Enforce SSL on incoming connections".
  - `frontend/.env.local` (from `frontend/.env.example`): `VITE_SUPABASE_URL` and the publishable key in
    `VITE_SUPABASE_ANON_KEY`.
- **Local** (the Supabase CLI's Postgres on `127.0.0.1:54322`): the backend tests, every worktree sharing it, as CI
  does. `make db` starts it slim, Postgres only:
  `supabase start -x gotrue,realtime,storage-api,imgproxy,kong,mailpit,postgrest,postgres-meta,studio,edge-runtime,logflare,vector,supavisor`.
  The tests use `TEST_DATABASE_URL` (default: that database) and never follow `DATABASE_URL`.

Schema changes: `supabase migration new <name>`, then apply it to both, `supabase migration up --local` and
`supabase db push` to the linked project (`supabase login` and `supabase link --project-ref <ref>` once).
`supabase config push` applies `supabase/config.toml`'s auth settings (anonymous sign-ins on) to the hosted
project. Never reset either database or drop its schema: the corpus in each is shared.

## Tracing

LangSmith traces each classification when `LANGSMITH_API_KEY` is set. Outside development (`AIACT_ENV` empty means
production) a trace keeps metadata only: node names, timings, model ids and the run's settings, never the
description, prompt, answer or error text. `AIACT_ENV=development` traces the content too, on a developer's own
machine only.

## Frontend

`frontend/`: Vite, React and TypeScript, Tailwind CSS and shadcn/ui, TanStack Router and Query, a TypeScript client
generated from the API's OpenAPI schema, react-i18next for English and German.
