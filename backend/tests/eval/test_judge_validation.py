"""The judge validation (V4): the committed cases, the labels file, the resumable run, the
measures and the report. Cases built here are invented."""

import json
from collections import Counter
from dataclasses import replace
from pathlib import Path

import pytest
from pydantic import SecretStr
from typer.testing import CliRunner

from aiact import cli
from aiact.corpus.eurlex import DEFAULT_PARSED_DIR, load_jsonl
from aiact.eval import judge, judge_report, judge_validation
from aiact.eval.judge import (
    BACKUP_INSTRUCTIONS,
    CHECKS,
    PROMPT_TOKENS_BOUND,
    BackupJudge,
    BackupVerdict,
    JevAnswer,
    JevJudge,
    JudgeError,
    JudgeItem,
)
from aiact.eval.judge_validation import (
    JudgeRecord,
    JudgeValidationError,
    Route,
    Scored,
    StopReason,
    ValidationCase,
    agreement,
    brier_score,
    calibration_bins,
    cases_to_run,
    combined_verdict,
    expected_calibration_error,
    input_sha256,
    jev_pairs,
    judge_case,
    judges_pairs,
    load_cases,
    load_labels,
    margin_rows,
    read_records,
    recommended_margin,
    run_validation,
)
from aiact.llm import DecisionsError
from aiact.schemas import Language
from aiact.settings import Settings

JEV = "typesafe/jev-1.13"
HAIKU = "anthropic/claude-haiku-5.5"
EU_VERTEX = "google-vertex/europe"
ROUTE = Route(JEV, HAIKU, EU_VERTEX)


def make_case(number: int = 1, lang: str = "en", **changes: object) -> ValidationCase:
    values: dict[str, object] = {
        "id": f"jv-{lang}-{number:02d}",
        "check": "evidence_tag",
        "language": lang,
        "claim": "The system is already in use.",
        "source": f"We plan to buy a scheduling tool (case {number}).",
    } | changes
    return ValidationCase.model_validate(values)


def make_record(
    case: ValidationCase, p_yes: float | None = 0.9, holds: bool | None = True, **changes: object
) -> JudgeRecord:
    values: dict[str, object] = {
        "case_id": case.id,
        "input_sha256": input_sha256(case),
        "jev_model": JEV,
        "p_yes": p_yes,
        "backup_model": HAIKU,
        "backup_provider": EU_VERTEX,
        "holds": holds,
        "reason": None if holds is None else "Stated.",
        "cost_usd": 0.0003,
        "tokens": 900,
    } | changes
    return JudgeRecord.model_validate(values)


# --- the committed set ---------------------------------------------------------------------------


def test_the_committed_set_has_48_cases_balanced_by_language_and_check() -> None:
    cases = load_cases()
    assert len(cases) == 48
    assert Counter(case.language for case in cases) == {Language.EN: 24, Language.DE: 24}
    per_cell = Counter((case.language, case.check) for case in cases)
    assert set(per_cell.values()) == {6}
    assert len(per_cell) == 8


def test_the_label_sheet_has_one_slot_per_case_in_case_order() -> None:
    cases = load_cases()
    text = judge_validation.LABELS_FILE.read_text(encoding="utf-8")
    slots = [line.split(":")[0] for line in text.splitlines() if line.startswith("jv-")]
    assert slots == [case.id for case in cases]
    load_labels(cases)  # the sheet reads


def test_legal_sources_quote_the_amended_act_word_for_word() -> None:
    texts = {
        language: {
            row.provision_id: row.text
            for row in load_jsonl(DEFAULT_PARSED_DIR / f"ai-act-consolidated.{language}.jsonl")
        }
        for language in ("en", "de")
    }
    quoting = [case for case in load_cases() if case.provisions]
    assert len(quoting) == 24
    for case in quoting:
        for provision in case.provisions:
            assert texts[case.language.value][provision] in case.source, (case.id, provision)


def test_every_committed_case_fits_the_prompt_bound() -> None:
    longest = max(len(case.claim) + len(case.source) for case in load_cases())
    assert (len(BACKUP_INSTRUCTIONS) + 600 + longest) / 3 < PROMPT_TOKENS_BOUND


def test_the_validation_files_are_pinned() -> None:
    folder = judge_validation.VALIDATION_DIR
    assert folder.parts[-2:] == ("eval", "judge_validation")
    assert [
        path.name
        for path in (
            judge_validation.CASES_FILE,
            judge_validation.LABELS_FILE,
            judge_validation.ANSWERS_FILE,
            judge_validation.REPORT_FILE,
        )
    ] == ["cases.yaml", "labels.yaml", "answers.jsonl", "report.md"]
    assert judge_validation.MARGINS == (0.0, 0.1, 0.2, 0.3, 0.4, 0.5)
    assert judge_validation.DEFAULT_MAX_COST_USD == 0.10


# --- reading the files ---------------------------------------------------------------------------


def _write(tmp_path: Path, name: str, text: str) -> Path:
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


def test_labels_read_yes_and_no_and_leave_empty_cases_out(tmp_path: Path) -> None:
    cases = [make_case(1), make_case(2), make_case(3)]
    path = _write(tmp_path, "labels.yaml", "jv-en-01: yes\njv-en-02: no\njv-en-03:\n")
    assert load_labels(cases, path) == {"jv-en-01": True, "jv-en-02": False}


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("jv-en-09: yes\n", "unknown case ids jv-en-09"),
        ("jv-en-01: maybe\n", "not yes, no or empty: jv-en-01"),
        ("jv-en-01: yes\njv-en-01: no\n", "duplicate key"),
        ("- jv-en-01\n", "expected a mapping"),
    ],
)
def test_a_bad_labels_file_is_refused(tmp_path: Path, text: str, message: str) -> None:
    with pytest.raises(JudgeValidationError, match=message):
        load_labels([make_case(1)], _write(tmp_path, "labels.yaml", text))


def test_a_repeated_case_id_is_refused(tmp_path: Path) -> None:
    case = make_case(1).model_dump(mode="json")
    path = _write(tmp_path, "cases.yaml", json.dumps([case, case]))
    with pytest.raises(JudgeValidationError, match="repeated ids jv-en-01"):
        load_cases(path)


def test_an_id_must_name_the_case_language() -> None:
    with pytest.raises(ValueError, match="jv-en-01 is not a de id"):
        make_case(1, "en", language="de")


# --- the run -------------------------------------------------------------------------------------


class FakeJev(JevJudge):
    def __init__(self, p_yes: float | None) -> None:
        self.model, self._p_yes = JEV, p_yes
        self.calls = 0

    def ask(self, item: JudgeItem) -> JevAnswer:
        self.calls += 1
        if self._p_yes is None:
            raise DecisionsError("decisions request failed with HTTP 503", 0.00003, 100)
        return JevAnswer(self._p_yes, 0.00002, 400)


class FakeBackup(BackupJudge):
    def __init__(self, holds: bool | None, *, is_call_failed: bool = True) -> None:
        self.model, self.provider, self._holds = HAIKU, EU_VERTEX, holds
        self._is_call_failed = is_call_failed

    def ask(self, item: JudgeItem) -> BackupVerdict:
        if self._holds is None:
            raise JudgeError(
                "ConnectTimeout",
                0.00066,
                0,
                is_cost_estimated=True,
                is_call_failed=self._is_call_failed,
            )
        return BackupVerdict(self._holds, "Not stated.", 0.0002, 800)


def test_a_case_record_holds_both_answers_and_their_summed_cost() -> None:
    record = judge_case(make_case(), FakeJev(0.2), FakeBackup(False))
    assert (record.p_yes, record.holds, record.reason) == (0.2, False, "Not stated.")
    assert (record.cost_usd, record.tokens) == (pytest.approx(0.00022), 1200)
    assert record.is_complete and not record.is_cost_estimated
    assert (record.jev_model, record.backup_model, record.backup_provider) == (
        JEV,
        HAIKU,
        EU_VERTEX,
    )


def test_a_failed_judge_leaves_its_error_and_both_costs_count() -> None:
    record = judge_case(make_case(), FakeJev(None), FakeBackup(None))
    assert (record.p_yes, record.holds) == (None, None)
    assert record.jev_error == "decisions request failed with HTTP 503"
    assert record.backup_error == "ConnectTimeout"
    assert (record.cost_usd, record.tokens) == (pytest.approx(0.00003 + 0.00066), 100)
    assert (record.is_cost_estimated, record.is_backup_call_failed) == (True, True)
    assert not record.is_complete


def test_a_broken_backup_answer_is_not_a_blocked_route() -> None:
    record = judge_case(make_case(), FakeJev(0.4), FakeBackup(None, is_call_failed=False))
    assert record.backup_error == "ConnectTimeout"
    assert not record.is_backup_call_failed


def _judge_with(record_for: dict[str, JudgeRecord], calls: list[str]):
    def judge_one(case: ValidationCase) -> JudgeRecord:
        calls.append(case.id)
        return record_for.get(case.id) or make_record(case)

    return judge_one


def test_the_run_appends_every_record_and_sums_the_cost(tmp_path: Path) -> None:
    cases = [make_case(1), make_case(2)]
    failed = make_record(cases[1], p_yes=None)
    path = tmp_path / "answers.jsonl"
    summary = run_validation(cases, _judge_with({"jv-en-02": failed}, []), path=path)
    assert (summary.planned, summary.answered, summary.failed) == (2, 1, 1)
    assert (summary.cost_usd, summary.tokens) == (pytest.approx(0.0006), 1800)
    assert summary.stopped is None
    assert list(read_records(path)) == ["jv-en-01", "jv-en-02"]


def test_a_backup_call_that_reaches_no_model_stops_the_run(tmp_path: Path) -> None:
    cases = [make_case(1), make_case(2), make_case(3)]
    blocked = make_record(cases[1], holds=None, is_backup_call_failed=True)
    calls: list[str] = []
    path = tmp_path / "a.jsonl"
    summary = run_validation(cases, _judge_with({"jv-en-02": blocked}, calls), path=path)
    assert calls == ["jv-en-01", "jv-en-02"]
    assert summary.stopped is StopReason.NO_ROUTE
    assert (summary.answered, summary.failed) == (1, 1)
    assert list(read_records(path)) == ["jv-en-01", "jv-en-02"]


def test_a_broken_backup_answer_never_stops_the_run(tmp_path: Path) -> None:
    cases = [make_case(1), make_case(2)]
    broken = make_record(cases[0], holds=None, backup_error="answer doesn't fit the schema")
    calls: list[str] = []
    summary = run_validation(cases, _judge_with({"jv-en-01": broken}, calls), path=tmp_path / "a")
    assert (calls, summary.stopped) == (["jv-en-01", "jv-en-02"], None)


def test_the_run_starts_no_case_the_cap_cannot_cover(tmp_path: Path) -> None:
    cases = [make_case(1), make_case(2), make_case(3)]
    calls: list[str] = []
    cap = judge_validation.CASE_ESTIMATE_USD + 0.0002  # one case fits, then 0.0003 is spent
    summary = run_validation(
        cases, _judge_with({}, calls), max_cost_usd=cap, path=tmp_path / "a.jsonl"
    )
    assert calls == ["jv-en-01"]
    assert summary.stopped is StopReason.COST_CAP


def test_the_case_estimate_is_pinned() -> None:
    assert pytest.approx(0.000786) == judge_validation.CASE_ESTIMATE_USD
    assert judge_validation.estimate_usd(48, HAIKU) == pytest.approx(0.037728)


def test_no_estimate_for_a_backup_model_the_prices_dont_belong_to() -> None:
    assert judge_validation.estimate_usd(48, "anthropic/claude-haiku-4.5") is None


def test_only_new_edited_failed_or_rerouted_cases_are_asked_again() -> None:
    done, edited, failed, rerouted, new = (make_case(n) for n in range(1, 6))
    records = {
        done.id: make_record(done),
        edited.id: make_record(edited, input_sha256="0" * 64),
        failed.id: make_record(failed, holds=None),
        rerouted.id: make_record(rerouted, backup_model="anthropic/claude-haiku-4.5"),
    }
    todo = cases_to_run([done, edited, failed, rerouted, new], records, ROUTE)
    assert [case.id for case in todo] == ["jv-en-02", "jv-en-03", "jv-en-04", "jv-en-05"]


def test_an_edited_case_changes_the_hash_and_is_asked_again() -> None:
    case = make_case()
    record = {case.id: make_record(case)}
    before = input_sha256(case)
    assert cases_to_run([case], record, ROUTE) == ()
    edited = [
        case.model_copy(update={"source": "We bought it last year."}),
        case.model_copy(update={"claim": "The system is planned."}),
        case.model_copy(update={"check": judge.JudgeCheck.INVENTED_CONTENT}),
    ]
    for changed in edited:
        assert input_sha256(changed) != before
        assert cases_to_run([changed], record, ROUTE) == (changed,)


def test_a_reworded_question_asks_the_case_again(monkeypatch: pytest.MonkeyPatch) -> None:
    case = make_case()
    record, before = {case.id: make_record(case)}, input_sha256(case)
    spec = CHECKS[case.check]
    question = spec.question.model_copy(update={"instructions": "Is the fact in the text?"})
    monkeypatch.setitem(CHECKS, case.check, replace(spec, question=question))
    assert input_sha256(case) != before
    assert cases_to_run([case], record, ROUTE) == (case,)


def test_reworded_criteria_ask_the_case_again(monkeypatch: pytest.MonkeyPatch) -> None:
    case = make_case()
    record, before = {case.id: make_record(case)}, input_sha256(case)
    spec = CHECKS[case.check]
    criteria = spec.question.criteria.model_copy(update={"false": "It is not said."})
    question = spec.question.model_copy(update={"criteria": criteria})
    monkeypatch.setitem(CHECKS, case.check, replace(spec, question=question))
    assert input_sha256(case) != before
    assert cases_to_run([case], record, ROUTE) == (case,)


def test_reworded_backup_instructions_ask_the_case_again(monkeypatch: pytest.MonkeyPatch) -> None:
    case = make_case()
    record, before = {case.id: make_record(case)}, input_sha256(case)
    monkeypatch.setattr(judge, "BACKUP_INSTRUCTIONS", BACKUP_INSTRUCTIONS + "Be brief.\n")
    assert input_sha256(case) != before
    assert cases_to_run([case], record, ROUTE) == (case,)


def test_a_missing_answers_file_has_no_records(tmp_path: Path) -> None:
    assert read_records(tmp_path / "none.jsonl") == {}


def test_a_broken_answers_line_is_named_by_its_number(tmp_path: Path) -> None:
    path = _write(tmp_path, "answers.jsonl", '\n{"case_id": "jv-en-01"}\n')
    with pytest.raises(JudgeValidationError, match="line 2 is not a judge record"):
        read_records(path)


# --- the measures --------------------------------------------------------------------------------


def test_agreement_gives_the_rate_and_cohens_kappa() -> None:
    result = agreement([(True, True), (True, True), (False, False), (True, False)])
    assert (result.n, result.agreed, result.rate) == (4, 3, 0.75)
    assert result.kappa == pytest.approx(0.5)


def test_kappa_is_undefined_when_both_sides_never_vary_and_nothing_is_no_cases() -> None:
    assert agreement([(True, True), (True, True)]).kappa is None
    empty = agreement([])
    assert (empty.n, empty.rate, empty.kappa) == (0, None, None)


def test_calibration_bins_brier_and_ece() -> None:
    points = [(0.1, False), (0.1, True), (0.9, True), (1.0, True)]
    bins = calibration_bins(points, bins=5)
    assert [item.n for item in bins] == [2, 0, 0, 0, 2]
    assert (bins[0].mean_p, bins[0].yes_rate) == (pytest.approx(0.1), 0.5)
    assert (bins[4].mean_p, bins[4].yes_rate) == (pytest.approx(0.95), 1.0)
    assert brier_score(points) == pytest.approx((0.01 + 0.81 + 0.01 + 0.0) / 4)
    assert expected_calibration_error(bins) == pytest.approx(0.5 * 0.4 + 0.5 * 0.05)
    assert brier_score([]) is None


def test_the_combined_verdict_takes_jev_when_sure_and_the_backup_otherwise() -> None:
    case = make_case()
    assert combined_verdict(make_record(case, p_yes=0.9, holds=False), 0.3) is True
    assert combined_verdict(make_record(case, p_yes=0.6, holds=False), 0.3) is False
    assert combined_verdict(make_record(case, p_yes=None, holds=True), 0.0) is True
    assert combined_verdict(make_record(case, p_yes=0.6, holds=None), 0.3) is None


def test_one_half_is_jevs_yes_in_every_measure() -> None:
    case = make_case()
    record = make_record(case, p_yes=0.5, holds=False)
    assert combined_verdict(record, 0.0) is True
    assert jev_pairs([Scored(case, record, False)]) == [(True, False)]
    assert judges_pairs([record]) == [(True, False)]


def _scored(rows: list[tuple[float | None, bool | None, bool]]) -> list[Scored]:
    scored = []
    for number, (p_yes, holds, label) in enumerate(rows, start=1):
        case = make_case(number)
        scored.append(Scored(case, make_record(case, p_yes=p_yes, holds=holds), label))
    return scored


def test_margins_count_hand_overs_and_the_smallest_best_margin_is_recommended() -> None:
    # Jev is wrong only on the 0.65 case, which the backup gets right; the 0.95 case is right.
    scored = _scored([(0.65, False, False), (0.95, True, True), (0.05, True, False)])
    rows = margin_rows(scored, margins=(0.0, 0.1, 0.2, 0.5))
    assert [row.sent_to_backup for row in rows] == [0, 0, 1, 3]
    assert [row.with_labels.agreed for row in rows] == [2, 2, 3, 2]
    assert recommended_margin(rows) == 0.2


def test_a_failed_backup_is_counted_apart_never_as_a_miss() -> None:
    rows = margin_rows(_scored([(0.5, None, True), (0.9, True, True)]), margins=(0.0, 0.3))
    assert [(row.with_labels.n, row.unmeasured) for row in rows] == [(2, 0), (1, 1)]


def test_no_margin_is_recommended_while_a_row_leaves_a_case_unmeasured() -> None:
    """Margin 0.3 would agree 1/1 against 0.0's 1/2, but over fewer cases."""
    rows = margin_rows(_scored([(0.6, None, False), (0.9, True, True)]), margins=(0.0, 0.3))
    assert [(row.with_labels.agreed, row.with_labels.n) for row in rows] == [(1, 2), (1, 1)]
    assert recommended_margin(rows) is None


def test_a_failed_jev_is_sent_to_the_backup_at_every_margin() -> None:
    rows = margin_rows(_scored([(None, True, True)]), margins=(0.0, 0.3))
    assert [row.sent_to_backup for row in rows] == [1, 1]
    assert [row.with_labels.agreed for row in rows] == [1, 1]


def test_no_margin_is_recommended_without_a_measured_case() -> None:
    assert recommended_margin(margin_rows([])) is None


# --- the report ----------------------------------------------------------------------------------


def test_the_report_quotes_the_measures_from_the_records() -> None:
    cases = [make_case(1), make_case(2, "de"), make_case(3)]
    labels = {"jv-en-01": True, "jv-de-02": False}
    records = {
        "jv-en-01": make_record(cases[0], p_yes=0.9, holds=True),
        "jv-de-02": make_record(cases[1], p_yes=0.7, holds=False, cost_usd=0.0004),
        "jv-en-03": make_record(cases[2], p_yes=0.1, holds=False),
    }
    text = judge_report.format_report(cases, labels, records, ROUTE)
    assert "Cases: 3 (2 EN, 1 DE); labelled: 2 (1 yes, 1 no)" in text
    assert "answered by both judges: 3; measured (labelled, with a current record): 2" in text
    assert "| all | 1/2 (50%, κ 0.00) | 2/2 (100%, κ 1.00) |" in text
    assert "Over every case both answered, labelled or not: 2/3" in text
    assert "| 0.3 | 1 | 2/2 (100%, κ 1.00) | 0 |" in text
    assert "Highest agreement at the smallest margin: **0.3**." in text
    assert "| jv-de-02 | evidence_tag | no | 0.700 | no |" in text
    assert "Cost of the answers counted here: $0.0010." in text


def test_the_report_breaks_agreement_down_by_language_check_and_bin() -> None:
    cases = [
        make_case(1, check="citation_support"),
        make_case(2, "de"),
        make_case(3, check="citation_support"),
    ]
    labels = {"jv-en-01": True, "jv-de-02": False, "jv-en-03": True}
    records = {
        "jv-en-01": make_record(cases[0], p_yes=0.9, holds=True),
        "jv-de-02": make_record(cases[1], p_yes=0.3, holds=False),
        "jv-en-03": make_record(cases[2], p_yes=0.8, holds=False),  # only the backup is wrong
    }
    text = judge_report.format_report(cases, labels, records, ROUTE)
    assert "| EN | 2/2 (100%, κ n/a) | 1/2 (50%, κ 0.00) |" in text
    assert "| DE | 1/1 (100%, κ n/a) | 1/1 (100%, κ n/a) |" in text
    assert "| citation_support | 2/2 (100%, κ n/a) | 1/2 (50%, κ 0.00) |" in text
    assert (
        "Over 3 labelled cases: Brier score 0.047 (0 is perfect), expected calibration error 0.200."
        in text
    )
    assert "| [0.8, 1.0] | 2 | 0.850 | 1.000 |" in text
    assert "| jv-en-03 | citation_support | yes | 0.800 | no |" in text
    assert "jv-en-01 |" not in text.split("## Cases a judge got wrong")[1]


def test_the_report_recommends_no_margin_while_a_case_is_unmeasured() -> None:
    case = make_case(1)
    record = make_record(case, p_yes=0.6, holds=None)
    text = judge_report.format_report([case], {case.id: True}, {case.id: record}, ROUTE)
    assert "No margin is recommended while 1 labelled case(s) have no combined answer" in text


def test_an_unlabelled_report_recommends_no_margin() -> None:
    case = make_case(1)
    text = judge_report.format_report([case], {}, {case.id: make_record(case)}, ROUTE)
    assert "No labelled case has a record yet, so no margin can be recommended." in text
    assert "| all | no cases | no cases |" in text


def _cli_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, count: int = 1, **values: object
) -> None:
    """The CLI on `count` invented cases, each labelled yes, and the given files, with settings
    that read no `.env`."""
    cases = [make_case(number).model_dump(mode="json") for number in range(1, count + 1)]
    labels = "".join(f"jv-en-{number:02d}: yes\n" for number in range(1, count + 1))
    monkeypatch.setattr(
        judge_validation, "CASES_FILE", _write(tmp_path, "c.yaml", json.dumps(cases))
    )
    monkeypatch.setattr(judge_validation, "LABELS_FILE", _write(tmp_path, "labels.yaml", labels))
    monkeypatch.setattr(judge_validation, "ANSWERS_FILE", tmp_path / "answers.jsonl")
    monkeypatch.setattr(judge_validation, "REPORT_FILE", tmp_path / "report.md")
    settings = Settings(_env_file=None, openrouter_api_key=SecretStr("k"), **values)  # pyright: ignore[reportCallIssue]
    monkeypatch.setattr(cli, "get_settings", lambda: settings)


def _no_judge(*args: object) -> None:
    raise AssertionError("no judge may be built")


def test_the_cli_dry_run_reads_the_files_and_makes_no_call(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _cli_files(tmp_path, monkeypatch)
    monkeypatch.setattr(cli, "JevJudge", _no_judge)
    result = CliRunner().invoke(cli.app, ["evaluate", "judge-validation", "--dry-run"])
    assert result.exit_code == 0, result.output
    assert "1 cases (1 labelled), 1 to answer with typesafe/jev-1.13 and" in result.output
    assert "anthropic/claude-haiku-5.5 on google-vertex/europe; at most $0.0008" in result.output
    assert not (tmp_path / "answers.jsonl").exists()
    assert not (tmp_path / "report.md").exists()


def test_the_cli_report_only_writes_the_report_without_a_call(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _cli_files(tmp_path, monkeypatch)
    monkeypatch.setattr(cli, "JevJudge", _no_judge)
    result = CliRunner().invoke(cli.app, ["evaluate", "judge-validation", "--report-only"])
    assert result.exit_code == 0, result.output
    report = (tmp_path / "report.md").read_text(encoding="utf-8")
    assert "labelled: 1 (1 yes, 0 no); answered by both judges: 0" in report
    assert not (tmp_path / "answers.jsonl").exists()


def test_the_cli_warns_when_the_prices_dont_belong_to_the_backup_model(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _cli_files(tmp_path, monkeypatch, judge_backup_model="anthropic/claude-haiku-4.5")
    result = CliRunner().invoke(cli.app, ["evaluate", "judge-validation", "--dry-run"])
    assert result.exit_code == 0, result.output
    assert "google-vertex/europe; COST UNKNOWN (cap $0.10)" in result.output
    assert "WARNING: prices known for anthropic/claude-haiku-5.5 only" in result.output


def _fake_judges(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli, "JevJudge", lambda settings: FakeJev(0.9))
    monkeypatch.setattr(cli, "BackupJudge", lambda settings: FakeBackup(True))


def test_the_cli_run_writes_the_answers_and_the_report_then_resumes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _cli_files(tmp_path, monkeypatch, count=2)
    _fake_judges(monkeypatch)
    result = CliRunner().invoke(cli.app, ["evaluate", "judge-validation"])
    assert result.exit_code == 0, result.output
    assert "2 answered by both judges, 0 with a failed judge, of 2" in result.output
    assert list(read_records(tmp_path / "answers.jsonl")) == ["jv-en-01", "jv-en-02"]
    report = (tmp_path / "report.md").read_text(encoding="utf-8")
    assert "answered by both judges: 2; measured (labelled, with a current record): 2" in report

    monkeypatch.setattr(cli, "JevJudge", _no_judge)
    again = CliRunner().invoke(cli.app, ["evaluate", "judge-validation"])
    assert again.exit_code == 0, again.output
    assert "2 cases (2 labelled), 0 to answer" in again.output
    lines = (tmp_path / "answers.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2


def test_the_cli_run_stops_at_the_cost_cap_and_reports_what_it_has(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _cli_files(tmp_path, monkeypatch, count=2)
    _fake_judges(monkeypatch)
    cap = str(judge_validation.CASE_ESTIMATE_USD + 0.0001)  # one case fits, not two
    result = CliRunner().invoke(cli.app, ["evaluate", "judge-validation", "--max-cost-usd", cap])
    assert result.exit_code == 0, result.output
    assert "Stopped early: the next case would pass the cost cap" in result.output
    assert list(read_records(tmp_path / "answers.jsonl")) == ["jv-en-01"]
    report = (tmp_path / "report.md").read_text(encoding="utf-8")
    assert "answered by both judges: 1; measured (labelled, with a current record): 1" in report
