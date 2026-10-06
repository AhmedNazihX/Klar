"""A cap on request bodies (P1): a body over `max_bytes` is answered with 413 before it is read.

A `Content-Length` over the cap is refused before the app runs. A body without one (chunked)
is counted as it arrives, and the read that crosses the cap raises the 413 as an
`HTTPException`, which FastAPI's own error handling answers; the middleware answers it itself
when the exception reaches it before a response has started.
"""

from fastapi import HTTPException, status
from starlette.types import ASGIApp, Message, Receive, Scope, Send

TOO_LARGE = "The request is too large."


class BodySizeLimit:
    """ASGI middleware that refuses HTTP request bodies over `max_bytes` with 413."""

    def __init__(self, app: ASGIApp, max_bytes: int) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        declared = _content_length(scope)
        if declared is not None and declared > self.max_bytes:
            await _too_large(send)
            return
        received = 0
        started = False

        async def counting_receive() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_bytes:
                    raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, TOO_LARGE)
            return message

        async def tracking_send(message: Message) -> None:
            nonlocal started
            started = started or message["type"] == "http.response.start"
            await send(message)

        try:
            await self.app(scope, counting_receive, tracking_send)
        except HTTPException as exc:
            if exc.status_code != status.HTTP_413_CONTENT_TOO_LARGE or started:
                raise
            await _too_large(send)


def _content_length(scope: Scope) -> int | None:
    """The declared length, or None when there is none (or the server let a malformed one
    through): the body is then counted as it arrives."""
    for name, value in scope["headers"]:
        if name == b"content-length" and value.isdigit():
            return int(value)
    return None


async def _too_large(send: Send) -> None:
    body = b'{"detail":"' + TOO_LARGE.encode() + b'"}'
    await send(
        {
            "type": "http.response.start",
            "status": status.HTTP_413_CONTENT_TOO_LARGE,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode()),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})
