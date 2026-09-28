"""The eval runner with an in-memory store and fake classifiers (no database, no models)."""

import json
import threading
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from pydantic import JsonValue
from typer.testing import CliRunner

from aiact.cli import app
from aiact.eval import runner
from aiact.eval.cases import AppliedAILabel, BenchmarkCase, CaseLabel, CaseSet
from aiact.eval.runner import (
    CaseRecord,
    Classification,
    ClassifierInfo,
    ClassifierInput,
    DummyClassifier,
    ExcludeMode,
    RunOptions,
    RunStatus,
    Split,
    SplitError,
    exclusions_for,
    load_split,
    run_benchmark,
    select_subset,
)
from aiact.schemas import ClassificationResult, Language, RiskClass

GIT_SHA = "0" * 40
SPLIT = Split(is_loo=False, pile_a=frozenset({"hr-ex-001"}), pile_b=("hr-ex-002", "hr-ex-003"))
LOO = Split(is_loo=True, pile_a=frozenset(), pile_b=())


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

    def start_run(self, git_sha: str, benchmark: str, config: Mapping[str, JsonValue]) -> UUID:
        run_id = uuid4()
        self.runs[run_id] = {"git_sha": git_sha, "benchmark": benchmark, "config": dict(config)}
        return run_id

    def add_case(self, run_id: UUID, record: CaseRecord) -> None:
        self.cases.append((run_id, record))

    def finish_run(self, run_id: UUID, outcome: Mapping[str, JsonValue]) -> None:
        self.outcomes[run_id] = dict(outcome)


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
    assert first.label == {
        "risk_class": "high_risk",
        "status": "decided",
        "role": None,
        "annex_point": None,
    }
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
    path.write_text(
        json.dumps({"mode": "split", "seed": 1, "pile_a": ["hr-ex-001"], "pile_b": ["hr-ex-3"]})
    )
    assert load_split(path) == Split(False, frozenset({"hr-ex-001"}), ("hr-ex-3",))
    path.write_text(json.dumps({"mode": "halves", "pile_a": [], "pile_b": []}))
    with pytest.raises(SplitError, match="mode"):
        load_split(path)
    path.write_text("{not json")
    with pytest.raises(SplitError, match="not a valid split"):
        load_split(path)


def test_appliedai_labels_are_stored_as_an_object() -> None:
    case = BenchmarkCase(
        id="aai-001",
        set_name=CaseSet.APPLIEDAI,
        language=Language.EN,
        description="Made-up",
        label=AppliedAILabel.HIGH,
    )
    assert runner.label_record(case) == {"appliedai": "high"}


@pytest.mark.parametrize(
    "changes", [{"concurrency": 0}, {"concurrency": 99}, {"max_cost_usd": 0}, {"subset": 0}]
)
def test_options_reject_bad_values(changes: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        options(**changes)


cli = CliRunner()


def test_cli_rejects_an_unknown_or_unbuilt_classifier() -> None:
    for name, message in (("nope", "unknown classifier"), ("engine", "E10")):
        result = cli.invoke(app, ["eval", "run", "--set", "own", "--classifier", name])
        assert result.exit_code == 2, name
        assert message in result.stderr


def test_cli_heldout_without_split_fails_clearly(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(runner, "SPLIT_FILE", tmp_path / "split.json")
    result = cli.invoke(app, ["eval", "run", "--set", "own", "--classifier", "dummy"])
    assert result.exit_code == 2
    assert "--exclude-mode all" in result.stderr
