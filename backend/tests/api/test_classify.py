"""`POST /classify` over scripted nodes (no model, database or network): the SSE events in order,
a failed check ending the stream with an `error` event and no class, setup errors as a 503
before any event, bodies rejected before any node is built, and a client disconnect stopping the
run. INIT's worked example through the API, on the recorded engine, is in
`test_classify_replay.py`."""

import json
import logging
import threading
from collections.abc import Iterator
from dataclasses import dataclass

import anyio
import httpx
import pytest
from fastapi import FastAPI

from aiact.api import create_app
from aiact.api.classify import BUSY, BUSY_RETRY_SECONDS, UNAVAILABLE
from aiact.engine import (
    ErrorEvent,
    ResultEvent,
    StepEvent,
)
from aiact.engine.classify import ClassifyRequest
from aiact.engine.graph import CheckNode, EngineNodes
from aiact.engine.scripted import Script, no_match, scripted_nodes
from aiact.engine.state import CheckOutcome, EngineState, FactsOutcome
from aiact.llm import LLMConfigError
from aiact.schemas import (
    STEP_ORDER,
    Citation,
    FollowUpQuestion,
    Language,
    LawVersion,
    RiskClass,
    Status,
    StepName,
    StepResult,
)
from aiact.settings import Settings
from tests.api.conftest import (
    BASE_URL,
    FULL_RUN,
    api_settings,
    outline,
    sse_events,
    use_builder,
    use_nodes,
)

DESCRIPTION = (
    "We use a tool that reads incoming job applications, scores them, and shows HR a ranked "
    "shortlist. We bought it from a vendor and didn't change it."
)
BODY = {"description": DESCRIPTION, "language": "en", "as_of": "2026-10-06"}
SECRET = "the-model-quoted-this-description"
"""Text a failed node's `__cause__` carries (pydantic's input_value fragment of the reply)."""


def cite(provision_id: str, quote: str) -> Citation:
    return Citation(
        provision_id=provision_id,
        document_id="ai-act-consolidated",
        law_version=LawVersion.AMENDED,
        language=Language.EN,
        quote=quote,
    )


HIGH_RISK_STEP = StepResult(
    step=StepName.HIGH_RISK,
    decision="High-risk: recruitment (Annex III point 4(a)).",
    citations=(
        cite("annex:III:4:a", "recruitment or selection of natural persons"),
        cite("art:6:3", "shall not be considered to be high-risk"),
    ),
)
SCRIPT = Script(
    checks={StepName.HIGH_RISK: CheckOutcome(step=HIGH_RISK_STEP)},
    risk_class=RiskClass.HIGH_RISK,
)


def with_check(nodes: EngineNodes, name: StepName, check: CheckNode) -> EngineNodes:
    return EngineNodes(
        facts=nodes.facts, checks={**nodes.checks, name: check}, finalize=nodes.finalize
    )


async def post(client: httpx.AsyncClient, body: object = BODY) -> httpx.Response:
    return await client.post("/classify", json=body)


# --- The stream ---------------------------------------------------------------------------------


@pytest.mark.anyio
async def test_the_stream_sends_the_facts_each_check_as_it_starts_and_ends_then_the_result(
    app: FastAPI, client: httpx.AsyncClient
) -> None:
    use_nodes(app, scripted_nodes(SCRIPT))
    response = await post(client)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    events = sse_events(response.text)
    assert outline(events) == FULL_RUN
    high_risk = next(
        e for e in events if isinstance(e, StepEvent) and e.step.step is StepName.HIGH_RISK
    )
    assert high_risk.matches == ("annex:III:4:a",)
    others = [e for e in events if isinstance(e, StepEvent) and e is not high_risk]
    assert all(e.matches == () for e in others)
    final = events[-1]
    assert isinstance(final, ResultEvent)
    assert final.result.risk_class is RiskClass.HIGH_RISK
    assert final.result.law_version.value == "amended"
    assert final.result.disclaimer


@pytest.mark.anyio
async def test_a_paused_step_arrives_with_its_status_and_question(
    app: FastAPI, client: httpx.AsyncClient
) -> None:
    paused = StepResult(
        step=StepName.SCOPE,
        decision="Working assumption: in scope.",
        status=Status.NEEDS_MORE_INFORMATION,
        missing_fact=FollowUpQuestion(id="ai_system", text="Does it learn from data?"),
    )
    use_nodes(app, scripted_nodes(Script(checks={StepName.SCOPE: CheckOutcome(step=paused)})))
    events = sse_events((await post(client)).text)
    scope = next(e for e in events if isinstance(e, StepEvent))
    assert scope.step == paused
    final = events[-1]
    assert isinstance(final, ResultEvent)
    assert final.result.status is Status.NEEDS_MORE_INFORMATION


@pytest.mark.anyio
async def test_a_failed_check_ends_the_stream_with_an_error_naming_it_and_no_class(
    app: FastAPI, client: httpx.AsyncClient, caplog: pytest.LogCaptureFixture
) -> None:
    def fails(_state: EngineState) -> CheckOutcome:
        try:
            raise ValueError(f"input_value='{SECRET}'")
        except ValueError as exc:
            raise RuntimeError("the reply did not fit the schema") from exc

    use_nodes(app, with_check(scripted_nodes(SCRIPT), StepName.HIGH_RISK, fails))
    with caplog.at_level(logging.DEBUG):
        response = await post(client)
    assert response.status_code == 200
    events = sse_events(response.text)
    last = events[-1]
    assert isinstance(last, ErrorEvent)
    assert last.step == StepName.HIGH_RISK.value
    assert "high_risk" in last.message and "no class" in last.message
    assert not any(isinstance(e, ResultEvent) for e in events)
    assert [e.step.step for e in events if isinstance(e, StepEvent)] == [
        StepName.SCOPE,
        StepName.PROHIBITED,
    ]
    for text in (response.text, caplog.text):
        assert SECRET not in text
        assert DESCRIPTION not in text
        assert "Traceback" not in text


@pytest.mark.anyio
async def test_the_error_message_is_in_the_runs_language(
    app: FastAPI, client: httpx.AsyncClient
) -> None:
    def fails(_state: EngineState) -> CheckOutcome:
        raise RuntimeError("boom")

    use_nodes(app, with_check(scripted_nodes(Script()), StepName.SCOPE, fails))
    events = sse_events((await post(client, {**BODY, "language": "de"})).text)
    last = events[-1]
    assert isinstance(last, ErrorEvent)
    assert "Klar keine Klasse" in last.message


# --- Before the stream --------------------------------------------------------------------------


@pytest.mark.anyio
@pytest.mark.parametrize(
    "error", [LLMConfigError("ENGINE_MODEL is not set"), OSError("records unreadable")]
)
async def test_a_setup_error_is_a_503_before_any_event(
    app: FastAPI,
    client: httpx.AsyncClient,
    caplog: pytest.LogCaptureFixture,
    error: Exception,
) -> None:
    def unconfigured(_settings: Settings, _meter: object) -> EngineNodes:
        raise error

    use_builder(app, unconfigured)
    with caplog.at_level(logging.DEBUG):
        response = await post(client)
    assert response.status_code == 503
    assert response.json() == {"detail": UNAVAILABLE}
    assert f"classification setup failed: {type(error).__name__}" in caplog.text
    for text in (response.text, caplog.text):
        assert str(error) not in text
        assert DESCRIPTION not in text
        assert "Traceback" not in text


def never_built(_settings: Settings, _meter: object) -> EngineNodes:
    raise AssertionError("the run was set up for a rejected body")


@pytest.mark.anyio
@pytest.mark.parametrize(
    "changes",
    [
        {"include_held_out": True},
        {"exclude_source_example_ids": ["hr-ex-001"]},
        {"description": "   "},
        {"description": "x" * (ClassifyRequest.MAX_DESCRIPTION_CHARS + 1)},
        {"answers": {f"q_{i}": "yes" for i in range(ClassifyRequest.MAX_ANSWERS + 1)}},
        {"answers": {"eu_use": "y" * (ClassifyRequest.MAX_ANSWER_CHARS + 1)}},
        {"answers": {"Not An Id": "yes"}},
        {"language": "fr"},
        {"law_version": "draft"},
    ],
    ids=[
        "held_out_opt_in",
        "excluded_examples",
        "blank",
        "description_too_long",
        "too_many_answers",
        "answer_too_long",
        "bad_answer_id",
        "language",
        "law_version",
    ],
)
async def test_a_bad_body_is_a_422_before_the_run_is_set_up(
    app: FastAPI, client: httpx.AsyncClient, changes: dict[str, object]
) -> None:
    use_builder(app, never_built)
    response = await post(client, {**BODY, **changes})
    assert response.status_code == 422


def description_catcher(seen: list[str]) -> EngineNodes:
    """The scripted nodes, with a facts node that notes the description the engine reads."""
    nodes = scripted_nodes(SCRIPT)

    def facts(state: EngineState) -> FactsOutcome:
        seen.append(state["description"])
        return nodes.facts(state)

    return EngineNodes(facts=facts, checks=nodes.checks, finalize=nodes.finalize)


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("language", "heading"),
    [("en", "Answers to follow-up questions:"), ("de", "Antworten auf Rückfragen:")],
)
async def test_a_follow_up_answer_reaches_the_description_the_engine_reads(
    app: FastAPI, client: httpx.AsyncClient, language: str, heading: str
) -> None:
    # P5b's follow-up loop: the screen sends the original description and the answers; the
    # engine reads them appended, one line each, under the heading (decision 019).
    seen: list[str] = []
    use_nodes(app, description_catcher(seen))
    answers = {
        "eu_link": "Yes. Question: Is the system used in the EU?",
        "confirmed_fact_1": "Confirmed:\nIt ranks the applications.",
    }
    response = await post(client, {**BODY, "language": language, "answers": answers})
    assert response.status_code == 200
    assert isinstance(sse_events(response.text)[-1], ResultEvent)
    assert seen == [
        f"{DESCRIPTION}\n\n{heading}\n"
        "- eu_link: Yes. Question: Is the system used in the EU?\n"
        "- confirmed_fact_1: Confirmed: It ranks the applications."
    ]


@pytest.mark.anyio
async def test_without_answers_the_engine_reads_the_description_alone(
    app: FastAPI, client: httpx.AsyncClient
) -> None:
    seen: list[str] = []
    use_nodes(app, description_catcher(seen))
    assert (await post(client)).status_code == 200
    assert seen == [DESCRIPTION]


@pytest.mark.anyio
async def test_the_language_is_required(app: FastAPI, client: httpx.AsyncClient) -> None:
    use_builder(app, never_built)
    body = {key: value for key, value in BODY.items() if key != "language"}
    assert (await post(client, body)).status_code == 422


# --- A client disconnect ------------------------------------------------------------------------


class ScopeGate:
    """Checks that note their name; scope signals `started` and then waits for `release`, so
    the client can leave while it runs."""

    def __init__(self) -> None:
        self.ran: list[StepName] = []
        self.started = threading.Event()
        self.release = threading.Event()

    def checks(self) -> dict[StepName, CheckNode]:
        return {name: self._check(name) for name in STEP_ORDER}

    def _check(self, name: StepName) -> CheckNode:
        def run(_state: EngineState) -> CheckOutcome:
            self.ran.append(name)
            if name is StepName.SCOPE:
                self.started.set()
                assert self.release.wait(timeout=10), "scope was never released"
            return no_match(name)

        return run


def http_scope() -> dict[str, object]:
    return {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": "/classify",
        "raw_path": b"/classify",
        "query_string": b"",
        "root_path": "",
        "headers": [(b"content-type", b"application/json"), (b"host", b"testserver")],
        "client": ("127.0.0.1", 50000),
        "server": ("testserver", 80),
    }


COST_LINE = "classification cost"
"""The line the engine logs once per run, when its event stream is closed or finished."""


@dataclass(frozen=True)
class LeftRun:
    """What a client that left mid-run saw, and the run's state when the app returned."""

    sent: tuple[dict[str, object], ...]
    ran: tuple[StepName, ...]
    cost_lines: int

    @property
    def bodies(self) -> bytes:
        return b"".join(body for m in self.sent if isinstance(body := m.get("body"), bytes))


async def leave_while_scope_runs(
    app: FastAPI, gate: ScopeGate, caplog: pytest.LogCaptureFixture
) -> LeftRun:
    """POST /classify over raw ASGI and disconnect once the scope check has started. Scope is
    released only once every task is blocked, so the disconnect has been handled by then. The
    run's state is read the moment the app returns."""
    stub = scripted_nodes(Script())
    use_nodes(app, EngineNodes(stub.facts, gate.checks(), stub.finalize))
    sent: list[dict[str, object]] = []
    calls = 0
    left: LeftRun | None = None

    async def release_when_idle() -> None:
        await anyio.wait_all_tasks_blocked()
        gate.release.set()

    async def send(message: dict[str, object]) -> None:
        sent.append(message)

    with caplog.at_level(logging.INFO):
        async with anyio.create_task_group() as tasks:

            async def receive() -> dict[str, object]:
                nonlocal calls
                calls += 1
                if calls == 1:
                    return {"type": "http.request", "body": json.dumps(BODY).encode()}
                await anyio.to_thread.run_sync(gate.started.wait)
                tasks.start_soon(release_when_idle)
                return {"type": "http.disconnect"}

            with anyio.fail_after(10):
                await app(http_scope(), receive, send)  # pyright: ignore[reportArgumentType]
            left = LeftRun(tuple(sent), tuple(gate.ran), caplog.text.count(COST_LINE))
    gate.release.set()
    assert left is not None
    return left


@pytest.mark.anyio
async def test_a_client_that_leaves_stops_and_closes_the_run(
    app: FastAPI, caplog: pytest.LogCaptureFixture
) -> None:
    """Scope finishes (a thread can't be interrupted), no later check starts, and the run is
    closed (its cost logged once) before the app returns."""
    left = await leave_while_scope_runs(app, ScopeGate(), caplog)
    assert left.ran == (StepName.SCOPE,)
    assert left.cost_lines == 1
    assert left.sent[0]["status"] == 200
    assert b'"event":"result"' not in left.bodies
    assert b'"event":"step","step":{"step":"scope"' not in left.bodies


# --- Classifications at once --------------------------------------------------------------------


@pytest.fixture
def one_slot_app() -> Iterator[FastAPI]:
    built = create_app(api_settings(classify_max_concurrent=1))
    yield built
    built.dependency_overrides.clear()


@pytest.mark.anyio
async def test_a_classification_over_the_concurrency_cap_is_refused_at_once(
    one_slot_app: FastAPI,
) -> None:
    """With the one slot taken by a run that waits in scope, a second request gets a 503 with
    `Retry-After` and sets up nothing; once the run ends, the slot is free again."""
    gate = ScopeGate()
    stub = scripted_nodes(Script())
    nodes = EngineNodes(stub.facts, gate.checks(), stub.finalize)
    built: list[int] = []

    def counting(_settings: Settings, _meter: object) -> EngineNodes:
        built.append(1)
        return nodes

    use_builder(one_slot_app, counting)
    transport = httpx.ASGITransport(app=one_slot_app)
    async with httpx.AsyncClient(transport=transport, base_url=BASE_URL) as client:
        first: list[httpx.Response] = []
        refused: httpx.Response | None = None

        async def run_first() -> None:
            first.append(await post(client))

        async with anyio.create_task_group() as tasks:
            tasks.start_soon(run_first)
            with anyio.fail_after(10):
                await anyio.to_thread.run_sync(gate.started.wait)
            refused = await post(client)
            gate.release.set()
        assert refused is not None
        assert refused.status_code == 503
        assert refused.json() == {"detail": BUSY}
        assert refused.headers["retry-after"] == str(BUSY_RETRY_SECONDS)
        assert built == [1]  # the refused request set nothing up
        assert outline(sse_events(first[0].text)) == FULL_RUN
        assert (await post(client)).status_code == 200  # the slot was given back


@pytest.mark.anyio
async def test_a_failed_setup_gives_its_slot_back(one_slot_app: FastAPI) -> None:
    def unconfigured(_settings: Settings, _meter: object) -> EngineNodes:
        raise LLMConfigError("ENGINE_MODEL is not set")

    transport = httpx.ASGITransport(app=one_slot_app)
    async with httpx.AsyncClient(transport=transport, base_url=BASE_URL) as client:
        use_builder(one_slot_app, unconfigured)
        assert (await post(client)).status_code == 503
        use_nodes(one_slot_app, scripted_nodes(Script()))
        assert (await post(client)).status_code == 200


@pytest.mark.anyio
async def test_a_client_that_leaves_gives_its_slot_back(
    one_slot_app: FastAPI, caplog: pytest.LogCaptureFixture
) -> None:
    await leave_while_scope_runs(one_slot_app, ScopeGate(), caplog)
    use_nodes(one_slot_app, scripted_nodes(Script()))
    transport = httpx.ASGITransport(app=one_slot_app)
    async with httpx.AsyncClient(transport=transport, base_url=BASE_URL) as client:
        assert (await post(client)).status_code == 200


@pytest.mark.anyio
async def test_a_busy_refusal_does_not_spend_the_clients_rate_limit() -> None:
    """With two classifications a minute, one running and one refused as busy, the client
    still has its second classification once the slot is free."""
    app = create_app(api_settings(classify_max_concurrent=1, rate_limit_classify=2))
    gate = ScopeGate()
    stub = scripted_nodes(Script())
    use_nodes(app, EngineNodes(stub.facts, gate.checks(), stub.finalize))
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url=BASE_URL) as client:
        refused: httpx.Response | None = None
        async with anyio.create_task_group() as tasks:
            tasks.start_soon(post, client)
            with anyio.fail_after(10):
                await anyio.to_thread.run_sync(gate.started.wait)
            refused = await post(client)
            gate.release.set()
        assert refused is not None and refused.status_code == 503
        use_nodes(app, scripted_nodes(Script()))
        assert (await post(client)).status_code == 200
        assert (await post(client)).status_code == 429  # the limit itself still holds
