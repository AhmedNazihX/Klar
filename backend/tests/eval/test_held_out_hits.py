"""Held-out rows a stored run retrieved, read from its traces (aiact/eval/held_out_hits.py, V8).
Synthetic traces for the rules; one traced search (real lookup code over a stand-in database) for
the path from the posted run to the count. No network."""

from collections.abc import Sequence
from uuid import uuid4

import pytest
from typer.testing import CliRunner

from aiact.cli import app
from aiact.eval import held_out_hits, records, tool_calls
from aiact.eval.held_out_hits import (
    HELD_OUT_IDS,
    NoTraceToCheckError,
    held_out_report,
    retrieved_ids,
)
from aiact.eval.tool_calls import TraceRun
from aiact.retrieval import search
from aiact.retrieval import tracing as lookup_tracing
from aiact.retrieval.search import search_ai_act
from tests.eval.test_tool_calls import FakeCursor, FakeLangSmith, RunRow, _row
from tests.retrieval.test_tracing import SECRET, FakeEmbedder, _search_row, posted_runs, traced
from tests.retrieval.test_tracing import FakeConnection as DatabaseConnection

PILE_B_ROW = "guide:guide-high-risk-annex-iii:example:hr-ex-002"
PILE_A_ROW = "guide:guide-high-risk-annex-iii:example:hr-ex-001"


class FakeConnection:
    """Answers the trace-id query and the held-out id query with fixed rows."""

    def __init__(self, trace_ids: Sequence[str | None]) -> None:
        self.trace_ids = trace_ids

    def execute(self, query: str, params: Sequence[object] = ()) -> FakeCursor:
        if query == HELD_OUT_IDS:
            return FakeCursor([(PILE_B_ROW,)])
        return FakeCursor([(trace_id,) for trace_id in self.trace_ids])


def _searched(*hit_ids: str) -> list[RunRow]:
    step = _row("high_risk")
    return [step, _row("search_ai_act", step, {lookup_tracing.HIT_IDS: list(hit_ids)})]


def _report(traces: dict[str, list[RunRow]], trace_ids: Sequence[str | None]) -> str:
    connection = FakeConnection(trace_ids)
    return held_out_report(connection, FakeLangSmith(traces), uuid4())  # pyright: ignore[reportArgumentType]


def test_a_trace_that_retrieved_a_held_out_row_is_counted() -> None:
    traces = {"gap": _searched(PILE_A_ROW, PILE_B_ROW), "clean": _searched(PILE_A_ROW)}
    text = _report(traces, ["gap", "clean", None])
    assert "- Traces checked: 2" in text
    assert "- Traces that retrieved a held-out row: 1 of 2 (50.0%)" in text
    assert "- Distinct held-out rows retrieved: 1" in text
    assert "- Cases without a trace: 1" in text


def test_a_reported_run_retrieves_none() -> None:
    text = _report({"a": _searched(PILE_A_ROW), "b": _searched()}, ["a", "b"])
    assert "- Traces that retrieved a held-out row: 0 of 2 (0.0%)" in text


def test_a_fetched_held_out_row_counts_too() -> None:
    step = _row("high_risk")
    fetched = [step, _row("get_provision", step, {lookup_tracing.PROVISION_ID: PILE_B_ROW})]
    text = _report({"a": fetched}, ["a"])
    assert "- Traces that retrieved a held-out row: 1 of 1 (100.0%)" in text


def test_traces_that_cannot_tell_are_counted_apart() -> None:
    step = _row("high_risk")
    without_ids = [step, _row("search_ai_act", step, {lookup_tracing.DOC_KEYS: ["guideline"]})]
    still_open = [step, _row("search_ai_act", step, has_ended=False)]
    traces = {"ok": _searched(PILE_A_ROW), "old": without_ids, "open": still_open}
    text = _report(traces, ["ok", "old", "open", "gone"])
    assert "- Traces checked: 1" in text
    assert (
        "- Left out, a search without recorded hit ids: 1 (traced before V8 recorded them)" in text
    )
    assert "- Left out, still being ingested: 1" in text
    assert (
        "- Left out, no runs returned: 1 (expired, another workspace, or not yet ingested)" in text
    )


def test_a_run_with_no_trace_to_check_is_refused() -> None:
    step = _row("high_risk")
    without_ids = [step, _row("search_ai_act", step)]
    with pytest.raises(NoTraceToCheckError, match="1 with a search that recorded no hit ids"):
        _report({"old": without_ids}, ["old"])


def test_a_failed_lookup_retrieves_nothing() -> None:
    runs = [
        TraceRun(id="s", name="high_risk"),
        TraceRun(id="f", parent_run_id="s", name="get_provision", error="ProvisionNotFoundError"),
    ]
    assert retrieved_ids(runs) == frozenset()


def test_a_traced_search_shows_the_held_out_row_it_returned(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """From the real search's posted run to the count: the metadata the check reads is there."""
    rows = [_search_row(1, PILE_B_ROW), _search_row(2, PILE_A_ROW)]
    monkeypatch.setattr(search, "_run", lambda connection, statement, params: rows)
    session = traced(_search)
    posted = [
        TraceRun(
            id=run["id"],
            parent_run_id=run.get("parent_run_id"),
            name=run["name"],
            error=run.get("error"),
            metadata=dict((run["extra"] or {}).get("metadata") or {}),  # pyright: ignore[reportArgumentType]
        )
        for run in posted_runs(session).values()
    ]
    assert retrieved_ids(posted) == frozenset({PILE_B_ROW, PILE_A_ROW})


def _search() -> None:
    search_ai_act(
        SECRET,
        doc_keys={"guideline"},
        max_distance=None,
        embedder=FakeEmbedder(),
        connection=DatabaseConnection(),  # pyright: ignore[reportArgumentType]
    )


cli = CliRunner()


def test_cli_needs_a_langsmith_key(monkeypatch: pytest.MonkeyPatch) -> None:
    def no_key(settings: object) -> None:
        raise tool_calls.TracingNotConfiguredError("LANGSMITH_API_KEY is not set")

    monkeypatch.setattr(tool_calls, "langsmith_source", no_key)
    outcome = cli.invoke(app, ["evaluate", "held-out-hits", str(uuid4())])
    assert outcome.exit_code == 2
    assert "LANGSMITH_API_KEY is not set" in outcome.stderr


def test_cli_prints_the_report(monkeypatch: pytest.MonkeyPatch) -> None:
    class Connection:
        def __enter__(self) -> "Connection":
            return self

        def __exit__(self, *exc: object) -> None:
            return None

    monkeypatch.setattr(tool_calls, "langsmith_source", lambda settings: object())
    monkeypatch.setattr(records, "connect", Connection)
    monkeypatch.setattr(
        held_out_hits, "held_out_report", lambda conn, source, run_id: f"## {run_id}\n"
    )
    run_id = uuid4()
    outcome = cli.invoke(app, ["evaluate", "held-out-hits", str(run_id)])
    assert (outcome.exit_code, outcome.stdout) == (0, f"## {run_id}\n")
