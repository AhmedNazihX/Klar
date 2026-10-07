"""Every document a result calls for, drafted with the user's answers and checked, with the
interview that fills it (P9): what the Documents screen shows for one tool, and what an export
starts from.

The result must be one the backend validated (the API parses it against the result contract),
never a row the browser wrote and the drafter trusted (P3's audit). The company's size class is
the profile's, passed in by the caller (P19), for the skeletons' note and its check.
"""

from collections.abc import Mapping

from pydantic import Field

from aiact.drafting.checks import CheckResult, run_checks
from aiact.drafting.deployer import deployer_templates_for, draft_deployer_documents
from aiact.drafting.draft import Answers, draft_document
from aiact.drafting.models import DraftDocument, QuestionKey, SizeClass
from aiact.drafting.registry import TEMPLATES
from aiact.drafting.skeletons import draft_skeletons, skeleton_templates_for
from aiact.drafting.templates import DocumentTemplate, section_questions
from aiact.schemas import ClassificationResult, Language
from aiact.schemas.base import ContractModel


class InterviewQuestion(ContractModel):
    """One question of a document's guided interview, and the section its answer fills."""

    key: QuestionKey
    text: str = Field(min_length=1)
    section: str = Field(description="The key of the section the answer fills.")


class CheckedDraft(ContractModel):
    """A drafted document, its three automatic checks and its interview, in the order asked."""

    document: DraftDocument
    checks: tuple[CheckResult, ...]
    questions: tuple[InterviewQuestion, ...]


class DocumentNotCalledForError(LookupError):
    """The result calls for no document with that template id."""


def templates_for(result: ClassificationResult) -> tuple[DocumentTemplate, ...]:
    """The documents the result calls for: the short deployer documents, then the skeletons."""
    return (*deployer_templates_for(result), *skeleton_templates_for(result))


def checked_drafts(
    result: ClassificationResult,
    answers: Mapping[str, Answers],
    language: Language,
    size_class: SizeClass | None,
) -> tuple[CheckedDraft, ...]:
    """Every document the result calls for, drafted with the answers given per template id and
    checked against the result, those answers and the size class. Answers for a template the
    result doesn't call for are kept for a later run, not used."""
    drafted = (
        *draft_deployer_documents(result, answers, language),
        *draft_skeletons(result, answers, language, size_class),
    )
    return tuple(
        _checked(document, result, answers.get(document.template, {}), size_class)
        for document in drafted
    )


def checked_draft(
    template_id: str,
    result: ClassificationResult,
    answers: Answers,
    language: Language,
    size_class: SizeClass | None,
) -> CheckedDraft:
    """The document `template_id`, drafted and checked as `checked_drafts` does. Raises
    DocumentNotCalledForError when the result doesn't call for it."""
    template = next((t for t in templates_for(result) if t.id == template_id), None)
    if template is None:
        raise DocumentNotCalledForError(template_id)
    document = draft_document(template, result, answers, language, size_class)
    return _checked(document, result, answers, size_class)


def _checked(
    document: DraftDocument,
    result: ClassificationResult,
    answers: Answers,
    size_class: SizeClass | None,
) -> CheckedDraft:
    template = TEMPLATES[document.template]
    return CheckedDraft(
        document=document,
        checks=run_checks(document, result, answers, size_class),
        questions=interview(template, document.language),
    )


def interview(template: DocumentTemplate, language: Language) -> tuple[InterviewQuestion, ...]:
    """The template's questions in the order its sections ask them."""
    return tuple(
        InterviewQuestion(key=question.key, text=question.text[language], section=spec.key)
        for spec in template.sections
        for question in section_questions(spec)
    )
