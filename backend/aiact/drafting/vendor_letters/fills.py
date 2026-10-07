"""What the vendor letters take from a classification result, and how they word it.

Each `*_paragraphs` function is a pre-fill (`prefill.PREFILLS`): it reads the result alone and
returns a section's paragraphs. The facts, the open question, its readings and what would settle
it are the result's own words, in the language the result was written in; only the sentences
around them are in the letter's language. `deciding_points` are the Art. 5(1) points the message
names; their text comes from the corpus (`quotes.py`), never from the result (decision 031). The
facts check (`facts.py`) verifies the written sections without calling these.
"""

import re
from collections.abc import Mapping, Sequence
from datetime import date

from aiact.dates import long_date
from aiact.provision_names import article_provision_name
from aiact.schemas import (
    LAW_TEXTS,
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

ART_5_POINT = re.compile(r"art:5:1:[a-z]+")
"""A point of the Art. 5(1) list of prohibited practices, such as `art:5:1:f`; not one of its
sub-points (`art:5:1:c:i`) or Art. 5(1a)'s routes. Matched whole (`is_art_5_point`): the
drafter and the facts check (`facts.py`) both read a point through it."""

PROHIBITIONS_APPLY_FROM = date(2025, 2, 2)
"""Art. 113(a): Art. 5 applies from 2 February 2025."""
LATER_POINTS: Mapping[str, date] = {
    "art:5:1:ba": date(2026, 12, 2),
    "art:5:1:bb": date(2026, 12, 2),
}
"""Art. 113(a) as the Omnibus amends it: points (ba) and (bb) apply only from 2 December 2026. A
decided prohibited step cites a point that applies only later after the points that decide it
(`tests/drafting/test_vendor_letters.py` pins these dates to the engine's)."""

TEXTS: Mapping[Language, Mapping[str, str]] = {
    EN: {
        "checked": "We checked the tool against the EU AI Act as it applies on {date} "
        "({version}, CELEX {celex}).",
        LawVersion.AMENDED: "the amended text",
        LawVersion.ORIGINAL: "the original text",
        "finding": "The check found that the tool falls under a practice prohibited by {points} "
        "of the AI Act.",
        "findings": "The check found that the tool falls under practices prohibited by {points} "
        "of the AI Act.",
        "and": " and ",
        "applied": "Applied until settled",
        "other": "The other reading",
    },
    DE: {
        "checked": "Wir haben das Tool anhand der KI-Verordnung geprüft, wie sie am {date} gilt "
        "({version}, CELEX {celex}).",
        LawVersion.AMENDED: "geänderte Fassung",
        LawVersion.ORIGINAL: "ursprüngliche Fassung",
        "finding": "Nach der Prüfung fällt das Tool unter eine nach {points} der KI-Verordnung "
        "verbotene Praktik.",
        "findings": "Nach der Prüfung fällt das Tool unter nach {points} der KI-Verordnung "
        "verbotene Praktiken.",
        "and": " und ",
        "applied": "Bis zur Klärung angewandt",
        "other": "Die andere Lesart",
    },
}
"""The letters' sentences around the result's own words: `finding` names one Art. 5(1) point,
`findings` two or more (user decision, 2026-10-08)."""


def is_art_5_point(provision_id: str) -> bool:
    """Whether `provision_id` is exactly a point of the Art. 5(1) list (`ART_5_POINT`)."""
    return ART_5_POINT.fullmatch(provision_id) is not None


def finding_key(count: int) -> str:
    """The `TEXTS` key of the finding naming `count` points: one, or two or more."""
    return "finding" if count == 1 else "findings"


def is_decided_prohibited(result: ClassificationResult) -> bool:
    """A prohibited result no open point holds up: the message's result."""
    return result.risk_class is RiskClass.PROHIBITED and result.status is Status.DECIDED


def applies_on(point: str, day: date) -> bool:
    """Whether the Art. 5(1) `point` applies on `day` (Art. 113(a))."""
    return LATER_POINTS.get(point, PROHIBITIONS_APPLY_FROM) <= day


def deciding_points(result: ClassificationResult) -> tuple[str, ...]:
    """The Art. 5(1) points a decided prohibited result's step cites that apply on the result's
    date: the points it found met, each once, in the step's order. None for any other
    result."""
    if not is_decided_prohibited(result):
        return ()
    step = next((step for step in result.steps if step.step is StepName.PROHIBITED), None)
    cited = (citation.provision_id for citation in step.citations) if step else ()
    points = (pid for pid in cited if is_art_5_point(pid) and applies_on(pid, result.as_of))
    return tuple(dict.fromkeys(points))


def point_names(points: Sequence[str], language: Language) -> str:
    """The points as a sentence names them: "Art. 5(1)(f)", "Art. 5(1)(c) and Art. 5(1)(f)"."""
    names = [article_provision_name(point, language) for point in points]
    if len(names) < 2:
        return "".join(names)
    return ", ".join(names[:-1]) + TEXTS[language]["and"] + names[-1]


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
    """Every Art. 5(1) point the tool falls under; nothing for a result that isn't a decided
    prohibited one."""
    points = deciding_points(result)
    if not points:
        return ()
    sentence = TEXTS[language][finding_key(len(points))]
    return (sentence.format(points=point_names(points, language)),)


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
