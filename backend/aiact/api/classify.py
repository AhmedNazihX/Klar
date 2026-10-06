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

The run is set up before the response starts, so a setup error (a missing model setting, the
amendment records unreadable) is a 503, not a broken stream. Nothing here logs or returns an
exception's text or traceback: a failed node's error, whose `__cause__` may quote the model's
reply, ends as the `error` event (the engine logs only its type). When the client disconnects,
the run stops: the node in progress finishes, no later node starts.
"""

import logging
from collections.abc import AsyncIterator, Generator, Iterator
from typing import Annotated

import anyio
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.concurrency import iterate_in_threadpool, run_in_threadpool
from fastapi.sse import EventSourceResponse

from aiact.api.dependencies import ApiContext, Bucket, api_context, node_builder, rate_limited
from aiact.engine import ClassifyEvent, ClassifyRequest, stream_classification
from aiact.engine.classify import NodeBuilder
from aiact.llm import LLMConfigError

logger = logging.getLogger(__name__)

SETUP_ERRORS = (LLMConfigError, OSError)
"""What `stream_classification` raises before the first event (see its docstring)."""
UNAVAILABLE = "Classification is not available right now. Please try again later."

EVENTS_DESCRIPTION = (
    "The run's events, one JSON object per SSE `data:` line, named by its `event` field: "
    "`facts`, then `step_started` and `step` for each check, then `result` or `error`."
)
"""The stream's schema is each event's (`schema`, which the generated client types the stream
with; FastAPI's own `itemSchema` says the same in OpenAPI 3.2's form)."""

router = APIRouter()


def started_run(
    body: ClassifyRequest,
    context: Annotated[ApiContext, Depends(api_context)],
    build_nodes: Annotated[NodeBuilder, Depends(node_builder)],
) -> Generator[ClassifyEvent, None, None]:
    """The run's events, set up here (in the threadpool, before the response starts). Raises a
    503 when the setup fails."""
    try:
        events = stream_classification(body, settings=context.settings, build_nodes=build_nodes)
    except SETUP_ERRORS as exc:
        logger.error("classification setup failed: %s", type(exc).__name__)
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, UNAVAILABLE) from None
    return _closable(events)


def _closable(events: Iterator[ClassifyEvent]) -> Generator[ClassifyEvent, None, None]:
    """`events` as a generator, whose `close()` closes the run's own stream."""
    yield from events


@router.post(
    "/classify",
    name="classify",
    response_class=EventSourceResponse,
    dependencies=[Depends(rate_limited(Bucket.CLASSIFY))],
    responses={
        status.HTTP_200_OK: {"model": ClassifyEvent, "description": EVENTS_DESCRIPTION},
        status.HTTP_429_TOO_MANY_REQUESTS: {"description": "Too many classifications"},
        status.HTTP_503_SERVICE_UNAVAILABLE: {"description": "The engine is not configured"},
    },
)
async def classify(
    events: Annotated[Generator[ClassifyEvent, None, None], Depends(started_run)],
) -> AsyncIterator[ClassifyEvent]:
    """Classify one AI system under the AI Act, streaming each step as it runs and then the
    result (or an `error` event, and no class, when a check fails). Guidance, not legal
    advice."""
    try:
        async for event in iterate_in_threadpool(events):
            yield event
    finally:
        # Ends the run's graph stream (and logs its cost) however the stream ended; on a
        # disconnect this task is cancelled, and the shield lets the close still run.
        with anyio.CancelScope(shield=True):
            await run_in_threadpool(events.close)
