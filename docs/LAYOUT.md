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
├── .github/workflows/ci.yml         lint, types, tests, deps check, isolation check, label-freeze check (F2, B10, B13)
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
│   │   ├── schemas/                 the result contract: RiskClass, Status, ClassificationResult… (F3)
│   │   ├── llm/                     OpenRouter chat + embeddings clients, record/replay (F6)
│   │   ├── corpus/                  fetch.py + sources.py (B1), eurlex.py (C1), guidelines.py (C2), load.py (C3),
│   │   │                            embed.py (C4)
│   │   ├── retrieval/               provisions.py: get_provision (C5); search.py: search_ai_act (C6)
│   │   ├── obligations/             list.py: list_obligations (C7)
│   │   ├── engine/                  ⚠ created only after B3 (hook-enforced)
│   │   │   ├── graph.py, state.py   the staged LangGraph (E1)
│   │   │   ├── nodes/               facts.py (E2), scope.py (E3), prohibited.py (E4), high_risk.py (E5),
│   │   │   │                        transparency.py (E6), role_obligations.py (E7), finalize.py (E8)
│   │   │   ├── prompts/             prompt files, one per node (E2–E8)
│   │   │   ├── citations.py         citation existence validator (E9)
│   │   │   └── __init__.py          classify_system (E10)
│   │   ├── eval/                    evaluation code, never benchmark data
│   │   │   ├── cases.py             BenchmarkCase schema + loader + appliedAI mapping (F7)
│   │   │   ├── split.py             seeded stratified split → eval/split.json; `aiact eval split` (B3)
│   │   │   ├── similarity.py        rewrite-vs-source similarity check; `aiact eval similarity` (B4)
│   │   │   ├── label_filter.py      second-model label filter; `aiact eval label-filter` (B9)
│   │   │   ├── runner.py            `aiact eval run` (V1)
│   │   │   ├── metrics.py           deterministic metrics + report tables (V2)
│   │   │   ├── baselines.py         (V3)
│   │   │   ├── judge.py             (V4)
│   │   │   ├── ragas_metrics.py     (V6)
│   │   │   ├── tool_calls.py        tool-call correctness from traces (V7)
│   │   │   └── experiments/         embeddings.py (X1), smoke.py (X2), free_agent.py (S1)
│   │   ├── qa/                      Q&A over the corpus with citations (P7)
│   │   ├── drafting/                deployer documents, skeletons, interview, export, automatic checks (P8, P9)
│   │   ├── mcp/                     server.py: the 4 MCP tools (P2a, P2b)
│   │   └── api/                     FastAPI app, SSE (P1)
│   └── tests/                       mirrors the package: tests/<area>/test_*.py
│       ├── db/                      schema tests against local Supabase (`db` marker; skipped when unreachable) (F4)
│       ├── fixtures/                small hand-made inputs (HTML snippets, sample cases)
│       ├── conftest.py              record/replay config (pytest-recording) and the network block; only `live` tests get through (F6)
│       ├── recordings/              recorded model responses, <module path under tests/>/<test>.yaml, e.g. llm/test_chat/ (F6)
│       ├── snapshots/               committed JSON snapshots, e.g. the result's JSON Schema (F3)
│       ├── test_network_guard.py    proves unmarked tests can't reach the network (F6)
│       └── test_isolation.py        benchmark isolation check (B13)
│
├── data/                            legal texts only — never benchmark material
│   ├── manifest.yaml                what was fetched: URL, language, version, sha256 (B1; committed)
│   ├── raw/                         downloaded HTML and PDFs (B1; gitignored)
│   └── parsed/                      <doc>.<lang>.jsonl, guide-*.jsonl (C1, C2)
│
├── eval/                            benchmark data and reports only — no code; the Corpus lane never reads it
│   ├── split.json                   Pile A / Pile B, committed once and never changed (B3; C2 may read it)
│   ├── commission_examples/         examples.jsonl extracted from the draft guidelines (B2)
│   ├── cases/                       labelled cases, frozen at tag labels-v1 (B10); folders created by F7,
│   │                                <set>/**/*.yaml, one case or a list per file, BenchmarkCase schema
│   │                                in aiact/eval/cases.py (except qa/, whose item shape comes with B7)
│   │   ├── commission_b/            (B4)
│   │   ├── own/<category>/          (B5a–e)
│   │   ├── soft_pairs/              (B6)
│   │   ├── qa/                      (B7)
│   │   ├── consistency/             (B8)
│   │   ├── academic/                (B12)
│   │   └── annex_match/             (X0)
│   ├── judge_validation/            hand-labelled judge cases (V4)
│   ├── reports/                     run-<date>.md, label_disagreements.md, final.md… (B9, B12, V8–V10, W1)
│   ├── LABEL_CHANGES.md             log of label changes after the freeze (B10)
│   └── private/                     appliedai.jsonl (B11; gitignored, never tracked; may be absent)
│
├── supabase/                        Supabase CLI project
│   ├── config.toml                  (F4)
│   ├── migrations/                  <timestamp>_<name>.sql via `supabase migration new` (F4, F5, C7, P3)
│   └── seed/                        obligations.yaml (C7)
│
├── frontend/                        Vite + React + TypeScript (P4); its inner layout is recorded here by P4
│   └── openapi.json                 exported from FastAPI; the TS client is generated from it (P1)
│
├── docs/
│   ├── BACKLOG.md                   stories, critical path, waves
│   ├── LAYOUT.md                    this file
│   ├── DEPENDENCIES.md              generated from pyproject + lockfiles; never edited by hand (F8)
│   ├── dependency-licences.json     licence + summary cache per name==version, written by `aiact deps generate` (F8)
│   ├── corpus_stats.md              row counts per document (C3)
│   └── decisions/NNN-<slug>.md      decision records (/decision skill)
│
└── .claude/                         Claude Code tooling (see CLAUDE.md › Tooling)
    ├── settings.json, rules/, skills/, agents/, hooks/, scripts/
    └── worktrees/                   agent worktrees (gitignored)
```

## Rules

| Rule | Why |
| --- | --- |
| All Python lives in `backend/aiact/`; scripts are CLI subcommands (`aiact corpus …`, `aiact eval …`), not loose files | One lint, type-check and test setup; scripts can import the package |
| `eval/` holds benchmark data and reports only; `backend/aiact/eval/` holds evaluation code | Keeps the answer key a pure data folder that hooks and sparse checkout can fence off |
| `data/` holds legal texts only; nothing from `eval/` is ever copied there | INIT › Benchmark isolation |
| `backend/aiact/engine/` doesn't exist before `eval/split.json` is committed | INIT › Benchmark isolation 1; `engine-gate.sh` |
| Tests mirror the package (`tests/corpus/test_eurlex.py` for `aiact/corpus/eurlex.py`); model calls use `tests/recordings/` | Findable tests; no live calls in CI |
| Migrations only via `supabase migration new`; never edit a merged migration | Parallel stories can't collide on names |
| Gitignored: `.env`, `data/raw/`, `eval/private/`, `.claude/worktrees/`, `.claude/settings.local.json` | Secrets, large downloads, unlicensed data, agent scratch |
| A new top-level folder or package area needs an entry here in the same story | Keeps this file the source of truth |
