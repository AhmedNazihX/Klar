import pytest
from pydantic import SecretStr

from aiact.llm.routing import (
    LLMConfigError,
    provider_preferences,
    require_api_key,
    require_setting,
)
from aiact.settings import Settings


def test_privacy_flags_are_always_on() -> None:
    assert provider_preferences() == {"data_collection": "deny", "zdr": True}


def test_pinned_order_disables_fallbacks() -> None:
    assert provider_preferences(["nebius"], allow_fallbacks=False) == {
        "data_collection": "deny",
        "zdr": True,
        "order": ["nebius"],
        "allow_fallbacks": False,
    }


def test_no_fallbacks_without_an_order_is_a_config_error() -> None:
    with pytest.raises(LLMConfigError, match="provider order"):
        provider_preferences(allow_fallbacks=False)


@pytest.mark.parametrize("value", [None, ""])
def test_unset_setting_names_the_env_var(value: str | None) -> None:
    with pytest.raises(LLMConfigError, match="ENGINE_MODEL is not set"):
        require_setting(value, "ENGINE_MODEL")


def test_missing_api_key_is_a_config_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    with pytest.raises(LLMConfigError, match="OPENROUTER_API_KEY"):
        require_api_key(Settings(_env_file=None))  # pyright: ignore[reportCallIssue]


def test_api_key_is_returned_as_secret() -> None:
    settings = Settings(_env_file=None, openrouter_api_key=SecretStr("k"))  # pyright: ignore[reportCallIssue]
    assert require_api_key(settings).get_secret_value() == "k"
