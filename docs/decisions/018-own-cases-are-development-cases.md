# 018 · Own cases are reported as development cases

- **Date:** 2026-09-30
- **Story:** V8 (docs/BACKLOG.md); also affects W1, W2
- **Status:** accepted (the user chose option (b) on 2026-09-30)

## Question
INIT › Test sets names the own cases a headline benchmark, but the E3–E7 DoDs replay each node against its own
category (BACKLOG E3–E7), so own-case accuracy partly measures the development set.

## Options
| Option | Effect | Source |
| --- | --- | --- |
| (a) Hold out part of each category | A scored slice the nodes never replay; the slices are a handful of cases each (13–14 per category today), and E3/E7 are already tuned on all of them | `eval/cases/own/{b,d,e}/`; backlog review finding A2 |
| (b) Keep all cases, label the number | Own-case accuracy is reported as "cases the engine was developed against"; Commission Pile B and the academic set carry the headline | same |

## Decision
Option (b): the slices would be too small to mean much, and Pile B stays the clean headline figure.

## Consequences
- V8 and W1 label own-case accuracy "development cases"; W2's README says why.
- Revisit if a later story adds enough new own cases to hold some out.
