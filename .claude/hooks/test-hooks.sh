#!/bin/bash
# Regression tests for the project hooks. Run: bash .claude/hooks/test-hooks.sh
# Builds throwaway git repos in a temp dir; never touches the real repo. Exit 1 if any case fails.

HOOKS="$(cd "$(dirname "$0")" && pwd)"
GATE="$HOOKS/engine-gate.sh"
GUARD="$HOOKS/isolation-guard.sh"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
FAILS=0
E=backend/aiact/engine   # built at runtime so this file's own commands never mention the path

run() {  # run <hook> <expected exit> <json> <label>
  printf '%s' "$3" | "$1" >/dev/null 2>&1
  local c=$?
  if [ "$c" = "$2" ]; then echo "  ok    $4"; else echo "  FAIL  $4 (exit $c, want $2)"; FAILS=$((FAILS + 1)); fi
}
bash_in() { jq -nc --arg c "$2" --arg d "$1" '{tool_name:"Bash",cwd:$d,tool_input:{command:$c}}'; }
tool_in() { jq -nc --arg t "$1" --arg d "$2" --arg p "$3" '{tool_name:$t,cwd:$d,tool_input:{file_path:$p,content:"x"}}'; }
new_repo() { rm -rf "$1"; mkdir -p "$1/backend/aiact"; git -C "$1" init -q; git -C "$1" commit -q --allow-empty -m init; }

# ---------------------------------------------------------------- engine gate
R="$TMP/gate"; new_repo "$R"
echo "engine gate, before the split is committed"
run "$GATE" 2 "$(tool_in Write "$R" "$R/$E/graph.py")"                     "Write engine file (absolute)"
run "$GATE" 2 "$(tool_in Write "$R" "$E/state.py")"                         "Write engine file (relative)"
run "$GATE" 2 "$(bash_in "$R" "mkdir -p $E")"                               "mkdir engine"
# bash 3.2 brace-expands literal {a,b} inside "$(...)", so these commands live in single-quoted variables.
BRACE_ENGINE='mkdir -p backend/aiact/{schemas,corpus,engine,eval}'
BRACE_F1='mkdir -p backend/aiact/{schemas,corpus,eval}'
run "$GATE" 2 "$(bash_in "$R" "$BRACE_ENGINE")"                             "mkdir with brace expansion"
run "$GATE" 2 "$(bash_in "$R" "cd backend/aiact && mkdir engine && touch engine/__init__.py")" "cd into aiact, then mkdir engine"
run "$GATE" 2 "$(bash_in "$R" "echo x > $E/a.py")"                          "redirect into engine"
run "$GATE" 2 "$(bash_in "$R" $'cat > '$E$'/graph.py <<EOF\nx = 1\nEOF')"   "heredoc writing into engine"
run "$GATE" 2 "$(bash_in "$R" $'x=$(cat <<<"hi")\nmkdir -p '$E)"            "here-string, then mkdir engine"
run "$GATE" 2 "$(bash_in "$R" $'cat > notes.txt <<-EOF\n\tx\n\tEOF\nmkdir -p '$E)" "<<- heredoc with tab terminator, then mkdir"
run "$GATE" 0 "$(bash_in "$R" $'cat > rules.md <<\'EOF\'\n  - "'$E$'/**"\nEOF\nls')" "heredoc only mentioning the path"
run "$GATE" 0 "$(bash_in "$R" "ls $E 2>/dev/null")"                         "ls engine with 2>/dev/null"
run "$GATE" 0 "$(bash_in "$R" "$BRACE_F1")"                                 "F1 scaffold without engine"
run "$GATE" 0 "$(tool_in Write "$R" "$R/backend/aiact/eval/runner.py")"     "Write aiact/eval package"
run "$GATE" 0 "$(tool_in Read "$R" "$R/$E/x.py")"                           "Read engine file"
mkdir -p "$R/eval"; echo '{}' > "$R/eval/split.json"
run "$GATE" 2 "$(tool_in Write "$R" "$R/$E/graph.py")"                     "split exists but not committed"
git -C "$R" add eval/split.json; git -C "$R" commit -q -m split
echo "engine gate, after the split is committed"
run "$GATE" 0 "$(tool_in Write "$R" "$R/$E/graph.py")"                     "Write engine file"
run "$GATE" 0 "$(bash_in "$R" "mkdir -p $E")"                               "mkdir engine"

# ---------------------------------------------------------------- isolation guard
R="$TMP/iso"; new_repo "$R"; M=/abs/main
git -C "$R" checkout -q -b story/C1-eurlex-parser
echo "isolation guard on story/C1"
run "$GUARD" 2 "$(tool_in Read "$R" "$M/eval/cases/own/a.yaml")"           "Read eval case in main checkout"
run "$GUARD" 2 "$(tool_in Read "$R" "eval/split.json")"                     "Read split.json (only C2 may)"
run "$GUARD" 0 "$(tool_in Read "$R" "$M/backend/aiact/eval/cases.py")"      "Read aiact/eval package code"
run "$GUARD" 0 "$(tool_in Read "$R" "$M/backend/aiact/corpus/eurlex.py")"   "Read corpus code"
run "$GUARD" 2 "$(jq -nc --arg d "$R" '{tool_name:"Grep",cwd:$d,tool_input:{pattern:"hr-ex",path:"/abs/main/eval"}}')" "Grep in eval/"
run "$GUARD" 2 "$(jq -nc --arg d "$R" '{tool_name:"Grep",cwd:$d,tool_input:{pattern:"x",glob:"eval/**"}}')" "Grep with eval glob"
run "$GUARD" 2 "$(jq -nc --arg d "$R" '{tool_name:"Glob",cwd:$d,tool_input:{pattern:"**/eval/**/*.yaml"}}')" "Glob eval/**"
run "$GUARD" 0 "$(jq -nc --arg d "$R" '{tool_name:"Grep",cwd:$d,tool_input:{pattern:"eval/",path:"/abs/main/backend"}}')" "Grep for the text eval/ in backend"
run "$GUARD" 2 "$(bash_in "$R" "cat eval/split.json")"                      "cat eval/split.json"
run "$GUARD" 2 "$(bash_in "$R" "cd eval && ls")"                            "cd eval"
run "$GUARD" 2 "$(bash_in "$R" "ls $M/eval")"                               "ls main checkout eval (no slash)"
run "$GUARD" 2 "$(bash_in "$R" "find $M/eval -name '*.json'")"              "find main checkout eval"
run "$GUARD" 2 "$(bash_in "$R" "grep -rn foo eval")"                        "grep -rn foo eval"
run "$GUARD" 2 "$(bash_in "$R" "rg foo eval")"                              "rg foo eval"
run "$GUARD" 2 "$(bash_in "$R" "git checkout main -- eval")"                "git checkout main -- eval"
run "$GUARD" 2 "$(bash_in "$R" "git ls-tree -r main eval")"                 "git ls-tree main eval"
run "$GUARD" 2 "$(bash_in "$R" "git show main:eval/split.json")"            "git show main:eval/…"
run "$GUARD" 2 "$(bash_in "$R" "git sparse-checkout disable")"              "sparse-checkout disable"
run "$GUARD" 2 "$(bash_in "$R" "git sparse-checkout set --no-cone '/*'")"   "sparse-checkout set (widening)"
run "$GUARD" 0 "$(bash_in "$R" "git sparse-checkout list")"                 "sparse-checkout list"
run "$GUARD" 2 "$(bash_in "$R" $'x=$(cat <<<"hi")\ncat eval/cases/a.json')" "here-string, then cat eval"
run "$GUARD" 0 "$(bash_in "$R" $'cat > notes.md <<\'EOF\'\nsee eval/cases\nEOF')" "heredoc only mentioning eval/"
run "$GUARD" 0 "$(bash_in "$R" 'git commit -m "feat(corpus): parser never reads eval data"')" "commit message mentioning eval"
run "$GUARD" 0 "$(bash_in "$R" "uv run pytest tests/test_eurlex.py")"       "run tests"
run "$GUARD" 0 "$(bash_in "$R" "cat backend/aiact/eval/__init__.py")"       "cat aiact/eval package"
git -C "$R" checkout -q -b story/C2-guidelines
echo "isolation guard on story/C2"
run "$GUARD" 0 "$(tool_in Read "$R" "$M/eval/split.json")"                  "Read split.json"
run "$GUARD" 0 "$(bash_in "$R" "jq .pile_b eval/split.json")"               "jq split.json"
run "$GUARD" 0 "$(bash_in "$R" "python3 -c \"import json; json.load(open('eval/split.json'))\"")" "python open('eval/split.json')"
run "$GUARD" 0 "$(bash_in "$R" "SPLIT=eval/split.json uv run python -m x")" "SPLIT=eval/split.json"
run "$GUARD" 2 "$(tool_in Read "$R" "$M/eval/commission_examples/examples.jsonl")" "Read examples.jsonl"
run "$GUARD" 2 "$(bash_in "$R" "cat eval/cases/a.yaml")"                    "cat an eval case"
git -C "$R" checkout -q -b story/B1-fetch-sources
echo "isolation guard on story/B1"
run "$GUARD" 2 "$(tool_in Read "$R" "$M/eval/cases/own/a.yaml")"           "Read eval case"
git -C "$R" checkout -q -b story/B4-rewrite-pile-b
echo "isolation guard on story/B4 (benchmark lane) and main"
run "$GUARD" 0 "$(tool_in Read "$R" "$M/eval/cases/own/a.yaml")"           "B4: Read eval case"
git -C "$R" checkout -q -b main 2>/dev/null || git -C "$R" checkout -q main
run "$GUARD" 0 "$(tool_in Read "$R" "$M/eval/cases/own/a.yaml")"           "main: Read eval case"

echo
[ "$FAILS" = 0 ] && echo "All hook tests passed." || { echo "$FAILS hook test(s) failed."; exit 1; }
