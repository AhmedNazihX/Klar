# 025 · Rewrite similarity: fail at an 8-word shared run, report the cosine only

- **Date:** 2026-10-01
- **Story:** B4a (docs/BACKLOG.md); applies to B4 and any case with a `source_example_id`
- **Status:** accepted (the user, 2026-10-01, the recommended option, "for now": to revisit later)

## Question
B4a's DoD asks for "an agreed threshold" for `aiact evaluate similarity`, which compares each rewritten case with
the Commission example it came from (INIT › Benchmark isolation). If a rewrite copies long stretches of the
Commission's wording, the held-out Pile B cases stop being a fair test. The question was where the command fails
a case, and whether the embedding cosine should fail cases too.

## Options
| Option | What was compared or measured | Result | Source |
| --- | --- | --- | --- |
| **A. Fail at a shared run of 8+ words; cosine reported only** (chosen) | The rule the case-writing skill already uses for rewrites | Same number as the skill, so the tool and the skill agree | `.claude/skills/case/SKILL.md` §3 ("rewrite any case at 8 words or more"); `RUN_LIMIT = 8` in `backend/aiact/eval/similarity.py` |
| B. A shorter run (5–6 words) | Ordinary legal phrases a faithful rewrite has to use | "placed on the market or put into service" alone is 7 words, so a limit of 5–6 would fail honest rewrites | the Act's wording; decision 015 uses 5 words, but for engine prompts, which must not paraphrase any Pile B feature at all |
| C. A longer run (10–12 words) | — | Lets half-sentences through | — |
| D. Also fail on cosine by default | How close a faithful restatement scores | A Pile B text scores a median 0.918 against its own stored row; topical prose on the same Annex III point reaches 0.894. A fixed cosine limit would fail good rewrites, or be a guess | `backend/aiact/eval/isolation.py` (`EMBEDDING_COSINE_LIMIT` docstring; Qwen3/1536, measured 2026-09-30) |

## Decision
A sourced case fails when it shares a run of **8 or more words** (lower-cased, letters only) with its example's
`text` or `lead_in`. The embedding cosine is **reported, not used to fail a case**. `--max-cosine <x>` turns it
into a limit for one run, and under a limit a case with no vector fails, with the missing side named.

## Consequences
- **B4** runs `uv run aiact evaluate similarity` (from `backend/`) on its rewrites; every case must pass. The
  cosine is for the reviewer to spot outliers. B4 may set `--max-cosine` if its rewrites show a useful cut-off,
  and records the value and why.
- **Who sees the numbers:** only whoever runs the command (the user, the B4 worker, the reviewers). The command
  prints and stores nothing; neither the app nor the `/eval` reports show it. The README (W2) may describe the
  rule in prose ("every rewrite shares fewer than 8 consecutive words with its source").
- **Changing it** means editing `RUN_LIMIT` and its two boundary tests
  (`test_the_default_limit_fails_an_eight_word_run_and_passes_a_seven_word_run`,
  `test_the_command_defaults_to_the_eight_word_limit`), plus the `/case` skill's §3, so the two stay in step.
- **Revisit** when B4's rewrites exist: if reviewers find close paraphrases that pass at 8 words, or honest
  rewrites that fail, or if the cosines of real rewrites separate cleanly enough to justify a default limit.
