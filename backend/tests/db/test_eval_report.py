"""The run report read from stored eval records (aiact/eval/report.py) against local Postgres."""

from collections.abc import Mapping
from uuid import UUID, uuid4

import psycopg
import pytest
from psycopg.types.json import Jsonb
from pydantic import BaseModel, JsonValue

from aiact.eval.cases import BenchmarkCase, CaseSet
from aiact.eval.citation_index import citation_checker, load_citation_index
from aiact.eval.metrics import Outcome, case_scores, metric_scorer
from aiact.eval.records import PostgresRunStore
from aiact.eval.report import (
    RunNotFoundError,
    RunRecordError,
    load_stored_cases,
    run_report,
    run_reports,
)
from aiact.eval.runner import DummyClassifier, ExcludeMode, RunOptions, run_benchmark
from aiact.schemas import ClassificationResult, LawVersion, RiskClass, Role
from tests.eval.outcomes import HIGH_ANNEX_POINT, WORKED_EXAMPLE_PROVISIONS, case, result
from tests.schemas.worked_example import DOCUMENT_ID

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


def _insert_case(
    db: psycopg.Connection,
    run_id: UUID,
    label: object,
    predicted: object,
    scores: Mapping[str, object] | None = None,
) -> None:
    case_id = label["id"] if isinstance(label, dict) else "broken"
    db.execute(
        "insert into eval_case_results (run_id, case_id, predicted, label, scores)"
        " values (%s, %s, %s, %s, %s)",
        (run_id, case_id, Jsonb(predicted), Jsonb(label), Jsonb(dict(scores or {}))),
    )


def _insert_worked_example_provisions(db: psycopg.Connection) -> None:
    """Make sure the worked example's provisions exist. DOCUMENT_ID is the real doc_key, so on a
    database with the corpus loaded the document (and most provisions) already exist: reuse the
    row and add only the missing provisions (all inside the test's rolled-back transaction)."""
    row = db.execute(
        """
        insert into documents
          (doc_key, title, doc_type, status, law_version, language, source_url, sha256)
        values
          (%s, 'Test', 'law', 'final', 'amended', 'en', 'https://example.eu/', %s)
        on conflict (doc_key, law_version, language) do update set doc_key = documents.doc_key
        returning id
        """,
        (DOCUMENT_ID, "b" * 64),
    ).fetchone()
    assert row is not None
    for provision_id in sorted(WORKED_EXAMPLE_PROVISIONS):
        db.execute(
            """
            insert into provisions (provision_id, document_id, language, heading, text, valid_from)
            select %(pid)s, %(doc)s, 'en', 'Heading', 'Text', '2024-08-01'
            where not exists (
              select 1 from provisions
              where document_id = %(doc)s and language = 'en' and provision_id = %(pid)s
            )
            """,
            {"pid": provision_id, "doc": row[0]},
        )


def _dump(model: BaseModel) -> dict[str, object]:
    return model.model_dump(mode="json")


def test_citations_resolve_exactly_against_the_corpus(db: psycopg.Connection) -> None:
    _insert_worked_example_provisions(db)
    exists = citation_checker(load_citation_index(db))
    assert exists is not None
    (quoted,) = result().steps[0].citations  # art:3:1 in the worked example's document
    assert exists(quoted)
    assert not exists(quoted.model_copy(update={"document_id": "made-up-document"}))
    assert not exists(quoted.model_copy(update={"law_version": LawVersion.ORIGINAL}))


def test_report_from_a_stored_run_uses_the_citation_scores_of_run_time(
    db: psycopg.Connection,
) -> None:
    _insert_worked_example_provisions(db)
    exists = citation_checker(load_citation_index(db))
    run_id = _insert_run(db)
    hit = case("a", role=Role.DEPLOYER, annex_point=HIGH_ANNEX_POINT)
    for label, predicted in ((hit, result()), (case("b"), result(RiskClass.MINIMAL_RISK))):
        scores = case_scores(Outcome(case=label, result=predicted), exists)
        _insert_case(db, run_id, _dump(label), _dump(predicted), scores)
    _insert_case(db, run_id, _dump(case("c")), {"error": "timeout"}, {"is_error": True})

    stored = load_stored_cases(db, run_id)
    assert [row.outcome.case.id for row in stored] == ["a", "b", "c"]
    assert stored[2].outcome.result is None

    report = run_report(db, run_id)
    assert f"## Run {run_id}" in report
    assert "- Model: openai/gpt-6-luna" in report
    assert "| Risk-class accuracy (development cases) | 33.3% | 1/3 |" in report
    assert "| Citation existence (at run time) | 100.0% | 2/2 |" in report

    # Today's corpus loses a cited provision: the stored run's report must not change. Its
    # children go in the same statement (the loaded corpus has them; the parent key needs it).
    db.execute(
        "delete from provisions p using documents d"
        " where d.id = p.document_id and d.doc_key = %s"
        " and (p.provision_id = 'art:5:1' or p.provision_id like 'art:5:1:%%')",
        (DOCUMENT_ID,),
    )
    assert "art:5:1" in WORKED_EXAMPLE_PROVISIONS
    assert run_report(db, run_id) == report


def test_a_stored_pile_b_runs_text_names_no_case(db: psycopg.Connection) -> None:
    row = db.execute(
        "insert into eval_runs (git_sha, benchmark, config)"
        " values (%s, 'commission_b', %s) returning id",
        (GIT_SHA, Jsonb(CONFIG)),
    ).fetchone()
    assert row is not None
    run_id = row[0]
    missed = case("cb-test-missed", set_name=CaseSet.COMMISSION_B)  # made up: see test_isolation
    _insert_case(db, run_id, _dump(missed), _dump(result(RiskClass.OUT_OF_SCOPE)))

    parts = run_reports(db, run_id, "eval/reports/pile_b/run-x.md")
    assert "cb-test-missed" not in parts.text
    assert "- **scope** (1)" in parts.text.splitlines()
    assert "`eval/reports/pile_b/run-x.md`" in parts.text
    assert parts.pile_b_text is not None
    assert "- **scope** (1): cb-test-missed (expected high_risk" in parts.pile_b_text
    assert run_reports(db, run_id).pile_b_text is None
    assert "cb-test-missed" in run_report(db, run_id)


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
    store = RecordingStore(db)
    with pytest.raises(ValueError, match="scorer bug"):
        run_benchmark(cases, DummyClassifier(), store, options, None, scorer)
    assert store.run_id is not None

    report = run_report(db, store.run_id)
    # The dummy answers out_of_scope; a and b are labelled high_risk; c's scoring failed.
    assert "- Cases: 2 (0 failed)" in report
    assert "| Risk-class accuracy (development cases) | 0.0% | 0/2 |" in report
    assert "Scoring failed, left out of the metrics: c" in report
