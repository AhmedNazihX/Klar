"""The facts check of the vendor letters' pre-filled sections, read directly from the result.

Like `facts_check.py`, it never calls the letters' pre-fills (`fills.py`), so a drafting bug
can't pass its own check: the date and text checked must be the result's, the finding must name
every Art. 5(1) point a decided prohibited result decided on and quote each from the text and
in the language checked (the quote's words are the corpus's: the nothing-invented check compares
them with what the caller read, decision 031), the facts must be the result's deciding facts,
and the open question, its readings and what would settle it must be the result's first open
question's. Problems name sections and positions, never the user's text.
"""

import re
from collections.abc import Callable, Mapping, Sequence

from aiact.dates import LONG_DATE_PATTERNS, long_date
from aiact.drafting.models import DraftSection, Provenance
from aiact.drafting.prefill import Fill
from aiact.drafting.templates import ClassificationSection
from aiact.drafting.vendor_letters.fills import TEXTS, applies_on
from aiact.provision_names import article_provision_name
from aiact.schemas import (
    LAW_TEXTS,
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


def _decided_points(result: ClassificationResult) -> list[str]:
    """The Art. 5(1) points the prohibited step of a decided prohibited result cites, each once,
    in its order, leaving out a point that applies only after the result's date."""
    if result.risk_class is not RiskClass.PROHIBITED or result.status is not Status.DECIDED:
        return []
    cited = [
        citation.provision_id
        for step in result.steps
        if step.step is StepName.PROHIBITED
        for citation in step.citations
    ]
    points = [pid for pid in cited if pid.startswith("art:5:1:") and pid.count(":") == 3]
    return list(dict.fromkeys(pid for pid in points if applies_on(pid, result.as_of)))


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
    points = _decided_points(result)
    if not points:
        return ["the result is not a decided prohibited one citing an Art. 5(1) point"]
    sentence = _one_sentence(section)
    if sentence is None:
        return ["it must name the Art. 5(1) points, from the classification"]
    problems = []
    named = ART_5_MENTIONS[language].findall(sentence)
    if named != [article_provision_name(point, language) for point in points]:
        problems.append("the Art. 5 points named are not the ones the result decided on")
    text = LAW_TEXTS[result.law_version]
    quoted = [(q.provision_id, q.document_id, q.law_version) for q in section.quotes]
    if quoted != [(point, text.document_id, result.law_version) for point in points]:
        problems.append("the quotes are not the points named, from the text checked against")
    if any(q.language is not language and not q.english_only for q in section.quotes):
        problems.append("a quote is not in the letter's language")
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
