import pytest
from langchain_core.messages import AIMessage
from pydantic import SecretStr

from aiact.llm import LLMConfigError, chat_model
from aiact.settings import Settings, get_settings

# The planned engine model: cheap, with zero-data-retention endpoints (Azure).
CHEAP_MODEL = "openai/gpt-6-luna"


def _settings(**values: object) -> Settings:
    return Settings(_env_file=None, openrouter_api_key=SecretStr("k"), **values)  # pyright: ignore[reportCallIssue]


def test_model_id_comes_from_settings_by_role() -> None:
    model = chat_model("judge", settings=_settings(judge_model="vendor/judge-model"))
    assert model.model_name == "vendor/judge-model"


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
