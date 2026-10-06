"""The three automatic checks on a draft (INIT > Documentation drafting), named as the
Documents artboard names them. They are deterministic: each compares the draft with its template,
the user's answers and the classification result. The judged "no invented content" score is V5's.

- Every required section is present: the template's sections, in order, none added.
- No content you didn't supply: the title, headings and fixed wording are the template's, and each
  interview section holds the user's answer word for word, or nothing.
- Facts match the classification: each pre-filled section is what the result says, and the draft
  names the result's law version and date.
"""

from collections.abc import Mapping
from enum import StrEnum
from typing import Self

from pydantic import model_validator

from aiact.drafting.deployer import Answers, supplied_paragraphs
from aiact.drafting.models import DraftDocument, DraftSection
from aiact.drafting.templates import (
    TEMPLATES,
    ClassificationSection,
    DocumentTemplate,
    InterviewSection,
    SectionSpec,
)
from aiact.schemas import ClassificationResult
from aiact.schemas.base import ContractModel


class CheckName(StrEnum):
    SECTIONS_PRESENT = "sections_present"
    NOTHING_INVENTED = "nothing_invented"
    FACTS_MATCH = "facts_match"


CHECK_LABELS: Mapping[CheckName, str] = {
    CheckName.SECTIONS_PRESENT: "Every required section is present",
    CheckName.NOTHING_INVENTED: "No content you didn't supply",
    CheckName.FACTS_MATCH: "Facts match the classification",
}
"""The checks as the Documents artboard names them (the interface translates them)."""


class CheckResult(ContractModel):
    """One check's outcome. `problems` names each failure; it passes when there are none."""

    check: CheckName
    passed: bool
    problems: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _passed_iff_no_problems(self) -> Self:
        if self.passed == bool(self.problems):
            raise ValueError("a check passes exactly when it found no problems")
        return self


def _outcome(check: CheckName, problems: list[str]) -> CheckResult:
    return CheckResult(check=check, passed=not problems, problems=tuple(problems))


def run_checks(
    document: DraftDocument, result: ClassificationResult, answers: Answers
) -> tuple[CheckResult, ...]:
    """All three checks on `document`, against the result and the answers it was drafted from."""
    return (
        check_sections_present(document),
        check_nothing_invented(document, answers),
        check_facts_match(document, result),
    )


def check_sections_present(document: DraftDocument) -> CheckResult:
    """Every section the template requires is there, in its order, and no other."""
    template = TEMPLATES.get(document.template)
    if template is None:
        return _outcome(CheckName.SECTIONS_PRESENT, [f"unknown template {document.template!r}"])
    required = [spec.key for spec in template.sections]
    present = [section.key for section in document.sections]
    problems = [f"missing section {key!r}" for key in required if key not in present]
    problems += [
        f"section {key!r} is not in the template" for key in present if key not in required
    ]
    problems += [f"section {key!r} appears more than once" for key in _repeated(present)]
    if not problems and present != required:
        problems.append(f"sections are out of order: {present}, expected {required}")
    return _outcome(CheckName.SECTIONS_PRESENT, problems)


def check_nothing_invented(document: DraftDocument, answers: Answers) -> CheckResult:
    """Only the template's own wording and the user's answers, word for word, outside the
    pre-filled sections; a section can't pass as pre-filled to escape this check."""
    template = TEMPLATES.get(document.template)
    if template is None:
        return _outcome(CheckName.NOTHING_INVENTED, [f"unknown template {document.template!r}"])
    problems = []
    if document.title != template.title[document.language]:
        problems.append("the title is not the template's")
    known = {spec.key for spec in template.sections}
    problems += [
        f"section {section.key!r} is not the template's"
        for section in document.sections
        if section.key not in known
    ]
    for spec, section in _pairs(template, document):
        problems += _invented(spec, section, document, answers)
    return _outcome(CheckName.NOTHING_INVENTED, problems)


def check_facts_match(document: DraftDocument, result: ClassificationResult) -> CheckResult:
    """Each pre-filled section holds exactly what the result says, and the draft carries the
    result's law version and date."""
    template = TEMPLATES.get(document.template)
    if template is None:
        return _outcome(CheckName.FACTS_MATCH, [f"unknown template {document.template!r}"])
    problems = []
    if (document.law_version, document.as_of) != (result.law_version, result.as_of):
        problems.append("the law version or date differs from the result's")
    if document.article != template.article:
        problems.append(f"the duty {document.article} is not the template's {template.article}")
    for spec, section in _pairs(template, document):
        if not isinstance(spec, ClassificationSection):
            continue
        expected = spec.prefill(result, document.language, template.article)
        if section.paragraphs != expected:
            problems.append(f"section {spec.key!r} doesn't match the classification result")
    return _outcome(CheckName.FACTS_MATCH, problems)


def _pairs(
    template: DocumentTemplate, document: DraftDocument
) -> list[tuple[SectionSpec, DraftSection]]:
    """Each of the draft's sections with the template section of its key; a section the template
    doesn't have is left out (missing ones are the sections check's to report)."""
    specs = {spec.key: spec for spec in template.sections}
    return [(specs[section.key], section) for section in document.sections if section.key in specs]


def _repeated(keys: list[str]) -> list[str]:
    return sorted({key for key in keys if keys.count(key) > 1})


def _invented(
    spec: SectionSpec, section: DraftSection, document: DraftDocument, answers: Answers
) -> list[str]:
    language = document.language
    if section.provenance is not spec.provenance:
        return [f"section {spec.key!r} claims to come from {section.provenance.value}"]
    if section.heading != spec.heading[language]:
        return [f"section {spec.key!r} has a heading the template doesn't give"]
    if isinstance(spec, ClassificationSection):
        return []
    if isinstance(spec, InterviewSection) and section.question_key != spec.question_key:
        return [f"section {spec.key!r} answers another question"]
    if section.paragraphs != supplied_paragraphs(spec, answers, language):
        return [f"section {spec.key!r} holds content the user didn't supply"]
    return []
