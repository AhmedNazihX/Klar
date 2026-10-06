"""`POST /classify`: one classification streamed as server-sent events (P1; decision 026,
Classify and ClassifyError).

The body is the engine's own `ClassifyRequest`, bounded before any paid call; it has no
retrieval options (`include_held_out`, `exclude_source_example_ids`), and an unknown field is a
422. The language comes from the interface, which detects it from the description or lets the
user pick it ("Detected language: …"). Each event is one SSE `data:` line holding the engine's
event as JSON, whose `event` field names it (`aiact.engine.events`):
- `facts`: the facts with their evidence tags and the questions they raise;
- `step_started` (the check is running), then `step` (done; paused when its status asks for more
  information), with `matches`, the Annex points the high-risk check weighed;
- `result`: the `ClassificationResult`, the last event; or
- `error`: the node that failed and a fixed, user-safe message; nothing follows it, so a run that
  failed never sends a class. The description and answers stay with the client.

Before the response starts, the run takes one of `CLASSIFY_MAX_CONCURRENT` slots (none free: a
503 with `Retry-After`, at once) and is set up, so a setup error (a missing model setting, the
amendment records unreadable) is a 503 too, before any paid call, not a broken stream. The run
is closed, and its slot freed, when the request ends, before the app returns: after the result,
or when the client leaves, in which case the node in progress finishes and no later node starts.
Nothing here logs or returns an exception's text or traceback: a failed node's error, whose
`__cause__` may quote the model's reply, ends as the `error` event (the engine logs its type).
"""

import logging
from collections.abc import AsyncIterator, Generator, Iterator
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.concurrency import iterate_in_threadpool
from fastapi.sse import EventSourceResponse

from aiact.api.dependencies import (
    ApiContext,
    api_context,
    client_key,
    limit_classify,
    node_builder,
)
from aiact.engine import ClassifyEvent, ClassifyRequest, stream_classification
from aiact.engine.classify import NodeBuilder
from aiact.llm import LLMConfigError

logger = logging.getLogger(__name__)

SETUP_ERRORS = (LLMConfigError, OSError)
"""What `stream_classification` raises before the first event (see its docstring)."""
UNAVAILABLE = "Classification is not available right now. Please try again later."
BUSY = "Klar is busy with other classifications. Please try again in a moment."
BUSY_RETRY_SECONDS = 10
"""`Retry-After` when every slot is taken; a classification takes about a minute."""

EVENTS_DESCRIPTION = (
    "The run's events, one JSON object per SSE `data:` line, named by its `event` field: "
    "`facts`, then `step_started` and `step` for each check, then `result` or `error`."
)
"""The stream's schema is each event's (`schema`, which the generated client types the stream
with; FastAPI's own `itemSchema` says the same in OpenAPI 3.2's form)."""

router = APIRouter()


def started_run(
    request: Request,
    body: ClassifyRequest,
    context: Annotated[ApiContext, Depends(api_context)],
    build_nodes: Annotated[NodeBuilder, Depends(node_builder)],
) -> Generator[Iterator[ClassifyEvent], None, None]:
    """The run's events, with a slot taken and the run set up before the response starts (in
    the threadpool). Raises a 503 when no slot is free (giving back the rate-limit count the
    request took, since it never ran) or the setup fails. When the request ends, however it
    ends, the run is closed and the slot freed."""
    slots = context.classify_slots
    if not slots.try_acquire():
        context.classify_limit.refund(client_key(request))
        logger.warning("classification refused: every slot is taken")
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            BUSY,
            headers={"Retry-After": str(BUSY_RETRY_SECONDS)},
        )
    try:
        try:
            events = stream_classification(body, settings=context.settings, build_nodes=build_nodes)
        except SETUP_ERRORS as exc:
            logger.error("classification setup failed: %s", type(exc).__name__)
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, UNAVAILABLE) from None
        try:
            yield events
        finally:
            # Closing ends the run's graph stream (it logs its cost); it never pulls more.
            if isinstance(events, Generator):
                events.close()
    finally:
        slots.release()


@router.post(
    "/classify",
    name="classify",
    response_class=EventSourceResponse,
    dependencies=[Depends(limit_classify)],
    responses={
        status.HTTP_200_OK: {"model": ClassifyEvent, "description": EVENTS_DESCRIPTION},
        status.HTTP_429_TOO_MANY_REQUESTS: {"description": "Too many classifications"},
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "description": "Every slot is taken (with Retry-After), or the engine is not configured"
        },
    },
)
async def classify(
    events: Annotated[Iterator[ClassifyEvent], Depends(started_run)],
) -> AsyncIterator[ClassifyEvent]:
    """Classify one AI system under the AI Act, streaming each step as it runs and then the
    result (or an `error` event, and no class, when a check fails). Guidance, not legal
    advice."""
    async for event in iterate_in_threadpool(events):
        yield event
