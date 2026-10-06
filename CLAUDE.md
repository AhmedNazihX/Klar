# AI Act Classification Assistant

This assistant classifies AI systems under the EU AI Act. Each result shows its steps, cites the provisions it relies on, and states its measured accuracy.

- **Design (INIT):** `AI Act Classification Assistant — Capstone Init Document.md`. This is the source of truth for what gets built.
- **Backlog:** `docs/BACKLOG.md`. It holds atomic stories with dependencies, the critical path and the parallel lanes. Tick stories off there (`[x]`) and add a one-line outcome note.
- **Course brief:** `AE.CAP_afa.md`.
- **Decisions:** `docs/decisions/NNN-title.md` (what was decided, the options measured, the numbers, the choice).

## Picking up a story
Read this file, then the story in `docs/BACKLOG.md`, then the INIT sections named in its *Context* line, then the files in its *Input*. That should be all the context a story needs.

## Repo layout
The full layout lives in **`docs/LAYOUT.md`**: the tree down to key files, which story creates each path, and the placement rules. Every new file must fit it, and a story that adds a new folder updates it. Placement rules the code alone won't teach: all Python lives in package `backend/aiact/`, and scripts are `aiact` subcommands (`aiact corpus …`, `aiact evaluate …`); `data/` holds legal texts only; `eval/` holds benchmark *data* and reports, never code (that lives in `aiact/eval/`); `tests/recordings/` holds the recorded model responses.

## Commands (run from `backend/`; frontend: `cd frontend && corepack pnpm lint && corepack pnpm build && corepack pnpm test`; `pnpm test` includes a Chromium browser project, so a fresh clone or worktree first needs `corepack pnpm exec playwright install chromium`, see `frontend/README.md`)
- `uv sync`: install
- `uv run pytest`: tests (live model tests are skipped unless `-m live`)
- `uv run ruff check . && uv run ruff format --check .`: lint and format
- `uv run pyright`: type check
- `uv run aiact deps generate` / `uv run aiact deps check`: regenerate or check `docs/DEPENDENCIES.md` (generated, never edit by hand)
- `git config core.hooksPath .githooks` (once per clone): pre-commit and pre-merge-commit regenerate `DEPENDENCIES.md`, pre-push runs `deps check`
- `supabase start` (from the repo root): local database. Never `supabase db reset`; see *Database is shared* below.

## Global rules
- **Benchmark isolation.** Corpus code (`aiact/corpus`, `aiact/retrieval`, stories B1 and C*) must never read `eval/`. The one exception is story C2, which reads the `pile_b` ID list in `eval/split.json`. Benchmark work must never write to `data/` or the corpus tables. No test description or label is ever ingested.
- **The split comes first.** `eval/split.json` is committed before anything under `aiact/engine/` exists. Each own category's labels are frozen before the engine node that replays it (decision 017, checked in CI by B10a) and the whole set is tagged `labels-v1` (B10b); any later change is logged in `eval/LABEL_CHANGES.md`.
- **No live model calls in CI.** Tests use recorded responses. Mark live tests `@pytest.mark.live`.
- **Done means green.** A story is done only when the `checks` in `.claude/foreman.json` pass and the story's DoD is met.
- **Postgres.** Before touching Postgres or Supabase, load the `supabase-postgres-best-practices` skill, and the `supabase` skill too.
- **Library APIs.** Check LangGraph, Docling, the MCP SDK, RAGAS, FastAPI and similar libraries through context7 before writing code against them.
- **Every result carries** the law version it used and the "guidance, not legal advice" notice.
- **Secrets.** Secrets live in `.env` (never committed); `.env.example` lists the keys.
- **Long documents.** A `.md` file over 20 KB (the backlog, the INIT, decision 001, DEPENDENCIES.md) is never read whole: use `backlog.py show/status/plan`, ask the `foreman:doc-reader` agent (main session), or search with `rg` and Read a range. foreman's doc guard blocks whole reads (`.claude/foreman.json` › `docs`).

## Story workflow (parallel agents, `foreman` plugin)
- **Design:** the INIT above (this project has no `docs/DESIGN.md`). **Backlog:** `docs/BACKLOG.md`. **Layout:** `docs/LAYOUT.md`; every new file fits it.
  **Decisions:** `docs/decisions/`. Settings: `.claude/foreman.json`; its `checks` is the only list of the
  lint, type and test commands ("the global checks", backend and frontend): change them there. Decision numbers
  kept for a story are under `decisions.reserved`.
- **Commands:** `/foreman:next` picks the right step. `/foreman:status` shows what's ready;
  `/foreman:story-start <IDs>` launches one `foreman:story-worker` per story, each in its own worktree;
  `/foreman:story-finish <ID>` has `foreman:dod-verifier` and the reviewers (`reviewers` in the config, plus
  `foreman:test-auditor`) check the work, runs fix rounds, and merges only after the user confirms.
  `/foreman:decision` writes decision records.
- **Worktrees:** `.claude/worktrees/` (gitignored). They branch from the local HEAD (`worktree.baseRef: head`). Each
  worker renames its branch to `story/<ID>-<slug>`.
- **Starting a story:** only after all its deps are merged into the base branch. `Solo` stories (E8, E9, E10) run with
  nothing else in flight. Stories sharing a `Resource:` (`db-schema`) never run at the same time.
- **The orchestrator owns the backlog.** Only the main session ticks `docs/BACKLOG.md` and adds hand-over notes,
  after a merge. Workers report their outcome in their final message.
- **Shared files:** keep edits to lockfiles, settings and env examples minimal and additive. If a lockfile conflicts,
  regenerate it rather than merging it by hand.
- **Files the worktree doesn't have:** gitignored files like `.env` aren't in new worktrees. The worker symlinks the
  files listed in `link_files` and exports `env` from the config.
- **Guards** (plugin hooks, configured in `.claude/foreman.json`): `gates` (no writes under a path until a file
  is committed), `lanes`/`stories` (a lane's `deny` folders are blocked on its story branches, and its worktree
  leaves them out), `format` (edited files are formatted with the project's formatter). File-tool checks are exact;
  shell-command checks are best effort. Project rules and their enforcement are listed under `guardrails`.

## Project rules for parallel work
- **Benchmark isolation in practice.** The Corpus lane (B1, C*) denies `eval/`; C2 may read `eval/split.json` only. The Engine lane (E4, E6, E8–E11) denies `eval/commission_examples`, `eval/cases/commission_b` and `eval/split.json`; own cases stay readable for replay tests. The engine gate blocks `backend/aiact/engine/` until `eval/split.json` is committed. `isolation-auditor` reviews every story; the CI isolation job and `tests/test_isolation.py` are the backstops.
- **Database is shared.** All worktrees use the same local Supabase instance. Create migrations only with `supabase migration new` (timestamped names), and never run `supabase db reset`: it wipes the corpus every worktree relies on. Only one running story at a time may change the schema (`Resource: db-schema`). Tests isolate themselves with a transaction per test or a per-story schema.
- **Don't name things with the bare word `eval`** in shell commands (for example `supabase migration new eval`): the lane guard reads it as a path. Use names like `eval_records`.
- **Lockfiles.** If `uv.lock` conflicts, regenerate it with `uv lock`, then run `uv run aiact deps generate` and commit `docs/DEPENDENCIES.md` and `docs/dependency-licences.json` with it. Case changes need `uv run aiact evaluate isolation-embed` and a committed `eval/isolation/embeddings.json`; on a merge conflict, regenerate it.
- **Paid calls.** A worker may spend up to `cost_cap_usd` in the config without asking; anything more, and any full benchmark run, needs the user's go-ahead.

## Project tooling (`.claude/`)
- **Scoped rules:** `.claude/rules/*.md` load only when Claude reads matching files. Subfolders are read too, so keep this folder small and specific to this project.
  - Visual design comes from the user's design system (copy in `docs/design-system/`) and Design canvas (see `docs/BACKLOG.md` › Phase 5 › Design reference), and the `frontend-design` skill covers gaps. It doesn't come from a rule.
