"""What the vendor letters take from a classification result, and how they word it.

Each `*_paragraphs` function is a pre-fill (`prefill.PREFILLS`): it reads the result alone and
returns a section's paragraphs. The facts, the open question, its readings and what would settle
it are the result's own words, in the language the result was written in; only the sentences
around them are in the letter's language. `prohibited_quote` is the Art. 5 point the message
quotes. The facts check (`facts.py`) verifies the written sections without calling these.
"""

import re
from collections.abc import Mapping

from aiact.dates import long_date
from aiact.provision_names import article_provision_name
from aiact.schemas import (
    LAW_TEXTS,
    Citation,
    ClassificationResult,
    Language,
    LawVersion,
    OpenQuestion,
    Reading,
    RiskClass,
    Status,
    StepName,
)

EN, DE = Language.EN, Language.DE

ART_5_POINT = re.compile(r"^art:5:1:[a-z]+$")
"""A point of the Art. 5(1) list of prohibited practices, such as `art:5:1:f`; not one of its
sub-points (`art:5:1:c:i`) or Art. 5(1a)'s routes."""

TEXTS: Mapping[Language, Mapping[str, str]] = {
    EN: {
        "checked": "We checked the tool against the EU AI Act as it applies on {date} "
        "({version}, CELEX {celex}).",
        LawVersion.AMENDED: "the amended text",
        LawVersion.ORIGINAL: "the original text",
        "finding": "The check found that the tool falls under a practice prohibited by {point} "
        "of the AI Act.",
        "applied": "Applied until settled",
        "other": "The other reading",
    },
    DE: {
        "checked": "Wir haben das Tool anhand der KI-Verordnung geprüft, wie sie am {date} gilt "
        "({version}, CELEX {celex}).",
        LawVersion.AMENDED: "geänderte Fassung",
        LawVersion.ORIGINAL: "ursprüngliche Fassung",
        "finding": "Nach der Prüfung fällt das Tool unter eine nach {point} der KI-Verordnung "
        "verbotene Praktik.",
        "applied": "Bis zur Klärung angewandt",
        "other": "Die andere Lesart",
    },
}
"""The letters' sentences around the result's own words."""


def is_decided_prohibited(result: ClassificationResult) -> bool:
    """A prohibited result no open point holds up: the message's result."""
    return result.risk_class is RiskClass.PROHIBITED and result.status is Status.DECIDED


def prohibited_quote(result: ClassificationResult) -> Citation | None:
    """The Art. 5(1) point a decided prohibited result's step cites first: the point it found
    met (the step lists the met practices' points before those that apply only from a later
    date). None for any other result."""
    if not is_decided_prohibited(result):
        return None
    step = next((step for step in result.steps if step.step is StepName.PROHIBITED), None)
    citations = step.citations if step else ()
    return next((c for c in citations if ART_5_POINT.match(c.provision_id)), None)


def open_question(result: ClassificationResult) -> OpenQuestion | None:
    """The question of law the result leaves open first, in check order; the request asks the
    vendor about this one."""
    return next((step.open_question for step in result.steps if step.open_question), None)


def checked_paragraphs(
    result: ClassificationResult, language: Language, article: str
) -> tuple[str, ...]:
    """The date checked and the text of the Act checked against."""
    texts = TEXTS[language]
    when = long_date(result.as_of, language.value)
    celex = LAW_TEXTS[result.law_version].celex
    version = texts[result.law_version]
    return (texts["checked"].format(date=when, version=version, celex=celex),)


def finding_paragraphs(
    result: ClassificationResult, language: Language, article: str
) -> tuple[str, ...]:
    """The Art. 5 point the tool falls under; nothing for a result that isn't a decided
    prohibited one."""
    quote = prohibited_quote(result)
    if quote is None:
        return ()
    point = article_provision_name(quote.provision_id, language)
    return (TEXTS[language]["finding"].format(point=point),)


def deciding_fact_paragraphs(
    result: ClassificationResult, language: Language, article: str
) -> tuple[str, ...]:
    """The facts the result rests on, word for word, in the result's order."""
    return tuple(fact.text for fact in result.deciding_facts)


def question_paragraphs(
    result: ClassificationResult, language: Language, article: str
) -> tuple[str, ...]:
    question = open_question(result)
    return (question.question,) if question else ()


def reading_paragraphs(
    result: ClassificationResult, language: Language, article: str
) -> tuple[str, ...]:
    """Each reading of the open question, the applied one first, marked as such."""
    question = open_question(result)
    return tuple(_reading(reading, language) for reading in question.readings) if question else ()


def _reading(reading: Reading, language: Language) -> str:
    label = TEXTS[language]["applied" if reading.is_applied else "other"]
    title = (f"{reading.title}.",) if reading.title else ()
    consequence = (reading.consequence,) if reading.consequence else ()
    return f"{label}: " + " ".join((*title, reading.explanation, *consequence))


def settled_by_paragraphs(
    result: ClassificationResult, language: Language, article: str
) -> tuple[str, ...]:
    """What would settle the open question, as the result names it."""
    question = open_question(result)
    return tuple(item.text for item in question.settled_by) if question else ()
