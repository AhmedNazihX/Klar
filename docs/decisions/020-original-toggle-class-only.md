# 020 · The original-text toggle covers the class, not the obligations

- **Date:** 2026-09-30
- **Story:** E11 (docs/BACKLOG.md); also affects P10, W2
- **Status:** accepted (the user chose option (b) on 2026-09-30)

## Question
INIT › Scope (MVP): "classify under the original Act or under the Act as amended by the Omnibus". Below the UI only
the amended text works: `list_obligations` raises `UnknownLawVersionError` for any other version
(`backend/aiact/obligations/list.py`), and no node is tested under `law_version="original"`.

## Options
| Option | Effect | Source |
| --- | --- | --- |
| (a) Class and obligations | A second, original-version obligations table with its own dates, reviewed by the user, plus node branching | backlog review finding A4 |
| (b) Class only | Nodes branch on `law_version` and are tested under both; obligations under `original` return an explicit "not modelled" result | same |

## Decision
Option (b). The toggle exists to show how the July 2026 changes alter outcomes; the class and route show that,
and a second dated obligations table is a lot of legal review for a comparison view.

## Consequences
- New story E11 (Deps E10, C7); P10 depends on it.
- W2's README and an INIT note state the limitation.

## Addendum (2026-10-01, decision 026 item 11)
The user chose (A) for the final UI design: under the original text the screens swap only the Art. 113 route
dates, 2 August 2026 for Annex III and 2 August 2027 for Annex I, on Result, Inventory, Obligations, the ambiguous
result and the timeline. The duty list stays the amended list, with the notice "Dates follow the original Art. 113.
The duties shown are the amended text's." Class and route still come from E11's original-version run. The
obligations table stays amended-only, and the "not modelled" result from E11 still holds for the duties
themselves. P10 owns the swap and the notice.
