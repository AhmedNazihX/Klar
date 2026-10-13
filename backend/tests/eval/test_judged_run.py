"""Judging a stored run (V5): what is planned, the cost cap, resuming and the judge's settings.
The judges and the store are fakes; the database round trip is in tests/db/test_eval_judged.py."""

from collections.abc import Mapping
from datetime import UTC, date, datetime
from uuid import UUID, uuid4

import pytest
from typer.testing import CliRunner

from aiact.cli import app
from aiact.engine import extended_description
from aiact.eval import judge, judged_command, judged_run, records
from aiact.eval.cases import QAItem
from aiact.eval.judge import (
    BACKUP_CALL_ESTIMATE_USD,
    JEV_CALL_ESTIMATE_USD,
    UNSURE_MARGIN,
    Judge,
    JudgeCheck,
    JudgeError,
    JudgeItem,
    Verdict,
)
from aiact.eval.judged import CheckScore, JudgedSettings
from aiact.eval.judged_run import (
    JudgedOptions,
    JudgedRowError,
    JudgedSettingsError,
    JudgedStatus,
    JudgedSummary,
    PlannedCase,
    StoredRow,
    StoredRun,
    check_settings,
    estimate_usd,
    item_counts,
    judge_run,
    plan_run,
)
from aiact.retrieval.provisions import Provision, ProvisionNotFoundError
from aiact.schemas import DISCLAIMER, DocumentStatus, Language, LawVersion
from aiact.settings import Settings
from tests.eval.outcomes import case
from tests.schemas.worked_example import worked_example_result

SETTINGS = JudgedSettings(
    jev_model="typesafe/jev-1.13",
    backup_model="anthropic/claude-haiku-5.5",
    backup_provider="google-vertex/europe",
    margin=UNSURE_MARGIN,
)
STARTED = datetime(2026, 10, 1, 9, 0, tzinfo=UTC)
PRICED = "anthropic/claude-haiku-5.5"
QA_ITEM = QAItem(
    id="qa-en-01",
    language=Language.EN,
    question="When do the rules apply?",
    required_provision_ids=("art:113",),
    reference_answer="From 2 August 2026.",
)
HITS = [
    {"doc_key": "ai-act-consolidated", "provision_id": "art:113"},
    {"doc_key": "guide-prohibited", "provision_id": "guide:guide-prohibited:3"},
]


def _classified(case_id: str, scores: Mapping[str, object] | None = None) -> StoredRow:
    label = case(case_id).model_dump(mode="json")
    predicted = worked_example_result().model_dump(mode="json")
    return StoredRow(case_id, label, predicted, scores or {"cost_usd": 0.01, "is_error": False})


def _failed(case_id: str) -> StoredRow:
    error = {"error": {"type": "TimeoutError", "message": "x"}}
    return StoredRow(case_id, case(case_id).model_dump(mode="json"), error, {"is_error": True})


def _run(
    *rows: StoredRow,
    benchmark: str = "own",
    settings: JudgedSettings | None = None,
    asked: Mapping[str, tuple[str, ...]] | None = None,
) -> StoredRun:
    return StoredRun(uuid4(), benchmark, STARTED, settings, rows, asked)


def _qa_row(**predicted: object) -> StoredRow:
    stored = {"answer": "From 2 August 2026.", "answer_kind": "answered", "retrieved": HITS}
    return StoredRow(QA_ITEM.id, QA_ITEM.model_dump(mode="json"), stored | predicted, {})


def _no_source(hit: Mapping[str, object], language: Language) -> str | None:
    raise AssertionError("a classification run reads no source")


def _source(hit: Mapping[str, object], language: Language) -> str | None:
    return f"[{hit['provision_id']}] text"


class Holding:
    """Every item holds, at a fixed cost."""

    def __init__(self, cost: float = 0.001) -> None:
        self.cost = cost
        self.items: list[JudgeItem] = []

    def judge(self, item: JudgeItem) -> Verdict:
        self.items.append(item)
        return Verdict(
            holds=True, decided_by="jev", p_yes=0.95, reason=None, cost_usd=self.cost, tokens=10
        )


class MemoryStore:
    def __init__(self) -> None:
        self.settings: list[JudgedSettings] = []
        self.cases: dict[str, Mapping[str, float | int]] = {}

    def save_settings(self, run_id: UUID, settings: JudgedSettings) -> None:
        self.settings.append(settings)

    def save_case(self, run_id: UUID, case_id: str, scores: Mapping[str, float | int]) -> None:
        self.cases[case_id] = scores


# --- planning ------------------------------------------------------------------------------------


def test_a_classification_run_plans_two_checks_per_answered_case() -> None:
    planned = plan_run(_run(_classified("a"), _failed("b")), _no_source)
    assert [case.case_id for case in planned] == ["a"]
    assert list(planned[0].plan) == [JudgeCheck.CITATION_SUPPORT, JudgeCheck.EVIDENCE_TAG]
    evidence = planned[0].plan[JudgeCheck.EVIDENCE_TAG]
    assert all(item and item.source == "A made-up system." for item in evidence)


HUMAN_REVIEW = "An HR officer checks every ranking."


def _answered_row(case_id: str) -> StoredRow:
    """A case whose stored answer to `human_review` states a fact the description doesn't."""
    answered = case(case_id).model_copy(update={"key_fact_answers": {"human_review": HUMAN_REVIEW}})
    predicted = worked_example_result().model_dump(mode="json")
    return StoredRow(case_id, answered.model_dump(mode="json"), predicted, {})


def test_an_answers_run_judges_evidence_against_the_text_the_engine_read() -> None:
    planned = plan_run(
        _run(_answered_row("a"), asked={"a": ("human_review", "profiling")}), _no_source
    )
    expected = (
        "A made-up system.\n\nAnswers to follow-up questions:\n"
        f"- human_review: {HUMAN_REVIEW}\n- profiling: don't know"
    )
    answers = {"human_review": HUMAN_REVIEW, "profiling": "don't know"}
    assert extended_description("A made-up system.", answers, Language.EN) == expected
    evidence = planned[0].plan[JudgeCheck.EVIDENCE_TAG]
    assert evidence
    assert all(item and item.source == expected for item in evidence)


def test_an_answers_run_whose_case_asked_nothing_reads_the_description_alone() -> None:
    planned = plan_run(_run(_answered_row("a"), asked={"a": ()}), _no_source)
    evidence = planned[0].plan[JudgeCheck.EVIDENCE_TAG]
    assert all(item and item.source == "A made-up system." for item in evidence)


def test_an_answers_run_missing_a_case_in_its_source_names_the_case() -> None:
    with pytest.raises(JudgedRowError, match="case a: the answers' source run has no row"):
        plan_run(_run(_answered_row("a"), asked={"b": ()}), _no_source)


def test_cases_already_judged_are_not_planned_again() -> None:
    judged_scores = {"cost_usd": 0.01, "judged_citation_support_held": 1}
    planned = plan_run(_run(_classified("a", judged_scores), _classified("b")), _no_source)
    assert [case.case_id for case in planned] == ["b"]


def test_a_malformed_row_names_the_case_but_not_its_text() -> None:
    row = StoredRow("a", {"id": "a", "description": "SECRET TEXT"}, {"steps": []}, {})
    with pytest.raises(JudgedRowError, match="case a: stored row is invalid at") as error:
        plan_run(_run(row), _no_source)
    assert "SECRET" not in str(error.value)


def test_a_qa_run_plans_q_and_a_support_from_the_sources() -> None:
    planned = plan_run(_run(_qa_row(), benchmark="qa"), _source)
    (item,) = planned[0].plan[JudgeCheck.QA_SUPPORT]
    assert item is not None
    assert item.claim == "Question: When do the rules apply?\nAnswer: From 2 August 2026."
    assert item.source == "[art:113] text\n\n[guide:guide-prohibited:3] text"


def test_the_qa_benchmark_name_is_the_ragas_runs() -> None:
    assert judged_run.QA_BENCHMARK == "qa"


@pytest.mark.parametrize("kind", ["outside_corpus", "compliance", "refused"])
def test_a_fixed_answer_is_not_judged(kind: str) -> None:
    assert plan_run(_run(_qa_row(answer_kind=kind), benchmark="qa"), _source) == ()


def test_the_stand_in_answerers_answer_without_a_kind_is_judged() -> None:
    planned = plan_run(_run(_qa_row(answer_kind=None), benchmark="qa"), _source)
    assert len(planned) == 1


def test_a_qa_row_without_an_answer_is_not_planned() -> None:
    no_hits = _qa_row(answer=None, answer_kind=None, retrieved=[])
    failed = _qa_row(error={"type": "X", "message": "y"})
    assert plan_run(_run(no_hits, failed, benchmark="qa"), _source) == ()


def test_a_source_the_corpus_lost_leaves_the_answer_not_measured() -> None:
    def partly(hit: Mapping[str, object], language: Language) -> str | None:
        return None if hit["provision_id"] == "art:113" else "text"

    planned = plan_run(_run(_qa_row(), benchmark="qa"), partly)
    assert planned[0].plan[JudgeCheck.QA_SUPPORT] == (None,)


def test_item_counts_count_only_sendable_items() -> None:
    planned = (
        PlannedCase("a", {JudgeCheck.EVIDENCE_TAG: (None,)}),
        PlannedCase("b", plan_run(_run(_qa_row(), benchmark="qa"), _source)[0].plan),
    )
    assert item_counts(planned) == {JudgeCheck.EVIDENCE_TAG: 0, JudgeCheck.QA_SUPPORT: 1}


def _planned(*items: JudgeItem | None) -> tuple[PlannedCase, ...]:
    return (PlannedCase("a", {JudgeCheck.EVIDENCE_TAG: items}),)


def _evidence(claim: str, source: str) -> JudgeItem:
    return JudgeItem(
        check=JudgeCheck.EVIDENCE_TAG, language=Language.EN, claim=claim, source=source
    )


def test_the_estimate_is_sized_from_each_items_texts() -> None:
    item = _evidence("c", "s")
    chars = sum(len(message.text) for message in judge.backup_messages(item))
    # Jev $0.042 and Haiku 5.5 $0.11 per million input tokens, 600 output tokens at $0.55.
    expected = (-(-chars // 3) * (0.042 + 0.11) + 600 * 0.55) / 1_000_000
    estimate = estimate_usd(_planned(item, None), "anthropic/claude-haiku-5.5")
    assert estimate == pytest.approx(expected)
    assert estimate_usd(_planned(item), "example/unpriced-model") is None


def test_a_long_item_is_estimated_above_the_validation_cases_bound() -> None:
    bound = JEV_CALL_ESTIMATE_USD + BACKUP_CALL_ESTIMATE_USD  # 3,000 prompt tokens an item
    estimate = estimate_usd(_planned(_evidence("c" * 4_000, "s" * 16_000)), PRICED)
    assert estimate is not None
    assert estimate > bound


# --- judging -------------------------------------------------------------------------------------


def test_each_judged_case_is_stored_with_the_settings() -> None:
    run = _run(_classified("a"), _classified("b"))
    store, judge = MemoryStore(), Holding()
    planned = plan_run(run, _no_source)
    summary = judge_run(run, planned, judge, SETTINGS, store, JudgedOptions())
    assert summary.status is JudgedStatus.COMPLETED
    assert (summary.cases_planned, summary.cases_judged) == (2, 2)
    assert store.settings == [SETTINGS]
    assert set(store.cases) == {"a", "b"}
    # The worked example: 5 citing steps, 3 stated facts.
    assert store.cases["a"]["judged_citation_support_judged"] == 5
    assert store.cases["a"]["judged_evidence_tag_judged"] == 3
    assert not any(key.startswith("judged_invented_content") for key in store.cases["a"])
    assert summary.cost_usd == pytest.approx(2 * 8 * 0.001)
    assert len(judge.items) == 16


def test_no_case_starts_once_the_cap_is_spent() -> None:
    run = _run(_classified("a"), _classified("b"), _classified("c"))
    store = MemoryStore()
    options = JudgedOptions(max_cost_usd=0.012)
    summary = judge_run(run, plan_run(run, _no_source), Holding(), SETTINGS, store, options)
    assert summary.status is JudgedStatus.COST_CAP_REACHED
    assert summary.cases_judged == 2  # 0.008 spent after the first case, 0.016 after the second
    assert set(store.cases) == {"a", "b"}


def test_no_case_starts_once_exactly_the_cap_is_spent() -> None:
    run = _run(_classified("a"), _classified("b"))
    store = MemoryStore()
    holding = Holding(cost=0.125)  # 8 items: exactly $1.00 after the first case
    options = JudgedOptions(max_cost_usd=1.0)
    summary = judge_run(run, plan_run(run, _no_source), holding, SETTINGS, store, options)
    assert summary.status is JudgedStatus.COST_CAP_REACHED
    assert summary.cost_usd == 1.0
    assert set(store.cases) == {"a"}


class UnreachedAt(Holding):
    """Holds every item until call number `at` reaches no model (a ConnectTimeout)."""

    def __init__(self, at: int) -> None:
        super().__init__()
        self.at = at
        self.calls = 0

    def judge(self, item: JudgeItem) -> Verdict:
        self.calls += 1
        if self.calls == self.at:
            raise JudgeError("ConnectTimeout", 0.0006, 0, is_call_failed=True)
        return super().judge(item)


def test_a_call_that_reaches_no_model_stops_the_pass_and_a_rerun_judges_the_case() -> None:
    rows = (_classified("a"), _classified("b"), _classified("c"))
    run, store = _run(*rows), MemoryStore()
    unreached = UnreachedAt(10)  # the second case's second item
    options = JudgedOptions(concurrency=1)
    summary = judge_run(run, plan_run(run, _no_source), unreached, SETTINGS, store, options)
    assert summary.status is JudgedStatus.UNREACHED
    assert summary.cases_judged == 1
    assert set(store.cases) == {"a"}
    assert unreached.calls == 10  # nothing sent after the unreached call
    assert summary.cost_usd == pytest.approx(9 * 0.001 + 0.0006)

    stored = [
        StoredRow(row.case_id, row.label, row.predicted, store.cases.get(row.case_id, row.scores))
        for row in rows
    ]
    rerun = _run(*stored, settings=SETTINGS)
    planned = plan_run(rerun, _no_source)
    assert [case.case_id for case in planned] == ["b", "c"]
    again = judge_run(rerun, planned, Holding(), SETTINGS, store, options)
    assert again.status is JudgedStatus.COMPLETED
    assert store.cases["b"]["judged_citation_support_judged"] == 5


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("jev_model", "typesafe/jev-2.0"),
        ("backup_model", "anthropic/claude-haiku-4.5"),
        ("backup_provider", "anthropic"),
        ("margin", 0.05),
    ],
)
def test_another_judge_than_the_stored_one_is_refused(field: str, value: object) -> None:
    other = SETTINGS.model_copy(update={field: value})
    with pytest.raises(JudgedSettingsError, match="one run's tallies come from one judge"):
        check_settings(_run(_classified("a"), settings=other), SETTINGS)
    check_settings(_run(_classified("a"), settings=SETTINGS), SETTINGS)
    check_settings(_run(_classified("a")), SETTINGS)


def test_the_same_judge_goes_on_where_it_stopped() -> None:
    run = _run(
        _classified("a", {"judged_evidence_tag_held": 3}), _classified("b"), settings=SETTINGS
    )
    store = MemoryStore()
    judge_run(run, plan_run(run, _no_source), Holding(), SETTINGS, store, JudgedOptions())
    assert set(store.cases) == {"b"}


def test_defaults_are_pinned() -> None:
    assert judged_run.DEFAULT_MAX_COST_USD == 0.10
    assert judged_run.CHARS_PER_TOKEN == 3
    assert judged_run.DEFAULT_CONCURRENCY == 4
    assert judged_run.MAX_CONCURRENCY == 16


# --- the corpus source ---------------------------------------------------------------------------


def _provision(provision_id: str) -> Provision:
    return Provision(
        provision_id=provision_id,
        doc_key="ai-act-consolidated",
        document_title="AI Act (consolidated)",
        doc_type="law",
        law_version=LawVersion.AMENDED,
        status=DocumentStatus.FINAL,
        language=Language.EN,
        english_only=False,
        heading="Entry into force",
        text="It shall apply from 2 August 2026.",
        valid_from=date(2024, 8, 1),
        valid_to=None,
        disclaimer=DISCLAIMER[Language.EN],
    )


def test_the_corpus_source_reads_the_hit_as_the_run_saw_it(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[object, ...]] = []

    def lookup(
        provision_id: str,
        language: Language,
        version: LawVersion,
        as_of: date | None,
        *,
        connection: object,
    ) -> Provision:
        calls.append((provision_id, language, version, as_of))
        return _provision(provision_id)

    monkeypatch.setattr(judged_run, "get_provision", lookup)
    read = judged_run.corpus_source(object(), date(2026, 10, 1))  # pyright: ignore[reportArgumentType]
    text = read({"doc_key": "ai-act-consolidated", "provision_id": "art:113"}, Language.DE)
    assert (
        text
        == "[art:113] AI Act (consolidated)\nEntry into force\nIt shall apply from 2 August 2026."
    )
    read({"doc_key": "ai-act", "provision_id": "art:113"}, Language.EN)
    read({"doc_key": "guide-prohibited", "provision_id": "guide:guide-prohibited:3"}, Language.EN)
    assert calls == [
        ("art:113", Language.DE, LawVersion.AMENDED, date(2026, 10, 1)),
        ("art:113", Language.EN, LawVersion.ORIGINAL, None),
        ("guide:guide-prohibited:3", Language.EN, LawVersion.AMENDED, date(2026, 10, 1)),
    ]


def test_a_hit_the_corpus_lost_reads_as_none(monkeypatch: pytest.MonkeyPatch) -> None:
    def missing(*args: object, **kwargs: object) -> Provision:
        raise ProvisionNotFoundError("gone")

    monkeypatch.setattr(judged_run, "get_provision", missing)
    read = judged_run.corpus_source(object(), date(2026, 10, 1))  # pyright: ignore[reportArgumentType]
    assert read({"doc_key": "ai-act", "provision_id": "art:113"}, Language.EN) is None
    assert read({"provision_id": "art:113"}, Language.EN) is None


# --- the command ---------------------------------------------------------------------------------

cli = CliRunner()


class FakeConnection:
    def __enter__(self) -> "FakeConnection":
        return self

    def __exit__(self, *exc: object) -> None:
        return None


def _settings() -> Settings:
    return Settings(
        _env_file=None,  # pyright: ignore[reportCallIssue]
        judge_model="typesafe/jev-1.13",
        judge_backup_model="anthropic/claude-haiku-5.5",
        judge_backup_provider="google-vertex/europe",
    )


def test_the_commands_judge_uses_the_judges_own_margin() -> None:
    chosen = judged_command.judged_settings(_settings())
    assert chosen.margin == UNSURE_MARGIN
    assert (chosen.jev_model, chosen.backup_model, chosen.backup_provider) == (
        "typesafe/jev-1.13",
        "anthropic/claude-haiku-5.5",
        "google-vertex/europe",
    )


def test_a_dry_run_prints_the_plan_and_makes_no_call(monkeypatch: pytest.MonkeyPatch) -> None:
    run = _run(_classified("a"))
    monkeypatch.setattr(records, "connect", FakeConnection)
    monkeypatch.setattr(judged_command, "get_settings", _settings)
    monkeypatch.setattr(judged_run, "load_run", lambda conn, run_id: run)
    monkeypatch.setattr(judged_run, "corpus_source", lambda conn, as_of: _no_source)

    def no_judging(*args: object) -> object:
        raise AssertionError("a dry run judges nothing")

    monkeypatch.setattr(judged_run, "judge_run", no_judging)
    outcome = cli.invoke(app, ["evaluate", "judged", str(run.id), "--dry-run"])
    assert outcome.exit_code == 0, outcome.output
    assert outcome.stdout.startswith(
        "1 cases to judge, 8 items (Citation support: 5, Evidence-tag accuracy: 3) with "
    )
    assert "margin " + str(UNSURE_MARGIN) in outcome.stdout
    assert "estimated at most $" in outcome.stdout
    assert "(cap $0.10)" in outcome.stdout


def test_a_run_judged_by_another_judge_exits_2(monkeypatch: pytest.MonkeyPatch) -> None:
    other = SETTINGS.model_copy(update={"margin": UNSURE_MARGIN / 2})
    run = _run(_classified("a"), settings=other)
    monkeypatch.setattr(records, "connect", FakeConnection)
    monkeypatch.setattr(judged_command, "get_settings", _settings)
    monkeypatch.setattr(judged_run, "load_run", lambda conn, run_id: run)
    outcome = cli.invoke(app, ["evaluate", "judged", str(run.id)])
    assert outcome.exit_code == 2
    assert "one run's tallies come from one judge" in outcome.stderr


def test_an_unknown_run_exits_2(monkeypatch: pytest.MonkeyPatch) -> None:
    def missing(conn: object, run_id: UUID) -> StoredRun:
        raise judged_run.JudgedRunNotFoundError(f"no eval run with id {run_id}")

    monkeypatch.setattr(records, "connect", FakeConnection)
    monkeypatch.setattr(judged_command, "get_settings", _settings)
    monkeypatch.setattr(judged_run, "load_run", missing)
    outcome = cli.invoke(app, ["evaluate", "judged", str(uuid4())])
    assert outcome.exit_code == 2
    assert outcome.stderr.startswith("Error: no eval run with id")


class FakeRouteJudge:
    """Stands in for `JevJudge` and `BackupJudge`: built from the settings, never called."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings


def test_the_command_passes_its_options_and_the_runs_date_to_the_pass(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run = _run(_qa_row(), benchmark="qa")
    seen: dict[str, object] = {}

    def source_as_of(conn: object, as_of: date) -> judged_run.SourceReader:
        seen["as_of"] = as_of
        return _source

    def judging(
        judged: StoredRun,
        planned: tuple[PlannedCase, ...],
        built: object,
        chosen: JudgedSettings,
        store: object,
        options: JudgedOptions,
    ) -> JudgedSummary:
        seen.update(run=judged, planned=planned, judge=built, chosen=chosen, options=options)
        totals = {JudgeCheck.QA_SUPPORT: CheckScore(held=1, judged=1, cost_usd=0.001)}
        return JudgedSummary(JudgedStatus.COMPLETED, 1, 1, totals)

    monkeypatch.setattr(records, "connect", FakeConnection)
    monkeypatch.setattr(judged_command, "get_settings", _settings)
    monkeypatch.setattr(judge, "JevJudge", FakeRouteJudge)
    monkeypatch.setattr(judge, "BackupJudge", FakeRouteJudge)
    monkeypatch.setattr(judged_run, "load_run", lambda conn, run_id: run)
    monkeypatch.setattr(judged_run, "corpus_source", source_as_of)
    monkeypatch.setattr(judged_run, "judge_run", judging)
    arguments = ["--max-cost-usd", "0.05", "--concurrency", "2"]
    outcome = cli.invoke(app, ["evaluate", "judged", str(run.id), *arguments])
    assert outcome.exit_code == 0, outcome.output
    assert seen["as_of"] == date(2026, 10, 1)
    assert seen["run"] is run
    assert seen["planned"] == plan_run(run, _source)
    built = seen["judge"]
    assert isinstance(built, Judge)
    assert built.margin == UNSURE_MARGIN
    assert seen["chosen"] == SETTINGS
    assert seen["options"] == JudgedOptions(max_cost_usd=0.05, concurrency=2)
    assert "1 of 1 cases judged, 0 items not measured; $0.0010" in outcome.stdout


@pytest.mark.parametrize(
    "arguments", [["--concurrency", "0"], ["--concurrency", "17"], ["--max-cost-usd", "0"]]
)
def test_the_commands_options_are_bounded(
    monkeypatch: pytest.MonkeyPatch, arguments: list[str]
) -> None:
    monkeypatch.setattr(judged_run, "load_run", _never)
    outcome = cli.invoke(app, ["evaluate", "judged", str(uuid4()), *arguments])
    assert outcome.exit_code == 2


def _never(*args: object) -> StoredRun:
    raise AssertionError("a bad option loads nothing")


@pytest.mark.parametrize("cap", ["nan", "inf"])
def test_a_cost_cap_that_is_not_finite_is_refused(
    monkeypatch: pytest.MonkeyPatch, cap: str
) -> None:
    """`nan` and `inf` pass a float range check and would switch the cap off."""
    monkeypatch.setattr(judged_run, "load_run", _never)
    outcome = cli.invoke(app, ["evaluate", "judged", str(uuid4()), "--max-cost-usd", cap])
    assert outcome.exit_code == 2
    assert "finite" in outcome.stderr


def _command_ending_with(monkeypatch: pytest.MonkeyPatch, status: JudgedStatus) -> UUID:
    """Wire `evaluate judged` to a pass that stops with `status`; returns the run's id."""
    run = _run(_classified("a"))
    monkeypatch.setattr(records, "connect", FakeConnection)
    monkeypatch.setattr(judged_command, "get_settings", _settings)
    monkeypatch.setattr(judge, "JevJudge", FakeRouteJudge)
    monkeypatch.setattr(judge, "BackupJudge", FakeRouteJudge)
    monkeypatch.setattr(judged_run, "load_run", lambda conn, run_id: run)
    monkeypatch.setattr(
        judged_run, "judge_run", lambda *args: JudgedSummary(status, 1, 0, {}, 0.0006, 0)
    )
    return run.id


def test_a_pass_stopped_by_an_unreached_call_says_so_and_exits_1(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_id = _command_ending_with(monkeypatch, JudgedStatus.UNREACHED)
    outcome = cli.invoke(app, ["evaluate", "judged", str(run_id)])
    assert outcome.exit_code == 1, outcome.output
    assert "0 of 1 cases judged, 0 items not measured; $0.0006" in outcome.stdout
    assert "Stopped: the backup judge's call reached no model" in outcome.stderr


def test_a_pass_stopped_at_the_cost_cap_says_so_and_exits_0(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_id = _command_ending_with(monkeypatch, JudgedStatus.COST_CAP_REACHED)
    outcome = cli.invoke(app, ["evaluate", "judged", str(run_id)])
    assert outcome.exit_code == 0, outcome.output
    assert "Stopped at the cost cap; run again to go on" in outcome.stderr
