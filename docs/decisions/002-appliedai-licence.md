# 002 · appliedAI data: CC BY 4.0, committed with credit, German text

- **Date:** 2026-10-14
- **Story:** B11 (docs/BACKLOG.md); feeds V9
- **Status:** accepted 2026-10-14: licence option A, German only, and the Annex I tag `annex_i` (all three the
  user's choices)

## Question
INIT › Open questions asked us to "open the PDF and confirm the fields per entry, the languages, and any
licence statement". INIT › Risks assumed no named licence, and so allowed only case IDs and results to be
published. Two choices followed from what was found: whether the data may be committed, and which of its two
languages the benchmark uses.

## What was found
| Fact | Finding | Source |
| --- | --- | --- |
| The PDF | A 17-slide deck (24 Sep 2024) with fields, statistics and limitations; it holds **no cases** | `eval/appliedai/source/appliedai-risk-classification-database-2024-09.pdf` |
| The cases | 106 systems (IDs 1–119, with gaps): appliedAI's own Use Case Database, batch #1 of the website's 641 | Notion page `2b58830bb7f54c9d8c869d37bdb27709`, collection `16c16466-adad-4cb4-9e94-ca9ea6bcbce3`; deck slide 4 |
| Fields per entry | Title (EN), Details EN and DE, AI high-risk or low-risk, AI prohibited, Annex II or III, Item and Subitem in Annex III, Enterprise Function EN and DE, Comment, Sources, Files & media | `eval/appliedai/source/appliedai-use-case-database.json` |
| Labels | low-risk 44, It is unclear 42, high-risk 19, prohibited 1 (matches the 2023 study's 42 / 40 / 18 %) | the JSON; `load_jsonl` on `eval/appliedai/appliedai.jsonl` |
| Annex | Annex III 50, Annex II (today's Annex I) 12, none 44; all 12 Annex II cases are labelled unclear | the JSON |
| Languages | German and English details for every system. The German is the original; the English is machine translated (deck slide 5: Google Translate), with artifacts such as "applicants: inside" for "Bewerber:innen" | the JSON; deck slides 5 and 14 |
| Licence | **CC BY 4.0**, credit "appliedAI Institute for Europe gGmbH" | deck slide 16; the Notion page ("Licence: CC BY 4.0") |

## Options
| Choice | Option | Result |
| --- | --- | --- |
| Licence | A. Commit the sources and the extraction with credit; drop the "publish only case IDs" rule | **chosen** |
| | B. Keep them gitignored in `eval/private/` | not chosen: a clone or a worktree couldn't rerun V9 |
| Language | A. German only (106 cases) | **chosen** |
| | B. English only (106) | not chosen: translation noise would count against the engine |
| | C. Both (212) | not chosen: about twice the V9 cost and twice the disagreements to judge |

## Decision
The user chose licence option A and language option A (2026-10-14). CC BY 4.0 is the confirmation of reuse
that INIT › Risks made the condition for publishing descriptions.

## Consequences
- The deck, the table (JSON and CSV), `SOURCE.md` (credit, hashes, how the extraction was made) and
  `appliedai.jsonl` are tracked in `eval/appliedai/`; `APPLIEDAI_FILE` points there (commit `dfbfb2b`).
- `.claude/rules/eval.md`, the eval skill, the INIT (test-set table, risk row, open question), LAYOUT and V9's DoD
  now ask for the credit in place of the n-gram check. `eval/private/` stays gitignored for local-only files.
- `tests/test_isolation.py` now always checks the appliedAI texts against the corpus (before, only when the
  private file happened to be present).
- V9 runs the 106 German cases; the English stays in the source JSON if a language comparison is wanted later.
- V9's review uses a fourth verdict, `label error` (user, 2026-10-14): the experts' 2023 label didn't fit even
  the 2021 text, and the engine's answer is right today. It deviates from INIT › Disagreement review's three, so the
  report can tell legal change (`outdated label`) from expert error; both leave the "after" accuracy, counted apart.
- Revisit if appliedAI changes the licence or the table. Re-extract from a new snapshot then, keeping the old one
  for the runs already stored.
