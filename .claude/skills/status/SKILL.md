---
name: status
description: Shows the AI Act project's backlog status — which stories are done, in progress (a story/<ID>-* branch exists), ready to start (all deps done) or blocked, and where the critical path stands — then recommends what to launch next. Use when the user asks for status, progress, what's next, what can run in parallel, or which stories are ready.
argument-hint: "[lane or story ID to focus on]"
---

# Backlog status

1. Run the parser from the repo root:
   ```bash
   python3 .claude/scripts/backlog.py status
   git worktree list
   ```
2. Present it compactly:
   - One line with the totals and the next story on the critical path.
   - **In progress:** each story with its worktree path, if it has one.
   - **Ready:** as a table (ID, title, type, lane). Mark `human` and `mixed` stories: they need the user's time.
     List any "check by hand" notes, such as "run in week 9" or "MVP done", as conditions, not as ready work.
   - **Blocked:** summarise it. Don't list all of it; name only the stories one step away from ready.
3. Recommend a launch set:
   - Put critical-path stories first, then stories that unblock the most others, then long `human` stories (for example B11), which should start early.
   - Respect the rules in `CLAUDE.md` › Parallel work:
     - F1, and the chain E8 → E9 → E10, run alone.
     - Only one schema-changing story at a time (stories that create migrations: F4, F5, C7, P3, or any story whose Output names a migration).
     - E* stories need `eval/split.json` committed.
   - End with the exact command, for example `/story-start F2 F3 F4 F6 B1`.
4. If `$ARGUMENTS` names a lane or story, focus the answer on it. For a story, also show
   `python3 .claude/scripts/backlog.py show <ID>` and its unmet deps.

Read-only: this skill never changes files or branches.
