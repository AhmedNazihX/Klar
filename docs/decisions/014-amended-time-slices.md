# 014 · Time slices of the amended AI Act

- **Date:** 2026-09-29
- **Story:** C3 (docs/BACKLOG.md)
- **Status:** proposed (awaiting the user's review)

## Question
Decision 009 says the consolidated (amended) document carries the full history, with slices split at
the Omnibus dates that C1 parses. Which provisions get split, at which dates, and do the deferred
application dates inside the Omnibus (`amendment.dates`, for example 2 December 2026 for the new
Art. 5(1)(ba) and (bb)) become slice boundaries for `as_of` lookups?

## Options
| Option | What was measured | Result | Source |
| --- | --- | --- | --- |
| Split every provision whose text differs between the original and the consolidation | Differences per language (C1 parse) | Rejected: 6 EN / 2 DE differences that no Omnibus amendment targets are corrigenda (e.g. DE Art. 3(40), "sofern es sich **nicht** um …"), which apply from the start | `data/parsed/ai-act*.jsonl` |
| Split a provision only when it differs **and** the Omnibus targets it, an ancestor or a descendant | Same | Chosen: 97 EN / 93 DE differing provisions, all but the corrigenda explained by the 88 targets | same |
| Split only the changed provision, not its unchanged children | Parent of an unchanged child | Rejected: the child's parent row would be the old slice after 2026-07-27 | `aiact/corpus/build.py` |
| Split the descendants of a split provision too | Same | Chosen: every slice's parent covers the same dates; 487 provisions have two slices per language | `docs/corpus_stats.md` |
| Also split at the deferred application dates in `amendment.dates` | The dates C1 finds: 12 distinct, from 2024-08-01 to 2030-08-02, mixing application dates, grace periods and deadlines | Rejected: the text is law from the Omnibus's entry into force; the dates only say when a rule applies, which the text states itself | `omnibus.*.jsonl` |

## Decision
- The amended document's slices split only at the Omnibus's entry into force, **2026-07-27**
  (`amendment.in_force_from`, the same for every instruction; the loader fails if it isn't).
- A provision is split when it differs from the original and the Omnibus touches it (it, an
  ancestor or a descendant is a target). Its descendants are split with it. A deleted provision
  keeps only `[2024-08-01, 2026-07-27)`, an inserted one only `[2026-07-27, ∞)`. Any other
  difference is a corrigendum and gets one slice from 2024-08-01 with the consolidated text.
- Deferred application dates are **not** slice boundaries. `as_of` on or after 2026-07-27 returns
  the new Art. 5(1)(ba); whether it already applies on that date is for the engine to read from the
  text (INIT › Legal corpus, "Omnibus details the engine must handle"). The AI Act's own staggered
  application dates (Art. 113) aren't slices either.
- Recitals are not in the consolidation and stay only in the original document.

## Consequences
- C5 and C6: `as_of` lookups against the amended document see the Omnibus text from 2026-07-27. A
  recital lookup has to use the original document (`law_version = 'original'`), since the amended
  document has no recitals.
- C4: split children have two rows with the same text; embed or dedupe by `content_sha256` to avoid
  paying twice.
- If a later amendment arrives, its entry-into-force date becomes one more boundary with the same rule.
