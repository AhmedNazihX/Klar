# AI Act Classification Assistant

This assistant classifies AI systems under the EU AI Act. Each result shows its steps, cites the provisions it relies on, and states its measured accuracy.

- **Design (INIT):** `AI Act Classification Assistant — Capstone Init Document.md`. This is the source of truth for what gets built.
- **Backlog:** `docs/BACKLOG.md`. It holds atomic stories with dependencies, the critical path and the parallel lanes. Tick stories off there (`[x]`) and add a one-line outcome note.
- **Course brief:** `AE.CAP_afa.md`.
- **Decisions:** `docs/decisions/NNN-title.md` (what was decided, the options measured, the numbers, the choice).

## Picking up a story
Read this file, then the story in `docs/BACKLOG.md`, then the INIT sections named in its *Context* line, then the files in its *Input*. That should be all the context a story needs.

## Repo layout
The full layout lives in **`docs/LAYOUT.md`**: the tree down to key files, which story creates each path, and the placement rules. Every new file must fit it, and a story that adds a new folder updates it. Summary:
```
backend/            the only Python project (uv); all Python lives in package `aiact/`
  aiact/cli.py      `aiact` command root: scripts are subcommands (`aiact corpus …`, `aiact evaluate …`)
  aiact/schemas/ llm/ corpus/ retrieval/ obligations/ qa/ drafting/ mcp/ api/
  aiact/engine/     staged LangGraph engine: DO NOT create before story B3 is committed
  aiact/eval/       evaluation *code*: cases, split, runner, metrics, judge, experiments/
  tests/            mirrors the package; tests/recordings/ holds recorded model responses
data/               legal texts only: manifest.yaml, raw/ (gitignored), parsed/
eval/               benchmark *data* and reports only, no code (eval/private/ is gitignored)
supabase/           config, migrations/, seed/
frontend/           Vite + React + TypeScript
docs/               BACKLOG.md, LAYOUT.md, decisions/
```

## Commands (run from `backend/`)
- `uv sync`: install
- `uv run pytest`: tests (live model tests are skipped unless `-m live`)
- `uv run ruff check . && uv run ruff format --check .`: lint and format
- `uv run pyright`: type check
- `uv run aiact deps generate` / `uv run aiact deps check`: regenerate or check `docs/DEPENDENCIES.md` (generated, never edit by hand)
- `git config core.hooksPath .githooks` (once per clone): pre-commit and pre-merge-commit regenerate `DEPENDENCIES.md`, pre-push runs `deps check`
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

## Tooling (`.claude/`)
- **Skills:**
  - `/status`: what's done, ready or blocked, and what to launch next.
  - `/story-start <IDs>`: checks deps and rules, then launches `story-worker` agents.
  - `/story-finish <ID>`: verify, review, merge, tick.
  - `/decision`: records in `docs/decisions/`.
  - `/case`: benchmark cases and labels.
  - `/eval`: runs a benchmark with a subset, cost cap and held-out/all mode; asks before a full or paid run; writes `eval/reports/run-<date>.md` from stored numbers.
- **Agents:**
  - `story-worker`: implements one story in its own worktree.
  - `dod-verifier`: checks a story's DoD independently.
  - `isolation-auditor`: benchmark-leak audit.
  - The global `diff-reviewer` reviews diffs.
- **Hooks** (`.claude/settings.json`):
  - `engine-gate.sh`: no `backend/aiact/engine/` before `eval/split.json` is committed.
  - `isolation-guard.sh`: no `eval/` access on Corpus-lane branches.
  - `ruff-format.sh`: formats edited `.py` files.
  - The global git and secrets guards also apply.
  - Checks on file tools (Read, Write, Edit, Grep, Glob) are exact. Checks on shell commands are best effort, because shell text can hide a path. The sparse checkout, `isolation-auditor` and `dod-verifier` are the backstops.
  - After changing a hook, run `bash .claude/hooks/test-hooks.sh`.
- **Scoped rules:** `.claude/rules/*.md` load only when Claude reads matching files. Subfolders are read too, so keep this folder small and specific to this project.
  - Areas: `eval`, `corpus`, `engine`, `supabase`.
  - Code: `python` (backend), `api` (FastAPI and MCP), `frontend`, `frontend-security`, `frontend-testing`.
  - Visual design comes from the user's Design canvas (see `docs/BACKLOG.md` › Phase 5 › Design reference), and the `frontend-design` skill covers gaps. It doesn't come from a rule.
- **Backlog helper:** `.claude/scripts/backlog.py` (`status`, `show`, `deps`, `info`, `tick`). The skills use it.

## Parallel work (worktrees)
- **One worktree per story.** Every agent running in parallel works in its own git worktree. `story-worker` has `isolation: worktree`; worktrees live in `.claude/worktrees/` (gitignored) and branch from the local HEAD (`worktree.baseRef: head`). The worker renames its branch to `story/<ID>-<slug>`, for example `story/C1-eurlex-parser`.
- **Branch from a merged base.** A story's worktree is created only after all its Deps are merged into the base branch. Engine worktrees (E*) must branch from a commit that already contains `eval/split.json` (the B3 gate).
- **Run alone.** F1 (every worktree needs its base) and the chain E8 → E9 → E10 run serially, without parallel agents.
- **The orchestrator owns the backlog.** Only the main session ticks boxes in `docs/BACKLOG.md`, after a merge. Agents report their outcome in their final message instead.
- **Merge flow.** When a story is done: the `diff-reviewer` agent checks the diff, then ruff, pyright and pytest run on the branch, then the branch is merged into the base. Dependent stories start only after that merge.
- **Shared files.** Keep edits to `pyproject.toml`, `settings.py` and `.env.example` minimal and additive. If `uv.lock` conflicts, regenerate it with `uv lock` rather than merging it by hand. Then run `uv run aiact deps generate` and commit `docs/DEPENDENCIES.md` and `docs/dependency-licences.json` with it.
- **Gitignored files.** `.env` and `data/raw/` are not in a new worktree. Copy or symlink `.env` into the worktree at the start. Point `AIACT_DATA_DIR` at the one shared absolute data path.
- **Database is shared.** All worktrees use the same local Supabase instance. Create migrations only with `supabase migration new` (timestamped names). Only one running story at a time may change the schema. Tests isolate themselves with a transaction per test or a per-story schema.
- **Enforced isolation.** Corpus-lane worktrees (B1, C*) use sparse checkout to leave out `eval/` entirely. C2 is the exception: it gets `eval/split.json` only. The worker sets the sparse checkout before renaming its branch, and `isolation-guard.sh` blocks any `eval/` access after that.
