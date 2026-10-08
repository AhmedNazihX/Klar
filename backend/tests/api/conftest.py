"""The API under test: an app per test (`create_app` with test settings), an httpx client over
the ASGI transport, the engine's nodes replaced through the `node_builder` dependency, and the
SSE stream parsed back into the engine's events."""

import json
from collections.abc import AsyncIterator, Iterator

import httpx
import pytest
from fastapi import FastAPI
from pydantic import SecretStr, TypeAdapter

from aiact.api import create_app
from aiact.api.dependencies import node_builder
from aiact.engine import (
    ClassifyEvent,
    ErrorEvent,
    FactsEvent,
    ResultEvent,
    StepEvent,
    StepStartedEvent,
)
from aiact.engine.classify import NodeBuilder
from aiact.engine.graph import EngineNodes
from aiact.schemas import STEP_ORDER
from aiact.settings import Settings

BASE_URL = "http://testserver"
TEST_HOST = "testserver"


def api_settings(**changes: object) -> Settings:
    """No `.env` and no LangSmith key (nothing is traced), the test client's host allowed, the
    default limits and origins unless `changes` say otherwise."""
    values: dict[str, object] = {
        "openrouter_api_key": SecretStr("k"),
        "api_allowed_hosts": (TEST_HOST,),
        **changes,
    }
    return Settings(_env_file=None, **values)  # pyright: ignore[reportCallIssue]


TEST_SETTINGS = api_settings()

EVENTS = TypeAdapter[ClassifyEvent](ClassifyEvent)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def settings() -> Settings:
    return TEST_SETTINGS


@pytest.fixture
def app(settings: Settings) -> Iterator[FastAPI]:
    built = create_app(settings)
    yield built
    built.dependency_overrides.clear()
    built.state.context.export_slots.close()


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url=BASE_URL) as c:
        yield c


def use_builder(app: FastAPI, builder: NodeBuilder) -> None:
    app.dependency_overrides[node_builder] = lambda: builder


def use_nodes(app: FastAPI, nodes: EngineNodes) -> None:
    use_builder(app, lambda _settings, _meter: nodes)


def sse_events(body: str) -> list[ClassifyEvent]:
    """The events of an SSE body: each block's `data:` lines, as JSON, read back into the
    engine's event models; comment lines (keep-alive pings) are skipped."""
    events: list[ClassifyEvent] = []
    for block in body.split("\n\n"):
        lines = block.splitlines()
        data = [line.removeprefix("data:").strip() for line in lines if line.startswith("data:")]
        if data:
            events.append(EVENTS.validate_python(json.loads("\n".join(data))))
    return events


def outline(events: list[ClassifyEvent]) -> list[tuple[str, str]]:
    """Each event as (its name, the check or node it is about; empty for facts and result)."""

    def about(event: ClassifyEvent) -> str:
        match event:
            case StepStartedEvent() | ErrorEvent():
                return str(event.step)
            case StepEvent():
                return event.step.step.value
            case FactsEvent() | ResultEvent():
                return ""

    return [(event.event, about(event)) for event in events]


FULL_RUN = [
    ("facts", ""),
    *((kind, name.value) for name in STEP_ORDER for kind in ("step_started", "step")),
    ("result", ""),
]
"""The outline of a run in which every check ran."""
