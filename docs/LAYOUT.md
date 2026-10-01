# Repo layout

This file is the single source of truth for where things live. Every *Output* path in `docs/BACKLOG.md` must fit
this layout. A story that adds a new folder, or a new top-level file, updates this file in the same branch.
`CLAUDE.md` keeps a short summary of it.

## Tree

```
.
├── CLAUDE.md                        project rules for Claude Code (short; links here)
├── README.md                        goal, how it works, measured accuracy, showcase link (W2)
├── AI Act Classification Assistant — Capstone Init Document.md   the design (INIT)
├── AE.CAP_afa.md                    course brief
├── .gitignore
├── .github/workflows/ci.yml         lint, types, tests, deps check, isolation check (F2, B13)
├── .github/workflows/label-freeze.yml  label-freeze check, never cancelled (B10a)
├── .githooks/                       pre-commit and pre-merge-commit regenerate DEPENDENCIES.md, pre-push checks it (F8)
│
├── backend/                         the only Python project (uv)
│   ├── pyproject.toml               deps, ruff, pyright, pytest config; `aiact` console script (F1)
│   ├── uv.lock                      locked dependencies; regenerate with `uv lock` on conflict (F1)
│   ├── .python-version              the Python uv and CI install (F2)
│   ├── .env.example                 every key the app reads, with placeholder values (F1)
│   ├── aiact/                       the package: all Python code lives here
│   │   ├── cli.py                   `aiact` command root; subcommands per area: corpus, eval (F1)
│   │   ├── settings.py              pydantic-settings, read from .env (F1)
│   │   ├── deps.py                  generates and checks docs/DEPENDENCIES.md; `aiact deps` (F8)
│   │   ├── db.py                    direct Postgres connection (DATABASE_URL) for server-only tables (C3)
│   │   ├── dates.py                 month names and long dates (EN, DE) shared by corpus and engine texts (C7b)
│   │   ├── schemas/                 the result contract: RiskClass, Status, ClassificationResult… (F3)
│   │   ├── llm/                     OpenRouter chat + embeddings clients, record/replay (F6); decisions.py: Decisions API for Jev (V3)
│   │   │                            chat.py: engine_chat_model, the engine model pinned to ENGINE_PROVIDER (E3)
│   │   │                            structured.py: JSON-schema response format + error text (V3, E2)
│   │   ├── corpus/                  fetch.py + sources.py (B1), eurlex.py + eurlex_html.py + amendments.py + files.py (C1),
│   │   │                            guidelines.py + guidelines_pdf.py + guideline_examples.py (C2),
│   │   │                            build.py + load.py (C3), embed.py (C4)
│   │   ├── retrieval/               provisions.py: get_provision (C5); search.py: search_ai_act (C6; relevance score and cut-off C8)
│   │   ├── obligations/             list.py: list_obligations; seed.py: YAML → SQL seed, `aiact obligations seed` (C7)
│   │   ├── engine/                  ⚠ created only after B3 (hook-enforced)
│   │   │   ├── graph.py, state.py   the staged LangGraph (E1)
│   │   │   ├── scripted.py          stub nodes that return scripted outcomes, for tests (E1)
│   │   │   ├── nodes/               facts.py (E2), scope.py + scope_texts.py (E3), prohibited.py (E4),
│   │   │   │                        high_risk.py + high_risk_retrieval.py + high_risk_texts.py (E5),
│   │   │   │                        transparency.py (E6), role_obligations.py + role_texts.py (E7),
│   │   │   │                        finalize.py (E8); key_facts.py: the key-fact answer shared by the
│   │   │   │                        checks (E3); common.py: the run's lookup, citations and prompt
│   │   │   │                        blocks shared by the checks (E5)
│   │   │   ├── prompts/             prompt files, one per node, e.g. facts.md (E2–E8)
│   │   │   │                        role_obligations_legacy.md: the high-risk Art. 111(2) section (C7b)
│   │   │   ├── citations.py         citation existence validator (E9)
│   │   │   └── __init__.py          classify_system (E10)
│   │   ├── eval/                    evaluation code, never benchmark data
│   │   │   ├── cases.py             BenchmarkCase schema + loader + appliedAI mapping (F7)
│   │   │   ├── academic.py          davidath scenarios → cases + overrides; `aiact evaluate academic-import|academic-sample` (B12)
│   │   │   ├── split.py             seeded stratified split → eval/split.json; `aiact evaluate split` (B3)
│   │   │   ├── similarity.py        rewrite-vs-source similarity check; `aiact evaluate similarity` (B4a)
│   │   │   ├── label_freeze.py      approved cases changed without a new LABEL_CHANGES.md row; `aiact evaluate label-freeze` (B10a)
│   │   │   ├── isolation.py         isolation measurements: Pile B tags, n-gram and embedding closeness to the
│   │   │   │                        retrievable corpus; `aiact evaluate isolation-embed` (B13)
│   │   │   ├── label_filter.py      second-model label filter; `aiact evaluate label-filter` (B9)
│   │   │   ├── runner.py            `aiact evaluate run`: classifier registry, subset, exclusions, cost cap (V1)
│   │   │   ├── records.py           writes eval_runs / eval_case_results over a direct connection (V1)
│   │   │   ├── metrics.py           deterministic metrics, per-case scores and run summary (V2)
│   │   │   ├── report.py            markdown metrics table for a stored run_id; `aiact evaluate report` (V2)
│   │   │   ├── citation_index.py    citation existence against the corpus (doc_key, provision, language, version) (V2)
│   │   │   ├── baselines.py         `baseline_luna` (engine model, one prompt, no retrieval) and `baseline_jev` (V3)
│   │   │   ├── judge.py             (V4)
│   │   │   ├── judged.py            judged metrics: citation support, evidence tags, Q&A support, invented content (V5)
│   │   │   ├── ragas_metrics.py     (V6)
│   │   │   ├── tool_calls.py        tool-call correctness from traces (V7)
│   │   │   └── experiments/         embeddings.py (X1a), smoke.py (X2), free_agent.py (S1)
│   │   ├── qa/                      Q&A over the corpus with citations (P7)
│   │   ├── drafting/                deployer documents, skeletons, interview, export, automatic checks (P8a, P8b, P9)
│   │   ├── mcp/                     server.py: the 4 MCP tools over stdio, `aiact mcp serve`; lookup tools (P2a), classify_system (P2b)
│   │   └── api/                     FastAPI app, SSE (P1)
│   └── tests/                       mirrors the package: tests/<area>/test_*.py
│       ├── db/                      schema tests against local Supabase (`db` marker; skipped when unreachable) (F4)
│       ├── fixtures/                small hand-made inputs (HTML snippets, sample cases); eurlex/ (C1)
│       ├── conftest.py              record/replay config (pytest-recording) and the network block; only `live` tests get through (F6)
│       ├── recordings/              recorded model responses, <module path under tests/>/<test>.yaml, e.g. llm/test_chat/ (F6);
│       │                            <test>.corpus.json next to one: the corpus rows a replayed engine node read,
│       │                            so the replay needs no database (E3, E5)
│       ├── snapshots/               committed JSON snapshots, e.g. the result's JSON Schema (F3)
│       ├── test_network_guard.py    proves unmarked tests can't reach the network (F6)
│       └── test_isolation.py        benchmark isolation check (B13)
│
├── data/                            legal texts only — never benchmark material
│   ├── manifest.yaml                what was fetched: URL, language, version, sha256 (B1; committed)
│   ├── raw/                         downloaded HTML and PDFs (B1; gitignored)
│   └── parsed/                      <doc>.<lang>.jsonl: laws (C1), guideline PDFs (C2)
│
├── eval/                            benchmark data and reports only — no code; the Corpus lane never reads it
│   ├── split.json                   Pile A / Pile B, committed once and never changed (B3; C2 may read it)
│   ├── commission_examples/         examples.jsonl extracted from the draft guidelines (B2)
│   ├── cases/                       labelled cases, frozen per category (B10a, decision 017) and tagged labels-v1 (B10b); folders created by F7,
│   │                                <set>/**/*.yaml, one case or a list per file, BenchmarkCase schema
│   │                                in aiact/eval/cases.py (except qa/, whose item shape comes with B7)
│   │   ├── commission_b/            (B4)
│   │   ├── own/<category>/          (B5a–e)
│   │   ├── soft_pairs/              (B6)
│   │   ├── qa/                      (B7)
│   │   ├── consistency/             (B8)
│   │   ├── academic/                <risk_class>.yaml (generated), SOURCE.md (CC BY 4.0) (B12)
│   │   ├── academic_overrides.yaml  spot-check label overrides the academic import applies (B12)
│   │   └── annex_match/             (X0)
│   ├── isolation/                   embeddings.json: vectors of the benchmark texts for the isolation check,
│   │                                never in the corpus tables; `aiact evaluate isolation-embed` (B13);
│   │                                contaminated.json: Pile B examples retold in the corpus, with the
│   │                                measured overlap (decision 016; `isolation.load_contaminated`)
│   ├── judge_validation/            hand-labelled judge cases (V4)
│   ├── reports/                     run-<date>.md, label_disagreements.md, final.md… (B9, B12, V8–V10, W1)
│   ├── LABEL_CHANGES.md             log of label changes (B12 starts it; the freeze check is B10a)
│   └── private/                     appliedai.jsonl (B11; gitignored, never tracked; may be absent)
│
├── supabase/                        Supabase CLI project
│   ├── config.toml                  (F4)
│   ├── migrations/                  <timestamp>_<name>.sql via `supabase migration new` (F4, F5, C7, P3, C3)
│   └── seed/                        obligations.yaml, the source; obligations.sql, generated from it (C7)
│
├── frontend/                        Vite + React + TypeScript SPA, pnpm (P4); run `pnpm …` from here
│   ├── package.json, pnpm-lock.yaml scripts: dev, build, test, lint, format, gen:api; lockfile committed (P4)
│   ├── pnpm-workspace.yaml          pnpm settings (which install scripts may run) (P4)
│   ├── vite.config.ts               Vite, Tailwind, TanStack Router plugin, Vitest config (P4)
│   ├── openapi-ts.config.ts         `pnpm gen:api`: openapi.json → src/api/ (hey-api) (P4)
│   ├── openapi.json                 exported from FastAPI; the TS client is generated from it (P1)
│   ├── components.json              shadcn/ui CLI config (P4)
│   ├── eslint.config.js, .prettierrc.json, tsconfig*.json   lint, format, types (app, test, node) (P4)
│   ├── .env.example                 VITE_API_URL, VITE_SUPABASE_URL, VITE_SUPABASE_ANON_KEY (public values only) (P4)
│   ├── public/                      static files: favicon.svg (P4)
│   └── src/
│       ├── main.tsx, router.tsx     entry: providers, router with the QueryClient in its context (P4)
│       ├── index.css                theme tokens from the Brand board: colours, fonts, glass, pills (P4)
│       ├── routeTree.gen.ts         generated by the router plugin; committed, never edited (P4)
│       ├── api/                     GENERATED client (`pnpm gen:api`), never edited; a placeholder until P1
│       ├── routes/                  TanStack Router file routes: __root, index, brand (token sheet) (P4); P5+
│       ├── components/              shared components in PascalCase: GlassPanel, RiskPill, KlarLogo,
│       │                            LanguageSwitch, AppShell, SessionNotice, ErrorView (P4)
│       │   └── ui/                  shadcn primitives, lower-case, added with the shadcn CLI (P4)
│       ├── features/<feature>/      feature components + their tests, e.g. classify/ (P5), inventory/ (P6)
│       ├── hooks/                   use-<name>.ts, e.g. use-anonymous-session.ts (P4)
│       ├── lib/                     env (validated VITE_*), supabase client, auth, query client,
│       │                            api-client-config, utils (P4)
│       ├── i18n/                    i18next set-up; locales/en.json, locales/de.json (P4)
│       └── test/                    setup.ts, test-utils.tsx (renderWithProviders), msw-server.ts, supabase-fixtures.ts (P4)
│
├── docs/
│   ├── BACKLOG.md                   stories, critical path, waves
│   ├── LAYOUT.md                    this file
│   ├── DEPENDENCIES.md              generated from pyproject + lockfiles; never edited by hand (F8)
│   ├── dependency-licences.json     licence + summary cache per name==version (npm:name==version for the frontend), written by `aiact deps generate` (F8, P4)
│   ├── corpus_stats.md              row counts per document (C3)
│   ├── design-system/               copy of the user's Klar design system (README brand book, localisation, components, components.d.ts, tokens.json); the claude.ai artifact is the source
│   └── decisions/NNN-<slug>.md      decision records (/decision skill)
│
└── .claude/                         Claude Code tooling (see CLAUDE.md › Project tooling)
    ├── foreman.json, settings.json, rules/, skills/ (case, eval), agents/ (isolation-auditor)
    └── worktrees/                   agent worktrees (gitignored)
```

## Rules

| Rule | Why |
| --- | --- |
| All Python lives in `backend/aiact/`; scripts are CLI subcommands (`aiact corpus …`, `aiact evaluate …`), not loose files | One lint, type-check and test setup; scripts can import the package |
| `eval/` holds benchmark data and reports only; `backend/aiact/eval/` holds evaluation code | Keeps the answer key a pure data folder that hooks and sparse checkout can fence off |
| `data/` holds legal texts only; nothing from `eval/` is ever copied there | INIT › Benchmark isolation |
| `backend/aiact/engine/` doesn't exist before `eval/split.json` is committed | INIT › Benchmark isolation 1; `engine-gate.sh` |
| Tests mirror the package (`tests/corpus/test_eurlex.py` for `aiact/corpus/eurlex.py`); model calls use `tests/recordings/` | Findable tests; no live calls in CI |
| Migrations only via `supabase migration new`; never edit a merged migration | Parallel stories can't collide on names |
| Frontend tests sit next to the file they test (`RiskPill.test.tsx`); `frontend/src/api/` is generated only | One place per component; the client always matches the API schema |
| Gitignored: `.env`, `data/raw/`, `eval/private/`, `.claude/worktrees/`, `.claude/settings.local.json`, `frontend/node_modules/`, `frontend/dist/` | Secrets, large downloads, unlicensed data, agent scratch, build output |
| A new top-level folder or package area needs an entry here in the same story | Keeps this file the source of truth |
