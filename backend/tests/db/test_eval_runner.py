"""The eval runner end to end with the dummy classifier, writing to the local Supabase Postgres.

Everything runs inside the test's rolled-back transaction: the store's writes become savepoints.
"""

from decimal import Decimal

import psycopg
import pytest

from aiact.eval.cases import BenchmarkCase, CaseLabel, CaseSet
from aiact.eval.records import PostgresRunStore
from aiact.eval.runner import (
    Classification,
    ClassifierFailedError,
    ClassifierInfo,
    ClassifierInput,
    DummyClassifier,
    ExcludeMode,
    RunOptions,
    RunStatus,
    run_benchmark,
)
from aiact.schemas import ClassificationResult, Language, RiskClass

pytestmark = pytest.mark.db

GIT_SHA = "0123456789abcdef0123456789abcdef01234567"
CASES = tuple(
    BenchmarkCase(
        id=f"fixture-run-{number}",
        set_name=CaseSet.OWN,
        language=Language.EN,
        description=f"Made-up description {number}",
        label=CaseLabel(risk_class=RiskClass.MINIMAL_RISK),
        label_citation=("art:3:1",),
    )
    for number in range(5)
)


def test_dummy_run_writes_runs_and_case_results(db: psycopg.Connection) -> None:
    db.execute("select 1")  # opens the test's transaction, so the store's writes nest in it
    options = RunOptions(
        benchmark=CaseSet.OWN,
        classifier_name="dummy",
        exclude_mode=ExcludeMode.ALL,
        git_sha=GIT_SHA,
        subset=3,
        concurrency=2,
    )
    summary = run_benchmark(CASES, DummyClassifier(), PostgresRunStore(db), options, None)
    assert summary.status is RunStatus.COMPLETED

    run = db.execute(
        "select git_sha, benchmark, config, cost_usd, tokens from eval_runs where id = %s",
        (summary.run_id,),
    ).fetchone()
    assert run is not None
    git_sha, benchmark, config, cost_usd, tokens = run
    assert (git_sha, benchmark, cost_usd, tokens) == (GIT_SHA, "own", Decimal(0), 0)
    assert config["classifier"] == "dummy"
    assert config["model"] is None
    assert config["outcome"]["status"] == "completed"
    assert config["outcome"]["cases_scored"] == 3

    rows = db.execute(
        "select case_id, predicted, label, scores from eval_case_results where run_id = %s"
        " order by case_id",
        (summary.run_id,),
    ).fetchall()
    assert len(rows) == 3
    for _, predicted, label, scores in rows:
        assert ClassificationResult.model_validate(predicted).risk_class is RiskClass.OUT_OF_SCOPE
        assert label["label"]["risk_class"] == "minimal_risk"
        assert label["set_name"] == "own"
        assert scores == {"cost_usd": 0.0, "tokens": 0, "is_error": False}


class SpendingFailureClassifier:
    info = ClassifierInfo(model="fake/model")

    def classify(self, request: ClassifierInput) -> Classification:
        raise ClassifierFailedError(0.4, 50, RuntimeError("answer did not validate"))


def test_failed_cases_that_spent_are_in_the_stored_total(db: psycopg.Connection) -> None:
    db.execute("select 1")
    options = RunOptions(
        benchmark=CaseSet.OWN,
        classifier_name="fake",
        exclude_mode=ExcludeMode.ALL,
        git_sha=GIT_SHA,
        concurrency=1,
        max_cost_usd=1.0,
    )
    summary = run_benchmark(CASES, SpendingFailureClassifier(), PostgresRunStore(db), options, None)
    assert summary.status is RunStatus.COST_CAP_REACHED

    run = db.execute(
        "select cost_usd, tokens, config -> 'outcome' ->> 'status' from eval_runs where id = %s",
        (summary.run_id,),
    ).fetchone()
    assert run == (Decimal("1.2"), 150, "cost_cap_reached")
    row = db.execute(
        "select count(*), sum((scores ->> 'cost_usd')::numeric) from eval_case_results"
        " where run_id = %s and (scores ->> 'is_error')::boolean",
        (summary.run_id,),
    ).fetchone()
    assert row == (3, Decimal("1.2"))
