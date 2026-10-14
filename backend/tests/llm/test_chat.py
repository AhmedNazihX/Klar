from typing import get_args

import httpx
import pytest
from langchain_core.messages import AIMessage
from langchain_openrouter import ChatOpenRouter
from openrouter.errors import OpenRouterError
from pydantic import SecretStr

from aiact.llm import (
    LLMConfigError,
    ModelRole,
    chat_model,
    engine_chat_model,
    engine_route,
    refusal_chat_model,
)
from aiact.settings import Settings, get_settings

# The planned engine model: cheap, with zero-data-retention endpoints (Azure).
CHEAP_MODEL = "openai/gpt-6-luna"


def _settings(**values: object) -> Settings:
    return Settings(_env_file=None, openrouter_api_key=SecretStr("k"), **values)  # pyright: ignore[reportCallIssue]


def test_model_id_comes_from_settings_by_role() -> None:
    settings = _settings(label_filter_model="vendor/filter-model")
    assert chat_model("label_filter", settings=settings).model_name == "vendor/filter-model"


def test_the_judge_has_no_chat_role() -> None:
    """Jev refuses chat completions, and the backup judge is built pinned (`BackupJudge`): a
    role would build either as an unpinned chat model."""
    assert get_args(ModelRole) == ("engine", "label_filter", "ragas")


def test_unset_model_id_is_a_config_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ENGINE_MODEL", raising=False)
    with pytest.raises(LLMConfigError, match="ENGINE_MODEL is not set"):
        chat_model("engine", settings=_settings())


def test_explicit_model_needs_no_setting() -> None:
    assert chat_model(model=CHEAP_MODEL, settings=_settings()).model_name == CHEAP_MODEL


def test_privacy_routing_is_sent_with_every_model() -> None:
    model = chat_model(
        model=CHEAP_MODEL,
        provider_order=["azure"],
        allow_fallbacks=False,
        settings=_settings(),
    )
    assert model.openrouter_provider == {
        "data_collection": "deny",
        "zdr": True,
        "order": ["azure"],
        "allow_fallbacks": False,
    }
    assert model.temperature == 0.0


def test_the_engine_model_is_pinned_to_its_provider_without_fallbacks() -> None:
    settings = _settings(engine_model=CHEAP_MODEL, engine_provider="azure/eu")
    model = engine_chat_model(max_tokens=100, settings=settings)
    assert model.model_name == CHEAP_MODEL
    assert model.max_tokens == 100
    assert model.openrouter_provider == {
        "data_collection": "deny",
        "zdr": True,
        "order": ["azure/eu"],
        "allow_fallbacks": False,
    }


@pytest.mark.parametrize(
    ("values", "missing"),
    [({"engine_provider": "azure/eu"}, "ENGINE_MODEL"), ({"engine_model": "m"}, "ENGINE_PROVIDER")],
)
def test_the_engine_model_needs_a_model_and_a_provider(
    values: dict[str, str], missing: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("ENGINE_MODEL", raising=False)
    monkeypatch.delenv("ENGINE_PROVIDER", raising=False)
    with pytest.raises(LLMConfigError, match=f"{missing} is not set"):
        engine_chat_model(max_tokens=100, settings=_settings(**values))


# --- The refusal route (decision 033) -----------------------------------------------------------

GEMINI = "google/gemini-3.1-flash-lite"
ROUTE = {
    "engine_model": CHEAP_MODEL,
    "engine_provider": "azure/eu",
    "refusal_model": GEMINI,
    "refusal_provider": "google-vertex/eu",
}


def test_the_refusal_model_is_pinned_to_its_provider_without_fallbacks() -> None:
    model = refusal_chat_model(max_tokens=100, settings=_settings(**ROUTE))
    assert model.model_name == "google/gemini-3.1-flash-lite"
    assert model.max_tokens == 100
    assert model.temperature == 0.0
    assert model.openrouter_provider == {
        "data_collection": "deny",
        "zdr": True,
        "order": ["google-vertex/eu"],
        "allow_fallbacks": False,
    }


@pytest.mark.parametrize("missing", ["REFUSAL_MODEL", "REFUSAL_PROVIDER"])
def test_the_refusal_model_needs_a_model_and_a_provider(
    missing: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("REFUSAL_MODEL", raising=False)
    monkeypatch.delenv("REFUSAL_PROVIDER", raising=False)
    values = {**ROUTE, missing.lower(): None}
    with pytest.raises(LLMConfigError, match=f"{missing} is not set"):
        refusal_chat_model(max_tokens=100, settings=_settings(**values))
    with pytest.raises(LLMConfigError, match=f"{missing} is not set"):
        engine_route(max_tokens=100, settings=_settings(**values))


def test_a_route_built_here_has_both_models_at_the_nodes_cap() -> None:
    route = engine_route(max_tokens=300, settings=_settings(**ROUTE))
    assert isinstance(route.chat, ChatOpenRouter)
    assert isinstance(route.refusal_chat, ChatOpenRouter)
    assert (route.chat.model_name, route.chat.max_tokens) == (CHEAP_MODEL, 300)
    assert (route.refusal_chat.model_name, route.refusal_chat.max_tokens) == (GEMINI, 300)
    assert route.retry_cut_off  # a run's route asks a cut-off reply once more (E20)


def test_a_given_chat_alone_gets_no_second_model() -> None:
    """The smoke harness's nodes (decision 004) and tests: a refusal is the outcome, and a
    cut-off reply is never asked again (one call per probe)."""
    given = chat_model(model=CHEAP_MODEL, settings=_settings())
    route = engine_route(max_tokens=300, settings=_settings(), chat=given)
    assert route.chat is given
    assert route.refusal_chat is None
    assert not route.retry_cut_off


def test_a_given_pair_is_used_as_it_is() -> None:
    """A classification run's models (`engine_nodes`), so a cut-off reply is asked once more."""
    first, second = (chat_model(model=m, settings=_settings()) for m in (CHEAP_MODEL, GEMINI))
    route = engine_route(max_tokens=300, settings=_settings(), chat=first, refusal_chat=second)
    assert (route.chat, route.refusal_chat) == (first, second)
    assert route.retry_cut_off


def _assert_chat_roundtrip(settings: Settings) -> None:
    model = chat_model(model=CHEAP_MODEL, max_tokens=200, settings=settings)
    reply = model.invoke("Reply with the single word: pong")
    assert isinstance(reply, AIMessage)
    assert "pong" in reply.text.lower()
    assert reply.usage_metadata is not None
    assert reply.usage_metadata["input_tokens"] > 0


@pytest.mark.vcr
def test_chat_roundtrip(openrouter_settings: Settings) -> None:
    _assert_chat_roundtrip(openrouter_settings)


@pytest.mark.live
def test_chat_roundtrip_live() -> None:
    _assert_chat_roundtrip(get_settings())


# --- Retries: max_retries=0 makes exactly one HTTP attempt (X2) ---------------------------------

COMPLETION = {
    "id": "gen-1",
    "object": "chat.completion",
    "created": 1,
    "model": CHEAP_MODEL,
    "system_fingerprint": None,
    "choices": [
        {"index": 0, "message": {"role": "assistant", "content": "pong"}, "finish_reason": "stop"}
    ],
    "usage": {"prompt_tokens": 3, "completion_tokens": 1, "total_tokens": 4},
}


@pytest.fixture
def attempts(monkeypatch: pytest.MonkeyPatch) -> list[int]:
    """Every HTTP client the SDK or ChatOpenRouter builds goes through a mock transport that
    answers 503 twice, then a completion; the SDK's backoff sleeps are skipped. Returns the
    statuses sent, one per attempt."""
    sent: list[int] = []
    real_client = httpx.Client

    def answer(request: httpx.Request) -> httpx.Response:
        status = 503 if len(sent) < 2 else 200
        sent.append(status)
        if status == 503:
            return httpx.Response(503, json={"error": {"message": "overloaded", "code": 503}})
        return httpx.Response(200, json=COMPLETION)

    def client(*args: object, **kwargs: object) -> httpx.Client:
        transport = httpx.MockTransport(answer)
        return real_client(*args, transport=transport, **kwargs)  # pyright: ignore[reportArgumentType]

    monkeypatch.setattr(httpx, "Client", client)
    monkeypatch.setattr("openrouter.utils.retries.time.sleep", lambda seconds: None)
    return sent


def test_no_retries_means_one_attempt_on_a_503(attempts: list[int]) -> None:
    model = chat_model(model=CHEAP_MODEL, max_retries=0, settings=_settings())
    with pytest.raises(OpenRouterError):
        model.invoke("Reply with the single word: pong")
    assert attempts == [503]


def test_the_default_still_retries_a_503(attempts: list[int]) -> None:
    model = chat_model(model=CHEAP_MODEL, settings=_settings())
    assert model.invoke("Reply with the single word: pong").text == "pong"
    assert attempts == [503, 503, 200]
