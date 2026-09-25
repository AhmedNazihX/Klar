# AI Act Classification Assistant

This assistant classifies AI systems under the EU AI Act. Each result shows its steps, cites the provisions it relies on, and states its measured accuracy.

- **Design (INIT):** `AI Act Classification Assistant — Capstone Init Document.md`. This is the source of truth for what gets built.
- **Backlog:** `docs/BACKLOG.md`. It holds atomic stories with dependencies, the critical path and the parallel lanes. Tick stories off there (`[x]`) and add a one-line outcome note.
- **Course brief:** `AE.CAP_afa.md`.
- **Decisions:** `docs/decisions/NNN-title.md` (what was decided, the options measured, the numbers, the choice).

## Picking up a story
Read this file, then the story in `docs/BACKLOG.md`, then the INIT sections named in its *Context* line, then the files in its *Input*. That should be all the context a story needs.

## Repo layout
```
backend/            uv project, Python package `aiact/`
  aiact/schemas/    Pydantic result contract (RiskClass, Status, ClassificationResult, …)
  aiact/corpus/     fetch, parse, load, embed the legal corpus
  aiact/retrieval/  get_provision, search_ai_act (no LLM)
  aiact/obligations/list_obligations
  aiact/engine/     LangGraph staged engine: DO NOT create before story B3 is committed
  aiact/eval/       case schema, runner, metrics, judge
  aiact/llm/        OpenRouter chat + embeddings clients, record/replay
  aiact/mcp/        MCP server
  aiact/api/        FastAPI
  tests/
eval/               benchmark cases, split, reports (eval/private/ is gitignored)
data/               raw and parsed legal texts (data/raw/ is gitignored)
supabase/           migrations and seeds
frontend/           Vite + React (later)
```

## Commands (run from `backend/`)
- `uv sync`: install
- `uv run pytest`: tests (live model tests are skipped unless `-m live`)
- `uv run ruff check . && uv run ruff format --check .`: lint and format
- `uv run pyright`: type check
- `supabase start` / `supabase db reset` (from the repo root): local database

## Global rules
- **Benchmark isolation.** Corpus code (`aiact/corpus`, `aiact/retrieval`, stories B1 and C*) must never read `eval/`. The one exception is story C2, which reads the `pile_b` ID list in `eval/split.json`. Benchmark work must never write to `data/` or the corpus tables. No test description or label is ever ingested.
- **The split comes first.** `eval/split.json` is committed before anything under `aiact/engine/` exists. Labels under `eval/cases/` are frozen at tag `labels-v1`; any later change is logged in `eval/LABEL_CHANGES.md`.
- **No live model calls in CI.** Tests use recorded responses. Mark live tests `@pytest.mark.live`.
- **Done means green.** A story is done only when ruff, pyright and pytest pass and the story's DoD is met.
- **Postgres.** Before touching Postgres or Supabase, load the `supabase-postgres-best-practices` skill, and the `supabase` skill too.
- **Library APIs.** Check LangGraph, Docling, the MCP SDK, RAGAS, FastAPI and similar libraries through context7 before writing code against them.
- **Every result carries** the law version it used and the "guidance, not legal advice" notice.
- **Secrets.** Secrets live in `.env` (never committed); `.env.example` lists the keys.
