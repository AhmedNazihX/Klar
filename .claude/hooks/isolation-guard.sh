#!/bin/bash
# PreToolUse hook: on Corpus-lane story branches (story/B1-*, story/C<n>-*), block any access to the
# benchmark folder eval/. Story C2 may read eval/split.json only. Backs up the sparse checkout that
# leaves eval/ out of those worktrees. Enforces INIT › Benchmark isolation.
# The lane comes from the branch checked out in the hook's cwd, which is the worktree root for
# worktree agents. The package folder backend/aiact/eval/ is code, not benchmark data, and is allowed.

INPUT=$(cat)
TOOL=$(echo "$INPUT" | jq -r '.tool_name // empty')
CWD=$(echo "$INPUT" | jq -r '.cwd // empty')

BRANCH=$(git -C "${CWD:-.}" rev-parse --abbrev-ref HEAD 2>/dev/null) || exit 0
STORY=$(echo "$BRANCH" | sed -nE 's#^story/(B1|C[0-9]+[a-z]?)-.*#\1#p')
[ -z "$STORY" ] && exit 0

block() {
  echo "BLOCKED: $1 Branch '$BRANCH' is a Corpus-lane story, and corpus work must never read the benchmark (CLAUDE.md › Global rules, Benchmark isolation). If you believe you need this, stop and ask the user." >&2
  exit 2
}

# Remove what is allowed, then look for any remaining eval/ path segment.
strip_allowed() {
  local s="$1"
  s=$(echo "$s" | sed -E 's#aiact/eval(/|$)#aiact/_pkg_\1#g')
  [ "$STORY" = "C2" ] && s=$(echo "$s" | sed -E "s#(^|[/[:space:]'\"=:(])eval/split\\.json#\\1_split_json_#g")
  echo "$s"
}

# An "eval" path segment in shell text: `eval/…`, `$MAIN/eval`, `-- eval`, `main:eval/…`, `'eval'`.
# Best effort: matching shell text can't catch every indirection (variables, scripts). The sparse
# checkout and the isolation-auditor are the backstops. Side effect on Corpus-lane branches: the word
# "eval" as a command argument (for example `aiact eval run`) is blocked too, which that lane never needs.
EVAL_SEGMENT_RE="(^|[/[:space:]'\"=:(])eval(/|[[:space:];&|'\")]|$)"

touches_eval_path() {
  echo "$(strip_allowed "$1")" | grep -qE '(^|/)eval(/|$)'
}

case "$TOOL" in
  Read|Write|Edit|MultiEdit|NotebookEdit)
    P=$(echo "$INPUT" | jq -r '.tool_input.file_path // .tool_input.notebook_path // empty')
    touches_eval_path "$P" && block "'$P' is inside eval/."
    ;;
  Grep|Glob)
    for P in "$(echo "$INPUT" | jq -r '.tool_input.path // empty')" \
             "$(echo "$INPUT" | jq -r '.tool_input.pattern // empty' | { [ "$TOOL" = Glob ] && cat || true; })" \
             "$(echo "$INPUT" | jq -r '.tool_input.glob // empty')"; do
      [ -n "$P" ] && touches_eval_path "$P" && block "'$P' searches inside eval/."
    done
    ;;
  Bash)
    RAW=$(echo "$INPUT" | jq -r '.tool_input.command // empty')
    # Any sparse-checkout change except listing it could bring eval/ back.
    if echo "$RAW" | grep -qE 'sparse-checkout' && ! echo "$RAW" | grep -qE 'sparse-checkout[[:space:]]+list([[:space:];&|]|$)'; then
      block "'$RAW' would change the sparse checkout that keeps eval/ out of this worktree."
    fi
    # Heredoc bodies and commit messages are text, not commands: drop them before matching.
    CMD=$(echo "$RAW" | awk -f "$(dirname "$0")/lib/strip-heredocs.awk" \
          | sed -E "s/(-m|--message)(=|[[:space:]]+)\"[^\"]*\"//g; s/(-m|--message)(=|[[:space:]]+)'[^']*'//g")
    CMD=$(strip_allowed "$CMD")
    if echo "$CMD" | grep -qE "$EVAL_SEGMENT_RE"; then
      block "'$RAW' touches eval/."
    fi
    ;;
esac

exit 0
