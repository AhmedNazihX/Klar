from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import psycopg
import pytest
from pydantic import JsonValue
from typer.testing import CliRunner

from aiact.cli import app
from aiact.eval import records, report
from aiact.eval.cases import BenchmarkCase, CaseSet, load_cases
from aiact.eval.isolation import ContaminatedExample, ContaminatedList
from aiact.eval.judge import UNSURE_MARGIN, JudgeCheck
from aiact.eval.judged import CheckScore, stored_scores
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
from aiact.schemas import Citation, ClassificationResult, FollowUpQuestion, RiskClass, Role
from tests.eval.outcomes import HIGH_ANNEX_POINT, case, outcome, refused_result, result

CASE_FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "cases"
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
    assert "| Risk-class accuracy (development cases) | 33.3% | 1/3 |" in lines
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
    assert "| Needs a description: asked (thin cases) | n/a | 0/0 |" in lines
    assert "| Needs a description: asked wrongly (other cases) | 0.0% | 0/2 |" in lines
    assert len(table) == 23  # header, separator and 21 metric rows


def test_report_rows_show_each_commission_metric_under_its_own_name() -> None:
    settled, _ = load_cases(CaseSet.COMMISSION_B, CASE_FIXTURES)
    base = result()
    variant = FollowUpQuestion(id="variant", text="Does it do more?", about="annex:III:7:a")
    asked = result(follow_up_questions=(*base.follow_up_questions, variant))
    outcomes = [
        outcome(settled, result(RiskClass.MINIMAL_RISK)),  # basis hit, flip miss
        outcome(settled, result(RiskClass.MINIMAL_RISK)),  # basis hit, flip miss
        outcome(settled, asked),  # basis miss (high-risk), flip hit
    ]
    lines = render_markdown(INFO, summarize(outcomes, always)).splitlines()
    assert "| Basis accuracy (Commission cases) | 66.7% | 2/3 |" in lines
    assert "| Flip variant asked or flagged | 33.3% | 1/3 |" in lines
    assert "| Label citation cited (any of) | 100.0% | 3/3 |" in lines


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
    assert "| Risk-class accuracy (development cases) | 33.3% | 1/3 |" in text


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


CONFIG: dict[str, object] = {
    "model": "openai/gpt-6-luna-20260922",
    "provider": "azure/eu",
    "second_model": "google/gemini-3.1-flash-lite",
    "second_provider": "google-vertex/eu",
    "classifier": "engine",
    "exclude_mode": "all",
    "subset": 20,
    "seed": 0,
    "git_dirty": True,
    "answers_from": "00000000-0000-4000-8000-0000000000aa",
    "outcome": {"status": "cost_cap_reached"},
}


def _info(benchmark: str = "commission_b", config: object = CONFIG) -> report.RunInfo:
    return report.run_info(INFO.id, benchmark, INFO.git_sha, INFO.started_at, config, 0.5, 900)


def test_the_header_names_the_runs_settings() -> None:
    lines = render_markdown(_info(), summarize([outcome(case("a"))], always)).splitlines()
    assert "- Benchmark: `commission_b`" in lines
    assert (
        f"- Commit: `{INFO.git_sha}` (uncommitted changes: this commit may not reproduce the run)"
        in lines
    )
    assert "- Status: cost_cap_reached" in lines
    assert "- Classifier: `engine`: `openai/gpt-6-luna-20260922` on `azure/eu`" in lines
    assert "- Cases run: a seeded sample of 20 (seed 0)" in lines
    assert (
        "- Second model for refused requests (decision 033): "
        "`google/gemini-3.1-flash-lite` on `google-vertex/eu`"
    ) in lines
    assert (
        "- Exclude mode: `all` (the gap run: held-out examples retrievable, never the reported "
        "number; decision 012)"
    ) in lines
    assert (
        "- Answers: the stored key-fact answers to the questions run "
        '`00000000-0000-4000-8000-0000000000aa` asked, any other question answered "don\'t know" '
        "(decision 019)"
    ) in lines
    assert "| Risk-class accuracy | 100.0% | 1/1 |" in lines


def test_a_heldout_run_on_every_case_says_so() -> None:
    config = CONFIG | {"exclude_mode": "heldout", "subset": None, "git_dirty": False}
    lines = render_markdown(_info(config=config), summarize([], always)).splitlines()
    assert (
        "- Exclude mode: `heldout` (held-out examples kept out of retrieval: the reported number)"
        in lines
    )
    assert "- Cases run: every case of the set" in lines
    assert f"- Commit: `{INFO.git_sha}`" in lines


def test_own_cases_are_labelled_development_cases() -> None:
    lines = render_markdown(_info("own"), summarize([outcome(case("a"))], always)).splitlines()
    assert lines[2] == (
        "- Benchmark: `own` (development cases: the engine's nodes were developed against them, "
        "so Commission Pile B carries the headline (decision 018))"
    )
    assert "| Risk-class accuracy (development cases) | 100.0% | 1/1 |" in lines


def test_a_run_stored_before_its_settings_were_recorded_still_loads() -> None:
    info = _info(config={"model": None, "embedding": None, "retrieval": None})
    assert (info.classifier, info.status, info.is_git_dirty, info.second_model) == (
        None,
        None,
        None,
        None,
    )
    lines = render_markdown(info, summarize([], always)).splitlines()
    assert lines[2:5] == [
        "- Benchmark: `commission_b`",
        f"- Commit: `{INFO.git_sha}`",
        f"- Started: {INFO.started_at.isoformat()}",
    ]


def test_settings_of_another_shape_are_left_out() -> None:
    info = _info(config={"subset": True, "git_dirty": "yes", "outcome": "done", "seed": "0"})
    assert (info.subset, info.is_git_dirty, info.status, info.seed) == (None, None, None, None)


CONTAMINATED = ContaminatedList(
    decision="docs/decisions/016-contaminated-pile-b-cases.md",
    examples=(
        ContaminatedExample(
            example_id="hr-ex-269",
            passage="guide:guide-high-risk-annex-iii:para:102",
            coverage=0.3,
            longest_run=10,
            cosine=0.7,
        ),
    ),
)


def _stored(
    label: BenchmarkCase, predicted: ClassificationResult | None, **scores: object
) -> StoredCase:
    dumped = {"error": {"type": "X"}} if predicted is None else predicted.model_dump(mode="json")
    return stored_case(label.id, label.model_dump(mode="json"), dumped, scores)


def test_a_run_with_contaminated_cases_reports_accuracy_without_them() -> None:
    contaminated = case("cb-269-x").model_copy(update={"source_example_id": "hr-ex-269"})
    clean = case("cb-100-y").model_copy(update={"source_example_id": "hr-ex-100"})
    rows = (_stored(contaminated, result()), _stored(clean, result(RiskClass.MINIMAL_RISK)))
    text = build_report(_info(), rows, CONTAMINATED)
    assert "| Risk-class accuracy | 50.0% | 1/2 |" in text
    assert (
        "Contaminated cases, flagged by docs/decisions/016-contaminated-pile-b-cases.md: "
        "cb-269-x (from hr-ex-269)"
    ) in text
    assert "| Risk-class accuracy without the contaminated cases | 0.0% | 0/1 |" in text


def test_a_run_without_contaminated_cases_has_no_such_row() -> None:
    text = build_report(_info(), (_stored(case("a"), result()),), CONTAMINATED)
    assert "contaminated" not in text.lower()


def test_the_report_adds_refusals_failures_and_texts() -> None:
    gemini = "google/gemini-3.1-flash-lite"
    models = {"facts": {"openai/gpt-6-luna-20260922": 1, gemini: 1}}
    rows = (
        _stored(case("a"), result(RiskClass.OUT_OF_SCOPE), models=models),
        _stored(case("b"), refused_result()),
    )
    text = build_report(_info(), rows)
    assert "| Not assessed (provider refused a check, decision 030) | 1 | |" in text
    assert "| Risk-class accuracy, not-assessed cases counted as misses | 0.0% | 0/2 |" in text
    assert "- Answered by the second model: 1 of 2 (50.0%): a" in text
    assert "- Refused by both (not assessed): 1 of 2 (50.0%): b" in text
    assert "- **scope** (1): a (expected high_risk, got out_of_scope (decided))" in text
    assert "- Longest fact or question:" in text


def test_malformed_stored_models_name_the_case() -> None:
    with pytest.raises(report.RunRecordError, match="case a: stored models are malformed"):
        _stored(case("a"), result(), models={"facts": {"m": "many"}})


def test_a_run_without_stored_citation_scores_shows_na() -> None:
    text = build_report(INFO, (_row("a", {"risk_class_accuracy": True}),))
    assert "| Citation existence (at run time) | n/a | 0/0 |" in text


# --- judged metrics (V5) -------------------------------------------------------------------------

JUDGE = {
    "jev_model": "typesafe/jev-1.13",
    "backup_model": "anthropic/claude-haiku-5.5",
    "backup_provider": "google-vertex/europe",
    "margin": UNSURE_MARGIN,
}


def _judged_scores(check: JudgeCheck, score: CheckScore) -> dict[str, object]:
    return {"risk_class_accuracy": True, **stored_scores({check: score})}


def test_the_judged_scores_stored_with_the_cases_appear_in_the_report() -> None:
    citation = JudgeCheck.CITATION_SUPPORT
    rows = (
        _row("a", _judged_scores(citation, CheckScore(held=4, judged=5, cost_usd=0.0005))),
        _row(
            "b",
            _judged_scores(citation, CheckScore(held=1, judged=1, not_measured=1, cost_usd=0.0001)),
        ),
        _row("c", {"risk_class_accuracy": True}),
        _stored(case("d"), None),
    )
    info = report.run_info(INFO.id, "own", INFO.git_sha, INFO.started_at, {"judged": JUDGE})
    lines = build_report(info, rows).splitlines()
    assert "### Judged metrics" in lines
    assert "- Cases judged: 2 of 3" in lines
    assert "| Citation support | 83.3% | 5/6 | 1 | 0 | $0.0006 | $0.000086 |" in lines
    assert any(line.startswith("- Judge: Jev `typesafe/jev-1.13`, backup ") for line in lines)
    assert "- Judge cost: $0.0006, 0 tokens (not in the run's cost above)" in lines


def test_a_run_not_judged_says_how_to_judge_it() -> None:
    lines = build_report(INFO, (_row("a", {"risk_class_accuracy": True}),)).splitlines()
    assert lines[-3:] == [
        "Judged metrics: not judged yet (`aiact evaluate judged <run_id>`).",
        "",
        "- No invented content: checked by code (P8a's `check_nothing_invented` on each document "
        "the results call for), not judged: 100.0%, 3/3 documents",
    ]


def test_no_invented_content_is_checked_by_code_on_the_answered_cases_only() -> None:
    rows = (
        _row("a", {"risk_class_accuracy": True}),
        _row("b", {"risk_class_accuracy": True}),
        _stored(case("c"), None),
    )
    text = build_report(INFO, rows)
    assert "not judged: 100.0%, 6/6 documents" in text
    assert "No invented content (drafted documents)" not in text


def test_a_malformed_judged_score_names_the_case() -> None:
    with pytest.raises(report.RunRecordError, match="case a: stored judged scores of"):
        _row("a", {"judged_evidence_tag_held": -2})


def test_a_qa_runs_report_shows_q_and_a_support() -> None:
    info = report.run_info(INFO.id, "qa", INFO.git_sha, INFO.started_at, {"judged": JUDGE}, 0.2)
    qa = JudgeCheck.QA_SUPPORT
    # Two judged rows, one still to judge, one with nothing to judge (a fixed answer).
    rows = ({qa: CheckScore(held=1, judged=1)}, {qa: CheckScore(held=0, judged=1)}, {}, None)
    lines = report.build_qa_report(info, rows).splitlines()
    assert lines[0] == f"## Run {INFO.id}"
    assert "- Benchmark: `qa`" in lines
    assert "- Items: 4, 3 with an answer drawn from the sources" in lines
    assert "- Cases judged: 2 of 3" in lines
    assert "| Q&A support | 50.0% | 1/2 | 0 | 0 | $0.0000 | $0.000000 |" in lines


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
