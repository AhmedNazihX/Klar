# 017 · Own-case labels freeze per category, before the node that uses them

- **Date:** 2026-09-30
- **Story:** B10 (docs/BACKLOG.md); also affects B10a, B10b, E4, E5, E6, W2
- **Status:** accepted (the user chose option (a) on 2026-09-30)

## Question
INIT › Evaluation › Label rules says "Frozen before the build. All labels are fixed before the engine exists."
The engine already exists (E1, E2, E3, E7 merged) while B4, B5a, B5c, B6, B7, B8 and X0 are unwritten, and
own-b-09 was relabelled during E3 (logged in `eval/LABEL_CHANGES.md`, 2026-09-30). The only CI-enforced gate is
B3 → E1; the freeze check itself arrives with B10. The backlog review (2026-09-30) asked how to handle this.

## Options
| Option | Effect | Source |
| --- | --- | --- |
| (a) Freeze each own category before its engine node starts | A CI freeze check lands now (B10a); an approved category is locked before the node that replays it; the global tag `labels-v1` comes later (B10b) | backlog review 2026-09-30, finding A1 |
| (b) One global freeze at B10 | Labels stay editable until every case exists; only discipline guards them meanwhile | same |

## Decision
Option (a). The INIT rule can no longer hold literally, so the closest honest version is: no category's labels
change, unlogged, after the node that uses it has started.

## Consequences
- B10 splits into **B10a** (the freeze check in CI, now) and **B10b** (tag `labels-v1`, after B9, B6, B7, B8, X0).
- B10a is a dependency of E4 and E6. E5 is already running: B10a must be merged before E5 merges, and own/e
  must not change meanwhile.
- Every relabel after a category is approved goes in `eval/LABEL_CHANGES.md` (as today); CI enforces it from B10a.
- W2 states the deviation as a limitation: labels were frozen per category before its node, not before the engine.
