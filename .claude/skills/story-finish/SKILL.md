---
name: story-finish
description: Finishes an AI Act backlog story — verifies its Definition of Done, reviews the diff and checks benchmark isolation in parallel, then (with the user's go-ahead) merges the story branch into main, ticks the backlog with an outcome note and cleans up the worktree. Use when a story-worker reports DONE, or when the user says to finish, review, verify or merge a story ("/story-finish C1").
argument-hint: "<ID> [ID ...]"
---

# Finish stories: $ARGUMENTS

You are the orchestrator in the main checkout, on `main`. Handle each ID in turn. Any review
agents can run in parallel.

## 1. Locate the story

```bash
python3 .claude/scripts/backlog.py info <ID>
git branch --list 'story/<ID>-*'                # exactly one branch expected
git worktree list                               # the worktree path of that branch, if it still exists
git log --oneline main..story/<ID>-<slug>       # must have at least one commit
git merge-base --is-ancestor main story/<ID>-<slug> || echo "main has moved on"
```

If there's no branch or no commits, stop and report. If `main` has moved on since the story branched,
tell the user. The merge in step 3 then becomes a real merge rather than a fast-forward. That's fine
unless the files conflict.

## 2. Review: launch these agents in one message

- **`dod-verifier`**: "Verify story `<ID>` at worktree `<path>` (branch `story/<ID>-<slug>`). The user's
  approvals so far: <list any the user has given in this conversation, or 'none'>."
  If the worktree is gone, give it the branch instead and ask it to check against the branch with `git show` and `git diff`.
- **`diff-reviewer`**: "Review the diff `main...story/<ID>-<slug>`." Run it in the worktree, if one exists.
- **`isolation-auditor`**: only when the lane is `corpus` or `c2`, the ID starts with `E` or `B`, or the diff touches
  `eval/`, `data/`, `backend/aiact/corpus/` or `backend/aiact/retrieval/`.
  Prompt: "Audit branch `story/<ID>-<slug>`."

## 3. Decide, then merge with the user's go-ahead

Summarise for the user:
- The DoD verdict table.
- The diff-reviewer's critical and major findings.
- The isolation result.

Then:
- **All green** (DoD is DONE, no critical or major findings, isolation PASS or not run): ask the user to confirm the merge.
- **Anything open:** don't merge. Say what's missing. Offer to send the findings back to the worker
  (SendMessage to the worker agent, if it's still available), or start a fix in the same worktree.
- **NEEDS USER:** list exactly what the user must review or approve, and wait.

When the user confirms, run from the main checkout:

```bash
git merge --no-ff story/<ID>-<slug> -m "merge: story <ID> <title>"
```

If the merge changed `backend/pyproject.toml` or `backend/uv.lock`, make sure the dependency manifest
matches. With hooks enabled, `pre-merge-commit` regenerates and stages the files, then stops the merge;
finish it with `git commit --no-edit`. Without hooks, the check catches it:

```bash
uv run --project backend aiact deps check \
  || { uv run --project backend aiact deps generate \
       && git add docs/DEPENDENCIES.md docs/dependency-licences.json \
       && git commit --amend --no-edit; }
```

The amend folds the regenerated files into the merge commit, which is still local and unpushed.

Then check that the tests still pass on `main` after the merge (skip this if `backend/` doesn't exist yet):

```bash
(cd backend && uv run pytest -q)
```

**Only if that passes**, tick the backlog and commit:

```bash
python3 .claude/scripts/backlog.py tick <ID> "<one-line outcome, taken from the worker's report>" \
  && git add docs/BACKLOG.md && git commit -m "docs(backlog): tick <ID>"
```

If the tests fail after the merge, don't tick. Tell the user what failed. The merge commit is local and
not pushed, so the user can decide whether to fix forward on `main` or undo the merge.

For a sub-story of a grouped entry (for example B5c), `tick` only adds a note. Tick the group itself
(`tick B5 …`) once every sub-story has been merged.

## 4. Clean up and point to what's next

```bash
git worktree remove <path>            # only after a successful merge
git branch -d story/<ID>-<slug>       # lowercase -d: refuses to delete an unmerged branch
```

Worktrees branch from the local HEAD, so dependent stories can start without a push. Offer to push
`main`; the push hook will ask the user to approve it. Finish by running
`python3 .claude/scripts/backlog.py status` and naming the stories this merge has just unblocked.
