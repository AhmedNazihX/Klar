"""The duties' texts, from Klar's obligations table, never from the posted result (decision 031,
user 2026-10-09): a duty is looked up by the result's class, its role (and the role it also
has), the duty's article and the law version, and the reports print the table's formal wording
(`duty`, `duty_de`), condition (`applies_if`, `applies_if_de`) and short
labels. A posted duty no table entry matches has no formal wording to print.

A duty's date and its Art. 111(2) marking stay the result's own: they are the run's, not the
Act's text.
"""

from collections.abc import Iterable
from datetime import date
from typing import NamedTuple

from aiact.obligations.list import ObligationEntry, default_table
from aiact.schemas import HighRiskRoute, LawVersion, LegacyStatus, Obligation, RiskClass, Role

TRANSPARENCY_ARTICLE = "art:50"


class DutyTiming(NamedTuple):
    """What dates a duty, as both reports read it."""

    article: str
    applies_from: date
    legacy: LegacyStatus | None
    is_route_duty: bool
    """Dated per high-risk route (Annex III or Annex I), so by the route's Chapter III date."""
    is_informational: bool
    route: HighRiskRoute | None = None
    """The high-risk route that dates it, when it is a route duty and the route is known."""

    @property
    def is_transparency(self) -> bool:
        """An Art. 50 duty (`art:50` or one of its paragraphs)."""
        article = self.article
        return article == TRANSPARENCY_ARTICLE or article.startswith(f"{TRANSPARENCY_ARTICLE}:")


def table_entry(
    article: str,
    texts: Iterable[str],
    *,
    risk_class: RiskClass,
    roles: Iterable[Role],
    law_version: LawVersion,
) -> ObligationEntry | None:
    """The committed table's entry for `article` that a system of `risk_class` has in one of
    `roles` under `law_version`: the only one, or, when several share the article, the only one
    whose formal duty or a label is one of `texts`; None when there is none, or no single one,
    or the table doesn't hold `law_version`."""
    table = default_table()
    if table.law_version is not law_version:
        return None
    wanted = frozenset(roles)
    entries = [
        entry
        for entry in table.obligations
        if entry.article == article
        and risk_class in entry.risk_classes
        and not wanted.isdisjoint(entry.roles)
    ]
    if len(entries) != 1:
        named = frozenset(texts)
        entries = [
            entry
            for entry in entries
            if not named.isdisjoint((entry.duty, entry.label_en, entry.label_de))
        ]
    return entries[0] if len(entries) == 1 else None


def formal_duties(
    duties: tuple[Obligation, ...],
    *,
    risk_class: RiskClass,
    roles: tuple[Role, ...],
    law_version: LawVersion,
) -> tuple[Obligation, ...]:
    """The posted duties a table entry matches, each with that entry's texts (`duty`,
    `duty_de`, `applies_if`, `applies_if_de`, the labels) and `is_informational`; the others
    are left out."""
    found = (
        (
            duty,
            table_entry(
                duty.article,
                (duty.duty, duty.label_en),
                risk_class=risk_class,
                roles=roles,
                law_version=law_version,
            ),
        )
        for duty in duties
    )
    return tuple(_with_texts(duty, entry) for duty, entry in found if entry is not None)


def _with_texts(duty: Obligation, entry: ObligationEntry) -> Obligation:
    return duty.model_copy(
        update={
            "duty": entry.duty,
            "duty_de": entry.duty_de,
            "label_en": entry.label_en,
            "label_de": entry.label_de,
            "applies_if": entry.applies_if,
            "applies_if_de": entry.applies_if_de,
            "is_informational": entry.is_informational,
        }
    )


def timing(duty: Obligation) -> DutyTiming:
    """A result's duty as the reports date it."""
    return DutyTiming(
        article=duty.article,
        applies_from=duty.applies_from,
        legacy=duty.legacy,
        is_route_duty=duty.high_risk_route is not None,
        is_informational=duty.is_informational,
        route=duty.high_risk_route,
    )
