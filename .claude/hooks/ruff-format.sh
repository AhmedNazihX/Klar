#!/bin/bash
# PostToolUse hook: formats edited Python files with ruff, using the repo's backend/ uv project.
# Never fails the tool call: silently does nothing until backend/pyproject.toml exists.
# Formats only (no `ruff check --fix`), so half-finished edits such as a new import are not removed.

INPUT=$(cat)
FILE=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')
CWD=$(echo "$INPUT" | jq -r '.cwd // empty')

[[ "$FILE" == *.py ]] || exit 0
[[ "$FILE" != /* ]] && FILE="$CWD/$FILE"
[ -f "$FILE" ] || exit 0

TOP=$(git -C "$(dirname "$FILE")" rev-parse --show-toplevel 2>/dev/null) || exit 0
[ -f "$TOP/backend/pyproject.toml" ] || exit 0

uv run --quiet --project "$TOP/backend" ruff format --quiet "$FILE" >/dev/null 2>&1
exit 0
