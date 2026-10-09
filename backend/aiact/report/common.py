"""What both reports share: the names of a class, status and role, a duty's timing, and the
footer. Every text is the report's language, from `texts.py`."""

from collections.abc import Iterable
from datetime import date

from aiact.dates import long_date
from aiact.provision_names import article_provision_name
from aiact.report.texts import (
    AFTER_CHANGE,
    ASSUMED_CLASS,
    CLASS_NAMES,
    FOOTER,
    LEGACY_FROM,
    NO_DUTIES_DATE,
    NOT_CLASSIFIED,
)
from aiact.schemas import DISCLAIMER, Language, LegacyStatus, RiskClass, Status

LEGACY_ARTICLE = "art:111:2"
"""Where a legacy duty's own timing comes from."""


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


def duties_from(timings: Iterable[tuple[date, LegacyStatus | None]], language: Language) -> str:
    """When the first duty applies: the earliest date of a duty that applies on its date,
    "only after a significant change" when every duty waits for one (Art. 111(2)), or "No
    specific duties" without any duty."""
    listed = tuple(timings)
    if not listed:
        return NO_DUTIES_DATE[language]
    dated = [
        applies_from for applies_from, legacy in listed if legacy is not LegacyStatus.UNCHANGED
    ]
    if not dated:
        return duty_timing(listed[0][0], LegacyStatus.UNCHANGED, language)
    return day(min(dated), language)
