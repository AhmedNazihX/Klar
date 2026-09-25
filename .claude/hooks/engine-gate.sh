#!/bin/bash
# PreToolUse hook: no file under backend/aiact/engine/ may be created or changed until
# eval/split.json is committed (story B3). Enforces INIT › Benchmark isolation, rule 1.
# The check runs against the repo (or worktree) that holds the target, so it works in worktrees.

INPUT=$(cat)
TOOL=$(echo "$INPUT" | jq -r '.tool_name // empty')
CWD=$(echo "$INPUT" | jq -r '.cwd // empty')
ENGINE_RE='(^|/)backend/aiact/engine(/|$)'

# Nearest existing directory of a path, so git can find the repo even for new files.
existing_dir() {
  local d="$1"
  while [ -n "$d" ] && [ ! -d "$d" ]; do d=$(dirname "$d"); done
  echo "${d:-.}"
}

split_committed() {
  local top
  top=$(git -C "$1" rev-parse --show-toplevel 2>/dev/null) || return 0  # not a git repo: nothing to gate
  git -C "$top" cat-file -e HEAD:eval/split.json 2>/dev/null
}

block() {
  echo "BLOCKED: $1 Engine code may only be written after story B3 has committed eval/split.json (see CLAUDE.md › Global rules and docs/BACKLOG.md › B3)." >&2
  exit 2
}

case "$TOOL" in
  Write|Edit|MultiEdit|NotebookEdit)
    FILE=$(echo "$INPUT" | jq -r '.tool_input.file_path // .tool_input.notebook_path // empty')
    [[ "$FILE" != /* ]] && FILE="$CWD/$FILE"
    if echo "$FILE" | grep -qE "$ENGINE_RE"; then
      split_committed "$(existing_dir "$(dirname "$FILE")")" || block "'$FILE' is engine code."
    fi
    ;;
  Bash)
    # Best effort: matching shell text can't catch every way to create a folder (variables, scripts).
    # The file-tool check above, the isolation-auditor and dod-verifier are the backstops.
    # Heredoc bodies are file content, not commands: drop them so text that merely mentions the path doesn't match.
    CMD=$(echo "$INPUT" | jq -r '.tool_input.command // empty' | awk -f "$(dirname "$0")/lib/strip-heredocs.awk")
    # Mentions the engine: the path itself, or "aiact" plus an "engine" path segment
    # (catches `mkdir -p aiact/{schemas,engine}` and `cd backend/aiact && mkdir engine`).
    MENTIONS=0
    echo "$CMD" | grep -qE 'aiact/engine' && MENTIONS=1
    echo "$CMD" | grep -qE 'aiact' && echo "$CMD" | grep -qE '(^|[/{,[:space:]])engine([/},[:space:];&|]|$)' && MENTIONS=1
    if [ "$MENTIONS" = 1 ]; then
      WRITES=0
      echo "$CMD" | grep -qE '(^|[^A-Za-z0-9_-])(mkdir|touch|cp|mv|tee|install|ln|rsync|git[[:space:]]+mv)([^A-Za-z0-9_-]|$)' && WRITES=1
      # A redirect counts only when it points into the engine (so `ls … 2>/dev/null` is fine).
      echo "$CMD" | grep -qE '>+[[:space:]]*[^[:space:]]*engine' && WRITES=1
      [ "$WRITES" = 1 ] && { split_committed "${CWD:-.}" || block "'$CMD' would create or change engine code."; }
    fi
    ;;
esac

exit 0
