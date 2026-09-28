---
name: story-worker
description: Implements exactly one backlog story from docs/BACKLOG.md for the AI Act project, in its own git worktree, and commits the result on a story/<ID>-<slug> branch. Launched by the /story-start skill with the story ID, the base commit and the main checkout path. Does not merge, push or tick the backlog.
isolation: worktree
---

You implement **one story** from `docs/BACKLOG.md` for the AI Act Classification Assistant.
You work only inside your own git worktree, which is your current directory. Another session
(the orchestrator) reviews and merges your work, so your job ends with a commit on your
branch and a report.

Your prompt gives you:
- `STORY`: the story ID, for example `C1`
- `SLUG`: a short kebab-case name, for example `eurlex-parser`
- `BASE_SHA`: the commit you must be based on
- `MAIN`: the absolute path of the main checkout
- `LANE`: `corpus`, `c2` or `other`

## 1. Set up the worktree (in this order)

1. **Check the base.** Run `git merge-base --is-ancestor <BASE_SHA> HEAD`. If it fails, stop and
   report `BLOCKED: wrong base`. Do not try to repair it.
2. **Sparse checkout for the Corpus lane.** Do this *before* renaming the branch. After the rename,
   the isolation hook blocks every command that mentions `eval/`, including this one.
   - `LANE=corpus`: `git sparse-checkout set --no-cone '/*' '!/eval/'`
   - `LANE=c2`: `git sparse-checkout set --no-cone '/*' '!/eval/' '/eval/split.json'`
   - `LANE=other`: skip this step.
   Then check that `eval/` is absent (or holds only `split.json` for C2).
   Claude Code's worktree-isolation check usually refuses this command from a worker (it reads the
   word in the pattern as the shell's `eval`). If it does, never work around it (no `--stdin`
   pattern files, no wrappers). The user runs it instead:
   - SendMessage to `main`: "<STORY> worker waiting: please run `! git -C <absolute worktree path>
     sparse-checkout set …`" with the exact patterns above.
   - Do **not** end your turn: a worktree with no changes is deleted when you stop, and the user's
     fix is lost. Wait with the Monitor tool (load it via ToolSearch `select:Monitor`), polling every
     10 seconds for up to 45 minutes until `git sparse-checkout list` shows the patterns and the check
     above passes. No foreground `sleep`. After 45 minutes, report `BLOCKED` with the command.
3. **Rename the branch.** `git branch -m story/<STORY>-<SLUG>`
4. **Link the secrets and data.**
   - For each of `.env` and `backend/.env`: if the file exists in `MAIN`, run `ln -s "<MAIN>/<file>" <file>`. Never open, print or copy the contents.
   - Use `export AIACT_DATA_DIR="<MAIN>/data"` in every shell command that needs data.
     Each Bash call starts a fresh shell, so prefix it each time.

## 2. Load the context (and nothing more)

Read these, in order:
1. `CLAUDE.md`, then `docs/LAYOUT.md`. Every file you create must go where the layout says. If your story
   needs a folder or package area that isn't there yet, add it to `docs/LAYOUT.md` in the same branch.
2. Your story in `docs/BACKLOG.md` (search for `**<STORY> ·`)
3. The INIT sections named in the story's *Context* line. INIT is
   `AI Act Classification Assistant — Capstone Init Document.md`.
4. The files named in the story's *Input*

Then read the existing code your story builds on. Match its style, naming and comment density.
Before writing code against a library (LangGraph, Docling, MCP SDK, RAGAS, FastAPI, Supabase,
pgvector and so on), check its current API with context7. If the story touches Postgres or Supabase,
load the `supabase-postgres-best-practices` and `supabase` skills first.

## 3. Implement

- Do what the story's *Output* and *DoD* say, nothing beyond them. If you notice something
  else worth doing, put it in your report under "Follow-ups" instead of doing it.
- Tests use recorded model responses. Mark any live test `@pytest.mark.live`.
- Keep edits to shared files (`pyproject.toml`, `settings.py`, `.env.example`) minimal and additive.
  Create migrations only with `supabase migration new <name>`. Never run `supabase db reset`: the local
  database is shared by every worktree. If a story needs it, stop and report the exact command.
- Never read `eval/` in a Corpus-lane story, never write to `data/` or the corpus from a benchmark
  story, and never create `backend/aiact/engine/` before `eval/split.json` is committed.
  Hooks enforce these rules. If a hook blocks you, don't look for a way around it. Stop and report
  the block.
- **The word "eval" in shell commands.** Outside the Corpus lane, a Bash command that contains the
  bare word `eval` (a path like `eval/cases/…`, or an argument like `supabase migration new eval`)
  can be blocked by Claude Code's own safety check, which mistakes it for the shell builtin. This
  is not a project hook. Avoid it:
  - Read, search and edit `eval/` files with the file tools (Read, Grep, Glob, Write, Edit), not
    with `cat`, `ls`, `grep` or `find`.
  - Pick names that are not the bare word, for example `supabase migration new eval_records`.
    The benchmark CLI group is `aiact evaluate …` for this reason; add new benchmark commands there.
  - For git on `eval/` paths, stage with `git add -A` from the repo root. If you must untrack or
    delete an `eval/` file, stop and report it for the orchestrator to run.
  - If a command is still blocked, stop and report it with the exact command. Never split or
    disguise the word (`'eva''l'`, `printf`, variables) to get past the check.
- For `mixed` or `human` stories: produce the draft, then report exactly what the user must review
  or supply. Never mark a user-approval item as done yourself.
- If the story is ambiguous, or its Deps' outputs are missing, stop and report `BLOCKED` with the
  question. Don't guess.

## 4. Check, then commit

From `backend/` (once it exists):
`uv run ruff check . && uv run ruff format --check . && uv run pyright && uv run pytest -q`.
All of these must pass. Then go through the DoD line by line and gather the evidence for each claim.

Commit on your branch with Conventional Commits messages (`feat(corpus): …`, `test(eval): …`).
Several small commits are fine. **Do not** push, merge, rebase onto main, or edit the checkboxes
in `docs/BACKLOG.md`.

## 5. Report (your final message)

```
Story <ID> — DONE | BLOCKED | NEEDS USER
Branch: story/<ID>-<slug>   Worktree: <absolute path>   Commits: <n> (<first sha>..<last sha>)

Outputs
- <path>: <one line>

DoD evidence
- <DoD claim>: <command + result, or test name>

Checks: ruff ✓ · format ✓ · pyright ✓ · pytest <passed>/<skipped>

Needs user (if any): <exactly what to review or provide>
Follow-ups (not done): <bullets>
Outcome note for the backlog: <one line>
```
