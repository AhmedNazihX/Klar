"""The facts check of the vendor letters' pre-filled sections, read directly from the result.

Like `facts_check.py`, it never calls the letters' pre-fills (`fills.py`), so a drafting bug
can't pass its own check: the date and text checked must be the result's, the finding must name
and quote the Art. 5 point a decided prohibited result cites, the facts must be the result's
deciding facts, and the open question, its readings and what would settle it must be the
result's first open question's. Problems name sections and positions, never the user's text.
"""

import re
from collections.abc import Callable, Mapping, Sequence

from aiact.dates import LONG_DATE_PATTERNS, long_date
from aiact.drafting.models import DraftSection, Provenance
from aiact.drafting.prefill import Fill
from aiact.drafting.templates import ClassificationSection
from aiact.drafting.vendor_letters.fills import TEXTS
from aiact.provision_names import article_provision_name
from aiact.schemas import (
    LAW_TEXTS,
    Citation,
    ClassificationResult,
    Language,
    OpenQuestion,
    RiskClass,
    Status,
    StepName,
)

ART_5_MENTIONS: Mapping[Language, re.Pattern[str]] = {
    Language.EN: re.compile(r"Art\. 5(?:\(\w+\))*"),
    Language.DE: re.compile(r"Art\. 5(?: (?:Abs\.|Buchst\.|Ziff\.) \w+)*"),
}
"""A provision of Art. 5 named in a sentence, as `article_provision_name` writes it."""


def vendor_problems(
    spec: ClassificationSection,
    section: DraftSection,
    result: ClassificationResult,
    language: Language,
) -> list[str]:
    """What in the vendor letter's pre-filled `section` doesn't match the result."""
    problems = CHECKS[spec.fill](spec, section, result, language)
    return [f"section {spec.key!r}: {problem}" for problem in problems]


def _open_question(result: ClassificationResult) -> OpenQuestion | None:
    return next((step.open_question for step in result.steps if step.open_question), None)


def _cited_point(result: ClassificationResult) -> Citation | None:
    """The first Art. 5(1) point the prohibited step of a decided prohibited result cites."""
    if result.risk_class is not RiskClass.PROHIBITED or result.status is not Status.DECIDED:
        return None
    step = next((step for step in result.steps if step.step is StepName.PROHIBITED), None)
    points = (c for c in step.citations if c.provision_id.count(":") == 3) if step else ()
    return next((c for c in points if c.provision_id.startswith("art:5:1:")), None)


def _one_sentence(section: DraftSection) -> str | None:
    """The section's single sentence, when it holds one from the classification."""
    if section.provenance is not Provenance.CLASSIFICATION or len(section.paragraphs) != 1:
        return None
    return section.paragraphs[0]


def _checked(
    spec: ClassificationSection,
    section: DraftSection,
    result: ClassificationResult,
    language: Language,
) -> list[str]:
    sentence = _one_sentence(section)
    if sentence is None:
        return ["it must give the date checked and the text, from the classification"]
    problems = []
    dates = LONG_DATE_PATTERNS[language].findall(sentence)
    if dates != [long_date(result.as_of, language.value)]:
        problems.append("the date checked is not the result's")
    named = [text.celex for text in LAW_TEXTS.values() if text.celex in sentence]
    if named != [LAW_TEXTS[result.law_version].celex]:
        problems.append("the text checked against is not the result's")
    return problems


def _finding(
    spec: ClassificationSection,
    section: DraftSection,
    result: ClassificationResult,
    language: Language,
) -> list[str]:
    point = _cited_point(result)
    if point is None:
        return ["the result is not a decided prohibited one citing an Art. 5(1) point"]
    sentence = _one_sentence(section)
    if sentence is None:
        return ["it must name the Art. 5 point, from the classification"]
    problems = []
    named = ART_5_MENTIONS[language].findall(sentence)
    if named != [article_provision_name(point.provision_id, language)]:
        problems.append("the Art. 5 point named is not the one the result cites")
    if section.requirement != point:
        problems.append("the quote is not the result's citation of the Art. 5 point")
    return problems


def _listed(
    expected: Callable[[ClassificationResult], Sequence[str]], what: str
) -> Callable[[ClassificationSection, DraftSection, ClassificationResult, Language], list[str]]:
    """A check that the section lists exactly `expected(result)`, in order, word for word; or,
    when the result gives none, the template's fixed line for that (no paragraphs without
    one)."""

    def check(
        spec: ClassificationSection,
        section: DraftSection,
        result: ClassificationResult,
        language: Language,
    ) -> list[str]:
        items = list(expected(result))
        if not items:
            line = (spec.empty[language],) if spec.empty else ()
            is_said = section.paragraphs == line and (
                not line or section.provenance is Provenance.TEMPLATE
            )
            return [] if is_said else [f"it must say that the result gives no {what}"]
        if section.provenance is not Provenance.CLASSIFICATION:
            return [f"it must hold the result's {what}"]
        paragraphs = list(section.paragraphs)
        problems = [
            f"paragraph {number} is not one of the result's {what}"
            for number, text in enumerate(paragraphs, start=1)
            if text not in items
        ]
        problems += [
            f"it leaves out item {number} of the result's {what}"
            for number, text in enumerate(items, start=1)
            if text not in paragraphs
        ]
        if not problems and paragraphs != items:
            problems.append(f"it doesn't keep the result's order of {what}")
        return problems

    return check


def _question(result: ClassificationResult) -> tuple[str, ...]:
    question = _open_question(result)
    return (question.question,) if question else ()


def _settled_by(result: ClassificationResult) -> tuple[str, ...]:
    question = _open_question(result)
    return tuple(item.text for item in question.settled_by) if question else ()


def _readings(
    spec: ClassificationSection,
    section: DraftSection,
    result: ClassificationResult,
    language: Language,
) -> list[str]:
    """Each reading in the result's order, marked applied exactly when the result applies it,
    with its title, explanation and consequence."""
    question = _open_question(result)
    readings = question.readings if question else ()
    if not readings:
        return [] if not section.paragraphs else ["the result leaves no question open"]
    if section.provenance is not Provenance.CLASSIFICATION or len(section.paragraphs) != len(
        readings
    ):
        return ["it must hold the open question's readings, from the classification"]
    problems = []
    for number, (text, reading) in enumerate(
        zip(section.paragraphs, readings, strict=True), start=1
    ):
        label = TEXTS[language]["applied" if reading.is_applied else "other"]
        if not text.startswith(f"{label}: "):
            problems.append(f"reading {number} is not marked as the result marks it")
        parts = (reading.title, reading.explanation, reading.consequence)
        if any(part and part not in text for part in parts):
            problems.append(f"reading {number} is not the result's")
    return problems


CHECKS: Mapping[
    Fill, Callable[[ClassificationSection, DraftSection, ClassificationResult, Language], list[str]]
] = {
    Fill.CHECKED: _checked,
    Fill.PROHIBITED_FINDING: _finding,
    Fill.DECIDING_FACTS: _listed(
        lambda result: [fact.text for fact in result.deciding_facts], "deciding facts"
    ),
    Fill.OPEN_QUESTION: _listed(_question, "open question"),
    Fill.READINGS: _readings,
    Fill.SETTLED_BY: _listed(_settled_by, "ways to settle the open question"),
}
"""The check of each vendor-letter fill."""
