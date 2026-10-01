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

## Addendum, 2026-10-01: two readings (user decisions during C7b review)

Wording and dates approved by the user on 2026-10-01, with three edits: the English public-authority question
("Is the system meant for use by public authorities?"), "Das System bleibt als Hochrisiko-System eingestuft." in
both German decision sentences, and "prüfen Sie dies beim Inverkehrbringen oder bei der Inbetriebnahme erneut." in
the German check-again sentence.

The text both rest on (`data/parsed/ai-act-consolidated.en.jsonl`):
- `art:111:2`: "this Regulation shall apply to operators of high-risk AI systems, other than the systems referred
  to in paragraph 1 of this Article, that have been placed on the market or put into service before the date of
  application of Chapter III referred to in Article 113, only if, as from that date, those systems are subject to
  significant changes in their designs. In any case, the providers and deployers of high-risk AI systems intended
  to be used by public authorities shall take the necessary steps to comply with the requirements and obligations
  laid down in this Regulation by 2 August 2030."
- `art:111:4`: "Providers of AI systems, including general-purpose AI systems, generating synthetic audio, image,
  video or text content, that have been placed on the market before 2 August 2026 shall take the necessary steps
  in order to comply with Article 50(2) by 2 December 2026."

| Question | Options | Choice |
| --- | --- | --- |
| What counts as "placed on the market or put into service before" the route's Chapter III date (2 Dec 2027 Annex III, 2 Aug 2028 Annex I), while that date is still ahead | (A) already on the market or in use, or launched before the date; (B) as of today: only a system already on the market or in use on the assessment date | **B** |
| Which duties the legacy marking covers | (A) only the route-dated high-risk (Chapter III) rows; Art. 4, Art. 50 and the Art. 53 flag keep their own dates (Art. 111(4) treats legacy Art. 50(2) separately, so Art. 111(2) isn't read as covering Art. 50); (B) every duty of the system ("this Regulation shall apply … only if") | **A** |

Consequences:
- A planned launch, even one planned before the date, is "no": the full duties are listed, and the step adds,
  citing `art:111:2`: "If the system is placed on the market or put into service before {date} and its design
  doesn't change significantly afterwards, Art. 111(2) may limit these duties; check again at launch." (German:
  "Wird das System vor dem {date} in Verkehr gebracht oder in Betrieb genommen und danach in seiner Konzeption nicht
  erheblich verändert, kann Art. 111 Abs. 2 diese Pflichten einschränken; prüfen Sie dies beim Inverkehrbringen
  oder bei der Inbetriebnahme erneut.") The engine model can't tell a planned launch from a new system, so the sentence is added whenever the
  answer is "no" for a high-risk system.
- A silent description gives "unknown" for each fact: the duties stay unmarked (an unknown public-authority answer
  takes the 2 Aug 2030 date) and the facts are asked as follow-up questions.
