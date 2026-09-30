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
