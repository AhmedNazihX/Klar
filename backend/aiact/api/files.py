"""Making a file from a `Paper`, for every route that returns one (the drafted documents, P9; the
reports, P25): the length cap checked before anything is rendered, a render in one of the export
workers (none free: a 503 with `Retry-After`, the rate-limit count given back), stopped past its
time limit (a 504), and the file as an attachment.

A file longer than `MAX_FILE_CHARS` characters or `MAX_FILE_LINES` lines, counted on the texts as
the renderers draw them, is refused with a 413. Nothing here logs a text of the paper.
"""

import logging
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Any, Literal

from fastapi import HTTPException, Request, Response, status

from aiact.api.dependencies import ApiContext, client_key
from aiact.export import Paper, block_texts
from aiact.export.pool import RenderTimeout, RenderWorker
from aiact.export.text import printable

logger = logging.getLogger(__name__)

MAX_FILE_CHARS = 120_000
"""The longest file, in characters: about 40 pages."""
MAX_FILE_LINES = 2_000
"""The most lines a file's texts may hold, so line breaks can't make thousands of pages."""
BUSY_RETRY_SECONDS = 5
"""`Retry-After` when every export slot is taken; a file takes well under a second."""

DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
PDF = "application/pdf"
ExportFormat = Literal["docx", "pdf"]
MEDIA_TYPES: dict[ExportFormat, str] = {"docx": DOCX, "pdf": PDF}

BUSY = "Klar is busy making other files. Please try again in a moment."

FILE_RESPONSE: dict[str, Any] = {
    "description": "The file (an attachment)",
    "content": {media: {"schema": {"type": "string", "format": "binary"}} for media in (DOCX, PDF)},
}
FILE_ERRORS: dict[int | str, dict[str, Any]] = {
    status.HTTP_413_CONTENT_TOO_LARGE: {"description": "The document is too long for a file"},
    status.HTTP_429_TOO_MANY_REQUESTS: {"description": "Too many requests"},
    status.HTTP_503_SERVICE_UNAVAILABLE: {"description": "Every export slot is taken"},
    status.HTTP_504_GATEWAY_TIMEOUT: {"description": "The file took too long to make"},
}

Renderer = Callable[[Paper], bytes]


def refuse_too_long(paper: Paper, too_long: str, *, max_lines: int = MAX_FILE_LINES) -> None:
    """A 413 saying `too_long` for a file over `MAX_FILE_CHARS` characters or `max_lines` lines,
    counted on the texts its blocks draw as the renderers draw them (`printable`: every `\\r\\n`
    and lone `\\r` a line break), so no line break gets past the count. Each text counts as a
    line at least, a table's cells too."""
    texts = [printable(text) for block in paper.blocks for text in block_texts(block)]
    chars = sum(len(text) for text in texts)
    lines = sum(text.count("\n") + 1 for text in texts)
    if chars > MAX_FILE_CHARS or lines > max_lines:
        logger.warning("export refused: %d characters, %d lines", chars, lines)
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, too_long)


def rendered(worker: RenderWorker, render: Renderer, paper: Paper, timed_out: str) -> bytes:
    """The file, rendered in `worker`'s process; a 504 saying `timed_out` when it runs past the
    time limit. The limit is wall-clock time, so a busy host can trip it on a normal document:
    the message says to try again."""
    try:
        return worker.run(render, paper)
    except RenderTimeout:
        logger.warning("export refused: the render ran past %g seconds", worker.timeout_seconds)
        raise HTTPException(status.HTTP_504_GATEWAY_TIMEOUT, timed_out) from None


@contextmanager
def export_worker(request: Request, context: ApiContext) -> Iterator[RenderWorker]:
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


def attachment(content: bytes, file_format: ExportFormat, stem: str) -> Response:
    """The file as an attachment named `stem` and the format's extension; `stem` is the
    caller's own ([a-z0-9_-] only), never a text from the request."""
    return Response(
        content,
        media_type=MEDIA_TYPES[file_format],
        headers={"Content-Disposition": f'attachment; filename="{stem}.{file_format}"'},
    )
