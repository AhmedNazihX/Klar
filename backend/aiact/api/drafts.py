"""The documents a result calls for (P9; artboards Documents and DocSkeleton), one document per
request, so no request carries more than one document's answers:
- `POST /documents/list`: every document the result calls for, with its duty and interview;
- `POST /documents/draft`: one of them drafted with the user's answers, with its three automatic
  checks;
- `POST /documents/export`: that same draft as a Word or PDF file, once its checks pass.

The posted result is validated against the result contract and nothing more (`valid_result`):
it may be a row the browser wrote or an imported file, so no document takes the Act's text from
it (decision 031). A skeleton quotes its template's requirements; a vendor message quotes the
Art. 5(1) points read from the corpus (`law_quotes`, the vendor letter's). The answers are the
user's own, stored by the browser in `interview_answers`, each capped as the database caps it; a
key the template doesn't ask (a stale row) is left out and logged by count, never a 422.

An export renders a file, which costs CPU: it has its own rate limit (`RATE_LIMIT_EXPORTS`) and
renders in one of `EXPORT_MAX_CONCURRENT` worker processes (`aiact.api.files`, shared with the
reports: none free is a 503 with `Retry-After`, the rate-limit count given back). A file longer
than `MAX_FILE_CHARS` characters or `MAX_FILE_LINES` lines, counted on the texts as the
renderers draw them, is refused with a 413 before anything is rendered; since no cap on a text's
shape bounds what drawing it costs, a render past `EXPORT_TIMEOUT_SECONDS` is stopped and
refused with a 504 (`aiact.export.pool`). The routes are plain `def`: drafting runs in
FastAPI's threadpool, which waits there for the worker's file. Nothing here logs the result, a
fact or an answer, and no error quotes them; the drafter's refusals are mapped as the vendor
letter's route maps them (`refused_drafts`).
"""

import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import Field

from aiact.api.dependencies import ApiContext, api_context, limit_exports, limit_lookups
from aiact.api.documents import ResultJson, law_quotes, refused_drafts, valid_result
from aiact.api.errors import UNPROCESSABLE
from aiact.api.files import (
    FILE_RESPONSE,
    ExportFormat,
    Renderer,
    attachment,
    export_worker,
    refuse_too_long,
    rendered,
)
from aiact.drafting import LawQuotes, SizeClass
from aiact.drafting.documents import (
    CheckedDraft,
    ListedDocument,
    checked_draft,
    listed_documents,
)
from aiact.drafting.models import TEMPLATE_PATTERN
from aiact.drafting.paper import document_paper
from aiact.export import Paper, render_docx, render_pdf
from aiact.export.pool import RenderWorker
from aiact.schemas import Language
from aiact.schemas.base import ContractModel

logger = logging.getLogger(__name__)

MAX_ANSWER_CHARS = 20_000
"""As `interview_answers.answer` allows."""
MAX_QUESTION_KEY_CHARS = 200
"""As `interview_answers.question_key` allows."""
MAX_TEMPLATE_CHARS = 200
MAX_ANSWERS = 100
"""The longest interview asks 26 questions; the rest leaves room for stale rows."""
RENDERERS: dict[ExportFormat, Renderer] = {"docx": render_docx, "pdf": render_pdf}

CHECKS_FAILED = "The draft failed its automatic checks, so it can't be exported."
TOO_LONG = "This document is too long to make into a file. Please shorten some answers."
TIMED_OUT = (
    "Making this file took too long. Please try again; if it happens again, shorten some answers."
)

TemplateId = Annotated[str, Field(pattern=TEMPLATE_PATTERN, max_length=MAX_TEMPLATE_CHARS)]
StoredQuestionKey = Annotated[str, Field(min_length=1, max_length=MAX_QUESTION_KEY_CHARS)]
AnswerText = Annotated[str, Field(max_length=MAX_ANSWER_CHARS)]


class ListRequest(ContractModel):
    """A tool's classification result and the language of the list."""

    result: ResultJson
    language: Language = Field(description="The language of the titles and the questions.")


class DocumentList(ContractModel):
    """Every document the result calls for, in the order the documents list shows them."""

    documents: tuple[ListedDocument, ...]


class DraftRequest(ContractModel):
    """One document of the result, with the user's answers to its interview."""

    result: ResultJson
    template: TemplateId
    language: Language = Field(description="The language of the draft's wording and notice.")
    size_class: SizeClass | None = Field(
        default=None, description="The company profile's size class; null without a profile."
    )
    answers: Annotated[dict[StoredQuestionKey, AnswerText], Field(max_length=MAX_ANSWERS)] = Field(
        default_factory=dict, description="The answers stored for this document, by question key."
    )


class ExportRequest(DraftRequest):
    """One document as `draft_document` drafts it, and the file wanted."""

    format: ExportFormat


router = APIRouter(prefix="/documents", responses=UNPROCESSABLE)

DRAFT_ERRORS: dict[int | str, dict[str, Any]] = {
    status.HTTP_404_NOT_FOUND: {"description": "The result calls for no such document"},
    status.HTTP_429_TOO_MANY_REQUESTS: {"description": "Too many requests"},
    status.HTTP_503_SERVICE_UNAVAILABLE: {"description": "The corpus is unreachable"},
}


@router.post(
    "/list",
    name="list_result_documents",
    response_model=DocumentList,
    dependencies=[Depends(limit_lookups)],
    responses={status.HTTP_429_TOO_MANY_REQUESTS: {"description": "Too many requests"}},
)
def list_documents(body: ListRequest) -> DocumentList:
    """Every document the result calls for, with the duty it answers and its guided interview,
    not yet drafted."""
    return DocumentList(documents=listed_documents(valid_result(body.result), body.language))


@router.post(
    "/draft",
    name="draft_document",
    response_model=CheckedDraft,
    dependencies=[Depends(limit_lookups)],
    responses=DRAFT_ERRORS,
)
def draft(
    body: DraftRequest, quotes_from: Annotated[LawQuotes, Depends(law_quotes)]
) -> CheckedDraft:
    """One document drafted with the user's answers, its three automatic checks, and its
    interview. Labelled DRAFT, with the "guidance, not legal advice" notice."""
    return _checked(body, quotes_from)


@router.post(
    "/export",
    name="export_document",
    response_class=Response,
    dependencies=[Depends(limit_exports)],
    responses={
        status.HTTP_200_OK: FILE_RESPONSE,
        **DRAFT_ERRORS,
        status.HTTP_409_CONFLICT: {"description": "The draft failed its automatic checks"},
        status.HTTP_413_CONTENT_TOO_LARGE: {"description": "The document is too long for a file"},
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "description": "Every export slot is taken, or the corpus is unreachable"
        },
        status.HTTP_504_GATEWAY_TIMEOUT: {"description": "The file took too long to make"},
    },
)
def export(
    request: Request,
    body: ExportRequest,
    quotes_from: Annotated[LawQuotes, Depends(law_quotes)],
    context: Annotated[ApiContext, Depends(api_context)],
) -> Response:
    """One document as a Word (.docx) or PDF file: the draft `draft_document` returns for the
    same body, and only once all three automatic checks pass."""
    checked = _checked(body, quotes_from)
    failed = [check.check.value for check in checked.checks if not check.passed]
    if failed:
        logger.error("export of %s refused: checks failed: %s", body.template, failed)
        raise HTTPException(status.HTTP_409_CONFLICT, CHECKS_FAILED)
    paper = document_paper(checked.document)
    refuse_too_long(paper, TOO_LONG)
    with export_worker(request, context) as worker:
        content = _rendered(worker, body.format, paper)
    return attachment(content, body.format, body.template)  # a template id: [a-z0-9_] only


def _checked(body: DraftRequest, quotes_from: LawQuotes) -> CheckedDraft:
    """The document drafted and checked, or the HTTP error that says why it can't be."""
    result = valid_result(body.result)
    with refused_drafts():
        return checked_draft(
            body.template, result, body.answers, body.language, body.size_class, quotes_from
        )


def _rendered(worker: RenderWorker, file_format: ExportFormat, paper: Paper) -> bytes:
    """The file, rendered in `worker`'s process (`RENDERERS`, looked up here so a test can swap
    one)."""
    return rendered(worker, RENDERERS[file_format], paper, TIMED_OUT)
