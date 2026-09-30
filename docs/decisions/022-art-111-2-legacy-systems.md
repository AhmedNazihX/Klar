# 022 · Art. 111(2) legacy high-risk systems are modelled

- **Date:** 2026-09-30
- **Story:** C7b (docs/BACKLOG.md); also affects E10, P6
- **Status:** accepted (the user chose option (a) on 2026-09-30)

## Question
Art. 111(2): high-risk systems placed on the market or put into service before the Chapter III date (2 Dec 2027
Annex III, 2 Aug 2028 Annex I) are covered "only if, as from that date, those systems are subject to significant
changes in their designs"; public-authority systems comply by 2 Aug 2030 either way
(`data/parsed/ai-act-consolidated.en.jsonl`, `art:111:2`). No story owned it (E8 note from B5e). The inventory is
aimed at existing tools, the systems this rule covers.

## Options
| Option | Effect | Source |
| --- | --- | --- |
| (a) Model it | A key-fact question on launch date and design changes; legacy obligations marked "applies only after a significant design change", public authorities dated 2 Aug 2030 | backlog review finding A6 |
| (b) Limitation only | A README line and a note on every high-risk result | same |

## Decision
Option (a): a small, self-contained change that stops the inventory giving companies duties that may not yet apply.

## Consequences
- New story C7b (Deps C7, E7; before E10).
- The class stays high-risk; only the obligations' applicability changes.
