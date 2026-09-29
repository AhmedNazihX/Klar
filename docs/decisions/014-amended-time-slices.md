# 014 · Time slices of the amended AI Act

- **Date:** 2026-09-29
- **Story:** C3 (docs/BACKLOG.md)
- **Status:** proposed (awaiting the user's review)

## Question
Decision 009 says the consolidated (amended) document carries the full history, with slices split at
the Omnibus dates that C1 parses. Which provisions get split, at which dates, what text does a slice
before the Omnibus hold, and do the deferred application dates inside the Omnibus (`amendment.dates`,
for example 2 December 2026 for the new Art. 5(1)(ba) and (bb)) become slice boundaries for `as_of`
lookups?

## Options
| Option | What was measured | Result | Source |
| --- | --- | --- | --- |
| Split every provision whose text differs between the original and the consolidation | Units that differ although no Omnibus amendment targets them, an ancestor, a descendant or an adjacent sibling | Rejected: these are corrigenda, which apply from the start. 11 EN units: Art. 108 and its paragraphs 2–4 (a formatting difference), and 7 heading-only differences in Art. 1(1) and 1(2)(a)–(f) (see below). 1 DE unit: Art. 3(40), "sofern es sich **nicht** um …" | `data/parsed/ai-act*.jsonl` |
| Count only targets, ancestors and descendants as touched | Units next to an inserted or deleted point | Rejected: the neighbours' punctuation changes with the Omnibus (Annex I Section B point 20 "concerned." → "concerned;" because point 21 is inserted; Annex VIII Section B point 8 "recalled);" → "recalled)." in EN and "zurückgerufen)" → "zurückgerufen)." in DE because points 7 and 9 are deleted) and would be backdated to 2024-08-01 | same |
| **Also count the siblings right before and after a target as touched** (in the original and in the consolidated order) | Same | Chosen: those points split normally, with the original punctuation before 2026-07-27. A whole-list sibling rule was rejected: it would turn DE Art. 3(40) into an amendment, because the Omnibus inserts other points of Art. 3 | same, local DB |
| Take the old slice from the original text as printed | DE Art. 3(40) `as_of` 2025-01-01 | Rejected: returns the uncorrected text, which says the opposite | same |
| Old slice = the **corrected original**: the original with each corrigendum's consolidated text put in, in the unit itself and in the text of every ancestor that quotes it | Same lookup | Chosen: DE Art. 3 and Art. 3(40) before 2026-07-27 both carry "nicht". EN 14 / DE 2 units get corrected text (the corrigenda plus the amended ancestors that quote them or share the corrected title: EN Art. 1, 1(2), 1(2)(g); DE Art. 3) | `aiact/corpus/build.py`, local DB |
| Split a provision when its corrected original still differs from the consolidation | Same | Chosen: every remaining difference is explained by the 88 Omnibus targets | same |
| Split only the changed provision, not its unchanged children | Parent of an unchanged child | Rejected: the child's parent row would be the old slice after 2026-07-27 | `aiact/corpus/build.py` |
| Split the descendants of a split provision too | Same | Chosen: every slice's parent covers the same dates; 487 provisions have two slices per language | `docs/corpus_stats.md` |
| Also split at the deferred application dates in `amendment.dates` | The dates C1 finds: 12 distinct, from 2024-08-01 to 2030-08-02, mixing application dates, grace periods and deadlines | Rejected: the text is law from the Omnibus's entry into force; the dates only say when a rule applies, which the text states itself | `omnibus.*.jsonl` |

## Decision
- The amended document's slices split only at the Omnibus's entry into force, **2026-07-27**
  (`amendment.in_force_from`, the same for every instruction; the loader fails if it isn't).
- **Corrigenda apply from the start.** A unit that differs from the consolidation although the
  Omnibus touches neither it, an ancestor, a descendant nor an **adjacent sibling** (the point
  right before or after a target, in either text: inserting or deleting a point changes its
  neighbours' closing punctuation or moves a trailing "and"/"or") is a corrigendum: its corrected original
  is the consolidated unit, and each ancestor's corrected original quotes the corrected text in place
  of the old one (the loader fails if an ancestor doesn't quote the old text exactly once). A title
  that changed while the Omnibus doesn't target the article (or annex) itself is a corrigendum for
  every unit of it, since they share the heading.
- A provision is split when its corrected original differs from the consolidation; its descendants
  are split with it, both slices from their own corrected original and consolidated text. A deleted
  provision keeps only `[2024-08-01, 2026-07-27)`, an inserted one only `[2026-07-27, ∞)`. Every
  other provision has one slice from 2024-08-01 with the consolidated text.
- Deferred application dates are **not** slice boundaries. `as_of` on or after 2026-07-27 returns
  the new Art. 5(1)(ba); whether it already applies on that date is for the engine to read from the
  text (INIT › Legal corpus, "Omnibus details the engine must handle"). The AI Act's own staggered
  application dates (Art. 113) aren't slices either.
- Recitals are not in the consolidation and stay only in the original document.

The EN Art. 1 heading difference is in the source, not the parse: the Official Journal HTML reads
"Subject matter\`" (a stray backtick) and the consolidation "Subject matter'" (checked in
`data/raw/*.html`). It is handled as a title corrigendum.

## Consequences
- C5 and C6: `as_of` lookups against the amended document see the Omnibus text from 2026-07-27 and
  the corrected text before it. The `law_version = 'original'` document stays as printed in the
  Official Journal (corrigenda not applied), for the original-vs-amended toggle. A recital lookup has
  to use the original document, since the amended document has no recitals.
- C4: split children have two rows with the same text; embed or dedupe by `content_sha256` to avoid
  paying twice.
- If a later amendment arrives, its entry-into-force date becomes one more boundary with the same rule.
