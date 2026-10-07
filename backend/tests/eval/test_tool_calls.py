"""Tool-call correctness (V7): which lookups each step made, read from a trace, and the rate per
step. Synthetic traces for the rules; one traced engine run (scripted nodes, real lookups over a
stand-in database) for the whole path from the posted runs to the rate. No network."""

import json
from collections.abc import Iterable, Sequence
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from langchain_core.tracers.langchain import LangChainTracer
from langsmith.schemas import Run
from pydantic import JsonValue, SecretStr
from typer.testing import CliRunner

from aiact.cli import app
from aiact.engine import ClassifyRequest, run_classification
from aiact.engine import classify as classify_module
from aiact.engine import tracing as engine_tracing
from aiact.engine.graph import CheckNode, EngineNodes
from aiact.engine.scripted import Script, scripted_nodes
from aiact.engine.state import CheckOutcome, EngineState
from aiact.engine.tracing import build_client, langsmith_tracer
from aiact.engine.usage import UsageMeter
from aiact.eval import records, tool_calls
from aiact.eval.tool_calls import (
    ANNEX_III_POINTS,
    EXPECTED_LOOKUPS,
    RunNotFoundError,
    StepCheck,
    TraceRecordError,
    TraceRun,
    check_trace,
    render_markdown,
    step_rates,
    stored_traces,
    tool_call_report,
)
from aiact.retrieval import provisions, search
from aiact.retrieval import tracing as lookup_tracing
from aiact.retrieval.provisions import get_provision
from aiact.retrieval.search import search_ai_act
from aiact.schemas import Language, StepName
from aiact.settings import Settings
from tests.engine.test_tracing import RecordingSession
from tests.retrieval.test_tracing import ROW, FakeEmbedder

SECRET = "the night shifts of our Leipzig depot"
DESCRIPTION = f"We use a tool that ranks applicants for {SECRET}."

# --- Synthetic traces ---------------------------------------------------------------------------


class TraceBuilder:
    """A trace written run by run: a root, step runs under it, lookups under a step."""

    def __init__(self) -> None:
        self.runs: list[TraceRun] = [TraceRun(id="root", name="classify")]

    def step(self, step: StepName, parent: str = "root") -> str:
        return self._add(step.value, parent)

    def fetched(self, parent: str, provision_id: str, *, error: str | None = None) -> str:
        metadata: dict[str, JsonValue] = {lookup_tracing.PROVISION_ID: provision_id}
        return self._add("get_provision", parent, metadata, error)

    def searched(
        self, parent: str, *, doc_keys: Sequence[str] = (), doc_types: Sequence[str] = ()
    ) -> str:
        metadata: dict[str, JsonValue] = {}
        if doc_keys:
            metadata[lookup_tracing.DOC_KEYS] = list(doc_keys)
        if doc_types:
            metadata[lookup_tracing.DOC_TYPES] = list(doc_types)
        return self._add("search_ai_act", parent, metadata)

    def _add(
        self,
        name: str,
        parent: str,
        metadata: dict[str, JsonValue] | None = None,
        error: str | None = None,
    ) -> str:
        run_id = f"run-{len(self.runs)}"
        self.runs.append(
            TraceRun(
                id=run_id, parent_run_id=parent, name=name, error=error, metadata=metadata or {}
            )
        )
        return run_id


def _by_step(checks: Iterable[StepCheck]) -> dict[StepName, tuple[str, ...]]:
    return {check.step: check.missing for check in checks}


def test_the_prohibited_step_that_fetched_art_5_and_searched_its_guidelines_is_correct() -> None:
    trace = TraceBuilder()
    step = trace.step(StepName.PROHIBITED)
    trace.fetched(step, "art:5")
    trace.searched(step, doc_keys=["guide-prohibited"])
    assert _by_step(check_trace(trace.runs)) == {StepName.PROHIBITED: ()}


def test_a_step_that_skipped_a_lookup_misses_it() -> None:
    trace = TraceBuilder()
    step = trace.step(StepName.PROHIBITED)
    trace.fetched(step, "art:5:1:a")  # a point is not the article the check must read whole
    trace.searched(step, doc_keys=["guide-art50"])  # another check's guidelines
    assert _by_step(check_trace(trace.runs)) == {
        StepName.PROHIBITED: ("Art. 5 fetched", "prohibited-practice guidelines searched")
    }


def test_a_lookup_counts_for_its_own_step_only() -> None:
    trace = TraceBuilder()
    scope = trace.step(StepName.SCOPE)
    trace.step(StepName.PROHIBITED)
    trace.fetched(scope, "art:5")
    missing = _by_step(check_trace(trace.runs))
    assert "Art. 5 fetched" in missing[StepName.PROHIBITED]


def test_a_lookup_nested_deeper_belongs_to_the_nearest_step_above_it() -> None:
    trace = TraceBuilder()
    step = trace.step(StepName.ROLE_OBLIGATIONS)
    validator = trace._add("citation_check", step)  # pyright: ignore[reportPrivateUsage]
    trace.fetched(validator, "art:3:4")
    assert _by_step(check_trace(trace.runs)) == {StepName.ROLE_OBLIGATIONS: ()}


def test_a_failed_lookup_fetched_nothing() -> None:
    trace = TraceBuilder()
    step = trace.step(StepName.TRANSPARENCY)
    trace.fetched(step, "art:50", error="ProvisionNotFoundError (details withheld)")
    trace.searched(step, doc_keys=["guide-art50"])
    assert _by_step(check_trace(trace.runs)) == {StepName.TRANSPARENCY: ("Art. 50 fetched",)}


def test_high_risk_needs_every_annex_iii_point_but_any_annex_i_point() -> None:
    trace = TraceBuilder()
    step = trace.step(StepName.HIGH_RISK)
    for point in sorted(ANNEX_III_POINTS - {"annex:III:4:a"}):
        trace.fetched(step, point)
    trace.fetched(step, "annex:I:B:21")
    trace.fetched(step, "annex:I:A:1", error="ProvisionNotFoundError")  # renumbered
    trace.searched(step, doc_types=["guideline"])
    assert _by_step(check_trace(trace.runs)) == {
        StepName.HIGH_RISK: ("every Annex III point fetched",)
    }
    trace.fetched(step, "annex:III:4:a")
    assert _by_step(check_trace(trace.runs)) == {StepName.HIGH_RISK: ()}


def test_scope_needs_both_articles_and_the_definition_guidelines() -> None:
    trace = TraceBuilder()
    step = trace.step(StepName.SCOPE)
    trace.fetched(step, "art:3:1")
    trace.searched(step, doc_keys=["guide-definition"])
    assert _by_step(check_trace(trace.runs)) == {StepName.SCOPE: ("Art. 2 fetched",)}


def test_a_step_that_did_not_run_is_not_checked() -> None:
    trace = TraceBuilder()
    trace.step(StepName.SCOPE)
    checked = [check.step for check in check_trace(trace.runs)]
    assert checked == [StepName.SCOPE]


def test_malformed_lookup_metadata_is_an_error_naming_the_run() -> None:
    trace = TraceBuilder()
    step = trace.step(StepName.PROHIBITED)
    trace.runs.append(
        TraceRun(
            id="odd",
            parent_run_id=step,
            name="get_provision",
            metadata={lookup_tracing.PROVISION_ID: 5},
        )
    )
    with pytest.raises(TraceRecordError, match="odd"):
        check_trace(trace.runs)


def test_every_step_has_expected_lookups() -> None:
    assert set(EXPECTED_LOOKUPS) == set(StepName)
    assert all(EXPECTED_LOOKUPS.values())


# --- The rate per step --------------------------------------------------------------------------


def test_the_rate_is_reported_per_step_over_the_traces_where_it_ran() -> None:
    checks = [
        StepCheck(step=StepName.PROHIBITED, missing=()),
        StepCheck(step=StepName.PROHIBITED, missing=("Art. 5 fetched",)),
        StepCheck(step=StepName.PROHIBITED, missing=()),
        StepCheck(step=StepName.SCOPE, missing=()),
    ]
    rates = {rate.step: rate for rate in step_rates(checks)}
    assert list(rates) == list(StepName)
    assert (rates[StepName.PROHIBITED].rate.hits, rates[StepName.PROHIBITED].rate.total) == (2, 3)
    assert rates[StepName.PROHIBITED].missed == {"Art. 5 fetched": 1}
    assert rates[StepName.HIGH_RISK].rate.total == 0

    run_id = uuid4()
    lines = render_markdown(run_id, step_rates(checks), traces=3, untraced=1).splitlines()
    assert lines[0] == f"## Tool-call correctness, run {run_id}"
    assert "- Traces checked: 3 (1 cases without a trace)" in lines
    assert "| prohibited | 66.7% | 2/3 | Art. 5 fetched (1) |" in lines
    assert "| scope | 100.0% | 1/1 |  |" in lines
    assert "| high_risk | n/a | 0/0 |  |" in lines


# --- Reading stored runs and LangSmith ----------------------------------------------------------


class FakeCursor:
    def __init__(self, rows: list[tuple[object, ...]]) -> None:
        self._rows = rows

    def fetchall(self) -> list[tuple[object, ...]]:
        return self._rows


class FakeConnection:
    """Answers the trace-id query with fixed rows and keeps the parameters."""

    def __init__(self, trace_ids: Sequence[str | None]) -> None:
        self.trace_ids = trace_ids
        self.params: list[object] = []

    def execute(self, query: str, params: Sequence[object]) -> FakeCursor:
        self.params.append(params)
        return FakeCursor([(trace_id,) for trace_id in self.trace_ids])


def _run(run_id: UUID, name: str, parent: UUID | None, metadata: dict[str, object]) -> Run:
    return Run(
        id=run_id,
        name=name,
        start_time=datetime(2026, 10, 7, tzinfo=UTC),
        run_type="tool",
        inputs={},
        trace_id=uuid4(),
        parent_run_id=parent,
        extra={"metadata": metadata},
    )


class FakeLangSmith:
    """Answers `list_runs` with one trace's runs and keeps the fields asked for."""

    def __init__(self, runs: Sequence[Run]) -> None:
        self.runs = runs
        self.asked: list[tuple[str, tuple[str, ...]]] = []

    def list_runs(self, *, trace_id: str, select: Sequence[str]) -> Iterable[Run]:
        self.asked.append((trace_id, tuple(select)))
        return iter(self.runs)


def test_a_stored_runs_traces_are_read_without_inputs_or_outputs() -> None:
    step = uuid4()
    langsmith = FakeLangSmith(
        [
            _run(step, "prohibited", None, {"ls_run_depth": 1}),
            _run(uuid4(), "get_provision", step, {lookup_tracing.PROVISION_ID: "art:5"}),
        ]
    )
    connection = FakeConnection(["trace-a", None, "trace-b"])
    run_id = uuid4()
    text = tool_call_report(connection, langsmith, run_id)  # pyright: ignore[reportArgumentType]
    assert connection.params == [(run_id,)]
    assert [trace for trace, _ in langsmith.asked] == ["trace-a", "trace-b"]
    assert all("inputs" not in fields and "outputs" not in fields for _, fields in langsmith.asked)
    assert "- Traces checked: 2 (1 cases without a trace)" in text
    assert "| prohibited | 0.0% | 0/2 | prohibited-practice guidelines searched (2) |" in text


def test_a_run_with_no_stored_cases_is_not_found() -> None:
    with pytest.raises(RunNotFoundError):
        stored_traces(FakeConnection([]), uuid4())  # pyright: ignore[reportArgumentType]


cli = CliRunner()


def test_cli_without_a_langsmith_key_exits_2(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = Settings(_env_file=None, langsmith_api_key=None)  # pyright: ignore[reportCallIssue]
    monkeypatch.setattr("aiact.cli.get_settings", lambda: settings)
    outcome = cli.invoke(app, ["evaluate", "tool-calls", str(uuid4())])
    assert outcome.exit_code == 2
    assert outcome.stderr.startswith("Error: LANGSMITH_API_KEY is not set")


def test_cli_prints_the_report(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = Settings(_env_file=None, langsmith_api_key=SecretStr("k"))  # pyright: ignore[reportCallIssue]
    monkeypatch.setattr("aiact.cli.get_settings", lambda: settings)
    monkeypatch.setattr(records, "connect", lambda: FakeConnectionContext())
    monkeypatch.setattr(tool_calls, "tool_call_report", lambda conn, source, run_id: "table\n")
    outcome = cli.invoke(app, ["evaluate", "tool-calls", str(uuid4())])
    assert outcome.exit_code == 0
    assert outcome.stdout == "table\n"


class FakeConnectionContext:
    def __enter__(self) -> object:
        return object()

    def __exit__(self, *exc: object) -> None:
        return None


# --- One traced engine run, end to end ----------------------------------------------------------


def _with_lookups(node: CheckNode) -> CheckNode:
    """`node` after the real lookups the prohibited check makes."""

    def run(state: EngineState) -> CheckOutcome:
        connection = object()
        get_provision("art:5", connection=connection)  # pyright: ignore[reportArgumentType]
        search_ai_act(
            state["description"],
            doc_keys={"guide-prohibited"},
            max_distance=None,
            embedder=FakeEmbedder(),
            connection=connection,  # pyright: ignore[reportArgumentType]
        )
        return node(state)

    return run


def _posted_trace(sent: Sequence[str]) -> list[TraceRun]:
    """The runs a recording session received, as the check reads them (each run's create post;
    an end post carries no name)."""
    created = [json.loads(body) for body in sent if body.startswith("{")]
    return [
        TraceRun(
            id=str(run["id"]),
            parent_run_id=run.get("parent_run_id"),
            name=run["name"],
            error=run.get("error"),
            metadata=(run.get("extra") or {}).get("metadata") or {},
        )
        for run in created
        if "name" in run
    ]


def traced_engine_run(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """A traced classification in production (metadata only) whose prohibited check makes real
    lookups (over a stand-in database), posting into a recording session."""
    monkeypatch.setattr(provisions, "_rows", lambda query, params, connection: [ROW])
    monkeypatch.setattr(search, "_run", lambda connection, statement, params: [])
    session = RecordingSession()
    client = build_client(
        "lsv2-test-key",
        is_metadata_only=True,
        api_url="http://127.0.0.1:9",
        session=session,
        auto_batch_tracing=False,
    )
    monkeypatch.setattr(engine_tracing, "_client", lambda _key, *, is_metadata_only: client)
    tracers: list[LangChainTracer] = []

    def keep(settings: Settings) -> LangChainTracer | None:
        tracer = langsmith_tracer(settings)
        if tracer is not None:
            tracers.append(tracer)
        return tracer

    monkeypatch.setattr(classify_module, "langsmith_tracer", keep)
    stub = scripted_nodes(Script())
    checks = dict(stub.checks)
    checks[StepName.PROHIBITED] = _with_lookups(stub.checks[StepName.PROHIBITED])

    def build(_settings: Settings, _meter: UsageMeter) -> EngineNodes:
        return EngineNodes(facts=stub.facts, checks=checks, finalize=stub.finalize)

    settings = Settings(
        _env_file=None,  # pyright: ignore[reportCallIssue]
        openrouter_api_key=SecretStr("k"),
        langsmith_api_key=SecretStr("lsv2-test-key"),
        aiact_env="production",
    )
    request = ClassifyRequest(description=DESCRIPTION, language=Language.EN)
    run_classification(request, settings=settings, build_nodes=build)
    [tracer] = tracers
    tracer.wait_for_futures()
    client.flush()
    return session.sent


def test_a_traced_engine_run_gives_the_rate_per_step(monkeypatch: pytest.MonkeyPatch) -> None:
    sent = traced_engine_run(monkeypatch)
    rates = {rate.step: rate.rate for rate in step_rates(check_trace(_posted_trace(sent)))}
    assert (rates[StepName.PROHIBITED].hits, rates[StepName.PROHIBITED].total) == (1, 1)
    assert all(
        rates[step].hits == 0 and rates[step].total == 1
        for step in rates
        if step is not StepName.PROHIBITED
    )


def test_the_traced_lookups_post_no_description_in_production(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sent = traced_engine_run(monkeypatch)
    assert [body for body in sent if lookup_tracing.PROVISION_ID in body]
    assert not [body for body in sent if SECRET in body]
