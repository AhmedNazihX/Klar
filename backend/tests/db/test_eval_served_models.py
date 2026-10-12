"""The `models` score (which model served each node's calls, X2c) against the scores check of
`eval_case_results` (V8a's migration, supabase/migrations/*_scores_allow_served_models.sql).

V8's first paid run failed on its first case write: F5's check allowed only number, boolean or
null scores, and `models` is `{node: {model: calls}}`. Everything runs inside the test's
rolled-back transaction: the store's writes become savepoints.
"""

from uuid import UUID

import psycopg
import pytest
from psycopg.types.json import Jsonb

from aiact.eval.cases import BenchmarkCase, CaseLabel, CaseSet
from aiact.eval.records import PostgresRunStore
from aiact.eval.report import load_stored_cases
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
from aiact.schemas import Language, RiskClass

pytestmark = pytest.mark.db

GIT_SHA = "0123456789abcdef0123456789abcdef01234567"
FIRST_MODEL = "anthropic/claude-sonnet-5"
SECOND_MODEL = "mistralai/mistral-large-3"
# Engine-shaped: several nodes, and a refused request the second model answered (decision 033)
# shows under both models.
SERVED = {
    "scope": {FIRST_MODEL: 1},
    "prohibited": {FIRST_MODEL: 2, SECOND_MODEL: 1},
    "facts": {FIRST_MODEL: 1},
}
CASE = BenchmarkCase(
    id="fixture-served-0",
    set_name=CaseSet.OWN,
    language=Language.EN,
    description="Made-up description",
    label=CaseLabel(risk_class=RiskClass.MINIMAL_RISK),
    label_citation=("art:3:1",),
)


class ServingClassifier:
    info = ClassifierInfo(model=FIRST_MODEL)

    def classify(self, request: ClassifierInput) -> Classification:
        result = DummyClassifier().classify(request).result
        return Classification(result, cost_usd=0.01, tokens=900, models=SERVED)


class FailingAfterServingClassifier:
    info = ClassifierInfo(model=FIRST_MODEL)

    def classify(self, request: ClassifierInput) -> Classification:
        raise ClassifierFailedError(
            0.01, 900, RuntimeError("answer did not validate"), models=SERVED
        )


def _options() -> RunOptions:
    return RunOptions(
        benchmark=CaseSet.OWN,
        classifier_name="engine",
        exclude_mode=ExcludeMode.ALL,
        git_sha=GIT_SHA,
        concurrency=1,
    )


def _stored_scores(db: psycopg.Connection, run_id: UUID) -> dict[str, object]:
    row = db.execute(
        "select scores from eval_case_results where run_id = %s and case_id = %s",
        (run_id, CASE.id),
    ).fetchone()
    assert row is not None
    return row[0]


def test_a_case_with_served_models_is_stored_and_read_back(db: psycopg.Connection) -> None:
    summary = run_benchmark((CASE,), ServingClassifier(), PostgresRunStore(db), _options(), None)
    assert summary.status is RunStatus.COMPLETED

    assert _stored_scores(db, summary.run_id) == {
        "cost_usd": 0.01,
        "tokens": 900,
        "is_error": False,
        "models": SERVED,
    }
    (stored,) = load_stored_cases(db, summary.run_id)
    assert stored.models == SERVED


def test_a_failed_case_with_served_models_is_stored(db: psycopg.Connection) -> None:
    summary = run_benchmark(
        (CASE,), FailingAfterServingClassifier(), PostgresRunStore(db), _options(), None
    )
    assert summary.status is RunStatus.COMPLETED

    scores = _stored_scores(db, summary.run_id)
    assert scores["is_error"] is True
    assert scores["models"] == SERVED


def _insert_run(db: psycopg.Connection) -> UUID:
    config = {"model": FIRST_MODEL, "embedding": None, "retrieval": None}
    row = db.execute(
        "insert into eval_runs (git_sha, benchmark, config) values (%s, 'own', %s) returning id",
        (GIT_SHA, Jsonb(config)),
    ).fetchone()
    assert row is not None
    return row[0]


def _insert_scores(db: psycopg.Connection, scores: object) -> None:
    db.execute(
        "insert into eval_case_results (run_id, case_id, predicted, label, scores)"
        " values (%s, %s, '{}', '{}', %s)",
        (_insert_run(db), CASE.id, Jsonb(scores)),
    )


@pytest.mark.parametrize(
    "scores",
    [
        {"citation_support": {"facts": {FIRST_MODEL: 1}}},
        {"tokens": {"total": 900}},
        {"models": {"facts": {FIRST_MODEL: "1"}}},
        {"models": {"facts": {FIRST_MODEL: True}}},
        {"models": {"facts": {FIRST_MODEL: None}}},
        {"models": {"facts": {FIRST_MODEL: -1}}},
        {"models": {"facts": {FIRST_MODEL: 1.5}}},
        {"models": {"facts": {FIRST_MODEL: {"calls": 1}}}},
        {"models": {"facts": [FIRST_MODEL]}},
        {"models": {"facts": 1}},
        {"models": [{"facts": {FIRST_MODEL: 1}}]},
        {"models": 3},
        {"models": None},
        ["models"],
    ],
    ids=[
        "nested-under-a-metric",
        "nested-under-tokens",
        "string-calls",
        "boolean-calls",
        "null-calls",
        "negative-calls",
        "fractional-calls",
        "object-calls",
        "node-is-array",
        "node-is-number",
        "models-is-array",
        "models-is-number",
        "models-is-null",
        "scores-not-object",
    ],
)
def test_the_check_still_refuses_other_shapes(db: psycopg.Connection, scores: object) -> None:
    with pytest.raises(psycopg.errors.CheckViolation):
        _insert_scores(db, scores)


@pytest.mark.parametrize(
    "scores",
    [
        {"models": {}},
        {"models": {"facts": {}}},
        {"models": {"facts": {FIRST_MODEL: 0}}},
        {"risk_class_accuracy": True, "citation_support": 0.5, "downgrade": None},
    ],
    ids=["no-nodes", "node-without-calls", "zero-calls", "flat-metrics"],
)
def test_the_check_accepts_these_shapes(db: psycopg.Connection, scores: object) -> None:
    _insert_scores(db, scores)
