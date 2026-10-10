"""`parse_reply`: a reply the provider's content filter stopped is a refusal, not a broken output
(decision 029); an answer that parses is used whatever the finish reason. `ChatRoute`: only such
a refusal sends the same request once to the second model (decision 033)."""

from typing import Any

import httpx
import pytest
from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.outputs import ChatResult
from pydantic import BaseModel, Field, ValidationError

from aiact.llm.structured import (
    CONTENT_FILTER,
    ChatRoute,
    ProviderRefusalError,
    json_schema_format,
    parse_reply,
)


class Small(BaseModel):
    value: int


REFUSAL = "I'm sorry, but I cannot assist with that request."


def reply(content: str, finish_reason: str | None) -> AIMessage:
    metadata = {"finish_reason": finish_reason} if finish_reason else {}
    return AIMessage(content=content, response_metadata=metadata)


def test_a_filtered_reply_without_an_answer_is_a_refusal() -> None:
    with pytest.raises(ProviderRefusalError) as raised:
        parse_reply(reply(REFUSAL, CONTENT_FILTER), Small)
    assert REFUSAL not in str(raised.value)


def test_a_filtered_reply_with_an_answer_is_used() -> None:
    assert parse_reply(reply('{"value": 3}', CONTENT_FILTER), Small) == Small(value=3)


@pytest.mark.parametrize("finish_reason", ["stop", "length", None])
def test_any_other_reply_that_does_not_fit_is_a_validation_error(finish_reason: str | None) -> None:
    with pytest.raises(ValidationError):
        parse_reply(reply(REFUSAL, finish_reason), Small)


# --- The refusal route (decision 033) -----------------------------------------------------------


class RecordingChat(GenericFakeChatModel):
    """A fake model that notes each request it gets: its messages and its call options."""

    seen: list[tuple[list[BaseMessage], dict[str, object]]] = Field(default_factory=list)

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        self.seen.append((messages, kwargs))
        return super()._generate(messages, stop, run_manager, **kwargs)


def chat(*replies: AIMessage) -> RecordingChat:
    return RecordingChat(messages=iter(replies))


MESSAGES = [SystemMessage("Answer in JSON."), HumanMessage("The description.")]
FORMAT = json_schema_format("small", Small)
REFUSED = reply(REFUSAL, CONTENT_FILTER)


def test_a_refused_request_goes_once_to_the_second_model_unchanged() -> None:
    first, second = chat(REFUSED), chat(reply('{"value": 7}', "stop"))
    assert ChatRoute(first, second).ask(MESSAGES, FORMAT, Small) == Small(value=7)
    assert len(first.seen) == len(second.seen) == 1
    assert second.seen[0][0] == first.seen[0][0] == MESSAGES
    assert second.seen[0][1]["response_format"] == first.seen[0][1]["response_format"] == FORMAT


def test_a_filtered_reply_that_parses_is_used_and_never_retried() -> None:
    """own-c-16's shape (decision 029): `content_filter` with a full answer."""
    first, second = chat(reply('{"value": 3}', CONTENT_FILTER)), chat()
    assert ChatRoute(first, second).ask(MESSAGES, FORMAT, Small) == Small(value=3)
    assert second.seen == []


@pytest.mark.parametrize("finish_reason", ["stop", "length", None])
def test_a_broken_reply_is_never_retried(finish_reason: str | None) -> None:
    second = chat()
    with pytest.raises(ValidationError):
        ChatRoute(chat(reply(REFUSAL, finish_reason)), second).ask(MESSAGES, FORMAT, Small)
    assert second.seen == []


def test_a_transport_error_is_never_retried() -> None:
    class Down(RecordingChat):
        def _generate(self, *args: Any, **kwargs: Any) -> ChatResult:
            raise httpx.ConnectError("down")

    second = chat()
    with pytest.raises(httpx.ConnectError):
        ChatRoute(Down(messages=iter(())), second).ask(MESSAGES, FORMAT, Small)
    assert second.seen == []


def test_both_refused_is_a_provider_refusal() -> None:
    second = chat(REFUSED)
    with pytest.raises(ProviderRefusalError):
        ChatRoute(chat(REFUSED), second).ask(MESSAGES, FORMAT, Small)
    assert len(second.seen) == 1


def test_without_a_second_model_a_refusal_is_raised_at_once() -> None:
    first = chat(REFUSED)
    with pytest.raises(ProviderRefusalError):
        ChatRoute(first).ask(MESSAGES, FORMAT, Small)
    assert len(first.seen) == 1


def test_a_broken_reply_from_the_second_model_is_a_validation_error() -> None:
    with pytest.raises(ValidationError):
        ChatRoute(chat(REFUSED), chat(reply("{}", "stop"))).ask(MESSAGES, FORMAT, Small)
