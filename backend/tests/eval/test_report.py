from collections.abc import Mapping
from datetime import UTC, datetime
from uuid import UUID, uuid4

import psycopg
import pytest
from pydantic import JsonValue
from typer.testing import CliRunner

from aiact.cli import app
from aiact.eval import records, report
from aiact.eval.cases import BenchmarkCase, CaseSet
from aiact.eval.metrics import metric_scorer, summarize
from aiact.eval.report import (
    RunInfo,
    RunNotFoundError,
    StoredCase,
    build_report,
    render_markdown,
    stored_case,
)
from aiact.eval.runner import (
    RUN_SCORE_KEYS,
    CaseRecord,
    Classification,
    ClassifierInfo,
    ClassifierInput,
    DummyClassifier,
    ExcludeMode,
    RunOptions,
    run_benchmark,
)
from aiact.schemas import Citation, ClassificationResult, RiskClass, Role
from tests.eval.outcomes import HIGH_ANNEX_POINT, case, outcome, result

INFO = RunInfo(
    id=UUID("00000000-0000-4000-8000-000000000001"),
    benchmark="own",
    git_sha="0123456789abcdef0123456789abcdef01234567",
    started_at=datetime(2026, 9, 28, 12, 0, tzinfo=UTC),
    model="openai/gpt-6-luna",
)


def always(citation: Citation) -> bool:
    return True


def test_report_is_a_markdown_table_of_every_metric() -> None:
    outcomes = [
        outcome(case("a", role=Role.DEPLOYER, annex_point=HIGH_ANNEX_POINT)),
        outcome(case("b"), result(RiskClass.MINIMAL_RISK)),
        outcome(case("c"), failed=True),
    ]
    report = render_markdown(INFO, summarize(outcomes, always))
    lines = report.splitlines()
    assert lines[0] == f"## Run {INFO.id}"
    assert "- Cases: 3 (1 failed)" in lines
    assert "| Metric | Value | Count |" in lines
    assert "| Risk-class accuracy | 33.3% | 1/3 |" in lines
    assert "| False-low-risk rate | 50.0% | 1/2 |" in lines
    assert "| Annex point accuracy | 100.0% | 1/1 |" in lines
    assert "| Consistency | n/a | 0/0 |" in lines
    assert "| Citation existence (at run time) | 100.0% | 2/2 |" in lines
    assert "| Ambiguous answered needs-more-information | 0 | |" in lines
    assert "| Academic out-of-scope review | 0 | |" in lines
    table = [line for line in lines if line.startswith("| ")]
    assert "| Basis accuracy (Commission cases) | n/a | 0/0 |" in lines
    assert "| Flip variant asked or flagged | n/a | 0/0 |" in lines
    assert "| Label citation cited (any of) | 0.0% | 0/2 |" in lines
    assert len(table) == 19  # header, separator and 17 metric rows


def test_report_names_no_description() -> None:
    report = render_markdown(INFO, summarize([outcome(case("a"))], always))
    assert "made-up system" not in report.lower()


# --- the runner's stored rows (V1 contract) ----------------------------------------------------


class MemoryStore:
    """Keeps what the runner would write to eval_runs / eval_case_results."""

    def __init__(self) -> None:
        self.records: list[CaseRecord] = []

    def start_run(self, git_sha: str, benchmark: str, config: Mapping[str, JsonValue]) -> UUID:
        return INFO.id

    def add_case(self, run_id: UUID, record: CaseRecord) -> None:
        self.records.append(record)

    def finish_run(self, run_id: UUID, outcome: Mapping[str, JsonValue]) -> None:
        pass


class FailingOnB:
    """The dummy classifier, except that case b's description makes it fail."""

    info = ClassifierInfo(model=None)

    def classify(self, request: ClassifierInput) -> Classification:
        if request.description == "fails":
            raise RuntimeError("model timed out")
        return DummyClassifier().classify(request)


OPTIONS = RunOptions(
    benchmark=CaseSet.OWN,
    classifier_name="dummy",
    exclude_mode=ExcludeMode.ALL,
    git_sha="0" * 40,
    concurrency=1,
)


def run_cases(cases: tuple[BenchmarkCase, ...]) -> MemoryStore:
    store = MemoryStore()
    run_benchmark(cases, FailingOnB(), store, OPTIONS, None, metric_scorer(always))
    return store


def report_of(store: MemoryStore) -> str:
    rows = tuple(stored_case(r.case_id, r.label, r.predicted, r.scores) for r in store.records)
    return build_report(INFO, rows)


def test_runner_rows_feed_the_report() -> None:
    cases = (
        case("a", RiskClass.OUT_OF_SCOPE),
        case("b").model_copy(update={"description": "fails"}),
        case("c", RiskClass.MINIMAL_RISK),
    )
    store = run_cases(cases)
    stored = {r.case_id: r for r in store.records}
    assert stored["a"].scores["risk_class_accuracy"] is True
    assert stored["c"].scores["risk_class_accuracy"] is False
    assert stored["b"].scores["is_error"] is True

    text = report_of(store)
    assert "- Cases: 3 (1 failed)" in text
    assert "| Risk-class accuracy | 33.3% | 1/3 |" in text


def test_report_leaves_out_the_runners_own_scores() -> None:
    text = report_of(run_cases((case("a", RiskClass.OUT_OF_SCOPE),)))
    table = [line for line in text.splitlines() if line.startswith("| ")]
    assert not any(key in line for key in RUN_SCORE_KEYS for line in table)


def test_metric_scorer_uses_only_unreserved_names() -> None:
    scores = metric_scorer(always)(case("a"), result())
    assert scores.keys().isdisjoint(RUN_SCORE_KEYS)
    assert "citation_existence" not in metric_scorer()(case("a"), result())


def test_a_scoring_error_is_listed_and_left_out_of_the_metrics() -> None:
    def scorer(label: BenchmarkCase, predicted: ClassificationResult) -> dict[str, bool | None]:
        if label.id == "c":
            raise ValueError("scorer bug")
        return metric_scorer(always)(label, predicted)

    cases = (case("a", RiskClass.OUT_OF_SCOPE), case("c", RiskClass.OUT_OF_SCOPE))
    store = MemoryStore()
    with pytest.raises(ValueError, match="scorer bug"):
        run_benchmark(cases, FailingOnB(), store, OPTIONS, None, scorer)
    assert store.records[-1].scores["scoring_error"] is True

    text = report_of(store)
    assert "- Cases: 1 (0 failed)" in text
    assert "Scoring failed, left out of the metrics: c" in text


def _row(case_id: str, scores: dict[str, object]) -> StoredCase:
    label = case(case_id).model_dump(mode="json")
    return stored_case(case_id, label, result().model_dump(mode="json"), scores)


def test_citation_existence_comes_from_the_scores_stored_at_run_time() -> None:
    rows = (
        _row("a", {"citation_existence": True}),
        _row("b", {"citation_existence": False}),
        _row("c", {"citation_existence": None}),
    )
    text = build_report(INFO, rows)
    assert "| Citation existence (at run time) | 50.0% | 1/2 |" in text


def test_a_run_without_stored_citation_scores_shows_na() -> None:
    text = build_report(INFO, (_row("a", {"risk_class_accuracy": True}),))
    assert "| Citation existence (at run time) | n/a | 0/0 |" in text


# --- CLI ---------------------------------------------------------------------------------------

cli = CliRunner()
SECRET_URL = "postgresql://postgres:hunter2@db.example:5432/postgres"


class FakeConnection:
    def __enter__(self) -> "FakeConnection":
        return self

    def __exit__(self, *exc: object) -> None:
        return None


def test_cli_prints_the_report(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(records, "connect", FakeConnection)
    monkeypatch.setattr(report, "run_report", lambda conn, run_id: f"## Run {run_id}\n")
    run_id = uuid4()
    outcome = cli.invoke(app, ["evaluate", "report", str(run_id)])
    assert outcome.exit_code == 0
    assert outcome.stdout == f"## Run {run_id}\n"


def test_cli_unknown_run_exits_2(monkeypatch: pytest.MonkeyPatch) -> None:
    def missing(conn: object, run_id: UUID) -> str:
        raise RunNotFoundError(f"no eval run with id {run_id}")

    monkeypatch.setattr(records, "connect", FakeConnection)
    monkeypatch.setattr(report, "run_report", missing)
    outcome = cli.invoke(app, ["evaluate", "report", str(uuid4())])
    assert outcome.exit_code == 2
    assert outcome.stderr.startswith("Error: no eval run with id")


def test_cli_database_error_hides_the_url(monkeypatch: pytest.MonkeyPatch) -> None:
    def connect() -> object:
        raise psycopg.OperationalError(f"could not connect to {SECRET_URL}")

    monkeypatch.setattr(records, "connect", connect)
    outcome = cli.invoke(app, ["evaluate", "report", str(uuid4())])
    assert outcome.exit_code == 2
    assert "Error: database error (OperationalError)" in outcome.stderr
    assert "hunter2" not in outcome.output


def test_cli_rejects_a_bad_run_id() -> None:
    outcome = cli.invoke(app, ["evaluate", "report", "not-a-uuid"])
    assert outcome.exit_code == 2
