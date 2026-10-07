"""The documents a result calls for (P9; artboards Documents and DocSkeleton):
`POST /documents/drafts` drafts, checks and lists every one with its guided interview, and
`POST /documents/export` hands one over as a Word or PDF file.

The browser sends the result and the user's answers; the answers are the user's own, stored by
the browser in `interview_answers` (system, user, template, question key). The result is parsed
against the result contract here, and the drafts are built only from that parsed result, never
from a stored row taken on trust (P3's audit). Each answer is capped as the database caps it;
a key the template doesn't ask (a stale row) is left out and logged by count, never a 422, so one
old row can't block a document. The routes are plain `def`: drafting and rendering are CPU work,
which FastAPI runs in its threadpool. Nothing here logs an answer, a fact or the description.
"""

import logging
from collections.abc import Mapping
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import Field, ValidationError

from aiact.api.dependencies import limit_lookups
from aiact.drafting import DutyDateError, SizeClass
from aiact.drafting.documents import (
    CheckedDraft,
    DocumentNotCalledForError,
    checked_draft,
    checked_drafts,
)
from aiact.drafting.models import TEMPLATE_PATTERN
from aiact.drafting.paper import document_paper
from aiact.export import render_docx, render_pdf
from aiact.schemas import ClassificationResult, Language
from aiact.schemas.base import ContractModel

logger = logging.getLogger(__name__)

MAX_ANSWER_CHARS = 20_000
"""As `interview_answers.answer` allows."""
MAX_QUESTION_KEY_CHARS = 200
"""As `interview_answers.question_key` allows."""
MAX_TEMPLATE_CHARS = 200
MAX_ANSWERS_PER_TEMPLATE = 100
"""The longest interview asks 26 questions; the rest leaves room for stale rows."""
MAX_TEMPLATES = 20
"""Nine templates exist; the rest leaves room for stale rows and the vendor letters (P28)."""

DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
PDF = "application/pdf"
MEDIA_TYPES = {"docx": DOCX, "pdf": PDF}

NOT_CALLED_FOR = "This result calls for no such document."
SEVERAL_DATES = "The result lists this document's duty with several dates, so it can't be drafted."
CHECKS_FAILED = "The draft failed its automatic checks, so it can't be exported."

TemplateId = Annotated[str, Field(pattern=TEMPLATE_PATTERN, max_length=MAX_TEMPLATE_CHARS)]
StoredQuestionKey = Annotated[str, Field(min_length=1, max_length=MAX_QUESTION_KEY_CHARS)]
AnswerText = Annotated[str, Field(max_length=MAX_ANSWER_CHARS)]
TemplateAnswers = Annotated[
    dict[StoredQuestionKey, AnswerText], Field(max_length=MAX_ANSWERS_PER_TEMPLATE)
]
ExportFormat = Literal["docx", "pdf"]

PostedResult = Annotated[
    dict[str, object],
    Field(
        description="A ClassificationResult as `POST /classify` returned it. It is parsed against "
        "the result contract (a result that breaks it is a 422), and the drafts are built from "
        "the parsed result."
    ),
]
"""Parsed in the route (`parsed_result`), not by the request model: a result model in a request
would make pydantic split its schema into an input and an output one, renaming the frontend's
`ClassificationResult` type."""


class DraftsRequest(ContractModel):
    """A tool's classification result and the user's answers, by template id."""

    result: PostedResult
    language: Language = Field(description="The language of the drafts' wording and notice.")
    size_class: SizeClass | None = Field(
        default=None, description="The company profile's size class; null without a profile."
    )
    answers: Annotated[dict[TemplateId, TemplateAnswers], Field(max_length=MAX_TEMPLATES)] = Field(
        default_factory=dict
    )


class ExportRequest(ContractModel):
    """One document of the result, its answers and the file wanted."""

    result: PostedResult
    template: TemplateId
    language: Language
    size_class: SizeClass | None = None
    answers: TemplateAnswers = Field(default_factory=dict)
    format: ExportFormat


class DraftList(ContractModel):
    """Every document the result calls for, in the order the documents list shows them."""

    documents: tuple[CheckedDraft, ...]


router = APIRouter(dependencies=[Depends(limit_lookups)])

FILE_RESPONSE: dict[str, Any] = {
    "description": "The document as a file (an attachment)",
    "content": {media: {"schema": {"type": "string", "format": "binary"}} for media in (DOCX, PDF)},
}


@router.post(
    "/documents/drafts",
    name="draft_documents",
    response_model=DraftList,
    responses={status.HTTP_422_UNPROCESSABLE_CONTENT: {"description": "Not a valid request"}},
)
def drafts(body: DraftsRequest) -> DraftList:
    """Drafts every document the result calls for with the user's answers, runs the three
    automatic checks on each, and lists each one's interview questions. Every draft is labelled
    DRAFT and carries the "guidance, not legal advice" notice."""
    result = parsed_result(body.result)
    try:
        documents = checked_drafts(result, body.answers, body.language, body.size_class)
    except DutyDateError:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, SEVERAL_DATES) from None
    return DraftList(documents=documents)


@router.post(
    "/documents/export",
    name="export_document",
    response_class=Response,
    responses={
        status.HTTP_200_OK: FILE_RESPONSE,
        status.HTTP_404_NOT_FOUND: {"description": "The result calls for no such document"},
        status.HTTP_409_CONFLICT: {"description": "The draft failed its automatic checks"},
    },
)
def export(body: ExportRequest) -> Response:
    """One document as a Word (.docx) or PDF file, drafted as `draft_documents` drafts it, and
    only once all three automatic checks pass."""
    result = parsed_result(body.result)
    try:
        checked = checked_draft(body.template, result, body.answers, body.language, body.size_class)
    except DocumentNotCalledForError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, NOT_CALLED_FOR) from None
    except DutyDateError:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, SEVERAL_DATES) from None
    failed = [check.check.value for check in checked.checks if not check.passed]
    if failed:
        logger.error("export of %s refused: checks failed: %s", body.template, failed)
        raise HTTPException(status.HTTP_409_CONFLICT, CHECKS_FAILED)
    paper = document_paper(checked.document)
    content = render_pdf(paper) if body.format == "pdf" else render_docx(paper)
    filename = f"{body.template}.{body.format}"  # a template id: [a-z0-9_] only
    return Response(
        content,
        media_type=MEDIA_TYPES[body.format],
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def parsed_result(posted: Mapping[str, object]) -> ClassificationResult:
    """The posted result, parsed against the result contract. A result that breaks it is a 422
    naming where and why, without echoing the values sent."""
    try:
        return ClassificationResult.model_validate(posted)
    except ValidationError as error:
        problems = [
            {
                "loc": ["body", "result", *problem["loc"]],
                "msg": problem["msg"],
                "type": problem["type"],
            }
            for problem in error.errors(
                include_url=False, include_context=False, include_input=False
            )
        ]
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, problems) from None
