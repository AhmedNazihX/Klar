from datetime import UTC, datetime
from typing import cast
from uuid import UUID, uuid4

import psycopg
import pytest
from typer.testing import CliRunner

from aiact.cli import app
from aiact.eval import breakdown, records, report
from aiact.eval.breakdown import NO_GROUP, GroupBy, group_cases, render_markdown
from aiact.eval.cases import BenchmarkCase, BusinessFunction, CaseSet
from aiact.eval.report import RunInfo, StoredCase
from aiact.schemas import Language, RiskClass
from tests.eval.outcomes import case, outcome, result

RUN_ID = UUID("00000000-0000-4000-8000-000000000007")
SERVER_NAME = "db-host-7f3a.example"
"""Stands for the server a connection error's text names; the command must never print it."""


def info(benchmark: str = "own") -> RunInfo:
    return RunInfo(
        id=RUN_ID,
        benchmark=benchmark,
        git_sha="0" * 40,
        started_at=datetime(2026, 10, 15, 3, 0, tzinfo=UTC),
        model="openai/gpt-6-luna",
        classifier="engine",
        exclude_mode="heldout",
        status="completed",
    )


def stored(
    label: BenchmarkCase, predicted: RiskClass, *, is_scoring_error: bool = False
) -> StoredCase:
    return StoredCase(outcome=outcome(label, result(predicted)), is_scoring_error=is_scoring_error)


def own(case_id: str, label: RiskClass, function: BusinessFunction | None) -> BenchmarkCase:
    return case(case_id, label).model_copy(update={"business_function": function})


def german(label: BenchmarkCase) -> BenchmarkCase:
    return label.model_copy(update={"language": Language.DE})


def commission(case_id: str, label: RiskClass, area: str | None) -> BenchmarkCase:
    tags = ("verdict:high_risk", f"area:{area}") if area else ("verdict:high_risk",)
    return case(case_id, label, set_name=CaseSet.COMMISSION_B, tags=tags)


OWN_CASES = (
    stored(own("own-a-01", RiskClass.HIGH_RISK, BusinessFunction.HR), RiskClass.HIGH_RISK),
    stored(own("own-a-02", RiskClass.HIGH_RISK, BusinessFunction.HR), RiskClass.MINIMAL_RISK),
    stored(own("own-a-03", RiskClass.MINIMAL_RISK, BusinessFunction.SALES), RiskClass.MINIMAL_RISK),
    stored(german(own("own-t-01", RiskClass.MINIMAL_RISK, None)), RiskClass.MINIMAL_RISK),
)


def test_cases_group_by_business_function_with_none_last() -> None:
    groups = group_cases(OWN_CASES, GroupBy.BUSINESS_FUNCTION)
    assert list(groups) == ["hr", "sales", NO_GROUP]
    assert [len(cases) for cases in groups.values()] == [2, 1, 1]


def test_cases_group_by_language() -> None:
    groups = group_cases(OWN_CASES, GroupBy.LANGUAGE)
    assert {name: len(cases) for name, cases in groups.items()} == {"de": 1, "en": 3}


def test_commission_cases_group_by_their_area_tag() -> None:
    cases = (
        stored(commission("cb-test-a1", RiskClass.HIGH_RISK, "annex_iii_4"), RiskClass.HIGH_RISK),
        stored(commission("cb-test-a2", RiskClass.HIGH_RISK, "annex_i"), RiskClass.HIGH_RISK),
        stored(commission("cb-test-a3", RiskClass.HIGH_RISK, None), RiskClass.HIGH_RISK),
    )
    assert list(group_cases(cases, GroupBy.AREA)) == ["annex_i", "annex_iii_4", NO_GROUP]


def test_scoring_errors_are_left_out_as_in_the_report() -> None:
    broken = stored(
        own("own-a-04", RiskClass.HIGH_RISK, BusinessFunction.HR),
        RiskClass.HIGH_RISK,
        is_scoring_error=True,
    )
    groups = group_cases((*OWN_CASES, broken), GroupBy.BUSINESS_FUNCTION)
    assert len(groups["hr"]) == 2


def test_each_group_row_has_its_count_and_rates() -> None:
    text = render_markdown(
        info(), GroupBy.BUSINESS_FUNCTION, group_cases(OWN_CASES, GroupBy.BUSINESS_FUNCTION)
    )
    lines = text.splitlines()
    assert lines[0] == f"## Run {RUN_ID} by business_function"
    assert (
        "| business_function | Cases | Risk-class accuracy | False-low-risk rate | "
        "Annex point accuracy | Role accuracy |"
    ) in lines
    assert "| hr | 2 | 50.0% (1/2) | 50.0% (1/2) | n/a (0/0) | n/a (0/0) |" in lines
    assert "| sales | 1 | 100.0% (1/1) | n/a (0/0) | n/a (0/0) | n/a (0/0) |" in lines
    assert "| (none) | 1 | 100.0% (1/1) | n/a (0/0) | n/a (0/0) | n/a (0/0) |" in lines
    assert f"- {breakdown.NOISY}" in lines


def test_the_header_is_the_reports_run_lines() -> None:
    text = render_markdown(info(), GroupBy.LANGUAGE, {})
    assert all(line in text.splitlines() for line in report.run_lines(info()))
    assert f"- Commit: `{'0' * 40}`" in text


def test_scoring_errors_are_counted_below_the_table(monkeypatch: pytest.MonkeyPatch) -> None:
    broken = stored(
        own("own-a-04", RiskClass.HIGH_RISK, BusinessFunction.HR),
        RiskClass.HIGH_RISK,
        is_scoring_error=True,
    )
    monkeypatch.setattr(breakdown, "load_run_info", lambda conn, run_id: info())
    monkeypatch.setattr(breakdown, "load_stored_cases", lambda conn, run_id: (*OWN_CASES, broken))
    text = breakdown.breakdown_report(cast(psycopg.Connection, object()), RUN_ID, GroupBy.LANGUAGE)
    assert text.splitlines()[-1] == "Scoring failed, left out of the metrics: 1"
    assert "| en | 3 |" in text
    clean = render_markdown(info(), GroupBy.LANGUAGE, group_cases(OWN_CASES, GroupBy.LANGUAGE))
    assert "Scoring failed" not in clean


def test_own_runs_are_labelled_development_cases() -> None:
    groups = group_cases(OWN_CASES, GroupBy.LANGUAGE)
    assert "development cases" in render_markdown(info("own"), GroupBy.LANGUAGE, groups)
    assert "development cases" not in render_markdown(info("academic"), GroupBy.LANGUAGE, groups)


def test_a_pile_b_breakdown_names_no_case() -> None:
    cases = tuple(
        stored(commission(f"cb-test-p{n}", RiskClass.HIGH_RISK, "annex_iii_4"), RiskClass.HIGH_RISK)
        for n in range(3)
    )
    for by in GroupBy:
        text = render_markdown(info("commission_b"), by, group_cases(cases, by), 1)
        assert "cb-test" not in text
        assert "made-up system" not in text.lower()


# --- the command -------------------------------------------------------------------------------

cli = CliRunner()


class Connection:
    def __enter__(self) -> "Connection":
        return self

    def __exit__(self, *exc: object) -> None:
        return None


def test_cli_prints_the_breakdown(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[UUID, GroupBy]] = []

    def fake(conn: object, run_id: UUID, by: GroupBy) -> str:
        calls.append((run_id, by))
        return "## Run x by area\n"

    monkeypatch.setattr(records, "connect", Connection)
    monkeypatch.setattr(breakdown, "breakdown_report", fake)
    outcome_ = cli.invoke(app, ["evaluate", "breakdown", str(RUN_ID), "--by", "area"])
    assert outcome_.exit_code == 0
    assert outcome_.stdout == "## Run x by area\n"
    assert calls == [(RUN_ID, GroupBy.AREA)]


def test_cli_refuses_an_unknown_grouping() -> None:
    outcome_ = cli.invoke(app, ["evaluate", "breakdown", str(RUN_ID), "--by", "colour"])
    assert outcome_.exit_code == 2


@pytest.mark.parametrize(
    ("error", "message"),
    [
        (
            psycopg.OperationalError(f"connection to {SERVER_NAME} failed"),
            "database error (OperationalError); check DATABASE_URL",
        ),
        (records.DatabaseNotConfiguredError("DATABASE_URL is not set"), "DATABASE_URL is not set"),
        (report.RunNotFoundError("no eval run with id x"), "no eval run with id x"),
        (report.RunRecordError("row 3: stored models are malformed"), "row 3: stored models are"),
        (breakdown.NotAClassificationRunError("run x is a Q&A run"), "run x is a Q&A run"),
    ],
)
def test_cli_errors_exit_2(monkeypatch: pytest.MonkeyPatch, error: Exception, message: str) -> None:
    def failing(conn: object, run_id: UUID, by: GroupBy) -> str:
        raise error

    monkeypatch.setattr(records, "connect", Connection)
    monkeypatch.setattr(breakdown, "breakdown_report", failing)
    outcome_ = cli.invoke(app, ["evaluate", "breakdown", str(uuid4()), "--by", "language"])
    assert outcome_.exit_code == 2
    assert f"Error: {message}" in outcome_.stderr
    assert SERVER_NAME not in outcome_.output
