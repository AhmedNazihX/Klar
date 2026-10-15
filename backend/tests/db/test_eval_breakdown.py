"""`breakdown.breakdown_report` on runs stored by the runner in the test database (W1): the groups
come from the labels the run stored, and a Pile B run's breakdown names no case. Everything runs
inside the test's rolled-back transaction."""

from uuid import UUID

import psycopg
import pytest
from psycopg.types.json import Jsonb

from aiact.eval.breakdown import GroupBy, NotAClassificationRunError, breakdown_report
from aiact.eval.cases import BenchmarkCase, BusinessFunction, CaseLabel, CaseSet
from aiact.eval.records import PostgresRunStore
from aiact.eval.runner import DummyClassifier, ExcludeMode, RunOptions, RunStatus, run_benchmark
from aiact.schemas import Language, RiskClass

pytestmark = pytest.mark.db

GIT_SHA = "0123456789abcdef0123456789abcdef01234567"


def _case(
    case_id: str,
    set_name: CaseSet,
    risk_class: RiskClass,
    *,
    language: Language = Language.EN,
    function: BusinessFunction | None = None,
    tags: tuple[str, ...] = (),
) -> BenchmarkCase:
    return BenchmarkCase(
        id=case_id,
        set_name=set_name,
        language=language,
        description="Made-up description",
        label=CaseLabel(risk_class=risk_class),
        label_citation=("art:3:1",),
        business_function=function,
        tags=tags,
    )


def _run(db: psycopg.Connection, set_name: CaseSet, cases: tuple[BenchmarkCase, ...]) -> UUID:
    """Run the dummy classifier (every system out of scope) and store it."""
    options = RunOptions(
        benchmark=set_name,
        classifier_name="dummy",
        exclude_mode=ExcludeMode.ALL,
        git_sha=GIT_SHA,
        concurrency=1,
    )
    summary = run_benchmark(cases, DummyClassifier(), PostgresRunStore(db), options, None)
    assert summary.status is RunStatus.COMPLETED
    return summary.run_id


OWN = (
    _case("fixture-bd-1", CaseSet.OWN, RiskClass.OUT_OF_SCOPE, function=BusinessFunction.HR),
    _case("fixture-bd-2", CaseSet.OWN, RiskClass.HIGH_RISK, function=BusinessFunction.HR),
    _case(
        "fixture-bd-3",
        CaseSet.OWN,
        RiskClass.OUT_OF_SCOPE,
        language=Language.DE,
        function=BusinessFunction.EDUCATION,
    ),
    _case("fixture-bd-4", CaseSet.OWN, RiskClass.OUT_OF_SCOPE, language=Language.DE),
)


def test_an_own_run_breaks_down_by_business_function(db: psycopg.Connection) -> None:
    text = breakdown_report(db, _run(db, CaseSet.OWN, OWN), GroupBy.BUSINESS_FUNCTION)
    rows = [line for line in text.splitlines() if line.startswith("| ")][2:]
    assert rows == [
        "| education | 1 | 100.0% (1/1) | n/a (0/0) | n/a (0/0) | n/a (0/0) |",
        "| hr | 2 | 50.0% (1/2) | 100.0% (1/1) | n/a (0/0) | n/a (0/0) |",
        "| (none) | 1 | 100.0% (1/1) | n/a (0/0) | n/a (0/0) | n/a (0/0) |",
    ]


def test_an_own_run_breaks_down_by_language(db: psycopg.Connection) -> None:
    text = breakdown_report(db, _run(db, CaseSet.OWN, OWN), GroupBy.LANGUAGE)
    assert "| de | 2 | 100.0% (2/2) | n/a (0/0) | n/a (0/0) | n/a (0/0) |" in text
    assert "| en | 2 | 50.0% (1/2) | 100.0% (1/1) | n/a (0/0) | n/a (0/0) |" in text


def test_a_commission_run_breaks_down_by_area_and_names_no_case(db: psycopg.Connection) -> None:
    cases = (
        _case("cb-test-d1", CaseSet.COMMISSION_B, RiskClass.HIGH_RISK, tags=("area:annex_iii_4",)),
        _case(
            "cb-test-d2", CaseSet.COMMISSION_B, RiskClass.OUT_OF_SCOPE, tags=("area:annex_iii_4",)
        ),
        _case("cb-test-d3", CaseSet.COMMISSION_B, RiskClass.OUT_OF_SCOPE, tags=("area:annex_i",)),
    )
    run_id = _run(db, CaseSet.COMMISSION_B, cases)
    text = breakdown_report(db, run_id, GroupBy.AREA)
    assert "| annex_i | 1 | 100.0% (1/1) | n/a (0/0) | n/a (0/0) | n/a (0/0) |" in text
    assert "| annex_iii_4 | 2 | 50.0% (1/2) | 100.0% (1/1) | n/a (0/0) | n/a (0/0) |" in text
    for by in GroupBy:
        output = breakdown_report(db, run_id, by)
        assert all(stored.id not in output for stored in cases)
        assert "cb-test" not in output
        assert "Made-up description" not in output


def test_a_qa_run_is_refused(db: psycopg.Connection) -> None:
    row = db.execute(
        "insert into eval_runs (git_sha, benchmark, config) values (%s, 'qa', %s) returning id",
        (GIT_SHA, Jsonb({"model": None, "embedding": None, "retrieval": None})),
    ).fetchone()
    assert row is not None
    with pytest.raises(NotAClassificationRunError, match="Q&A run"):
        breakdown_report(db, row[0], GroupBy.LANGUAGE)
