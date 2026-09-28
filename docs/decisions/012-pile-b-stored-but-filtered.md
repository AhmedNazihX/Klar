# 012 · Pile B is stored in the corpus but filtered out by default

- **Date:** 2026-09-28
- **Story:** C2 (docs/BACKLOG.md); also changes C6, B13 and V8
- **Status:** accepted (the user chose option (a) on 2026-09-28)

## Question
INIT > Evaluation > Benchmark isolation asks for two things that pull against each other. Rule 1 says Pile B
"is removed from the corpus", so the engine can't find the example a test case was written from. Rule 4 asks
for a gap run: the headline benchmark run a second time "with all examples retrievable", to show how much the
engine leans on memorised examples. If Pile B is never loaded, the gap run has nothing to switch on. Decision
011 fixed the split at 153 Pile B examples of 307, and leave-one-out (rule 2) only applies below about 40.

## Options
| Option | What was measured | Result | Source |
| --- | --- | --- | --- |
| (a) Store Pile B chunks tagged with `source_example_id`; every search excludes them by default; only the gap run turns the filter off | Whether both INIT numbers can be produced | Headline and gap numbers both possible; leak protection rests on the default filter, which B13 checks | INIT > Benchmark isolation 1, 4, 5 |
| (b) Never load Pile B | Whether both INIT numbers can be produced | Headline number only; no gap run in split mode with 307 examples | decisions 001, 011 |

No run numbers are involved: this is a design choice made before C2 exists.

## Decision
Option (a): Pile B guideline chunks are stored in the corpus, tagged with their `source_example_id`, and are not
retrievable by default. The user chose it to keep the gap measurement (INIT rule 4), accepting that isolation now
depends on a default filter that CI checks.

## Consequences
- **INIT wording:** read rule 1 as "Pile B is stored but not retrievable by default" rather than "removed".
- **C2:** keeps Pile B chunks, tagged with `source_example_id`, instead of dropping them in split mode. It still
  reads only the `pile_b` ID list from `eval/split.json`. Its DoD test becomes: every Pile B ID is present and
  tagged, and no Pile B text is untagged.
- **C3:** loads the tagged rows; `provisions.source_example_id` carries the tag.
- **C6:** `search_ai_act` excludes the Pile B IDs by default. Turning the exclusion off is an explicit opt-in
  used only by the gap run, never by the engine, the API, the MCP server or the Q&A path.
- **B13:** the isolation test checks behaviour, not absence: (1) every search entry point applies the Pile B
  exclusion by default, (2) a default search never returns a Pile B row, including a query copied from a
  Pile B example, (3) every Pile B ID from `split.json` is tagged in `provisions`, and (4) the near-duplicate
  check on benchmark descriptions, against the retrievable corpus.
- **V1 / V8:** `--exclude-mode heldout` (the reported number) keeps the Pile B exclusion; `--exclude-mode all`
  (the gap run) turns it off. Both numbers go in the README.
- **isolation-auditor:** "Pile B never reaches the corpus" becomes "Pile B is never retrievable by default".
- **Revisit** if B13 finds a search path that can skip the filter and it can't be closed, or if the gap run is
  dropped from the README; then option (b) is the safer choice.
