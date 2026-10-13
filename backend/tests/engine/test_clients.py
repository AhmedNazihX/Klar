"""The engine's model clients, built once per process (E15): every run of the process shares the
chat model of each node and the query embedder, so repeated classifications leave no HTTP
clients behind. Live clients are counted without a garbage collection, with the collector off,
so clients a run left in reference cycles would stay countable. The end-to-end check replays
INIT's worked example several times on the engine's own nodes, from E10's recording
(`tests/recordings/engine/test_classify_worked_example/test_replay_worked_example.*`); re-record
that replay (its `RECORD_COMMAND`), never this test."""

import gc
from collections.abc import Callable, Iterator, Mapping
from contextlib import AbstractContextManager
from functools import partial
from types import MappingProxyType

import httpx
import pytest
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_openrouter import ChatOpenRouter
from pydantic import SecretStr

from aiact.engine import classify, run_classification
from aiact.engine.classify import NodeBuilder, engine_nodes
from aiact.engine.clients import engine_chats, engine_embeddings, refusal_chats
from aiact.engine.usage import UsageMeter
from aiact.llm import LLMConfigError
from aiact.settings import Settings
from tests.conftest import RECORDINGS_DIR, REFUSAL_ROUTE
from tests.engine.built_corpus import built_validator
from tests.engine.nodes.corpus_recording import corpus_recording
from tests.engine.nodes.known_gaps import E20_PROMPTS_RECORDING_PENDING, stale_recording_pending
from tests.engine.replayed_engine import LUNA, LUNA_PROVIDER, LiveCorpus, recorded_libraries
from tests.engine.test_classify_worked_example import (
    RECORD_COMMAND,
    assert_the_expected_result,
    worked_example_request,
)

RECORDING = RECORDINGS_DIR / "engine" / "test_classify_worked_example"
CASSETTE = "test_replay_worked_example"
REPEATS = 3
"""Runs after the first, which may build the process's clients."""


def live_http_clients() -> int:
    """The httpx clients alive now, counted without a garbage collection. By `type`, not
    `isinstance`: a lazy proxy (openai's module client) builds a client when asked its
    `__class__`."""
    clients = (httpx.Client, httpx.AsyncClient)
    return sum(issubclass(type(item), clients) for item in gc.get_objects())


@pytest.fixture
def no_automatic_gc() -> Iterator[None]:
    """The collector off, so clients left in reference cycles stay countable."""
    gc.disable()
    try:
        yield
    finally:
        gc.enable()


def engine_settings(**values: object) -> Settings:
    configured: dict[str, object] = {
        "openrouter_api_key": SecretStr("k"),
        "engine_model": "openai/gpt-6-luna-20260922",
        "engine_provider": "azure/eu",
        "embedding_model": "qwen/qwen3-embedding-8b",
        "embedding_provider": "nebius",
        **REFUSAL_ROUTE,
        **values,
    }
    return Settings(_env_file=None, **configured)  # pyright: ignore[reportCallIssue]


# --- The clients --------------------------------------------------------------------------------


def test_every_node_gets_the_pinned_engine_model_with_its_own_output_cap() -> None:
    chats = engine_chats(engine_settings())
    assert {
        node: chat.max_tokens for node, chat in chats.items() if isinstance(chat, ChatOpenRouter)
    } == {
        "facts": 6000,
        "scope": 3000,
        "prohibited": 6000,
        "high_risk": 10000,
        "transparency": 4000,
        "role_obligations": 4000,
    }
    for chat in chats.values():
        assert isinstance(chat, ChatOpenRouter)
        assert chat.model_name == "openai/gpt-6-luna-20260922"
        assert chat.openrouter_provider is not None
        assert chat.openrouter_provider["order"] == ["azure/eu"]
        assert chat.openrouter_provider["allow_fallbacks"] is False


def test_every_node_gets_the_pinned_refusal_model_with_its_own_output_cap() -> None:
    """Decision 033: the second model a node's refused request goes to."""
    chats = refusal_chats(engine_settings())
    engine = engine_chats(engine_settings())
    assert set(chats) == set(engine)
    for node, chat in chats.items():
        assert isinstance(chat, ChatOpenRouter)
        assert chat.model_name == "google/gemini-3.1-flash-lite"
        assert chat.max_tokens == engine[node].max_tokens  # pyright: ignore[reportAttributeAccessIssue]
        assert chat.openrouter_provider == {
            "data_collection": "deny",
            "zdr": True,
            "order": ["google-vertex/eu"],
            "allow_fallbacks": False,
        }
    assert refusal_chats(engine_settings())["facts"] is chats["facts"]


@pytest.mark.parametrize("missing", ["refusal_model", "refusal_provider"])
def test_a_missing_refusal_setting_raises_on_every_call(missing: str) -> None:
    unset = engine_settings(**{missing: None})
    for _ in range(2):
        with pytest.raises(LLMConfigError):
            refusal_chats(unset)


def test_equal_settings_get_the_same_models_and_embedder() -> None:
    first, again = engine_chats(engine_settings()), engine_chats(engine_settings())
    assert all(again[node] is model for node, model in first.items())
    assert engine_embeddings(engine_settings()) is engine_embeddings(engine_settings())


def test_other_settings_get_their_own_models_and_embedder() -> None:
    other = engine_settings(engine_model="openai/gpt-6-sol", embedding_model="qwen/qwen3-mini")
    chat = engine_chats(other)["facts"]
    assert isinstance(chat, ChatOpenRouter) and chat.model_name == "openai/gpt-6-sol"
    assert chat is not engine_chats(engine_settings())["facts"]
    assert engine_embeddings(other).model == "qwen/qwen3-mini"
    assert engine_embeddings(other) is not engine_embeddings(engine_settings())


@pytest.mark.parametrize("missing", ["engine_model", "engine_provider", "openrouter_api_key"])
def test_a_missing_model_setting_raises_on_every_call(missing: str) -> None:
    unset = engine_settings(**{missing: None})
    for _ in range(2):
        with pytest.raises(LLMConfigError):
            engine_chats(unset)


@pytest.mark.parametrize("missing", ["embedding_model", "embedding_provider"])
def test_a_missing_embedding_setting_raises_on_every_call(missing: str) -> None:
    unset = engine_settings(**{missing: None})
    for _ in range(2):
        with pytest.raises(LLMConfigError):
            engine_embeddings(unset)


NODE_CLASSES: Mapping[str, str] = MappingProxyType(
    {
        "facts": "FactExtractor",
        "scope": "ScopeCheck",
        "prohibited": "ProhibitedCheck",
        "high_risk": "HighRiskCheck",
        "transparency": "TransparencyCheck",
        "role_obligations": "RoleObligationsCheck",
    }
)
"""The class `engine_nodes` builds for each node that calls the engine model."""

REPLY_COST_USD = 0.25
REPLY_TOKENS = 7


def fake_reply(*_: object, **__: object) -> ChatResult:
    """A reply in place of OpenRouter's, with its cost and token count."""
    message = AIMessage(
        content="ok",
        response_metadata={"cost": REPLY_COST_USD},
        usage_metadata={"input_tokens": 5, "output_tokens": 2, "total_tokens": REPLY_TOKENS},
    )
    return ChatResult(generations=[ChatGeneration(message=message)])


RunChats = Callable[[UsageMeter], Mapping[str, BaseChatModel]]


@pytest.fixture
def run_chats(monkeypatch: pytest.MonkeyPatch) -> RunChats:
    """Builds one run's nodes for a meter and returns the chat model each node was given; a
    model's call gets `fake_reply`, not OpenRouter."""
    monkeypatch.setattr(ChatOpenRouter, "_generate", fake_reply)
    given: dict[str, BaseChatModel] = {}
    for node, name in NODE_CLASSES.items():
        built = getattr(classify, name)

        def recorded(
            *args: object,
            chat: BaseChatModel,
            _node: str = node,
            _built: Callable[..., object] = built,
            **kw: object,
        ) -> object:
            given[_node] = chat
            return _built(*args, chat=chat, **kw)

        monkeypatch.setattr(classify, name, recorded)

    def build(meter: UsageMeter) -> Mapping[str, BaseChatModel]:
        given.clear()
        engine_nodes(engine_settings(), meter, validator=built_validator())
        assert set(given) == set(NODE_CLASSES)
        return MappingProxyType(dict(given))

    return build


def test_a_run_counts_only_its_own_calls_and_leaves_the_shared_models_untouched(
    run_chats: RunChats,
) -> None:
    """Two runs over the same process-wide models: each run's calls reach its own meter only,
    and the shared models keep no run's callback (one would leak a meter into later runs and
    race between the API's threads)."""
    shared = engine_chats(engine_settings())
    assert all(not model.callbacks for model in shared.values())
    first_meter, second_meter = UsageMeter(), UsageMeter()
    first, second = run_chats(first_meter), run_chats(second_meter)

    for node in NODE_CLASSES:
        first[node].invoke("first run")
        for _ in range(2):
            second[node].invoke("second run")

    for meter, calls in ((first_meter, 1), (second_meter, 2)):
        usage = meter.usage()
        assert set(usage.by_node) == set(NODE_CLASSES)
        assert all(node.calls == calls for node in usage.by_node.values())
        assert usage.tokens == REPLY_TOKENS * calls * len(NODE_CLASSES)
        assert usage.cost_usd == pytest.approx(REPLY_COST_USD * calls * len(NODE_CLASSES))
    assert engine_chats(engine_settings()) is shared
    assert all(not model.callbacks for model in shared.values())


@pytest.mark.usefixtures("no_automatic_gc")
def test_building_a_runs_nodes_again_builds_no_http_client() -> None:
    """The production default: no injected models, the embedder built for the live corpus."""
    settings = engine_settings()
    engine_nodes(settings, UsageMeter())
    after_first = live_http_clients()
    for _ in range(REPEATS):
        engine_nodes(settings, UsageMeter())
    assert live_http_clients() == after_first


# --- Repeated runs ------------------------------------------------------------------------------


@pytest.fixture(scope="module")
def vcr_cassette_dir() -> str:
    return str(RECORDING)


@pytest.fixture
def default_cassette_name() -> str:
    return CASSETTE


@pytest.fixture
def luna_settings(openrouter_settings: Settings, record_mode: str) -> Settings:
    if record_mode != "none":
        pytest.skip(f"replay only: record the engine's replay instead, `{RECORD_COMMAND}`")
    return openrouter_settings.model_copy(
        update={"engine_model": LUNA, "engine_provider": LUNA_PROVIDER, "langsmith_api_key": None}
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


@E20_PROMPTS_RECORDING_PENDING
@pytest.mark.vcr(allow_playback_repeats=True)
@pytest.mark.usefixtures("no_automatic_gc")
def test_repeated_classifications_leave_no_http_clients_behind(
    luna_settings: Settings, replay_nodes: NodeBuilder
) -> None:
    def classify() -> None:
        with stale_recording_pending():
            run = run_classification(
                worked_example_request(), settings=luna_settings, build_nodes=replay_nodes
            )
        assert_the_expected_result(run)

    classify()
    after_first = live_http_clients()
    for _ in range(REPEATS):
        classify()
    assert live_http_clients() == after_first
