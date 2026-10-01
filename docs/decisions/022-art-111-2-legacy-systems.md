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
| ~~Whether a significant design change made before the date counts~~ | (A) only changes "as from that date", as Art. 111(2) says; (B) a significant design change before the date also counts as changed (stricter than the text; full duties stay) | ~~**B** (seen and approved in the wording review, 2026-10-01)~~ **Replaced** by the first row of the table below |

### Revision, 2026-10-01: after reviewing recital 177 and Art. 3(23)

Sources: `recital:177` (`data/parsed/ai-act.en.jsonl`; the consolidated text carries no recitals): "…only if,
from that date, those systems are subject to significant changes in their design or intended purpose. … the
concept of significant change should be understood as equivalent in substance to the notion of substantial
modification … operators of high-risk AI systems that are intended to be used by public authorities should …
comply … by 2 August 2030." `art:3:23`: "'substantial modification' means a change to an AI system after its
placing on the market or putting into service which is not foreseen or planned in the initial conformity
assessment carried out by the provider and as a result of which the compliance of the AI system with the
requirements set out in Chapter III, Section 2 is affected or results in a modification to the intended purpose
for which the AI system has been assessed;"

| Question | Choice | Source | Decided |
| --- | --- | --- | --- |
| Which design changes count (replaces "before the date also counts") | Only a significant change to the design or intended purpose planned or foreseen for on or after the route's date; a change made before it doesn't end the grandfathering. Unknown stays strict: full duties, and the question is asked | `art:111:2` ("as from that date"), `recital:177` | user, 2026-10-01, after reviewing recital 177 and Art. 3(23) |
| ~~Who gets the 2 Aug 2030 date for a legacy public-authority system~~ | ~~Every operator: providers, deployers, importers and distributors (recital 177 says "operators", wider than the article's "providers and deployers"; the stricter reading)~~ | `recital:177`, `art:111:2` | ~~user, 2026-10-01, after reviewing recital 177 and Art. 3(23)~~ **Replaced** by the next row |
| Who gets the 2 Aug 2030 date for a legacy public-authority system (replaces "all operators") | Providers and deployers only; an importer or distributor of such a system gets the ordinary `legacy_unchanged` marking. The article ("providers and deployers") and the German recital 177 ("Betreiber", the deployer of Art. 3 Nr. 4) agree; the English recital's "operators" is an outlier, and recitals don't bind, so this isn't an ambiguity | `art:111:2`, `recital:177` (EN and DE) | user chose the article, 2026-10-01 |
| What "significant" means | A substantial modification: a change not foreseen or planned in the initial conformity assessment that affects compliance with the Chapter III Section 2 requirements, or that changes the intended purpose; routine updates, bug fixes and changes the provider's plan foresaw are not | `art:3:23`, `recital:177` ("equivalent in substance") | user, 2026-10-01, after reviewing recital 177 and Art. 3(23) |
| Per-product caveat | For providers, importers and distributors (not deployers), every marked result adds: "This covers copies placed on the market or put into service before {date}; copies supplied on or after that date may be fully covered." (German: "Dies gilt für Exemplare, die vor dem {date} in Verkehr gebracht oder in Betrieb genommen wurden; ab diesem Datum bereitgestellte Exemplare können vollständig erfasst sein.") Wording revised by the user on 2026-10-01 | The New Legislative Framework reading that placing on the market is per individual product (the Commission's Blue Guide, named in the Act's recitals but not in our corpus, so not quoted) | user, 2026-10-01, after reviewing recital 177 and Art. 3(23) |

A marked result cites `art:111:2` and `art:3:23`; `recital:177` isn't cited because the consolidated (amended)
text, the only one the obligations table holds, has no recitals. The check-again sentence cites `art:111:2` only.

Consequences:
- A planned launch, even one planned before the date, is "no": the full duties are listed, and the step adds,
  citing `art:111:2`: "If the system is placed on the market or put into service before {date} and its design or
  intended purpose doesn't change significantly afterwards, Art. 111(2) may limit these duties; check again at launch." (German:
  "Wird das System vor dem {date} in Verkehr gebracht oder in Betrieb genommen und danach in seiner Konzeption oder Zweckbestimmung nicht
  erheblich verändert, kann Art. 111 Abs. 2 diese Pflichten einschränken; prüfen Sie dies beim Inverkehrbringen
  oder bei der Inbetriebnahme erneut.") The engine model can't tell a planned launch from a new system, so the sentence is added whenever the
  answer is "no" for a high-risk system.
- Only stated or inferred facts can mark duties: an assumed answer counts as "unknown", except a "no" on
  placed before, which already keeps the full duties. A silent description gives "unknown" for each fact: the duties stay unmarked (an unknown public-authority answer
  takes the 2 Aug 2030 date) and the facts are asked as follow-up questions.
