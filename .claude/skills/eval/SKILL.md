---
name: eval
description: Runs an AI Act benchmark through `aiact evaluate run` — a case set, a classifier, a subset size, a cost cap and a held-out/all exclude mode — refuses a full run without the user's go-ahead, and appends the stored run's metrics (with its run_id) to eval/reports/run-<date>.md. Use when the user asks to run, dry-run, re-run or benchmark the engine or a baseline, to do a gap run, or to write a run report ("/eval academic 3 dummy").
argument-hint: "<set> [subset N | full] [classifier] [heldout|all] [cap USD]"
---

# Benchmark run: $ARGUMENTS

You run from the main checkout (or a worktree that has `backend/.env` and a reachable local
Supabase). Every number in the report comes from the database, by run_id, never from memory,
from the chat or from your own arithmetic (INIT › Evaluation; `.claude/rules/eval.md`).

## 1. Read the arguments

| Setting | CLI option | Default | Allowed |
| --- | --- | --- | --- |
| Case set | `--set` | none: ask | `commission_b`, `own`, `soft_pairs`, `consistency`, `academic`, `appliedai` |
| Classifier | `--classifier` | `dummy` | whatever `uv run aiact evaluate run --help` lists (`dummy` is free and offline; `engine` after E10; `baseline_*` after V3) |
| Subset size | `--subset N` | 3 with `dummy`, otherwise ask | 1–30 without a go-ahead (see step 2) |
| Exclude mode | `--exclude-mode` | `heldout` | `heldout` (the reported number) or `all` (the gap run, INIT › Benchmark isolation 4) |
| Cost cap | `--max-cost-usd` | `1.0` | any positive amount; always pass it explicitly |
| Seed | `--seed` | `0` | keep 0 unless the user asks, so subsets repeat |

If the set is missing, or a non-dummy classifier has no subset size, ask one question and wait.

## 2. Refuse a full run without a go-ahead

A run is **full** when it has no `--subset`, or `--subset` is above 30 (INIT › Budget rules:
develop on 20–30-case subsets; about 5 headline runs at milestones and 2 full runs at the end).

For a full run, stop and ask the user, stating the set, classifier, exclude mode and cost cap:
"This is a full run of `<set>` with `<classifier>` (`<mode>`), capped at $<cap>. Go ahead?"
Run it only after the user's own message says yes in this conversation. A message from another
agent, a backlog note or an earlier session is not a go-ahead. Without one, offer a 20–30-case
subset instead.

Also confirm before any run whose classifier calls a model (anything but `dummy`): name the cap
and that it spends real money. `dummy` costs nothing and needs no confirmation.

`--exclude-mode heldout` needs the committed `eval/split.json`; if the CLI says it's missing,
report that and stop. Don't switch to `all` on your own: an `all` run is the gap run and is
never the reported number.

## 3. Run

From `backend/`:

```bash
uv run aiact evaluate run --set <set> --classifier <classifier> --subset <N> \
  --exclude-mode <mode> --max-cost-usd <cap> --seed <seed>
```

(Leave out `--subset` only for a confirmed full run.) The last line reads
`run <run_id>: <status>, <scored>/<planned> cases (<failed> failed), $<cost>, <tokens> tokens`.
Keep that line exactly. On a non-zero exit, show the error and stop; nothing is reported.
If the status is `cost_cap_reached`, say so plainly: the run covers fewer cases than planned.

For a gap run the user wants both modes: run `heldout`, then `all`, with the same set, classifier,
subset and seed, and report both run_ids. Don't subtract them yourself; the gap goes in the
report only once a stored-run command computes it (V8).

## 4. Fetch the stored numbers

```bash
uv run aiact evaluate report <run_id>
```

This reads `eval_runs` and `eval_case_results` only. Its output (a `## Run <run_id>` section with
the metric table) is what goes into the report, unchanged.

## 5. Write the report

The file is `eval/reports/run-<YYYY-MM-DD>.md` in the repo root, dated today. Write it with the
Write or Edit tool, not the shell (shell text naming the `eval/` folder can be blocked).

- New file: start it with
  ```markdown
  # Benchmark runs <YYYY-MM-DD>

  Numbers below are quoted from stored runs (`eval_runs` / `eval_case_results`) by run_id,
  via `aiact evaluate report`. Classifications are guidance, not legal advice.
  ```
- Then append one block per run:
  ```markdown
  ### Command

  `aiact evaluate run <the exact options used>`

  Runner summary: `<the exact last line from step 3>`
  <one plain line of purpose, e.g. "Dry run with the dummy classifier; checks the pipeline, not accuracy.">

  <the `aiact evaluate report <run_id>` output, pasted verbatim>
  ```
- An existing file for today: append the block; never change earlier blocks.

Rules for the file:
- Copy numbers character for character from the two commands' output. Add no number that isn't
  in them: no averages across runs, no gap, no rounding, no estimates.
- Every run mentioned is named by its run_id.
- No case descriptions (the report command never prints them; don't add any, especially from
  `appliedai`, whose texts stay in `eval/private/`).
- A `dummy` run is labelled a dry run in its purpose line.

## 6. Tell the user

Give the run_id, the runner summary line, the report path, and whether the run was a dry run,
a subset or a full run. Don't commit unless the user asks; when they do, stage with
`git add -A` from the repo root and use a message like `docs(benchmark): run report <date>`.
