"""The three automatic checks on a draft (INIT > Documentation drafting), named as the
Documents artboard names them. They are deterministic and read the draft against its template,
the user's answers and the classification result. The judged "no invented content" score is V5's.

- Every required section is present: the template's sections, each once, in order, none added.
- No content you didn't supply: the title and headings are the template's; each fixed section
  holds the template's wording; each interview section holds the user's answer word for word, or
  nothing; each pre-filled section holds only the drafter's wording of the result.
- Facts match the classification: verified from the result alone, not by drafting again
  (`facts_check.py`): the stated facts, the class, Annex point and its certainty, the duty's
  date, the duty itself, and the result's law version and date.
"""

from collections.abc import Mapping
from enum import StrEnum
from typing import Self

from pydantic import model_validator

from aiact.drafting.deployer import Answers, prefilled_section, supplied_paragraphs
from aiact.drafting.facts_check import prefilled_problems
from aiact.drafting.models import DraftDocument, DraftSection
from aiact.drafting.prefill import DutyDateError
from aiact.drafting.templates import (
    TEMPLATES,
    ClassificationSection,
    DocumentTemplate,
    InterviewSection,
    SectionSpec,
)
from aiact.schemas import ClassificationResult, Language
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
        check_nothing_invented(document, result, answers),
        check_facts_match(document, result),
    )


def check_sections_present(document: DraftDocument) -> CheckResult:
    """Guarantees the draft has every section its template requires, each once and in the
    template's order, and no section the template doesn't have."""
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


def check_nothing_invented(
    document: DraftDocument, result: ClassificationResult, answers: Answers
) -> CheckResult:
    """Guarantees every word of the draft is the template's, the user's answer as given, or the
    drafter's wording of the result: no added section, sentence or paragraph, no answer moved to
    another question, and no section passing as another kind to escape the comparison."""
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
        problems += _invented(spec, section, document, template, result, answers)
    return _outcome(CheckName.NOTHING_INVENTED, problems)


def check_facts_match(document: DraftDocument, result: ClassificationResult) -> CheckResult:
    """Guarantees, from the result alone, that each pre-filled section states the result's facts
    (`facts_check.py`), that the draft answers its template's duty, and that it carries the
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
        if isinstance(spec, ClassificationSection):
            problems += prefilled_problems(
                spec, section, result, document.language, template.article
            )
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
    spec: SectionSpec,
    section: DraftSection,
    document: DraftDocument,
    template: DocumentTemplate,
    result: ClassificationResult,
    answers: Answers,
) -> list[str]:
    key, language = spec.key, document.language
    if section.heading != spec.heading[language]:
        return [f"section {key!r} has a heading the template doesn't give"]
    if isinstance(spec, ClassificationSection):
        return _prefill_invented(spec, section, template, result, language)
    if section.provenance is not spec.provenance:
        return [f"section {key!r} claims to come from {section.provenance.value}"]
    if isinstance(spec, InterviewSection) and section.question_key != spec.question_key:
        return [f"section {key!r} answers another question"]
    if section.paragraphs != supplied_paragraphs(spec, answers, language):
        return [f"section {key!r} holds content the user didn't supply"]
    return []


def _prefill_invented(
    spec: ClassificationSection,
    section: DraftSection,
    template: DocumentTemplate,
    result: ClassificationResult,
    language: Language,
) -> list[str]:
    try:
        drafted = prefilled_section(spec, result, language, template.article)
    except DutyDateError:
        return [f"section {spec.key!r}: the result lists its duty with several dates"]
    if (section.provenance, section.paragraphs) != (drafted.provenance, drafted.paragraphs):
        return [f"section {spec.key!r} holds content the result doesn't give"]
    return []
