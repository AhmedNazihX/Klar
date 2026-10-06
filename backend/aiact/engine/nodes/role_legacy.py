"""Art. 111(2) for the role and obligations node (C7b, decision 022): a high-risk system already
on the market or in use before its route's Chapter III date keeps its class, but its high-risk
duties are marked. Moved out of `role_obligations` by E8, unchanged.

The key facts are placed on the market or put into service before the route's date, a
significant change to its design or intended purpose from then on (a substantial modification,
Art. 3(23)), and use by public authorities. An unknown answer keeps the duties as they are and
becomes a follow-up question.
"""

from collections.abc import Sequence
from dataclasses import dataclass

from aiact.dates import long_date
from aiact.engine.nodes.key_facts import Answer, KeyFact
from aiact.engine.nodes.role_texts import TEXTS, KeyQuestion, legacy_questions
from aiact.obligations.list import (
    CHAPTER_III_DATES,
    LEGACY_ARTICLE,
    PUBLIC_AUTHORITY_DEADLINE,
    SUBSTANTIAL_MODIFICATION_ARTICLE,
    legacy_status,
)
from aiact.schemas import EvidenceTag, HighRiskRoute, Language, LegacyStatus, Obligation, Role
from aiact.schemas.base import ContractModel


class LegacyAnswer(ContractModel):
    """The Art. 111(2) key facts of a high-risk system."""

    placed_before: KeyFact
    significant_design_change: KeyFact
    for_public_authority: KeyFact


@dataclass(frozen=True)
class LegacySettlement:
    """What Art. 111(2) gives: the marking for the duties (None: they apply as usual), whether
    to check again at launch (not yet on the market or in use), the answers it rests on, and the
    unknown ones to ask."""

    status: LegacyStatus | None = None
    route: HighRiskRoute | None = None
    used: tuple[KeyFact, ...] = ()
    questions: tuple[KeyQuestion, ...] = ()
    check_at_launch: bool = False
    is_public_authority_assumed: bool = False
    """The 2030 date rests on an unsettled (unknown or assumed) public-authority answer."""

    @property
    def articles(self) -> tuple[str, ...]:
        """What the step cites for Art. 111(2): the article for the check-again sentence, and
        with a marking also Art. 3(23), the substantial modification a significant change is
        read as (recital 177, which the consolidated text doesn't carry)."""
        if self.status is not None:
            return (LEGACY_ARTICLE, SUBSTANTIAL_MODIFICATION_ARTICLE)
        return (LEGACY_ARTICLE,) if self.check_at_launch else ()


def _settled_answer(key_fact: KeyFact) -> Answer:
    """An assumed answer settles nothing under Art. 111(2): it counts as unknown and is asked."""
    return Answer.UNKNOWN if key_fact.evidence is EvidenceTag.ASSUMED else key_fact.answer


def settle_legacy(legacy: LegacyAnswer | None, route: HighRiskRoute | None) -> LegacySettlement:
    """Apply Art. 111(2) to the answers, as of the assessment date (user decision, 2026-10-01):
    only a system already on the market or in use counts as placed before the route's date. One
    that isn't yet keeps its duties as usual, with a note to check again at launch (the model
    can't tell a planned launch from a new system, so every "no" gets it, assumed or not). One
    whose design changes keeps its duties too, and the launch and public-use facts aren't relied
    on or asked. Otherwise an assumed answer counts as unknown, so only stated or inferred facts
    can mark duties, and an unknown fact counts the stricter way (not placed before the date,
    changed, for public authorities: the earlier deadline) and is asked as a follow-up question."""
    if legacy is None or route is None:
        return LegacySettlement()
    keys = legacy_questions(CHAPTER_III_DATES[route], LEGACY_ARTICLE)
    if legacy.placed_before.answer is Answer.NO:
        return LegacySettlement(route=route, used=(legacy.placed_before,), check_at_launch=True)
    placed = _settled_answer(legacy.placed_before)
    changed = _settled_answer(legacy.significant_design_change)
    public = _settled_answer(legacy.for_public_authority)
    chain = (
        (legacy.placed_before, placed, keys.placed_before),
        (legacy.significant_design_change, changed, keys.design_change),
        (legacy.for_public_authority, public, keys.public_authority),
    )
    if changed is Answer.YES:
        # The duties apply as usual whatever the launch or public use: ask neither.
        chain = tuple(link for link in chain[:2] if link[1] is not Answer.UNKNOWN)
    status = legacy_status(
        placed_before=placed is Answer.YES,
        significantly_changed=changed is not Answer.NO,
        for_public_authority=public is not Answer.NO,
    )
    return LegacySettlement(
        status=status,
        route=route,
        used=tuple(fact for fact, settled, _ in chain if settled is not Answer.UNKNOWN),
        questions=tuple(question for _, settled, question in chain if settled is Answer.UNKNOWN),
        is_public_authority_assumed=public is Answer.UNKNOWN,
    )


PER_PRODUCT_ROLES = frozenset({Role.PROVIDER, Role.IMPORTER, Role.DISTRIBUTOR})
"""The roles that supply the system: placing on the market counts per product supplied (the New
Legislative Framework reading), so new copies may be fully covered. A deployer uses its copy."""


def _sentence_key(status: LegacyStatus, legacy: LegacySettlement) -> str:
    """The decision sentence for a marking: the 2030 date on an unsettled public-authority
    answer is worded as an assumption, not as a fact."""
    if status is LegacyStatus.PUBLIC_AUTHORITY and legacy.is_public_authority_assumed:
        return "legacy_public_authority_assumed"
    return status.value


def legacy_summary(
    kept: Sequence[Obligation], legacy: LegacySettlement, language: Language, roles: Sequence[Role]
) -> tuple[str, ...]:
    """One sentence per Art. 111(2) marking the kept duties carry, then the per-product caveat
    for a role that supplies the system; or the check-again sentence for a system not yet on the
    market or in use."""
    if not legacy.articles or legacy.route is None:
        return ()
    texts = TEXTS[language]
    since = long_date(CHAPTER_III_DATES[legacy.route], language)
    if legacy.check_at_launch:
        return (texts["legacy_check_at_launch"].format(date=since),)
    deadline = long_date(PUBLIC_AUTHORITY_DEADLINE, language)
    counts = {status: sum(o.legacy is status for o in kept) for status in LegacyStatus}
    marked = tuple(
        texts[_sentence_key(status, legacy)].format(count=count, date=since, deadline=deadline)
        for status, count in counts.items()
        if count
    )
    supplies = any(role in PER_PRODUCT_ROLES for role in roles)
    caveat = (texts["legacy_per_product"].format(date=since),) if marked and supplies else ()
    return (*marked, *caveat)
