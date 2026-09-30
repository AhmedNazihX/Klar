---
name: story-start
description: Starts one or more AI Act backlog stories — checks their deps and the parallel-work rules, then launches a story-worker agent per story in its own git worktree (story/<ID>-<slug> branch, sparse checkout for the Corpus lane). Use when the user says to start, launch, kick off or work on a story or wave (e.g. "/story-start C1", "start F2 F3 F4").
argument-hint: "<ID> [ID ...]"
---

# Start stories: $ARGUMENTS

You are the **orchestrator**: the main session. You don't implement the stories yourself. You check that
each one can start, then launch one `story-worker` agent per story. Each agent works in its own worktree.

## 1. Check the whole set before launching anything

Run from the main checkout, which must be on `main`:

```bash
git rev-parse --abbrev-ref HEAD      # must be main
git status --porcelain               # must be empty: a worktree branches from HEAD, not from uncommitted work
git rev-parse HEAD                   # BASE_SHA
git branch --list 'story/*'          # stories already in flight
```

If the checkout is not on `main`, or has uncommitted changes, stop and tell the user.

For each requested ID:

```bash
python3 .claude/scripts/backlog.py info <ID>   # slug, lane, type, deps, done
python3 .claude/scripts/backlog.py deps <ID>   # exit 1 = unmet deps
```

Refuse a story, and say why, if any of these hold:
- It's already done (`info` → `"done": true`; a sub-story such as B5c counts as done once its outcome note exists), or a `story/<ID>-*` branch already exists.
- It's a grouped entry's own ID (`B5`, `B5a–e`: `info` shows a non-empty `sub_stories`). Start the sub-stories instead, for example `/story-start B5a B5b`.
- It has unmet deps. List them.
- It has a "check by hand" condition (for example "run in week 9" or "MVP done"). Ask the user to confirm the condition holds.
- It's **F1**, or one of **E8, E9, E10**, and anything else is requested or in flight. These run alone.
- It's an **E\*** story and `git cat-file -e HEAD:eval/split.json` fails (the B3 gate).
- It **changes the schema** (it creates a migration: F4, F5, C7, P3, or `info` shows `"may_change_schema": true` and the story's text confirms it) and another schema-changing story is in the set or in flight.

Launch whatever passes, and report what was refused.

## 2. Human stories don't get an agent

For `Type: human` stories, don't launch a worker. Show the user the story (`backlog.py show <ID>`),
list exactly what they need to do or provide, and offer to create the branch for them.
Launch `mixed` stories normally: the worker drafts, then reports what the user must review.

## 3. Launch one worker per story, all in a single message

Launch all the workers in one message, so they run in parallel. Use the Agent tool with
`subagent_type: "story-worker"`, which runs in a worktree by default. The prompt must be self-contained:

```
STORY: <branch_id from info>
SLUG: <slug>
BASE_SHA: <sha>
MAIN: <absolute path of the main checkout>
LANE: <lane from info: corpus | c2 | other>

Story entry (from docs/BACKLOG.md):
<paste the full output of `backlog.py show <ID>`>

For a sub-story of a grouped entry (for example B5c of B5a–e), do only the part for <branch_id>.
Follow your agent instructions: set up the worktree, load context, implement, check, commit, report.
```

Never paste the contents of `.env`, or any benchmark file, into a Corpus-lane prompt.

## 4. Tell the user

Give one line per launched story: its ID, title and lane. Then any refused stories and why. Then say that you'll
report as each worker finishes, and that the next step for each is `/story-finish <ID>`.
When a worker's final report arrives, relay its status (DONE / BLOCKED / NEEDS USER) and what it needs.
Don't merge anything yourself at this stage.
