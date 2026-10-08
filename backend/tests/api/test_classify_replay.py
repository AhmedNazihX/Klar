"""INIT's worked example through `POST /classify`, on the engine's own nodes in replay mode: the
recorded model replies and corpus answers of E10's end-to-end replay
(`tests/recordings/engine/test_classify_worked_example/test_replay_worked_example.*`), with
every citation checked against the corpus built from `data/parsed/`. No model, database or
network is used; re-record that replay (its `RECORD_COMMAND`), never this test."""

from collections.abc import Iterator
from contextlib import AbstractContextManager
from functools import partial

import httpx
import pytest
from fastapi import FastAPI

from aiact.engine import FactsEvent, ResultEvent, StepEvent
from aiact.engine.classify import NodeBuilder, engine_nodes
from aiact.settings import Settings
from tests.api.conftest import BASE_URL, FULL_RUN, TEST_HOST, outline, sse_events, use_builder
from tests.conftest import RECORDINGS_DIR
from tests.engine.built_corpus import built_validator
from tests.engine.nodes.corpus_recording import corpus_recording
from tests.engine.test_classify_worked_example import (
    AS_OF,
    LUNA,
    LUNA_PROVIDER,
    RECORD_COMMAND,
    LiveCorpus,
    assert_the_expected_classification,
    recorded_libraries,
    worked_example_request,
)

RECORDING = RECORDINGS_DIR / "engine" / "test_classify_worked_example"
CASSETTE = "test_replay_worked_example"
API_HOST = httpx.URL(BASE_URL).host


@pytest.fixture(scope="module")
def vcr_cassette_dir() -> str:
    return str(RECORDING)


@pytest.fixture
def default_cassette_name() -> str:
    return CASSETTE


@pytest.fixture(scope="module")
def vcr_config(vcr_config: dict[str, object]) -> dict[str, object]:
    """The project's config; the test's own requests to the app pass through vcrpy, which
    patches httpx's ASGI transport too."""
    return {**vcr_config, "ignore_hosts": [API_HOST]}


@pytest.fixture
def settings(openrouter_settings: Settings, record_mode: str) -> Settings:
    if record_mode != "none":
        pytest.skip(f"replay only: record the engine's replay instead, `{RECORD_COMMAND}`")
    return openrouter_settings.model_copy(
        update={
            "engine_model": LUNA,
            "engine_provider": LUNA_PROVIDER,
            "langsmith_api_key": None,
            "api_allowed_hosts": (TEST_HOST,),
        }
    )


def no_live_corpus() -> AbstractContextManager[LiveCorpus]:
    raise AssertionError("this test only replays")


@pytest.fixture
def replay_nodes(record_mode: str) -> Iterator[NodeBuilder]:
    with corpus_recording(
        str(RECORDING), CASSETTE, record_mode, RECORD_COMMAND, no_live_corpus
    ) as recording:
        yield partial(
            engine_nodes, libraries=recorded_libraries(recording), validator=built_validator()
        )


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="facts recording pending (E13): the facts prompt and answer schema changed; re-record "
    "the worked example, then drop this mark",
)
@pytest.mark.vcr
@pytest.mark.anyio
async def test_the_worked_example_streams_every_step_then_the_expected_result(
    app: FastAPI, client: httpx.AsyncClient, replay_nodes: NodeBuilder
) -> None:
    use_builder(app, replay_nodes)
    body = worked_example_request().model_dump(mode="json")
    assert body["as_of"] == AS_OF.isoformat()
    response = await client.post("/classify", json=body)
    assert response.status_code == 200
    events = sse_events(response.text)
    assert outline(events) == FULL_RUN
    facts = events[0]
    assert isinstance(facts, FactsEvent) and facts.facts
    high_risk = next(e for e in events if isinstance(e, StepEvent) and e.matches)
    assert "annex:III:4:a" in high_risk.matches
    final = events[-1]
    assert isinstance(final, ResultEvent)
    steps = [e.step for e in events if isinstance(e, StepEvent)]
    assert final.result.steps == tuple(steps)
    assert_the_expected_classification(final.result)
