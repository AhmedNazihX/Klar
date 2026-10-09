"""What both reports share: the names of a class, status and role, a duty's timing, and the
footer. Every text is the report's language, from `texts.py`."""

from collections.abc import Iterable, Sequence
from datetime import date
from typing import Annotated

from pydantic import StringConstraints

from aiact.dates import long_date
from aiact.provision_names import article_provision_name
from aiact.report.duties import DutyTiming
from aiact.report.texts import (
    AFTER_CHANGE,
    ASSUMED_CLASS,
    CLASS_NAMES,
    FOOTER,
    FROM_DATE,
    LEGACY_FROM,
    NO_DUTIES_DATE,
    NOT_CLASSIFIED,
    NOTHING,
    ONLY_AFTER_CHANGE,
    STOP_USING,
)
from aiact.schemas import DISCLAIMER, Language, LegacyStatus, RiskClass, Status

LEGACY_ARTICLE = "art:111:2"
"""Where a legacy duty's own timing comes from."""
MAX_NAME_CHARS = 200
"""A tool's name and the company's, as the database caps them (`systems.name`,
`inventories.company_name`)."""

Name = Annotated[str, StringConstraints(min_length=1, max_length=MAX_NAME_CHARS)]


def footer(language: Language) -> str:
    """The notice on every page: the disclaimer in the report's language (never the posted
    result's), then that Klar, an AI system, prepared it."""
    return f"{DISCLAIMER[language]} {FOOTER[language]}"


def day(value: date, language: Language) -> str:
    """A date as the Act writes it: "2 December 2027", "2. Dezember 2027"."""
    return long_date(value, language.value)


def class_name(risk_class: RiskClass | None, status: Status | None, language: Language) -> str:
    """The class, marked as assumed while the result is uncertain; a tool without one is "not
    classified yet"."""
    if risk_class is None:
        return NOT_CLASSIFIED[language]
    name = CLASS_NAMES[risk_class][language]
    if status in (None, Status.DECIDED):
        return name
    return ASSUMED_CLASS[language].format(name=name)


def duty_timing(applies_from: date, legacy: LegacyStatus | None, language: Language) -> str:
    """When a duty applies: its date, or under Art. 111(2) only after a significant change, or
    its 2030 date marked with the article."""
    article = article_provision_name(LEGACY_ARTICLE, language)
    if legacy is LegacyStatus.UNCHANGED:
        return AFTER_CHANGE[language].format(article=article)
    if legacy is LegacyStatus.PUBLIC_AUTHORITY:
        return LEGACY_FROM[language].format(date=day(applies_from, language), article=article)
    return day(applies_from, language)


def applies_when(applies_from: date, legacy: LegacyStatus | None, language: Language) -> str:
    """When a duty applies, to follow a heading or a provision: "from 2 December 2027", "only
    after a significant change (Art. 111(2))", "from 2 August 2030 (Art. 111(2))"."""
    if legacy is LegacyStatus.UNCHANGED:
        return ONLY_AFTER_CHANGE[language].format(
            article=article_provision_name(LEGACY_ARTICLE, language)
        )
    return FROM_DATE[language].format(date=duty_timing(applies_from, legacy, language))


def duties_from(duties: Sequence[DutyTiming], language: Language) -> str:
    """When the duties apply, as the Result screen dates them (`dutiesDate`): a high-risk
    result's route date (its Chapter III date), else the earliest date of a duty that isn't
    informational; "No specific duties" without one. When Art. 111(2) marks every route duty,
    "only after a significant change", or its 2030 date for a system meant for public
    authorities, as the inventory says it."""
    route = [duty for duty in duties if duty.is_route_duty]
    if route and all(duty.legacy is not None for duty in route):
        authority = next((d for d in route if d.legacy is LegacyStatus.PUBLIC_AUTHORITY), None)
        if authority is None:
            return duty_timing(route[0].applies_from, LegacyStatus.UNCHANGED, language)
        return duty_timing(authority.applies_from, authority.legacy, language)
    dated = [duty for duty in route if duty.legacy is not LegacyStatus.PUBLIC_AUTHORITY]
    if dated:
        return day(dated[0].applies_from, language)
    return _earliest((duty for duty in duties if not duty.is_informational), language)


def tool_duties_from(
    risk_class: RiskClass | None, duties: Sequence[DutyTiming], language: Language
) -> str:
    """When a tool's duties apply, as the inventory dates them (`appliesFrom`): none for a
    minimal-risk or out-of-scope tool, the Art. 50 duties' date for a limited-risk one, "stop
    using or supplying it" for a prohibited one (the inventory's "needs you"), and the Result
    screen's date (`duties_from`) for a high-risk one."""
    match risk_class:
        case None:
            return NOTHING
        case RiskClass.PROHIBITED:
            return STOP_USING[language]
        case RiskClass.HIGH_RISK:
            return duties_from(duties, language)
        case RiskClass.LIMITED_RISK:
            art_50 = (d for d in duties if d.is_transparency and not d.is_informational)
            return _earliest(art_50, language)
        case RiskClass.MINIMAL_RISK | RiskClass.OUT_OF_SCOPE:
            return NO_DUTIES_DATE[language]


def _earliest(duties: Iterable[DutyTiming], language: Language) -> str:
    dates = sorted(duty.applies_from for duty in duties)
    return day(dates[0], language) if dates else NO_DUTIES_DATE[language]
