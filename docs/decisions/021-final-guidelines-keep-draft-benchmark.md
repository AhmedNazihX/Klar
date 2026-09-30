# 021 · If the high-risk guidelines are finalised, the draft benchmark stays frozen

- **Date:** 2026-09-30
- **Story:** W0 (docs/BACKLOG.md); also affects W1, C2, C3
- **Status:** accepted (the user chose option (a) on 2026-09-30)

## Question
INIT › Legal corpus: the high-risk guidelines are a draft, adoption "expected by end of 2026"; check "before the
build freezes". W0 planned to re-run B2–B4, but decision 011 says a renumbering means a new extraction and split
(which can't come before an engine that already exists), and decision 009 says a reload replaces the draft (which
would drop the Pile B tags).

## Options
| Option | Effect | Source |
| --- | --- | --- |
| (a) Keep the draft benchmark frozen | Ingest the final prose; map each final example to its draft id and tag Pile B before the reload; the benchmark stays "draft examples, 2026-05-19" | backlog review finding A5 |
| (b) New benchmark version | Re-extract and re-split the final examples; report them separately without the split-before-engine claim | same |

## Decision
Option (a): it keeps the headline number clean and adds no benchmark work late in the project.

## Consequences
- W0 runs now and again right before W1; W1 depends on W0.
- A reload of final guidelines is a new story that maps final examples to draft ids and tags Pile B first.
- The README states the date the guidelines were finalised, if they are.
