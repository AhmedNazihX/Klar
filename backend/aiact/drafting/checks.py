"""The three automatic checks on a draft (INIT > Documentation drafting), named as the
Documents artboard names them. They are deterministic and read the draft against its template,
the user's answers and the classification result. The judged "no invented content" score is V5's.

- Every required section is present: the template's sections, each once, in order, none added.
- No content you didn't supply: the title, note and headings are the template's; each fixed
  section holds the template's wording; each interview section holds the user's answers word for
  word, or nothing, and a skeleton's section quotes the template's requirement; each pre-filled
  section holds only the drafter's wording of the result, and quotes only the corpus's text the
  caller read for it (`quotes`, decision 031).
- Facts match the classification: verified from the result alone, not by drafting again
  (`facts_check.py`): the stated facts, the class, Annex point and its certainty, the duty's
  date, the duty itself, and the result's law version and date.
"""

from collections.abc import Mapping, Sequence
from enum import Enum, StrEnum
from typing import Self

from pydantic import model_validator

from aiact.drafting.draft import (
    Answers,
    prefilled_section,
    small_company_note,
    supplied_section,
)
from aiact.drafting.facts_check import prefilled_problems
from aiact.drafting.models import DraftDocument, DraftSection, SizeClass
from aiact.drafting.prefill import DutyDateError
from aiact.drafting.registry import TEMPLATES
from aiact.drafting.templates import ClassificationSection, DocumentTemplate, SectionSpec
from aiact.schemas import Citation, ClassificationResult, Language
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


class Unknown(Enum):
    """A size class the caller didn't give (distinct from None, a company without a profile)."""

    SIZE_CLASS = "unknown"


SIZE_CLASS_UNKNOWN = Unknown.SIZE_CLASS

CompanySize = SizeClass | None | Unknown
"""The company profile's size class as a check gets it: a class, None for no profile, or
`SIZE_CLASS_UNKNOWN` when the caller doesn't say."""


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
    document: DraftDocument,
    result: ClassificationResult,
    answers: Answers,
    size_class: CompanySize = SIZE_CLASS_UNKNOWN,
    quotes: Sequence[Citation] = (),
) -> tuple[CheckResult, ...]:
    """All three checks on `document`, against the result, the answers, the company size class
    and the corpus quotes it was drafted from (see `check_nothing_invented`)."""
    return (
        check_sections_present(document),
        check_nothing_invented(document, result, answers, size_class, quotes),
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
    document: DraftDocument,
    result: ClassificationResult,
    answers: Answers,
    size_class: CompanySize = SIZE_CLASS_UNKNOWN,
    quotes: Sequence[Citation] = (),
) -> CheckResult:
    """Guarantees every word of the draft is the template's, the user's answer as given, or the
    drafter's wording of the result: no added section, sentence or paragraph, no answer moved to
    another question, and no section passing as another kind to escape the comparison. A
    quoting pre-filled section quotes exactly `quotes`, the corpus's text the caller read for
    the draft; no other section quotes anything but its template's requirement.

    With the company's `size_class` (None for no profile), the note must be exactly the one the
    template gives that company; without it, the template's note or none is accepted."""
    template = TEMPLATES.get(document.template)
    if template is None:
        return _outcome(CheckName.NOTHING_INVENTED, [f"unknown template {document.template!r}"])
    problems = []
    if document.title != template.title_for(answers, document.language):
        problems.append("the title is not the template's")
    if document.note not in _notes(template, document.language, size_class):
        problems.append("the note is not the template's")
    known = {spec.key for spec in template.sections}
    problems += [
        f"section {section.key!r} is not the template's"
        for section in document.sections
        if section.key not in known
    ]
    for spec, section in _pairs(template, document):
        problems += _invented(spec, section, document, template, result, answers, quotes)
    return _outcome(CheckName.NOTHING_INVENTED, problems)


def check_facts_match(document: DraftDocument, result: ClassificationResult) -> CheckResult:
    """Guarantees, from the result alone, that each pre-filled section states the result's facts
    (`facts_check.py`), that the draft answers its template's duty (for the vendor request, the
    article of the result's open question), and that it carries the result's law version and
    date."""
    template = TEMPLATES.get(document.template)
    if template is None:
        return _outcome(CheckName.FACTS_MATCH, [f"unknown template {document.template!r}"])
    problems = []
    if (document.law_version, document.as_of) != (result.law_version, result.as_of):
        problems.append("the law version or date differs from the result's")
    article = template.article_for(result)
    if document.article != article:
        problems.append(f"the duty {document.article} is not the template's {article}")
    for spec, section in _pairs(template, document):
        if isinstance(spec, ClassificationSection):
            problems += prefilled_problems(spec, section, result, document.language, article)
    return _outcome(CheckName.FACTS_MATCH, problems)


def _pairs(
    template: DocumentTemplate, document: DraftDocument
) -> list[tuple[SectionSpec, DraftSection]]:
    """Each of the draft's sections with the template section of its key; a section the template
    doesn't have is left out (missing ones are the sections check's to report)."""
    specs = {spec.key: spec for spec in template.sections}
    return [(specs[section.key], section) for section in document.sections if section.key in specs]


def _notes(
    template: DocumentTemplate, language: Language, size_class: CompanySize
) -> set[str | None]:
    """The notes a draft of `template` may carry: the one for `size_class`, or, when it is
    unknown, none or the template's small-company note."""
    if not isinstance(size_class, Unknown):
        return {small_company_note(template, size_class, language)}
    note = template.small_company_note
    return {None} if note is None else {None, note[language]}


def _repeated(keys: list[str]) -> list[str]:
    return sorted({key for key in keys if keys.count(key) > 1})


def _invented(
    spec: SectionSpec,
    section: DraftSection,
    document: DraftDocument,
    template: DocumentTemplate,
    result: ClassificationResult,
    answers: Answers,
    quotes: Sequence[Citation],
) -> list[str]:
    key, language = spec.key, document.language
    if section.heading != spec.heading[language]:
        return [f"section {key!r} has a heading the template doesn't give"]
    if isinstance(spec, ClassificationSection):
        return _prefill_invented(spec, section, template, result, language, quotes)
    if section.provenance is not spec.provenance:
        return [f"section {key!r} claims to come from {section.provenance.value}"]
    expected = supplied_section(spec, answers, language)
    if section.question_keys != expected.question_keys:
        return [f"section {key!r} answers another question"]
    if section.paragraphs != expected.paragraphs:
        return [f"section {key!r} holds content the user didn't supply"]
    if (section.requirement, section.quotes) != (expected.requirement, expected.quotes):
        return [f"section {key!r} quotes a requirement the template doesn't"]
    if (section.unanswered, section.status) != (expected.unanswered, expected.status):
        return [f"section {key!r} misstates what is left to answer"]
    return []


def _prefill_invented(
    spec: ClassificationSection,
    section: DraftSection,
    template: DocumentTemplate,
    result: ClassificationResult,
    language: Language,
    quotes: Sequence[Citation],
) -> list[str]:
    try:
        drafted = prefilled_section(spec, result, language, template.article_for(result), quotes)
    except DutyDateError:
        return [f"section {spec.key!r}: the result lists its duty with several dates"]
    if (section.provenance, section.paragraphs) != (drafted.provenance, drafted.paragraphs):
        return [f"section {spec.key!r} holds content the result doesn't give"]
    if section.requirement is not None:
        return [f"section {spec.key!r} quotes a requirement the template doesn't"]
    if section.quotes != drafted.quotes:
        return [f"section {spec.key!r} quotes a text the corpus doesn't give"]
    return []
