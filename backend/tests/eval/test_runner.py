"""The eval runner with an in-memory store and fake classifiers (no database, no models)."""

import contextlib
import json
import threading
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from uuid import UUID, uuid4

import psycopg
import pytest
from pydantic import JsonValue
from typer.testing import CliRunner, Result

from aiact.cli import app
from aiact.eval import records, runner
from aiact.eval import split as split_module
from aiact.eval.cases import AppliedAILabel, BenchmarkCase, CaseLabel, CaseSet
from aiact.eval.runner import (
    CaseRecord,
    Classification,
    ClassifierFailedError,
    ClassifierInfo,
    ClassifierInput,
    DummyClassifier,
    ExcludeMode,
    RunOptions,
    RunStatus,
    exclusions_for,
    load_split,
    run_benchmark,
    select_subset,
)
from aiact.eval.split import Split, SplitError, SplitMode
from aiact.schemas import ClassificationResult, Language, RiskClass

GIT_SHA = "0" * 40


def make_split(mode: SplitMode, pile_a: tuple[str, ...], pile_b: tuple[str, ...]) -> Split:
    return Split(
        mode=mode,
        seed=1,
        pile_b_fraction=0.5,
        stratify_by=("area", "verdict"),
        pile_a=pile_a,
        pile_b=pile_b,
    )


SPLIT = make_split(SplitMode.SPLIT, ("hr-ex-001",), ("hr-ex-002", "hr-ex-003"))
LOO = make_split(SplitMode.LOO, (), ())


def make_case(number: int, source: str | None = None) -> BenchmarkCase:
    return BenchmarkCase(
        id=f"case-{number:03d}",
        set_name=CaseSet.COMMISSION_B,
        language=Language.DE if number % 2 else Language.EN,
        description=f"Made-up description {number}",
        label=CaseLabel(risk_class=RiskClass.HIGH_RISK),
        label_citation=("annex:III:4:a",),
        source_example_id=source,
    )


CASES = tuple(make_case(n, "hr-ex-002") for n in range(1, 7))


@dataclass
class MemoryStore:
    runs: dict[UUID, dict[str, object]] = field(default_factory=dict)
    cases: list[tuple[UUID, CaseRecord]] = field(default_factory=list)
    outcomes: dict[UUID, dict[str, JsonValue]] = field(default_factory=dict)
    is_finish_broken: bool = False

    def start_run(self, git_sha: str, benchmark: str, config: Mapping[str, JsonValue]) -> UUID:
        run_id = uuid4()
        self.runs[run_id] = {"git_sha": git_sha, "benchmark": benchmark, "config": dict(config)}
        return run_id

    def add_case(self, run_id: UUID, record: CaseRecord) -> None:
        self.cases.append((run_id, record))

    def finish_run(self, run_id: UUID, outcome: Mapping[str, JsonValue]) -> None:
        if self.is_finish_broken:
            raise RuntimeError("database went away")
        self.outcomes[run_id] = dict(outcome)

    def stored_cost(self) -> float:
        return sum(record.cost_usd for _, record in self.cases)


class PricedClassifier:
    """Answers like the dummy but reports a fixed cost; fails on the cases it's told to."""

    info = ClassifierInfo(model="fake/model", retrieval={"top_k": 3})

    def __init__(self, cost_usd: float = 0.0, failing: frozenset[str] = frozenset()) -> None:
        self.cost_usd = cost_usd
        self.failing = failing
        self.requests: list[ClassifierInput] = []
        self._lock = threading.Lock()

    def classify(self, request: ClassifierInput) -> Classification:
        with self._lock:
            self.requests.append(request)
        if request.description in self.failing:
            raise RuntimeError("model timed out")
        answer = DummyClassifier().classify(request)
        return Classification(answer.result, cost_usd=self.cost_usd, tokens=100, trace_id="t-1")


class SpendingFailureClassifier:
    """Fails every case after spending, like a model call whose answer didn't validate."""

    info = ClassifierInfo(model="fake/model")

    def classify(self, request: ClassifierInput) -> Classification:
        raise ClassifierFailedError(0.4, 50, RuntimeError("answer did not validate"))


def options(**changes: object) -> RunOptions:
    values: dict[str, object] = {
        "benchmark": CaseSet.COMMISSION_B,
        "classifier_name": "dummy",
        "exclude_mode": ExcludeMode.HELDOUT,
        "git_sha": GIT_SHA,
    } | changes
    return RunOptions(**values)  # pyright: ignore[reportArgumentType]


def test_dummy_run_records_every_case_and_a_completed_outcome() -> None:
    store = MemoryStore()
    summary = run_benchmark(CASES, DummyClassifier(), store, options(concurrency=3), SPLIT)

    assert summary.status is RunStatus.COMPLETED
    assert (summary.cases_planned, summary.cases_scored, summary.cases_failed) == (6, 6, 0)
    run = store.runs[summary.run_id]
    assert run["benchmark"] == "commission_b"
    config = run["config"]
    assert isinstance(config, dict)
    assert {"model", "embedding", "retrieval"} <= config.keys()
    assert config["exclude_mode"] == "heldout"
    assert config["split_mode"] == "split"
    outcome = store.outcomes[summary.run_id]
    assert (outcome["status"], outcome["cases_scored"]) == ("completed", 6)
    assert isinstance(outcome["finished_at"], str)
    assert sorted(record.case_id for _, record in store.cases) == [c.id for c in CASES]
    _, first = store.cases[0]
    assert ClassificationResult.model_validate(first.predicted).risk_class is RiskClass.OUT_OF_SCOPE
    assert BenchmarkCase.model_validate(first.label) == next(
        c for c in CASES if c.id == first.case_id
    )
    assert first.scores == {"cost_usd": 0.0, "tokens": 0, "is_error": False}


def test_the_classifier_never_sees_the_label_or_case_id() -> None:
    classifier = PricedClassifier()
    run_benchmark(CASES[:1], classifier, MemoryStore(), options(), SPLIT)
    assert classifier.requests == [
        ClassifierInput("Made-up description 1", Language.DE, ("hr-ex-002", "hr-ex-003"))
    ]


def test_cost_cap_stops_starting_new_cases() -> None:
    store = MemoryStore()
    summary = run_benchmark(
        CASES,
        PricedClassifier(cost_usd=0.4),
        store,
        options(concurrency=1, max_cost_usd=1.0),
        SPLIT,
    )
    assert summary.status is RunStatus.COST_CAP_REACHED
    assert summary.cases_scored == 3
    assert summary.cost_usd == pytest.approx(1.2)
    assert summary.tokens == 300
    outcome = store.outcomes[summary.run_id]
    assert (outcome["status"], outcome["cases_planned"], outcome["cases_scored"]) == (
        "cost_cap_reached",
        6,
        3,
    )


def test_a_failing_case_is_recorded_as_an_error_and_the_run_goes_on() -> None:
    store = MemoryStore()
    classifier = PricedClassifier(failing=frozenset({"Made-up description 2"}))
    summary = run_benchmark(CASES, classifier, store, options(), SPLIT)

    assert summary.status is RunStatus.COMPLETED
    assert (summary.cases_scored, summary.cases_failed) == (6, 1)
    failed = next(record for _, record in store.cases if record.case_id == "case-002")
    assert failed.predicted == {"error": {"type": "RuntimeError", "message": "model timed out"}}
    assert failed.scores["is_error"] is True


def test_metric_scores_are_merged_and_reserved_names_rejected() -> None:
    store = MemoryStore()

    def scorer(case: BenchmarkCase, result: ClassificationResult) -> dict[str, float | bool | None]:
        return {"risk_class_accuracy": result.risk_class is RiskClass.HIGH_RISK}

    run_benchmark(CASES[:1], DummyClassifier(), store, options(), SPLIT, scorer=scorer)
    assert store.cases[0][1].scores["risk_class_accuracy"] is False

    clashing = MemoryStore()
    with pytest.raises(ValueError, match="reserved"):
        run_benchmark(
            CASES[:1], DummyClassifier(), clashing, options(), SPLIT, lambda c, r: {"tokens": 1}
        )
    (outcome,) = clashing.outcomes.values()
    assert outcome["status"] == "interrupted"


def test_subset_is_seeded_and_in_id_order() -> None:
    first = select_subset(CASES, 3, seed=7)
    assert first == select_subset(tuple(reversed(CASES)), 3, seed=7)
    assert [case.id for case in first] == sorted(case.id for case in first)
    assert select_subset(CASES, None, seed=7) == CASES
    assert select_subset(CASES, 99, seed=7) == CASES


def test_exclusions_per_mode() -> None:
    case = make_case(1, "hr-ex-002")
    assert exclusions_for(case, SPLIT) == ("hr-ex-002", "hr-ex-003")
    assert exclusions_for(case, LOO) == ("hr-ex-002",)
    assert exclusions_for(make_case(2), LOO) == ()
    assert exclusions_for(case, None) == ()
    with pytest.raises(SplitError, match="Pile A"):
        exclusions_for(make_case(3, "hr-ex-001"), SPLIT)


def test_exclude_mode_all_passes_no_exclusions_and_needs_no_split() -> None:
    classifier = PricedClassifier()
    store = MemoryStore()
    summary = run_benchmark(
        CASES[:2], classifier, store, options(exclude_mode=ExcludeMode.ALL), None
    )
    assert all(request.exclude_source_example_ids == () for request in classifier.requests)
    config = store.runs[summary.run_id]["config"]
    assert isinstance(config, dict)
    assert config["split_mode"] is None


def test_heldout_without_a_split_fails_before_recording() -> None:
    store = MemoryStore()
    with pytest.raises(SplitError):
        run_benchmark(CASES, DummyClassifier(), store, options(), None)
    assert store.runs == {}


def test_load_split_reads_b3_format_and_fails_clearly(tmp_path: Path) -> None:
    path = tmp_path / "split.json"
    with pytest.raises(SplitError, match="needs the committed split"):
        load_split(path)
    path.write_text(split_module.render(SPLIT))
    assert load_split(path) == SPLIT
    path.write_text(json.dumps({**SPLIT.model_dump(mode="json"), "mode": "halves"}))
    with pytest.raises(SplitError, match="not a valid split"):
        load_split(path)
    path.write_text("{not json")
    with pytest.raises(SplitError, match="not a valid split"):
        load_split(path)


def test_the_committed_split_loads() -> None:
    split = load_split()
    assert split.mode is SplitMode.SPLIT
    assert split.pile_b


def test_appliedai_cases_are_stored_whole() -> None:
    case = BenchmarkCase(
        id="aai-001",
        set_name=CaseSet.APPLIEDAI,
        language=Language.EN,
        description="Made-up",
        label=AppliedAILabel.HIGH,
    )
    record = runner.label_record(case)
    assert (record["label"], record["set_name"]) == ("high", "appliedai")
    assert BenchmarkCase.model_validate(record) == case


@pytest.mark.parametrize(
    "changes", [{"concurrency": 0}, {"concurrency": 99}, {"max_cost_usd": 0}, {"subset": 0}]
)
def test_options_reject_bad_values(changes: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        options(**changes)


cli = CliRunner()


def test_cli_rejects_an_unknown_or_unbuilt_classifier() -> None:
    for name, message in (("nope", "unknown classifier"), ("engine", "E10")):
        result = cli.invoke(app, ["evaluate", "run", "--set", "own", "--classifier", name])
        assert result.exit_code == 2, name
        assert message in result.stderr


def test_cli_heldout_without_split_fails_clearly(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(split_module, "SPLIT_FILE", tmp_path / "split.json")
    result = cli.invoke(app, ["evaluate", "run", "--set", "own", "--classifier", "dummy"])
    assert result.exit_code == 2
    assert "--exclude-mode all" in result.stderr


def test_a_failure_that_spent_counts_toward_the_cap_and_the_totals() -> None:
    store = MemoryStore()
    summary = run_benchmark(
        CASES, SpendingFailureClassifier(), store, options(concurrency=1, max_cost_usd=1.0), SPLIT
    )
    assert summary.status is RunStatus.COST_CAP_REACHED
    assert (summary.cases_scored, summary.cases_failed, summary.tokens) == (3, 3, 150)
    assert summary.cost_usd == pytest.approx(1.2)
    assert store.stored_cost() == pytest.approx(1.2)
    _, first = store.cases[0]
    assert first.predicted == {
        "error": {"type": "RuntimeError", "message": "answer did not validate"}
    }
    assert first.scores == {"cost_usd": 0.4, "tokens": 50, "is_error": True}


def test_a_scorer_error_records_the_cases_in_flight_before_raising() -> None:
    store = MemoryStore()

    def scorer(case: BenchmarkCase, result: ClassificationResult) -> dict[str, float | bool | None]:
        if case.id == "case-001":
            raise ValueError("scorer bug")
        return {"risk_class_accuracy": False}

    with pytest.raises(ValueError, match="scorer bug"):
        run_benchmark(
            CASES, PricedClassifier(cost_usd=0.1), store, options(concurrency=6), SPLIT, scorer
        )
    assert sorted(record.case_id for _, record in store.cases) == [c.id for c in CASES]
    assert store.stored_cost() == pytest.approx(0.6)
    failed = next(record for _, record in store.cases if record.case_id == "case-001")
    assert failed.scores == {"cost_usd": 0.1, "tokens": 100, "is_error": False}
    (outcome,) = store.outcomes.values()
    assert (outcome["status"], outcome["cases_scored"]) == ("interrupted", 6)


@dataclass
class InterruptingStore(MemoryStore):
    """Raises KeyboardInterrupt right after writing the first case, as a Ctrl-C mid-write would."""

    is_interrupted: bool = False

    def add_case(self, run_id: UUID, record: CaseRecord) -> None:
        super().add_case(run_id, record)
        if not self.is_interrupted:
            self.is_interrupted = True
            raise KeyboardInterrupt


def test_an_interrupt_during_a_write_records_every_case_in_flight_once() -> None:
    store = InterruptingStore()
    with pytest.raises(KeyboardInterrupt):
        run_benchmark(CASES, PricedClassifier(cost_usd=0.1), store, options(concurrency=6), SPLIT)
    assert sorted(record.case_id for _, record in store.cases) == [c.id for c in CASES]


def test_a_scorer_error_stops_new_cases_from_starting() -> None:
    store = MemoryStore()

    def scorer(case: BenchmarkCase, result: ClassificationResult) -> dict[str, float | bool | None]:
        raise ValueError("scorer bug")

    with pytest.raises(ValueError):
        run_benchmark(CASES, DummyClassifier(), store, options(concurrency=1), SPLIT, scorer)
    assert [record.case_id for _, record in store.cases] == ["case-001"]


def test_a_failing_finish_does_not_replace_the_original_error() -> None:
    store = MemoryStore(is_finish_broken=True)

    def scorer(case: BenchmarkCase, result: ClassificationResult) -> dict[str, float | bool | None]:
        raise ValueError("scorer bug")

    with pytest.raises(ValueError, match="scorer bug"):
        run_benchmark(CASES, DummyClassifier(), store, options(concurrency=1), SPLIT, scorer)


SECRET_URL = "postgresql://postgres:hunter2@db.example:5432/postgres"


def _cli_with_database(monkeypatch: pytest.MonkeyPatch, connect: Callable[[], object]) -> Result:
    monkeypatch.setattr(runner, "load_benchmark", lambda case_set: CASES)
    monkeypatch.setattr(records, "connect", connect)
    return cli.invoke(
        app,
        [
            *("evaluate", "run", "--set", "commission_b"),
            *("--classifier", "dummy", "--exclude-mode", "all"),
        ],
    )


def test_cli_reports_a_connection_error_without_the_url(monkeypatch: pytest.MonkeyPatch) -> None:
    def connect() -> object:
        raise psycopg.OperationalError(f"could not connect to {SECRET_URL}")

    result = _cli_with_database(monkeypatch, connect)
    assert result.exit_code == 2
    assert "Error: database error (OperationalError)" in result.stderr
    assert "hunter2" not in result.output


def test_cli_reports_a_database_error_during_the_run(monkeypatch: pytest.MonkeyPatch) -> None:
    def failing_run(*args: object, **kwargs: object) -> None:
        raise psycopg.errors.CheckViolation(f"check failed at {SECRET_URL}")

    monkeypatch.setattr(runner, "run_benchmark", failing_run)
    result = _cli_with_database(monkeypatch, contextlib.nullcontext)
    assert result.exit_code == 2
    assert "Error: database error (CheckViolation)" in result.stderr
    assert "hunter2" not in result.output
