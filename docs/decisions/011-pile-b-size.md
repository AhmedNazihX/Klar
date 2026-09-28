# 011 · Pile B size and split seed

- **Date:** 2026-09-28
- **Story:** B3 (docs/BACKLOG.md)
- **Status:** accepted (the user chose a half split on 2026-09-28, relayed by the orchestrator)

## Question
Decision 001 settled on a split (307 examples, mode `split`) but left open how large Pile B is. Pile B is removed
from the corpus and every Pile B example is rewritten by B4 with a user-approved label, so the fraction trades
benchmark size against the retrievable guidance left in Pile A and against B4's authoring and approval load
(INIT > Evaluation > Benchmark isolation 1).

## Options
| Option | What was measured | Result | Source |
| --- | --- | --- | --- |
| Half split (fraction 0.5) | Pile sizes on the 307 examples | Pile A 154, Pile B 153; every one of the 18 area × verdict strata in both piles | `eval/split.json`; `aiact eval split` |
| Smaller Pile B | Not run | Lighter B4 load, smaller benchmark, more retrievable examples | Decision 001 > Consequences |

## Decision
**Half split, seed 20260928.** Each area × verdict stratum is shuffled with the seed and split in half. The three
odd strata (III.3 not_high 19, III.6 high 15, III.8 high 7) each have half an example to spare; one of them, chosen
in seeded order, gives its spare to Pile B, so Pile B holds floor(307 / 2) = 153 examples (largest-remainder
allocation). The fraction, the seed and the stratification keys are recorded in `eval/split.json`.

Per stratum (total / Pile A / Pile B):

| Area | high | not_high |
| --- | --- | --- |
| annex_i | 8 / 4 / 4 | 4 / 2 / 2 |
| annex_iii_1 | 14 / 7 / 7 | 26 / 13 / 13 |
| annex_iii_2 | 10 / 5 / 5 | 16 / 8 / 8 |
| annex_iii_3 | 12 / 6 / 6 | 19 / 10 / 9 |
| annex_iii_4 | 14 / 7 / 7 | 18 / 9 / 9 |
| annex_iii_5 | 22 / 11 / 11 | 26 / 13 / 13 |
| annex_iii_6 | 15 / 7 / 8 | 32 / 16 / 16 |
| annex_iii_7 | 20 / 10 / 10 | 24 / 12 / 12 |
| annex_iii_8 | 7 / 4 / 3 | 20 / 10 / 10 |

## Consequences
- `eval/split.json` is committed in a commit of its own, before any file under `backend/aiact/engine/` exists.
  From then on the IDs are frozen: `aiact eval split` refuses to write a different assignment, and a test checks
  that the committed file covers exactly the IDs in `examples.jsonl` with every area in both piles. A later
  verdict correction in `examples.jsonl` changes the strata but never moves an example between piles.
- B4 rewrites the 153 Pile B examples. C2 drops the same 153 IDs from the guideline chunks.
- Revisit only if the Commission adopts final high-risk guidelines that renumber the examples (see 001); that
  would mean a new extraction and a new split, not an edit of this one.
