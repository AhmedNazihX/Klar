---
name: status
description: Shows the AI Act project's backlog status — which stories are done, in progress (a story/<ID>-* branch exists), ready to start (all deps done) or blocked, and where the critical path stands — then recommends what to launch next. Use when the user asks for status, progress, what's next, what can run in parallel, or which stories are ready.
argument-hint: "[lane or story ID to focus on]"
---

# Backlog status

1. Run the parser and the repo checks from the repo root:
   ```bash
   python3 .claude/scripts/backlog.py status
   git worktree list
   git log --oneline origin/main..main          # unpushed commits on main
   gh run list --branch main --limit 1          # the latest CI run on main
   ```
2. Check that each ready story can actually finish. `Deps:` can miss an input the story's DoD or
   Context needs (a case set, a decision record, a file another story writes). For every ready
   story you might recommend, read `python3 .claude/scripts/backlog.py show <ID>` and confirm each
   input its DoD names exists in the repo. If one is missing, call the story "ready to build, not to
   finish", name the missing input and the story that makes it, and offer to add that dep to the backlog.
3. Present it compactly:
   - One line with the totals and the next story on the critical path. If the parser says that story is
     waiting on something, name what it waits on: that is the real next step.
   - **Repo:** unpushed commits on `main` (how many) and the latest CI run's result, only when there is
     something to say (commits not pushed, or a run that failed or is still running).
   - **In progress:** each story with its worktree path, if it has one.
   - **Ready:** as a table (ID, title, type, lane). Mark `human` and `mixed` stories: they need the user's time.
     Mark stories the parser tags `migration?`: they may change the schema.
     List any "check by hand" notes, such as "run in week 9" or "MVP done", as conditions, not as ready work.
   - **Blocked:** summarise it. Don't list all of it; name only the stories one step away from ready.
4. Recommend a launch set:
   - Put critical-path stories first, then stories that unblock the most others, then long `human` stories (for example B11), which should start early.
   - Respect the rules in `CLAUDE.md` › Parallel work:
     - F1, and the chain E8 → E9 → E10, run alone.
     - Only one schema-changing story at a time: the parser's `migration?` tag, `info`'s `may_change_schema`, and
       F4, F5, C7, P3. Read the story to confirm; the tag only means a migration is mentioned.
     - E* stories need `eval/split.json` committed.
   - Mind the user's review time: put at most two `mixed` or `human` stories in one set unless the user asks
     for more, and say which of them lands on the user first.
   - End with the exact command, for example `/story-start F2 F3 F4 F6 B1`.
5. If `$ARGUMENTS` names a lane or story, focus the answer on it. For a story, also show
   `python3 .claude/scripts/backlog.py show <ID>` and its unmet deps.

Read-only: this skill never changes files or branches.
