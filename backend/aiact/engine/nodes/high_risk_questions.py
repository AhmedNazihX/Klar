"""What the high-risk step adds to its questions for the screens (E12; decision 026 items 4, 13
and 18): what a yes settles on a route, the quotes a route's question rests on (the Annex I
question quotes Art. 6(1) and the Annex I entry naming the product law), the two readings of an
open question, and what would settle it. The dates a yes or a reading gives are the law version's
(E11): the original Art. 113 dates differ from the amended ones."""

from collections.abc import Sequence
from datetime import date

from aiact.corpus.sources import HIGH_RISK_DATE
from aiact.dates import long_date
from aiact.engine.nodes.high_risk_texts import READINGS, SETTLED_BY, point_name
from aiact.engine.nodes.questions import quoted
from aiact.engine.nodes.reading_side import ReadingSide
from aiact.obligations.list import CHAPTER_III_DATES, ORIGINAL_CHAPTER_III_DATES
from aiact.schemas import (
    AnswerOutcome,
    Citation,
    HighRiskRoute,
    Language,
    LawVersion,
    RiskClass,
    SettledBy,
    SettledByKind,
)

ANNEX_I_RULE = "art:6:1"
"""The Annex I route's rule, which its question and readings quote."""
SECTION_B_PREFIX = "annex:I:B:"
"""An Annex I Section B point: Art. 2(2) leaves the duties to the sector law."""

GUIDELINES_DRAFT_DATE = date.fromisoformat(HIGH_RISK_DATE)
"""The date of the Commission's draft high-risk guidelines, as fetched."""


def chapter_iii_date(route: HighRiskRoute, law_version: LawVersion) -> date:
    """The date the high-risk duties on `route` apply from under the text of `law_version`."""
    dates = ORIGINAL_CHAPTER_III_DATES if law_version is LawVersion.ORIGINAL else CHAPTER_III_DATES
    return dates[route]


def is_section_b(point: str | None) -> bool:
    return point is not None and point.startswith(SECTION_B_PREFIX)


def high_risk_outcome(
    route: HighRiskRoute, point: str | None, law_version: LawVersion
) -> AnswerOutcome:
    """What a yes settles when it makes the system high-risk on `route` at `point`: the class,
    the route, the point and the route's Chapter III date under `law_version` (none for Section
    B, whose duties come from the sector law)."""
    duties_from = None if is_section_b(point) else chapter_iii_date(route, law_version)
    return AnswerOutcome(
        risk_class=RiskClass.HIGH_RISK,
        high_risk_route=route,
        provision_id=point,
        duties_from=duties_from,
    )


def question_citations(
    route: HighRiskRoute | None, point: str | None, citations: Sequence[Citation]
) -> tuple[Citation, ...]:
    """The step's citations a route's question quotes: the Annex I entry and Art. 6(1) on the
    Annex I route, the Annex III point on the other."""
    if route is None or point is None:
        return ()
    wanted = (point, ANNEX_I_RULE) if route is HighRiskRoute.ANNEX_I else (point,)
    found = (quoted(pid, citations) for pid in wanted)
    return tuple(citation for citation in found if citation is not None)


def reading_sides(
    route: HighRiskRoute,
    point: str,
    law: str,
    language: Language,
    law_version: LawVersion,
    exemption: str | None = None,
) -> tuple[ReadingSide, ReadingSide]:
    """The stricter reading (high-risk on the route, its duties dated under `law_version`) and
    the lenient one: exempt under `exemption` (the Art. 6(3) provision) when the open question is
    the exemption, otherwise outside the Annex III point or Art. 6(1)."""
    words = READINGS[language]
    if is_section_b(point):
        high = words["section_b_consequence"].format(law=law)
    else:
        high = words["high_consequence"].format(
            date=long_date(chapter_iii_date(route, law_version), language.value)
        )
    if route is HighRiskRoute.ANNEX_I:
        stricter = ReadingSide(words["high_i"], high, RiskClass.HIGH_RISK, ANNEX_I_RULE)
        return stricter, ReadingSide(
            words["not_i"], words["not_high_consequence"], None, ANNEX_I_RULE
        )
    name = point_name(point, language)
    stricter = ReadingSide(words["high_iii"].format(point=name), high, RiskClass.HIGH_RISK, point)
    if exemption is not None:
        return stricter, ReadingSide(words["exempt"], words["exempt_consequence"], None, exemption)
    not_listed = words["not_iii"].format(point=name)
    return stricter, ReadingSide(not_listed, words["not_high_consequence"], None, point)


def settled_by(language: Language, *, is_open_on_exemption: bool) -> tuple[SettledBy, ...]:
    """The final high-risk guidelines (still a draft, never a promise to check again), and the
    provider's own Art. 6(3) assessment when the open question is the exemption."""
    texts = SETTLED_BY[language]
    guidelines = texts["guidelines"].format(date=long_date(GUIDELINES_DRAFT_DATE, language.value))
    items = [SettledBy(kind=SettledByKind.GUIDANCE, text=guidelines)]
    if is_open_on_exemption:
        items.append(SettledBy(kind=SettledByKind.PROVIDER, text=texts["provider"]))
    return tuple(items)
