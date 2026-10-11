"""The held-out vs in-corpus gap of two stored runs (aiact/eval/gap.py)."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import psycopg
import pytest
from typer.testing import CliRunner

from aiact.cli import app
from aiact.eval import gap, records
from aiact.eval.gap import LIMITS, RunMismatchError, check_pair, gap_points, render_markdown
from aiact.eval.metrics import Rate
from aiact.eval.report import RunInfo

HELDOUT_ID = UUID("00000000-0000-4000-8000-000000000001")
ALL_ID = UUID("00000000-0000-4000-8000-000000000002")


def info(run_id: UUID = HELDOUT_ID, **changes: object) -> RunInfo:
    values: dict[str, object] = {
        "id": run_id,
        "benchmark": "commission_b",
        "git_sha": "0" * 40,
        "started_at": datetime(2026, 10, 11, tzinfo=UTC),
        "model": "openai/gpt-6-luna-20260922",
        "classifier": "engine",
        "exclude_mode": "heldout",
        "status": "completed",
    } | changes
    return RunInfo.model_validate(values)


def test_a_heldout_run_and_its_gap_run_match() -> None:
    check_pair(info(), info(ALL_ID, exclude_mode="all"))
    source = "00000000-0000-4000-8000-000000000009"
    check_pair(info(answers_from=source), info(ALL_ID, exclude_mode="all", answers_from=source))


@pytest.mark.parametrize(
    ("first", "second", "message"),
    [
        ({}, {"exclude_mode": "heldout"}, "give the heldout run first"),
        ({"exclude_mode": "all"}, {"exclude_mode": "heldout"}, "give the heldout run first"),
        ({}, {"exclude_mode": "all", "benchmark": "own"}, "differ in benchmark"),
        ({}, {"exclude_mode": "all", "classifier": "baseline_luna"}, "differ in classifier"),
        ({}, {"exclude_mode": "all", "model": "other/model"}, "differ in model"),
        ({}, {"exclude_mode": "all", "subset": 20}, "differ in subset"),
        ({"subset": 20, "seed": 0}, {"exclude_mode": "all", "subset": 20, "seed": 1}, "seed"),
        (
            {"second_model": "google/gemini-3.1-flash-lite"},
            {"exclude_mode": "all", "second_model": None},
            "differ in second_model",
        ),
        (
            {"answers_from": "00000000-0000-4000-8000-000000000009"},
            {"exclude_mode": "all"},
            "differ in answers_from",
        ),
        ({"status": "cost_cap_reached"}, {"exclude_mode": "all"}, "status cost_cap_reached"),
        ({}, {"exclude_mode": "all", "status": "cost_cap_reached"}, "status cost_cap_reached"),
        ({"status": "interrupted"}, {"exclude_mode": "all"}, "status interrupted"),
        ({"status": "running"}, {"exclude_mode": "all"}, "status running"),
        ({"status": None}, {"exclude_mode": "all"}, "status n/a, not completed"),
    ],
)
def test_runs_that_cannot_be_compared_are_refused(
    first: dict[str, object], second: dict[str, object], message: str
) -> None:
    with pytest.raises(RunMismatchError, match=message):
        check_pair(info(HELDOUT_ID, **first), info(ALL_ID, **second))


def test_the_gap_is_heldout_minus_all_in_points() -> None:
    assert gap_points(Rate(hits=6, total=10), Rate(hits=8, total=10)) == "-20.0 pp"
    assert gap_points(Rate(hits=8, total=10), Rate(hits=6, total=10)) == "+20.0 pp"
    assert gap_points(Rate(hits=0, total=0), Rate(hits=6, total=10)) == "n/a"


def test_the_table_quotes_both_runs_and_the_limits() -> None:
    rates = {"Every case": (Rate(hits=6, total=10), Rate(hits=7, total=10))}
    text = render_markdown(info(), info(ALL_ID, exclude_mode="all"), rates)
    lines = text.splitlines()
    assert lines[0] == "## Held-out vs in-corpus gap: `commission_b`"
    assert f"- Held-out run (the reported number): {HELDOUT_ID}, status completed" in lines
    assert "| Every case | 60.0% (6/10) | 70.0% (7/10) | -10.0 pp |" in lines
    assert all(f"- {limit}" in lines for limit in LIMITS)
    assert len(LIMITS) == 4
    assert "6-gram coverage only (threshold 0.8, B13)" in LIMITS[0]
    assert "hr-ex-024, -067, -124, -187" in LIMITS[1]


cli = CliRunner()


def test_cli_reports_a_mismatch(monkeypatch: pytest.MonkeyPatch) -> None:
    class Connection:
        def __enter__(self) -> "Connection":
            return self

        def __exit__(self, *exc: object) -> None:
            return None

    def mismatched(conn: object, heldout: UUID, everything: UUID) -> str:
        raise RunMismatchError("the runs differ in benchmark: own and commission_b")

    monkeypatch.setattr(records, "connect", Connection)
    monkeypatch.setattr(gap, "gap_report", mismatched)
    outcome = cli.invoke(app, ["evaluate", "gap", str(uuid4()), str(uuid4())])
    assert outcome.exit_code == 2
    assert "Error: the runs differ in benchmark" in outcome.stderr


@pytest.mark.parametrize(
    ("error", "message"),
    [
        (psycopg.OperationalError("no route to postgresql://u:hunter2@db"), "database error"),
        (records.DatabaseNotConfiguredError("DATABASE_URL is not set"), "DATABASE_URL is not set"),
    ],
)
def test_cli_database_errors_exit_2(
    monkeypatch: pytest.MonkeyPatch, error: Exception, message: str
) -> None:
    def connect() -> object:
        raise error

    monkeypatch.setattr(records, "connect", connect)
    outcome = cli.invoke(app, ["evaluate", "gap", str(uuid4()), str(uuid4())])
    assert outcome.exit_code == 2
    assert f"Error: {message}" in outcome.stderr
    assert "hunter2" not in outcome.output
