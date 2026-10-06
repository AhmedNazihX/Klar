"""The body cap (aiact/api/body_limit.py): a body over API_MAX_BODY_BYTES is a 413 whether it
declares its length or streams without one, nothing is set up for it, and the biggest valid
classification fits under the default cap."""

import json
from collections.abc import AsyncIterator, Iterator

import httpx
import pytest
from fastapi import FastAPI

from aiact.api import create_app
from aiact.api.body_limit import TOO_LARGE
from aiact.engine.classify import ClassifyRequest
from aiact.engine.graph import EngineNodes
from aiact.engine.scripted import Script, scripted_nodes
from aiact.settings import Settings
from tests.api.conftest import BASE_URL, api_settings, use_builder, use_nodes

SMALL_CAP = 2_048


def never_built(_settings: Settings, _meter: object) -> EngineNodes:
    raise AssertionError("the run was set up for a refused body")


def body_of(description: str) -> bytes:
    return json.dumps({"description": description, "language": "en"}).encode()


@pytest.fixture
def small_app() -> Iterator[FastAPI]:
    built = create_app(api_settings(api_max_body_bytes=SMALL_CAP))
    use_builder(built, never_built)
    yield built
    built.dependency_overrides.clear()


@pytest.fixture
async def small_client(small_app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=small_app)
    async with httpx.AsyncClient(transport=transport, base_url=BASE_URL) as c:
        yield c


@pytest.mark.anyio
async def test_a_declared_length_over_the_cap_is_a_413(small_client: httpx.AsyncClient) -> None:
    response = await small_client.post(
        "/classify", content=body_of("x" * SMALL_CAP), headers={"content-type": "application/json"}
    )
    assert response.status_code == 413
    assert response.json() == {"detail": TOO_LARGE}


@pytest.mark.anyio
async def test_a_streamed_body_without_a_length_is_counted(small_client: httpx.AsyncClient) -> None:
    body = body_of("x" * SMALL_CAP)

    async def chunks() -> AsyncIterator[bytes]:
        for start in range(0, len(body), 512):
            yield body[start : start + 512]

    response = await small_client.post(
        "/classify", content=chunks(), headers={"content-type": "application/json"}
    )
    assert "content-length" not in response.request.headers
    assert response.status_code == 413
    assert response.json() == {"detail": TOO_LARGE}


@pytest.mark.anyio
async def test_a_streamed_body_under_the_cap_gets_through(small_app: FastAPI) -> None:
    use_nodes(small_app, scripted_nodes(Script()))
    body = body_of("A chatbot that answers customer questions.")

    async def chunks() -> AsyncIterator[bytes]:
        yield body[:10]
        yield body[10:]

    transport = httpx.ASGITransport(app=small_app)
    async with httpx.AsyncClient(transport=transport, base_url=BASE_URL) as client:
        response = await client.post(
            "/classify", content=chunks(), headers={"content-type": "application/json"}
        )
    assert response.status_code == 200


def largest_classification() -> bytes:
    """The biggest body ClassifyRequest accepts, all in three-byte UTF-8 characters (the euro
    sign), with answer ids as long as real question ids get."""
    char = "€"
    assert len(char.encode()) == 3
    answers = {
        f"answer_question_id_{i:02d}": char * ClassifyRequest.MAX_ANSWER_CHARS
        for i in range(ClassifyRequest.MAX_ANSWERS)
    }
    body = {
        "description": char * ClassifyRequest.MAX_DESCRIPTION_CHARS,
        "language": "de",
        "law_version": "amended",
        "as_of": "2026-10-06",
        "answers": answers,
    }
    return json.dumps(body, ensure_ascii=False).encode()


@pytest.mark.anyio
async def test_the_largest_classification_fits_under_the_default_cap(
    app: FastAPI, client: httpx.AsyncClient
) -> None:
    body = largest_classification()
    assert len(body) <= Settings(_env_file=None).api_max_body_bytes  # pyright: ignore[reportCallIssue]
    use_nodes(app, scripted_nodes(Script()))
    response = await client.post(
        "/classify", content=body, headers={"content-type": "application/json"}
    )
    assert response.status_code == 200
