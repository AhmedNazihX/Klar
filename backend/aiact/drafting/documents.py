"""Every document a result calls for, with the interview that fills it, and one of them drafted
with the user's answers and checked (P9): what the Documents screen lists for one tool, what it
shows for the document picked, and what an export starts from.

A posted result is only checked against the result contract, so a document never takes the
Act's text from it (decision 031): a skeleton quotes its template's requirements, and a vendor
message's Art. 5(1) points are read from the corpus (`quoted_points`, through the caller's
`LawQuotes`). The company's size class is the profile's, passed in by the caller (P19), for the
skeletons' note and its check. The screen and the files draft through the one `checked_draft`,
so a file always holds the draft on screen.
"""

from collections.abc import Sequence

from pydantic import Field

from aiact.drafting.checks import CheckResult, run_checks
from aiact.drafting.deployer import deployer_templates_for
from aiact.drafting.draft import Answers, draft_document
from aiact.drafting.models import TEMPLATE_PATTERN, DraftDocument, QuestionKey, SizeClass
from aiact.drafting.prefill import QUOTING_FILLS
from aiact.drafting.skeletons import skeleton_templates_for
from aiact.drafting.templates import ClassificationSection, DocumentTemplate, section_questions
from aiact.drafting.vendor_letters.draft import vendor_letter_for
from aiact.drafting.vendor_letters.quotes import LawQuotes, quoted_points
from aiact.schemas import Citation, ClassificationResult, Language
from aiact.schemas.base import ContractModel


class InterviewChoice(ContractModel):
    """One answer a choice question offers: the key stored as the answer, and its label."""

    key: QuestionKey
    label: str = Field(min_length=1)


class InterviewQuestion(ContractModel):
    """One question of a document's guided interview, and the section its answer fills. A choice
    question lists its `choices`; its answer is one of their keys."""

    key: QuestionKey
    text: str = Field(min_length=1)
    section: str = Field(description="The key of the section the answer fills.")
    choices: tuple[InterviewChoice, ...] = ()


class ListedDocument(ContractModel):
    """A document the result calls for, as the documents list shows it before it is drafted."""

    template: str = Field(pattern=TEMPLATE_PATTERN)
    title: str = Field(min_length=1)
    article: str = Field(min_length=1, description="The duty it answers, e.g. `art:26:7`.")
    questions: tuple[InterviewQuestion, ...]


class CheckedDraft(ContractModel):
    """A drafted document, its three automatic checks and its interview, in the order asked."""

    document: DraftDocument
    checks: tuple[CheckResult, ...]
    questions: tuple[InterviewQuestion, ...]


class DocumentNotCalledForError(LookupError):
    """The result calls for no document with that template id."""


def templates_for(result: ClassificationResult) -> tuple[DocumentTemplate, ...]:
    """The documents the result calls for: the short deployer documents, the skeletons, then the
    vendor letter (P28), in the order the documents list shows them."""
    letter = vendor_letter_for(result)
    return (
        *deployer_templates_for(result),
        *skeleton_templates_for(result),
        *((letter,) if letter is not None else ()),
    )


def listed_documents(
    result: ClassificationResult, language: Language
) -> tuple[ListedDocument, ...]:
    """Every document the result calls for, with its title, duty and interview in `language`."""
    return tuple(
        ListedDocument(
            template=template.id,
            title=template.title[language],
            article=template.article_for(result),
            questions=interview(template, language),
        )
        for template in templates_for(result)
    )


def checked_draft(
    template_id: str,
    result: ClassificationResult,
    answers: Answers,
    language: Language,
    size_class: SizeClass | None,
    law_quotes: LawQuotes,
) -> CheckedDraft:
    """The document `template_id`, drafted with its answers and checked against the result,
    those answers, the size class and the corpus quotes it was drafted from. Raises
    DocumentNotCalledForError when the result doesn't call for it, UnknownPointError when it
    quotes a point the corpus doesn't have, and DutyDateError when the result lists its duty
    with several dates."""
    template = next((t for t in templates_for(result) if t.id == template_id), None)
    if template is None:
        raise DocumentNotCalledForError(template_id)
    quotes = _quotes(template, result, language, law_quotes)
    document = draft_document(template, result, answers, language, size_class, quotes)
    return CheckedDraft(
        document=document,
        checks=run_checks(document, result, answers, size_class, quotes),
        questions=interview(template, language),
    )


def _quotes(
    template: DocumentTemplate,
    result: ClassificationResult,
    language: Language,
    law_quotes: LawQuotes,
) -> Sequence[Citation]:
    """The corpus's text of the provisions the template's quoting sections quote; none (and no
    corpus read) for a template without one."""
    quotes_the_act = any(
        isinstance(spec, ClassificationSection) and spec.fill in QUOTING_FILLS
        for spec in template.sections
    )
    return quoted_points(result, language, law_quotes) if quotes_the_act else ()


def interview(template: DocumentTemplate, language: Language) -> tuple[InterviewQuestion, ...]:
    """The template's questions in the order its sections ask them."""
    return tuple(
        InterviewQuestion(
            key=question.key,
            text=question.text[language],
            section=spec.key,
            choices=tuple(
                InterviewChoice(key=choice.key, label=choice.label[language])
                for choice in question.choices
            ),
        )
        for spec in template.sections
        for question in section_questions(spec)
    )
