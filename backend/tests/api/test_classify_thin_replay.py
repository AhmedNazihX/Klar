"""README, Voice's "AI for HR" line through `POST /classify` (P20, E13): a description too thin
to start streams its facts and then the needs-a-description result, with the three prompts and no
step event. It replays the facts node's recorded answer for the same description
(`tests/recordings/engine/nodes/test_facts/`, E13's thin replay); no model, database or network
is used. Re-record that replay (`THIN_RECORD_COMMAND`), never this test."""

from dataclasses import replace

import httpx
import pytest
from fastapi import FastAPI

from aiact.engine import FactsEvent, ResultEvent
from aiact.engine.classify import ClassifyRequest, NodeBuilder, engine_nodes
from aiact.engine.graph import CheckNode, EngineNodes
from aiact.engine.state import CheckOutcome, EngineState
from aiact.engine.usage import UsageMeter
from aiact.schemas import STEP_ORDER, Language, Status, StepName
from aiact.settings import Settings
from tests.api.conftest import BASE_URL, TEST_HOST, outline, sse_events, use_builder
from tests.conftest import RECORDINGS_DIR
from tests.engine.built_corpus import built_validator
from tests.engine.nodes.test_facts import LUNA, LUNA_PROVIDER, THIN

RECORDING = RECORDINGS_DIR / "engine" / "nodes" / "test_facts"
CASSETTE = "test_recorded_thin_description_asks_for_a_description[ai_for_hr_en]"
THIN_RECORD_COMMAND = (
    "uv run pytest tests/engine/nodes/test_facts.py -k thin_description --record-mode=once"
)
API_HOST = httpx.URL(BASE_URL).host

PROMPTS = [
    (
        "what_it_decides",
        "What does it decide or suggest?",
        "For example: it ranks applicants, answers staff questions, plans shifts.",
    ),
    ("who_it_affects", "Who does it affect?", "For example: applicants, your staff, customers."),
    (
        "bought_or_built",
        "Did you buy it or build it?",
        "And whether you changed it or put your own name on it.",
    ),
]
"""The three prompts as artboard `ClassifyVague` words them, in its order."""


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
        pytest.skip(f"replay only: record the facts replay instead, `{THIN_RECORD_COMMAND}`")
    return openrouter_settings.model_copy(
        update={
            "engine_model": LUNA,
            "engine_provider": LUNA_PROVIDER,
            # Built by the checks' nodes, never called: no check runs on a thin description.
            "embedding_model": "qwen/qwen3-embedding-8b",
            "embedding_provider": "nebius",
            "langsmith_api_key": None,
            "api_allowed_hosts": (TEST_HOST,),
        }
    )


def _no_check(name: StepName) -> CheckNode:
    def fail(_state: EngineState) -> CheckOutcome:
        raise AssertionError(f"the {name.value} check ran on a thin description")

    return fail


def thin_nodes(settings: Settings, meter: UsageMeter) -> EngineNodes:
    """The engine's own nodes (the real facts node and finalize); a check that runs fails."""
    nodes = engine_nodes(settings, meter, validator=built_validator())
    return replace(nodes, checks={name: _no_check(name) for name in STEP_ORDER})


@pytest.mark.vcr
@pytest.mark.anyio
async def test_a_thin_description_streams_its_facts_then_the_three_prompts(
    app: FastAPI, client: httpx.AsyncClient
) -> None:
    builder: NodeBuilder = thin_nodes
    use_builder(app, builder)
    body = ClassifyRequest(description=THIN, language=Language.EN).model_dump(mode="json")
    response = await client.post("/classify", json=body)

    assert response.status_code == 200
    events = sse_events(response.text)
    assert outline(events) == [("facts", ""), ("result", "")]
    assert isinstance(events[0], FactsEvent)
    final = events[-1]
    assert isinstance(final, ResultEvent)
    result = final.result
    assert result.steps == ()
    assert result.risk_class is None
    assert result.status is Status.NEEDS_MORE_INFORMATION
    assert [(q.id, q.text, q.hint) for q in result.follow_up_questions] == PROMPTS
