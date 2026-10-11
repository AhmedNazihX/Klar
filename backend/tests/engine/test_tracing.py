"""LangSmith tracing of a classification (E10; INIT > Tech stack): off without a key, with no
default tracer from the environment either, and metadata only outside development, errors
included. Nothing reaches the network: posts go to a recording session."""

from collections.abc import Callable, Iterator
from concurrent.futures import ThreadPoolExecutor
from contextvars import copy_context
from typing import Literal

import pytest
import requests
from langchain_core.callbacks import CallbackManager
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage
from langchain_core.runnables.config import ensure_config, get_callback_manager_for_config
from langchain_core.tracers.langchain import LangChainTracer
from langsmith import utils as ls_utils
from pydantic import SecretStr

from aiact.engine import (
    ClassificationFailedError,
    ClassifyRequest,
    ResultEvent,
    run_classification,
    stream_classification,
    tracing,
)
from aiact.engine import classify as classify_module
from aiact.engine.graph import EngineNodes
from aiact.engine.nodes.facts import FactExtractor
from aiact.engine.scripted import Script, scripted_nodes
from aiact.engine.state import EngineState, FactsOutcome
from aiact.engine.tracing import build_client, langsmith_tracer, withheld_error
from aiact.engine.usage import UsageMeter
from aiact.schemas import Language, StepName
from aiact.settings import Settings

RUN_INPUTS = {"description": "We screen job applicants.", "language": "en"}
RUN_OUTPUTS = {"result": {"risk_class": "high_risk"}}
SECRET = "the night shifts of our Leipzig depot"
DESCRIPTION = f"We use a tool that ranks applicants for {SECRET}."
TRUNCATED = '{"facts":[{"text":"The tool ranks applicants for ' + SECRET
"""A facts reply cut off mid-answer: it quotes the description, and doesn't parse."""


def _settings(env: Literal["development", "production"] | None, key: str | None) -> Settings:
    values: dict[str, object] = {"langsmith_project": "aiact-test"}
    if env is not None:
        values["aiact_env"] = env
    if key is not None:
        values["langsmith_api_key"] = SecretStr(key)
    return Settings(_env_file=None, openrouter_api_key=SecretStr("k"), **values)  # pyright: ignore[reportCallIssue]


def test_without_a_key_nothing_is_traced() -> None:
    assert langsmith_tracer(_settings("development", None)) is None
    assert langsmith_tracer(_settings("development", "")) is None


EU_ENDPOINT = "https://eu.api.smith.langchain.com"
"""LangSmith's EU region: an EU-region key is refused (403) at the default US endpoint."""


def test_traces_go_to_the_configured_endpoint() -> None:
    settings = _settings(None, "lsv2-test-key").model_copy(
        update={"langsmith_endpoint": EU_ENDPOINT}
    )
    tracer = langsmith_tracer(settings)
    assert tracer is not None
    assert tracer.client.api_url == "https://eu.api.smith.langchain.com"


@pytest.mark.parametrize("endpoint", [None, ""])
def test_without_an_endpoint_traces_go_to_the_sdk_default(
    monkeypatch: pytest.MonkeyPatch, endpoint: str | None
) -> None:
    for name in ("LANGSMITH_ENDPOINT", "LANGCHAIN_ENDPOINT"):
        monkeypatch.delenv(name, raising=False)
    ls_utils.get_env_var.cache_clear()  # pyright: ignore[reportFunctionMemberAccess]
    settings = _settings(None, "lsv2-test-key").model_copy(update={"langsmith_endpoint": endpoint})
    tracer = langsmith_tracer(settings)
    assert tracer is not None
    assert tracer.client.api_url == "https://api.smith.langchain.com"


def test_production_is_the_default_and_its_traces_carry_metadata_only() -> None:
    tracer = langsmith_tracer(_settings(None, "lsv2-test-key"))
    assert tracer is not None
    assert tracer.project_name == "aiact-test"
    client = tracer.client
    assert client._hide_run_inputs(RUN_INPUTS) == {}  # pyright: ignore[reportPrivateUsage]
    assert client._hide_run_outputs(RUN_OUTPUTS) == {}  # pyright: ignore[reportPrivateUsage]
    withheld = client._hide_run_error(f"ValueError('{SECRET}')")  # pyright: ignore[reportPrivateUsage]
    assert isinstance(withheld, str)
    assert withheld == withheld_error("ValueError")
    assert SECRET not in withheld


def test_development_traces_keep_inputs_and_outputs() -> None:
    tracer = langsmith_tracer(_settings("development", "lsv2-test-key"))
    assert tracer is not None
    client = tracer.client
    assert client._hide_run_inputs(RUN_INPUTS) == RUN_INPUTS  # pyright: ignore[reportPrivateUsage]
    assert client._hide_run_outputs(RUN_OUTPUTS) == RUN_OUTPUTS  # pyright: ignore[reportPrivateUsage]


@pytest.mark.parametrize(
    ("error", "kind"),
    [
        ("FactsOutputError('facts answer doesn't fit')\n\nTraceback ...", "FactsOutputError"),
        ("psycopg.errors.QueryCanceled: canceling statement", "psycopg.errors.QueryCanceled"),
        ("", "Error"),
        ("  the description quoted back  ", "Error"),
    ],
)
def test_an_error_is_cut_down_to_its_type(error: str, kind: str) -> None:
    assert withheld_error(error) == tracing.WITHHELD.format(error_type=kind)


# --- What a traced run posts --------------------------------------------------------------------


class RecordingSession(requests.Session):
    """Answers every request with an empty 200 and keeps what was sent."""

    def __init__(self) -> None:
        super().__init__()
        self.sent: list[str] = []

    def request(self, method: str | bytes, url: str | bytes, *args: object, **kwargs: object):  # type: ignore[override]
        body = kwargs.get("data") or kwargs.get("json") or b""
        self.sent.append(body.decode() if isinstance(body, bytes) else str(body))
        response = requests.Response()
        response.status_code = 200
        response._content = b"{}"  # pyright: ignore[reportAttributeAccessIssue]
        return response


Failure = Literal["truncated_reply", "echoing_error"]


def traced_failing_run(
    env: Literal["development", "production"],
    monkeypatch: pytest.MonkeyPatch,
    failure: Failure = "truncated_reply",
) -> RecordingSession:
    """A traced run whose facts node fails, posting into a recording session: the real node on a
    reply cut off at `TRUNCATED`, or a node whose error echoes the description (as a provider's
    or the database's error text may)."""
    session = RecordingSession()
    client = build_client(
        "lsv2-test-key",
        is_metadata_only=env != "development",
        api_url="http://127.0.0.1:9",
        session=session,
        auto_batch_tracing=False,
    )
    monkeypatch.setattr(tracing, "_client", lambda _key, *, is_metadata_only, api_url: client)
    tracers: list[LangChainTracer] = []

    def keep(settings: Settings) -> LangChainTracer | None:
        tracer = langsmith_tracer(settings)
        if tracer is not None:
            tracers.append(tracer)
        return tracer

    monkeypatch.setattr(classify_module, "langsmith_tracer", keep)
    settings = _settings(env, "lsv2-test-key")
    model = GenericFakeChatModel(messages=iter([AIMessage(content=TRUNCATED)]))
    stub = scripted_nodes(Script())

    def echoing(_state: EngineState) -> FactsOutcome:
        raise RuntimeError(f"upstream said: {DESCRIPTION}")

    def build(_settings: Settings, _meter: UsageMeter) -> EngineNodes:
        facts = FactExtractor(settings, chat=model) if failure == "truncated_reply" else echoing
        return EngineNodes(facts=facts, checks=stub.checks, finalize=stub.finalize)

    request = ClassifyRequest(description=DESCRIPTION, language=Language.EN)
    with pytest.raises(ClassificationFailedError):
        run_classification(request, settings=settings, build_nodes=build)
    [tracer] = tracers
    tracer.wait_for_futures()
    return session


@pytest.mark.parametrize("failure", ["truncated_reply", "echoing_error"])
def test_a_failed_run_posts_no_description_text_in_production(
    failure: Failure, monkeypatch: pytest.MonkeyPatch
) -> None:
    sent = traced_failing_run("production", monkeypatch, failure).sent
    assert any('"error"' in body and "withheld" in body for body in sent)  # the failure is posted
    assert not [body for body in sent if SECRET in body]


@pytest.mark.parametrize("failure", ["truncated_reply", "echoing_error"])
def test_the_same_run_in_development_posts_the_text(
    failure: Failure, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The check above can fail: in development the description reaches the posts."""
    sent = traced_failing_run("development", monkeypatch, failure).sent
    assert [body for body in sent if SECRET in body]


# --- No default tracer --------------------------------------------------------------------------


@pytest.fixture
def tracing_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """The environment that makes langchain-core add its own tracer, with full content."""
    for name, value in (
        ("LANGSMITH_TRACING", "true"),
        ("LANGCHAIN_TRACING_V2", "true"),
        ("LANGCHAIN_API_KEY", "lsv2-env-key"),
    ):
        monkeypatch.setenv(name, value)
    ls_utils.get_env_var.cache_clear()  # pyright: ignore[reportFunctionMemberAccess]
    yield
    ls_utils.get_env_var.cache_clear()  # pyright: ignore[reportFunctionMemberAccess]


def _tracers() -> list[str]:
    manager = get_callback_manager_for_config(ensure_config())
    return [type(h).__name__ for h in manager.handlers if isinstance(h, LangChainTracer)]


def test_without_a_key_the_environment_adds_no_tracer_to_a_run(tracing_env: None) -> None:
    assert isinstance(CallbackManager.configure(), CallbackManager)
    assert _tracers() == ["LangChainTracer"]  # outside a run, the environment would trace
    seen: list[list[str]] = []
    stub = scripted_nodes(Script())

    def facts(_state: EngineState) -> FactsOutcome:
        seen.append(_tracers())
        return FactsOutcome()

    def build(_settings: Settings, _meter: UsageMeter) -> EngineNodes:
        return EngineNodes(facts=facts, checks=stub.checks, finalize=stub.finalize)

    request = ClassifyRequest(description=DESCRIPTION, language=Language.EN)
    run_classification(request, settings=_settings("production", None), build_nodes=build)
    assert seen == [[]]


def test_a_stream_read_one_event_per_fresh_context_adds_no_tracer(tracing_env: None) -> None:
    """As Starlette's StreamingResponse reads a sync iterator: each `next()` on a worker thread,
    in a fresh copy of the reader's context. Every node, the last included, sees no tracer."""
    seen: dict[str, list[str]] = {}
    stub = scripted_nodes(Script())

    def watched[T](name: str, node: Callable[[EngineState], T]) -> Callable[[EngineState], T]:
        def run(state: EngineState) -> T:
            seen[name] = _tracers()
            return node(state)

        return run

    def build(_settings: Settings, _meter: UsageMeter) -> EngineNodes:
        return EngineNodes(
            facts=watched("facts", stub.facts),
            checks={name: watched(name.value, check) for name, check in stub.checks.items()},
            finalize=watched("finalize", stub.finalize),
        )

    request = ClassifyRequest(description=DESCRIPTION, language=Language.EN)
    events = stream_classification(
        request, settings=_settings("production", None), build_nodes=build
    )
    done = object()
    read: list[object] = []
    with ThreadPoolExecutor(max_workers=1) as worker:
        while (event := worker.submit(copy_context().run, next, events, done).result()) is not done:
            read.append(event)
    assert isinstance(read[-1], ResultEvent)
    assert list(seen) == ["facts", *(name.value for name in StepName), "finalize"]
    assert all(found == [] for found in seen.values()), seen
