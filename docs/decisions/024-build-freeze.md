# 024 · The build freezes when W1 starts

- **Date:** 2026-09-30
- **Story:** W1 (docs/BACKLOG.md); also affects W0, C7b, E11, P8, P10, P11, S2
- **Status:** accepted (the user agreed, with S2 outside the freeze, on 2026-09-30)

## Question
INIT says to check "before the build freezes", but no story defined the freeze, and stories that change engine
output (P11, P10/E11, C7b, P8, W0) weren't dependencies of W1's final runs.

## Options
| Option | Effect |
| --- | --- |
| (a) S2 outside the freeze | Sonnet 5 on 25 cases runs after V8 and adds a table if time allows |
| (b) S2 a dependency of W1 | The final report always has the premium comparison |

## Decision
W1 depends on W0, C7b, E11, P8, P10 and P11; the freeze is "W1 starts; after that only the report and the deck
change", and a later fix means a logged re-run. S2 stays outside the freeze (option (a)): it is stretch work with
its own budget, and X2 already covers INIT's Luna mitigation.

## Consequences
- W1's Deps grow as above.
