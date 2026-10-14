"""`parse_reply`: a reply the provider's content filter stopped is a refusal, not a broken output
(decision 029); an answer that parses is used whatever the finish reason. `ChatRoute`: only such
a refusal sends the same request once to the second model (decision 033), and only a reply the
output cap cut off is asked once more of the same model, on the engine's routes only (E20)."""

import logging
from collections.abc import Callable
from typing import Any

import httpx
import pytest
from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models import BaseChatModel
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.outputs import ChatResult
from openrouter.errors import (
    BadRequestResponseError,
    NoResponseError,
    NotFoundResponseError,
    OpenRouterDefaultError,
)
from pydantic import BaseModel, Field, SecretStr, ValidationError
from vcr.errors import CannotOverwriteExistingCassetteException

from aiact.llm.chat import chat_model, engine_route
from aiact.llm.structured import (
    CONTENT_FILTER,
    ChatRoute,
    ProviderRefusalError,
    json_schema_format,
    parse_reply,
)
from aiact.settings import Settings


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


@pytest.mark.parametrize("retry_cut_off", [False, True])
@pytest.mark.parametrize("finish_reason", ["stop", None])
def test_a_broken_reply_is_never_retried(finish_reason: str | None, retry_cut_off: bool) -> None:
    """Only a cut-off reply is asked again, and only on an engine route; a reply that doesn't fit
    for any other reason never is, on any route."""
    first, second = chat(reply(REFUSAL, finish_reason)), chat()
    with pytest.raises(ValidationError):
        ChatRoute(first, second, retry_cut_off=retry_cut_off).ask(MESSAGES, FORMAT, Small)
    assert len(first.seen) == 1
    assert second.seen == []


# --- A reply cut off at the output cap: the engine's routes only (E20) ----------------------------

CUT_OFF_TEXT = '{"value": 1, "numbers": [1,2,3,4,5,6,7,8,9,10,11,12,13'
"""A runaway answer the output cap cut off mid-list, as the German worked example's was."""
NODE_CAP = 300


def run_route(first: BaseChatModel, second: BaseChatModel) -> ChatRoute:
    """A classification run's route for one node: its model and its refusal model."""
    return engine_route(max_tokens=NODE_CAP, chat=first, refusal_chat=second)


def test_an_engine_route_asks_a_cut_off_reply_once_more_of_the_same_model() -> None:
    first = chat(reply(CUT_OFF_TEXT, "length"), reply('{"value": 2}', "stop"))
    second = chat()
    assert run_route(first, second).ask(MESSAGES, FORMAT, Small) == Small(value=2)
    assert len(first.seen) == 2
    assert first.seen[1][0] == first.seen[0][0] == MESSAGES
    assert first.seen[1][1]["response_format"] == first.seen[0][1]["response_format"] == FORMAT
    assert second.seen == []


def test_on_an_engine_route_a_reply_cut_off_twice_is_a_validation_error_after_two_calls() -> None:
    first, second = chat(reply(CUT_OFF_TEXT, "length"), reply(CUT_OFF_TEXT, "length")), chat()
    with pytest.raises(ValidationError):
        run_route(first, second).ask(MESSAGES, FORMAT, Small)
    assert len(first.seen) == 2
    assert second.seen == []


def test_a_default_route_never_asks_a_cut_off_reply_again() -> None:
    """Q&A's and the RAGAS answerer's routes (`qa_route`, `metered_qa_route`): one call."""
    first, second = chat(reply(CUT_OFF_TEXT, "length"), reply('{"value": 2}', "stop")), chat()
    with pytest.raises(ValidationError):
        ChatRoute(first, second).ask(MESSAGES, FORMAT, Small)
    assert len(first.seen) == 1
    assert second.seen == []


def test_a_given_engine_chat_alone_never_asks_a_cut_off_reply_again() -> None:
    """The smoke harness's nodes get their model alone: one call per probe (decision 004)."""
    first = chat(reply(CUT_OFF_TEXT, "length"), reply('{"value": 2}', "stop"))
    with pytest.raises(ValidationError):
        engine_route(max_tokens=NODE_CAP, chat=first).ask(MESSAGES, FORMAT, Small)
    assert len(first.seen) == 1


def test_a_cut_off_reply_that_parses_is_used_without_another_call() -> None:
    first = chat(reply('{"value": 3}', "length"))
    assert run_route(first, chat()).ask(MESSAGES, FORMAT, Small) == Small(value=3)
    assert len(first.seen) == 1


def test_a_refusal_on_the_second_try_goes_to_the_second_model() -> None:
    first = chat(reply(CUT_OFF_TEXT, "length"), REFUSED)
    second = chat(reply('{"value": 4}', "stop"))
    assert run_route(first, second).ask(MESSAGES, FORMAT, Small) == Small(value=4)
    assert (len(first.seen), len(second.seen)) == (2, 1)


def test_the_second_try_logs_the_finish_reason_but_never_the_reply(
    caplog: pytest.LogCaptureFixture,
) -> None:
    first = chat(reply(CUT_OFF_TEXT, "length"), reply('{"value": 2}', "stop"))
    with caplog.at_level(logging.WARNING, logger="aiact.llm.structured"):
        run_route(first, chat()).ask(MESSAGES, FORMAT, Small)
    assert [record.getMessage() for record in caplog.records] == [
        "the reply was cut off at the output cap; asking once more"
    ]
    assert "numbers" not in caplog.text


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


def test_both_refused_logs_the_second_refusal(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING), pytest.raises(ProviderRefusalError):
        ChatRoute(chat(REFUSED), chat(REFUSED)).ask(MESSAGES, FORMAT, Small)
    assert "the second model refused too" in caplog.text
    assert "failed" not in caplog.text


# --- A failed second hop ends as a refusal too: the route is never worse than no route ---------

SECRET = "the night shifts of our Leipzig depot"
"""Stands for the user's description in the request and in the second model's reply."""
SECRET_MESSAGES = [SystemMessage("Answer in JSON."), HumanMessage(f"We rank staff for {SECRET}.")]


def assert_refused_after_a_failed_second_hop(
    second: BaseChatModel, kind: str, caplog: pytest.LogCaptureFixture
) -> None:
    """A refusal sent to `second`, which fails with `kind`: a refusal whose log line names the
    kind only, with the description in neither the error nor the logs."""
    with caplog.at_level(logging.WARNING), pytest.raises(ProviderRefusalError) as raised:
        ChatRoute(chat(REFUSED), second).ask(SECRET_MESSAGES, FORMAT, Small)
    error = raised.value
    assert error.__cause__ is None and error.__suppress_context__
    assert SECRET not in str(error)
    assert f"the second model failed ({kind})" in caplog.text
    assert "Leipzig" not in caplog.text


@pytest.mark.parametrize("content", ["{}", f'{{"value": "{SECRET}"}}', f"Sure: {SECRET}"])
def test_a_broken_reply_from_the_second_model_is_a_refusal(
    content: str, caplog: pytest.LogCaptureFixture
) -> None:
    second = chat(reply(content, "stop"))
    assert_refused_after_a_failed_second_hop(second, "ValidationError", caplog)
    assert len(second.seen) == 1


@pytest.fixture
def http_answer(monkeypatch: pytest.MonkeyPatch) -> list[Callable[[httpx.Request], httpx.Response]]:
    """Every HTTP client OpenRouter's SDK builds goes through a mock transport that answers with
    the handler the test puts in the returned list."""
    handlers: list[Callable[[httpx.Request], httpx.Response]] = []
    real_client = httpx.Client

    def client(*args: object, **kwargs: object) -> httpx.Client:
        transport = httpx.MockTransport(lambda request: handlers[0](request))
        return real_client(*args, transport=transport, **kwargs)  # pyright: ignore[reportArgumentType]

    monkeypatch.setattr(httpx, "Client", client)
    return handlers


def status(code: int) -> Callable[[httpx.Request], httpx.Response]:
    return lambda request: httpx.Response(code, json={"error": {"message": "busy", "code": code}})


def html_status(code: int) -> Callable[[httpx.Request], httpx.Response]:
    """A gateway's non-JSON error page, which the SDK raises as `OpenRouterDefaultError`."""
    return lambda request: httpx.Response(
        code, text="<html>Bad gateway</html>", headers={"content-type": "text/html"}
    )


def raising(error: type[httpx.TransportError]) -> Callable[[httpx.Request], httpx.Response]:
    def handle(request: httpx.Request) -> httpx.Response:
        raise error("no answer", request=request)

    return handle


def no_response(request: httpx.Request) -> httpx.Response:
    """The SDK's own "no response received" error, as its client raises it."""
    raise NoResponseError()


def provider_error(request: httpx.Request) -> httpx.Response:
    """A 200 whose body is the provider's error, not a completion."""
    return httpx.Response(200, json={"error": {"message": "upstream error", "code": 502}})


@pytest.mark.parametrize(
    ("handler", "kind"),
    [
        pytest.param(status(429), "TooManyRequestsResponseError", id="rate-limited"),
        pytest.param(status(408), "RequestTimeoutResponseError", id="request-timeout"),
        pytest.param(status(500), "InternalServerResponseError", id="server-error"),
        pytest.param(status(503), "ServiceUnavailableResponseError", id="unavailable"),
        pytest.param(status(504), "OpenRouterDefaultError", id="gateway-timeout-json"),
        pytest.param(html_status(502), "OpenRouterDefaultError", id="bad-gateway-html"),
        pytest.param(html_status(503), "OpenRouterDefaultError", id="unavailable-html"),
        pytest.param(raising(httpx.ReadTimeout), "ReadTimeout", id="timeout"),
        pytest.param(raising(httpx.ConnectError), "ConnectError", id="transport"),
        pytest.param(no_response, "NoResponseError", id="no-response"),
        pytest.param(provider_error, "ResponseValidationError", id="provider-error-in-body"),
    ],
)
def test_a_failed_call_to_the_second_model_is_a_refusal(
    handler: Callable[[httpx.Request], httpx.Response],
    kind: str,
    http_answer: list[Callable[[httpx.Request], httpx.Response]],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The real second model (pinned, one attempt) over an endpoint that fails."""
    http_answer.append(handler)
    assert_refused_after_a_failed_second_hop(pinned_second_model(), kind, caplog)


@pytest.mark.parametrize(
    ("handler", "error"),
    [
        pytest.param(status(404), NotFoundResponseError, id="mistyped-model-or-provider"),
        pytest.param(status(400), BadRequestResponseError, id="schema-rejected"),
        pytest.param(html_status(404), OpenRouterDefaultError, id="not-found-html"),
        pytest.param(html_status(400), OpenRouterDefaultError, id="bad-request-html"),
    ],
)
def test_a_config_or_request_error_of_the_second_model_still_raises(
    handler: Callable[[httpx.Request], httpx.Response],
    error: type[Exception],
    http_answer: list[Callable[[httpx.Request], httpx.Response]],
) -> None:
    """A 4xx the route can't fix is never counted as a refusal (decision 033), whatever its body."""
    http_answer.append(handler)
    with pytest.raises(error):
        ChatRoute(chat(REFUSED), pinned_second_model()).ask(MESSAGES, FORMAT, Small)


def pinned_second_model() -> BaseChatModel:
    """The real second model (pinned, one attempt), over the mocked endpoint."""
    settings = Settings(_env_file=None, openrouter_api_key=SecretStr("k"))  # pyright: ignore[reportCallIssue]
    return chat_model(
        model="google/gemini-3.1-flash-lite",
        provider_order=["google-vertex/eu"],
        allow_fallbacks=False,
        max_retries=0,
        settings=settings,
    )


class Unrecorded(CannotOverwriteExistingCassetteException):
    """What a replay raises for a call its cassette lacks, without a cassette to describe."""

    def __init__(self, message: str) -> None:
        Exception.__init__(self, message)


@pytest.mark.parametrize("error", [Unrecorded, RuntimeError])
def test_any_other_error_of_the_second_call_still_raises(error: type[Exception]) -> None:
    """A bug, or a replay whose second call isn't recorded, is never
    hidden behind the refusal step."""

    class Broken(RecordingChat):
        def _generate(self, *args: Any, **kwargs: Any) -> ChatResult:
            raise error("not a model failure")

    with pytest.raises(error):
        ChatRoute(chat(REFUSED), Broken(messages=iter(()))).ask(MESSAGES, FORMAT, Small)
