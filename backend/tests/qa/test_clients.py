"""P7: the Q&A's model is the engine model pinned to its EU endpoint, with one attempt and its own
output cap, built once per settings; its search is `search_ai_act` with the cut-off and V6's top
five, on a connection of its own."""

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date
from typing import Any

import pytest
from langchain_openrouter import ChatOpenRouter

from aiact.llm import LLMConfigError
from aiact.qa import clients
from aiact.qa.clients import corpus_searcher, qa_chat, qa_route
from aiact.schemas import Language, LawVersion
from tests.engine.test_clients import engine_settings


def test_the_qa_model_is_luna_pinned_to_azure_eu_with_one_attempt() -> None:
    chat = qa_chat(engine_settings())
    assert isinstance(chat, ChatOpenRouter)
    assert chat.model_name == "openai/gpt-6-luna-20260922"
    assert chat.openrouter_provider == {
        "data_collection": "deny",
        "zdr": True,
        "order": ["azure/eu"],
        "allow_fallbacks": False,
    }
    assert chat.max_tokens == 3000
    assert chat.max_retries == 0
    sdk_retries = chat.client.sdk_configuration.retry_config  # pyright: ignore[reportAttributeAccessIssue]
    assert sdk_retries is not None and sdk_retries.strategy == "none"


def test_the_route_has_no_second_model() -> None:
    route = qa_route(engine_settings())
    assert route.refusal_chat is None
    assert route.chat is qa_chat(engine_settings())


def test_equal_settings_share_one_model() -> None:
    assert qa_chat(engine_settings()) is qa_chat(engine_settings())
    assert qa_chat(engine_settings(engine_model="openai/gpt-6-sol")) is not qa_chat(
        engine_settings()
    )


@pytest.mark.parametrize("missing", ["engine_model", "engine_provider", "openrouter_api_key"])
def test_a_missing_setting_raises_on_every_call(missing: str) -> None:
    for _ in range(2):
        with pytest.raises(LLMConfigError):
            qa_chat(engine_settings(**{missing: None}))


def test_the_search_uses_v6s_top_five_and_the_settings_cut_off(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = []
    opened: list[str] = []

    def fake_search(*args: Any, **kwargs: Any) -> str:
        calls.append((args, kwargs))
        return "results"

    @contextmanager
    def connect() -> Iterator[str]:
        opened.append("open")
        yield "connection"
        opened.append("closed")

    embedder = object()
    monkeypatch.setattr(clients, "search_ai_act", fake_search)
    search = corpus_searcher(connect, embedder)  # pyright: ignore[reportArgumentType]
    on = date(2026, 10, 1)
    assert search("Q?", Language.DE, LawVersion.AMENDED, on) == "results"
    ((args, kwargs),) = calls
    assert args == ("Q?", Language.DE, LawVersion.AMENDED, on)
    assert kwargs == {"limit": 5, "embedder": embedder, "connection": "connection"}
    # No cut-off passed: `search_ai_act`'s default is the SEARCH_MAX_DISTANCE setting; and the
    # held-out opt-in is never passed (decision 012).
    assert "max_distance" not in kwargs and "include_held_out" not in kwargs
    assert opened == ["open", "closed"]
