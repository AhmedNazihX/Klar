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
renders in one of `EXPORT_MAX_CONCURRENT` worker processes (none free: a 503 with
`Retry-After`, the rate-limit count given back). A file longer than `MAX_FILE_CHARS`
characters or `MAX_FILE_LINES` lines, counted on the texts as the renderers draw them, is
refused with a 413 before anything is rendered; since no cap on a text's shape bounds what
drawing it costs, a render past `EXPORT_TIMEOUT_SECONDS` is stopped and refused with the same
413 (`aiact.export.pool`). The routes are plain `def`: drafting runs in FastAPI's threadpool,
which waits there for the worker's file. Nothing here logs the result, a fact or an answer, and
no error quotes them; the drafter's refusals are mapped as the vendor letter's route maps them
(`refused_drafts`).
"""

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import Field

from aiact.api.dependencies import (
    ApiContext,
    api_context,
    client_key,
    limit_exports,
    limit_lookups,
)
from aiact.api.documents import ResultJson, law_quotes, refused_drafts, valid_result
from aiact.api.errors import UNPROCESSABLE
from aiact.drafting import LawQuotes, SizeClass
from aiact.drafting.documents import (
    CheckedDraft,
    ListedDocument,
    checked_draft,
    listed_documents,
)
from aiact.drafting.models import TEMPLATE_PATTERN
from aiact.drafting.paper import document_paper
from aiact.export import Block, Paper, Quote, render_docx, render_pdf
from aiact.export.pool import RenderTimeout, RenderWorker
from aiact.export.text import printable
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
MAX_FILE_CHARS = 120_000
"""The longest draft made into a file, in characters: about 40 pages."""
MAX_FILE_LINES = 2_000
"""The most lines a file's texts may hold, so line breaks can't make thousands of pages."""
BUSY_RETRY_SECONDS = 5
"""`Retry-After` when every export slot is taken; a file takes well under a second."""

DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
PDF = "application/pdf"
MEDIA_TYPES = {"docx": DOCX, "pdf": PDF}
RENDERERS = {"docx": render_docx, "pdf": render_pdf}

CHECKS_FAILED = "The draft failed its automatic checks, so it can't be exported."
TOO_LONG = "This document is too long to make into a file. Please shorten some answers."
BUSY = "Klar is busy making other files. Please try again in a moment."
TIMED_OUT = (
    "Making this file took too long. Please try again; if it happens again, shorten some answers."
)

TemplateId = Annotated[str, Field(pattern=TEMPLATE_PATTERN, max_length=MAX_TEMPLATE_CHARS)]
StoredQuestionKey = Annotated[str, Field(min_length=1, max_length=MAX_QUESTION_KEY_CHARS)]
AnswerText = Annotated[str, Field(max_length=MAX_ANSWER_CHARS)]
ExportFormat = Literal["docx", "pdf"]


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
FILE_RESPONSE: dict[str, Any] = {
    "description": "The document as a file (an attachment)",
    "content": {media: {"schema": {"type": "string", "format": "binary"}} for media in (DOCX, PDF)},
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
    _refuse_too_long(paper)
    with _export_worker(request, context) as worker:
        content = _rendered(worker, body.format, paper)
    filename = f"{body.template}.{body.format}"  # a template id: [a-z0-9_] only
    return Response(
        content,
        media_type=MEDIA_TYPES[body.format],
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _checked(body: DraftRequest, quotes_from: LawQuotes) -> CheckedDraft:
    """The document drafted and checked, or the HTTP error that says why it can't be."""
    result = valid_result(body.result)
    with refused_drafts():
        return checked_draft(
            body.template, result, body.answers, body.language, body.size_class, quotes_from
        )


def _refuse_too_long(paper: Paper) -> None:
    """A 413 for a file over `MAX_FILE_CHARS` characters or `MAX_FILE_LINES` lines, counted on
    the texts its blocks draw as the renderers draw them (`printable`: every `\r\n` and lone
    `\r` a line break), so no line break gets past the count."""
    texts = [printable(text) for block in paper.blocks for text in _block_texts(block)]
    chars = sum(len(text) for text in texts)
    lines = sum(text.count("\n") + 1 for text in texts)
    if chars > MAX_FILE_CHARS or lines > MAX_FILE_LINES:
        logger.warning("export refused: %d characters, %d lines", chars, lines)
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, TOO_LONG)


def _block_texts(block: Block) -> tuple[str, ...]:
    """The texts a block draws: a quote's source line too."""
    return (block.text, block.source) if isinstance(block, Quote) else (block.text,)


def _rendered(worker: RenderWorker, file_format: ExportFormat, paper: Paper) -> bytes:
    """The file, rendered in `worker`'s process; a 504 when it runs past the time limit. The limit
    is wall-clock time, so a busy host can trip it on a normal document: the message says to try
    again, not that the document is too long."""
    try:
        return worker.run(RENDERERS[file_format], paper)
    except RenderTimeout:
        logger.warning("export refused: the render ran past %g seconds", worker.timeout_seconds)
        raise HTTPException(status.HTTP_504_GATEWAY_TIMEOUT, TIMED_OUT) from None


@contextmanager
def _export_worker(request: Request, context: ApiContext) -> Iterator[RenderWorker]:
    """One of the export workers while a file renders; a 503 when none is free, giving back the
    rate-limit count the request took, since it made no file."""
    slots = context.export_slots
    worker = slots.try_acquire()
    if worker is None:
        context.export_limit.refund(client_key(request))
        logger.warning("export refused: every slot is taken")
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            BUSY,
            headers={"Retry-After": str(BUSY_RETRY_SECONDS)},
        )
    try:
        yield worker
    finally:
        slots.release(worker)
