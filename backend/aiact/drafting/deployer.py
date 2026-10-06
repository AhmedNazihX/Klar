"""Drafting the short deployer documents from a classification result and the user's answers.

No model is involved: a draft holds the result's facts, the user's answers word for word and the
template's fixed wording, nothing else (INIT > Documentation drafting). Draft only from a result
the backend validated, never from a row the browser wrote (P3's audit).
"""

from collections.abc import Mapping

from aiact.drafting.models import DraftDocument, DraftSection, status_for, unanswered_count
from aiact.drafting.templates import (
    DEPLOYER_TEMPLATES,
    ClassificationSection,
    DocumentTemplate,
    InterviewSection,
    SectionSpec,
    TemplateSection,
)
from aiact.schemas import DISCLAIMER, ClassificationResult, Language

Answers = Mapping[str, str]
"""One template's interview answers by question key, as `interview_answers` stores them."""


class UnknownQuestionError(ValueError):
    """An answer names a question the template doesn't ask."""


def deployer_templates_for(result: ClassificationResult) -> tuple[DocumentTemplate, ...]:
    """The documents the result calls for: one per Art. 26 duty it lists, and one disclosure text
    per Art. 50 duty it lists that has a text to show."""
    articles = {obligation.article for obligation in result.obligations}
    articles |= set(result.transparency_duties)
    return tuple(template for template in DEPLOYER_TEMPLATES if template.article in articles)


def draft_deployer_documents(
    result: ClassificationResult,
    answers: Mapping[str, Answers],
    language: Language,
) -> tuple[DraftDocument, ...]:
    """Every document the result calls for, drafted with the answers given per template id.
    Answers for a template the result doesn't call for are kept for a later run, not used."""
    return tuple(
        draft_document(template, result, answers.get(template.id, {}), language)
        for template in deployer_templates_for(result)
    )


def draft_document(
    template: DocumentTemplate,
    result: ClassificationResult,
    answers: Answers,
    language: Language,
) -> DraftDocument:
    """One document: its sections in the template's order, each pre-filled, answered or fixed.
    Raises UnknownQuestionError for an answer to a question the template doesn't ask."""
    asked = {question.question_key for question in template.questions}
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
        sections=sections,
        unanswered=unanswered,
        status=status_for(unanswered),
        law_version=result.law_version,
        as_of=result.as_of,
        disclaimer=DISCLAIMER[language],
    )


def supplied_paragraphs(
    spec: TemplateSection | InterviewSection, answers: Answers, language: Language
) -> tuple[str, ...]:
    """What a section the user or the template supplies must hold: the fixed wording, or the
    answer as given (without surrounding blank space); nothing while unanswered or blank."""
    if isinstance(spec, TemplateSection):
        return (spec.text[language],)
    answer = answers.get(spec.question_key, "").strip()
    return (answer,) if answer else ()


def _section(
    spec: SectionSpec,
    result: ClassificationResult,
    answers: Answers,
    language: Language,
    article: str,
) -> DraftSection:
    paragraphs = (
        spec.prefill(result, language, article)
        if isinstance(spec, ClassificationSection)
        else supplied_paragraphs(spec, answers, language)
    )
    return DraftSection(
        key=spec.key,
        heading=spec.heading[language],
        provenance=spec.provenance,
        paragraphs=paragraphs,
        question_key=spec.question_key if isinstance(spec, InterviewSection) else None,
    )
