"""The run report read from stored eval records (aiact/eval/report.py) against local Postgres."""

from collections.abc import Mapping
from uuid import UUID, uuid4

import psycopg
import pytest
from psycopg.types.json import Jsonb
from pydantic import BaseModel, JsonValue

from aiact.eval.cases import BenchmarkCase, CaseSet
from aiact.eval.metrics import metric_scorer
from aiact.eval.records import PostgresRunStore
from aiact.eval.report import (
    RunNotFoundError,
    RunRecordError,
    load_citation_index,
    load_stored_cases,
    run_report,
)
from aiact.eval.runner import DummyClassifier, ExcludeMode, RunOptions, run_benchmark
from aiact.schemas import ClassificationResult, RiskClass, Role
from tests.eval.outcomes import HIGH_ANNEX_POINT, WORKED_EXAMPLE_PROVISIONS, case, result

pytestmark = pytest.mark.db

GIT_SHA = "0123456789abcdef0123456789abcdef01234567"
CONFIG = {"model": "openai/gpt-6-luna", "embedding": None, "retrieval": None}


def _insert_run(db: psycopg.Connection) -> UUID:
    row = db.execute(
        "insert into eval_runs (git_sha, benchmark, config) values (%s, 'own', %s) returning id",
        (GIT_SHA, Jsonb(CONFIG)),
    ).fetchone()
    assert row is not None
    return row[0]


def _insert_case(db: psycopg.Connection, run_id: UUID, label: object, predicted: object) -> None:
    case_id = label["id"] if isinstance(label, dict) else "broken"
    db.execute(
        "insert into eval_case_results (run_id, case_id, predicted, label) values (%s, %s, %s, %s)",
        (run_id, case_id, Jsonb(predicted), Jsonb(label)),
    )


def _insert_worked_example_provisions(db: psycopg.Connection) -> None:
    row = db.execute(
        """
        insert into documents
          (doc_key, title, doc_type, status, law_version, language, source_url, sha256)
        values
          ('v2-report-test', 'Test', 'law', 'final', 'amended', 'en', 'https://example.eu/', %s)
        returning id
        """,
        ("b" * 64,),
    ).fetchone()
    assert row is not None
    for provision_id in sorted(WORKED_EXAMPLE_PROVISIONS):
        db.execute(
            """
            insert into provisions (provision_id, document_id, language, heading, text, valid_from)
            values (%s, %s, 'en', 'Heading', 'Text', '2024-08-01')
            """,
            (provision_id, row[0]),
        )


def _dump(model: BaseModel) -> dict[str, object]:
    return model.model_dump(mode="json")


def test_report_from_a_stored_run(db: psycopg.Connection) -> None:
    _insert_worked_example_provisions(db)
    run_id = _insert_run(db)
    hit = case("a", role=Role.DEPLOYER, annex_point=HIGH_ANNEX_POINT)
    _insert_case(db, run_id, _dump(hit), _dump(result()))
    _insert_case(db, run_id, _dump(case("b")), _dump(result(RiskClass.MINIMAL_RISK)))
    _insert_case(db, run_id, _dump(case("c")), {"error": "timeout"})

    stored = load_stored_cases(db, run_id)
    assert [row.outcome.case.id for row in stored] == ["a", "b", "c"]
    assert stored[2].outcome.result is None
    assert {pid for pid, _ in load_citation_index(db)} >= WORKED_EXAMPLE_PROVISIONS

    report = run_report(db, run_id)
    assert f"## Run {run_id}" in report
    assert "- Model: openai/gpt-6-luna" in report
    assert "| Risk-class accuracy | 33.3% | 1/3 |" in report
    assert "| Citation existence | 100.0% | 12/12 |" in report


def test_unknown_run_is_an_error(db: psycopg.Connection) -> None:
    with pytest.raises(RunNotFoundError):
        run_report(db, uuid4())


def test_invalid_stored_prediction_names_the_case(db: psycopg.Connection) -> None:
    run_id = _insert_run(db)
    _insert_case(db, run_id, _dump(case("a")), {"risk_class": "high_risk"})
    with pytest.raises(RunRecordError, match="case a") as raised:
        load_stored_cases(db, run_id)
    assert "made-up system" not in str(raised.value).lower()


class RecordingStore(PostgresRunStore):
    """The production store, remembering the run id it created."""

    run_id: UUID | None = None

    def start_run(self, git_sha: str, benchmark: str, config: Mapping[str, JsonValue]) -> UUID:
        self.run_id = super().start_run(git_sha, benchmark, config)
        return self.run_id


def test_a_dummy_run_written_by_the_runner_reads_back_into_the_report(
    db: psycopg.Connection,
) -> None:
    cases = (case("a"), case("b", tags=("triple:t1",)), case("c", tags=("triple:t1",)))

    def scorer(label: BenchmarkCase, predicted: ClassificationResult) -> dict[str, bool | None]:
        if label.id == "c":
            raise ValueError("scorer bug")
        return metric_scorer()(label, predicted)

    options = RunOptions(
        benchmark=CaseSet.OWN,
        classifier_name="dummy",
        exclude_mode=ExcludeMode.ALL,
        git_sha=GIT_SHA,
        concurrency=1,
    )
    db.execute("select 1")  # opens the test's transaction, so the store's writes nest in it
    store = RecordingStore(db)
    with pytest.raises(ValueError, match="scorer bug"):
        run_benchmark(cases, DummyClassifier(), store, options, None, scorer)
    assert store.run_id is not None

    report = run_report(db, store.run_id)
    # The dummy answers out_of_scope; a and b are labelled high_risk; c's scoring failed.
    assert "- Cases: 2 (0 failed)" in report
    assert "| Risk-class accuracy | 0.0% | 0/2 |" in report
    assert "Scoring failed, left out of the metrics: c" in report
