"""Drafting one document from its template, a classification result and the user's answers.

No model is involved: a draft holds the result's facts, the user's answers word for word, the
template's fixed wording and the requirements it quotes, nothing else (INIT > Documentation
drafting). Draft only from a result the backend validated, never from a row the browser wrote
(P3's audit). The deployer documents (`deployer.py`) and the skeletons (`skeletons/`) are both
drafted here.
"""

from collections.abc import Mapping

from aiact.drafting.models import (
    DraftDocument,
    DraftSection,
    Provenance,
    SectionStatus,
    SizeClass,
    status_for,
    unanswered_count,
)
from aiact.drafting.prefill import PREFILLS
from aiact.drafting.templates import (
    ClassificationSection,
    DocumentTemplate,
    InterviewSection,
    RequirementSection,
    SectionSpec,
    TemplateSection,
    section_questions,
)
from aiact.schemas import DISCLAIMER, ClassificationResult, Language

Answers = Mapping[str, str]
"""One template's interview answers by question key, as `interview_answers` stores them."""

SMALL_COMPANIES = frozenset({SizeClass.SME, SizeClass.SMC})
"""The size classes the simplified technical documentation form is for (Art. 11(1))."""


class UnknownQuestionError(ValueError):
    """An answer names a question the template doesn't ask."""


def draft_document(
    template: DocumentTemplate,
    result: ClassificationResult,
    answers: Answers,
    language: Language,
    size_class: SizeClass | None = None,
) -> DraftDocument:
    """One document: its sections in the template's order, each pre-filled, answered or fixed.
    `size_class` is the company profile's (None without a profile); it decides the template's
    small-company note. Raises UnknownQuestionError for an answer to a question the template
    doesn't ask, and DutyDateError when the result lists the document's duty with several
    dates."""
    asked = {question.key for question in template.questions}
    unknown = sorted(set(answers) - asked)
    if unknown:
        raise UnknownQuestionError(f"{template.id} asks no question {unknown}")
    sections = tuple(
        _section(spec, result, answers, language, template.article) for spec in template.sections
    )
    unanswered = unanswered_count(sections)
    return DraftDocument(
        template=template.id,
        title=template.title[language],
        article=template.article,
        language=language,
        note=small_company_note(template, size_class, language),
        sections=sections,
        unanswered=unanswered,
        status=status_for(unanswered),
        law_version=result.law_version,
        as_of=result.as_of,
        disclaimer=DISCLAIMER[language],
    )


def small_company_note(
    template: DocumentTemplate, size_class: SizeClass | None, language: Language
) -> str | None:
    """The template's note for an SME or a small mid-cap; None for any other company, or none
    known, and for a template without one."""
    if template.small_company_note is None or size_class not in SMALL_COMPANIES:
        return None
    return template.small_company_note[language]


def supplied_section(
    spec: TemplateSection | InterviewSection | RequirementSection,
    answers: Answers,
    language: Language,
) -> DraftSection:
    """The section the template or the user supplies: the fixed wording, or each answer as given
    (without surrounding blank space) in the order asked, with the questions still unanswered
    or answered blank, and the requirement it quotes."""
    if isinstance(spec, TemplateSection):
        return DraftSection(
            key=spec.key,
            heading=spec.heading[language],
            provenance=spec.provenance,
            paragraphs=(spec.text[language],),
            status=SectionStatus.DRAFTED,
        )
    given = [
        (question.key, answers.get(question.key, "").strip())
        for question in section_questions(spec)
    ]
    unanswered = tuple(key for key, answer in given if not answer)
    is_requirement = isinstance(spec, RequirementSection)
    return DraftSection(
        key=spec.key,
        heading=spec.heading[language],
        provenance=spec.provenance,
        paragraphs=tuple(answer for _, answer in given if answer),
        question_keys=tuple(key for key, _ in given),
        unanswered=unanswered,
        status=_waiting_status(spec) if unanswered else SectionStatus.DRAFTED,
        requirement=spec.requirement.citation(language) if is_requirement else None,
    )


def _waiting_status(spec: InterviewSection | RequirementSection) -> SectionStatus:
    return spec.waits_for if isinstance(spec, RequirementSection) else SectionStatus.QUESTIONS


def _section(
    spec: SectionSpec,
    result: ClassificationResult,
    answers: Answers,
    language: Language,
    article: str,
) -> DraftSection:
    if isinstance(spec, ClassificationSection):
        return prefilled_section(spec, result, language, article)
    return supplied_section(spec, answers, language)


def prefilled_section(
    spec: ClassificationSection, result: ClassificationResult, language: Language, article: str
) -> DraftSection:
    """The section from the result, or its fixed `empty` line when the result has nothing for
    it, so an empty pre-filled section never waits for an answer no one is asked for."""
    paragraphs = PREFILLS[spec.fill](result, language, article)
    if paragraphs or spec.empty is None:
        provenance = spec.provenance
    else:
        provenance, paragraphs = Provenance.TEMPLATE, (spec.empty[language],)
    return DraftSection(
        key=spec.key,
        heading=spec.heading[language],
        provenance=provenance,
        paragraphs=paragraphs,
        status=SectionStatus.DRAFTED,
    )
