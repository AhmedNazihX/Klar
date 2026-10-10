"""The label filter's disagreements report (B9): the comparison, the resolutions kept across
regenerations, and the DoD check. Cases here are invented, not benchmark cases."""

from pathlib import Path

import pytest
from typer.testing import CliRunner

from aiact import cli
from aiact.cli import app
from aiact.eval import label_filter, label_filter_report
from aiact.eval.cases import BenchmarkCase, CaseLabel, CaseSet
from aiact.eval.label_filter import FilterAnswer, FilterRecord, input_sha256
from aiact.eval.label_filter_report import (
    Difference,
    check_report,
    compare,
    differences,
    read_resolutions,
    render_report,
)
from aiact.schemas import RiskClass, Role, Status
from aiact.settings import Settings
from tests.eval.test_label_filter import DESCRIPTION, EU_VERTEX, HAIKU, RUN_DATE, answer, make_case

HIGH = CaseLabel(
    risk_class=RiskClass.HIGH_RISK,
    status=Status.DECIDED,
    role=Role.DEPLOYER,
    annex_point=("annex:III:4:a", "annex:III:4:b"),
)


def record(case: BenchmarkCase, given: FilterAnswer | None, **changes: object) -> FilterRecord:
    values: dict[str, object] = {
        "case_id": case.id,
        "set_name": case.set_name,
        "input_sha256": input_sha256(case),
        "judged_on": RUN_DATE,
        "model": HAIKU,
        "provider": EU_VERTEX,
        "answer": given,
        "error": None if given else "ConnectTimeout",
        "cost_usd": 0.004,
        "tokens": 100,
    } | changes
    return FilterRecord.model_validate(values)


# --- differences ---------------------------------------------------------------------------------


def test_an_answer_that_states_the_same_has_no_difference() -> None:
    assert differences(HIGH, answer(annex_point="annex:III:4:b")) == ()


@pytest.mark.parametrize(
    ("changes", "found"),
    [
        ({"risk_class": RiskClass.MINIMAL_RISK, "annex_point": None}, (Difference.CLASS,)),
        ({"status": Status.LEGALLY_AMBIGUOUS}, (Difference.STATUS,)),
        ({"role": Role.PROVIDER}, (Difference.ROLE,)),
        ({"annex_point": "annex:III:5:b"}, (Difference.ANNEX_POINT,)),
        ({"annex_point": None}, (Difference.ANNEX_POINT,)),
        (
            {"risk_class": None, "status": Status.NEEDS_MORE_INFORMATION, "role": None},
            (Difference.CLASS, Difference.STATUS, Difference.ROLE),
        ),
    ],
)
def test_each_kind_of_difference_is_found(
    changes: dict[str, object], found: tuple[Difference, ...]
) -> None:
    assert differences(HIGH, answer(**changes)) == found


def test_a_role_the_label_leaves_open_is_not_compared() -> None:
    label = HIGH.model_copy(update={"role": None})
    assert differences(label, answer(role=Role.PROVIDER)) == ()


def test_an_annex_point_is_compared_only_when_both_say_high_risk() -> None:
    no_points = HIGH.model_copy(update={"annex_point": ()})
    assert differences(no_points, answer(annex_point="annex:III:1:a")) == ()
    limited = CaseLabel(risk_class=RiskClass.LIMITED_RISK, role=Role.DEPLOYER)
    assert differences(limited, answer(annex_point="annex:III:4:a")) == (Difference.CLASS,)


# --- comparison and check ------------------------------------------------------------------------

AGREE, DISAGREE, FAILED, EDITED, NEW = (make_case(n) for n in range(1, 6))


def comparison() -> label_filter_report.Comparison:
    edited_now = make_case(4, description=DESCRIPTION + " Edited.")
    records = {
        AGREE.id: record(AGREE, answer()),
        DISAGREE.id: record(DISAGREE, answer(risk_class=RiskClass.MINIMAL_RISK, annex_point=None)),
        FAILED.id: record(FAILED, None),
        EDITED.id: record(EDITED, answer()),
    }
    cases = (AGREE, DISAGREE, FAILED, edited_now, NEW)
    return compare(cases, records, HAIKU, EU_VERTEX)


def test_compare_sorts_every_case_and_says_why_one_is_unlabelled() -> None:
    result = comparison()
    assert [c.id for c in result.agreeing] == [AGREE.id]
    assert [(d.case.id, d.differences) for d in result.disagreements] == [
        (DISAGREE.id, (Difference.CLASS,))
    ]
    assert [c.id for c in result.unlabelled] == [FAILED.id, EDITED.id, NEW.id]
    assert result.errors == {
        FAILED.id: "the call failed: ConnectTimeout",
        EDITED.id: "the case or the model changed since it was labelled",
        NEW.id: "not labelled yet",
    }
    assert result.cost_usd == pytest.approx(0.008)


def test_an_answer_from_another_model_does_not_count() -> None:
    records = {AGREE.id: record(AGREE, answer(), model="other/model")}
    assert [c.id for c in compare((AGREE,), records, HAIKU, EU_VERTEX).unlabelled] == [AGREE.id]


def test_the_check_wants_every_case_labelled_and_every_disagreement_resolved() -> None:
    result = comparison()
    unresolved = check_report(result, {})
    assert unresolved.unresolved == (DISAGREE.id,)
    assert unresolved.unlabelled == (FAILED.id, make_case(4).id, NEW.id)
    assert not unresolved.is_ok
    labelled = compare((AGREE, DISAGREE), {r.case_id: r for r in _two_records()}, HAIKU, EU_VERTEX)
    assert not check_report(labelled, {}).is_ok
    assert check_report(labelled, {DISAGREE.id: "kept: Annex III 4(a) applies."}).is_ok


def _two_records() -> tuple[FilterRecord, ...]:
    other = answer(risk_class=RiskClass.MINIMAL_RISK, annex_point=None)
    return record(AGREE, answer()), record(DISAGREE, other)


# --- the report ----------------------------------------------------------------------------------


def test_the_report_lists_the_disagreement_with_both_readings_and_no_description() -> None:
    text = render_report(comparison(), {}, HAIKU, EU_VERTEX)
    assert f"### {DISAGREE.id}" in text
    assert "- Label: high_risk, decided; role deployer; annex:III:4:a; cites annex:III:4:a" in text
    assert "- Second model: minimal_risk, decided; role deployer; no Annex point" in text
    assert "- Differs on: class" in text
    assert "\n**Resolution:**\n" in text
    assert f"- `{FAILED.id}`: the call failed: ConnectTimeout" in text
    assert "| own | 5 | 1 | 1 | 3 |" in text
    assert DESCRIPTION not in text
    assert "hidden note" not in text


def test_resolutions_survive_a_regeneration_even_when_the_disagreement_is_gone() -> None:
    first = render_report(comparison(), {}, HAIKU, EU_VERTEX)
    written = first.replace(
        "\n**Resolution:**\n",
        "\n**Resolution:** kept: CV ranking is Annex III 4(a).\nSecond line.\n",
        1,
    )
    resolutions = read_resolutions(written)
    assert resolutions[DISAGREE.id] == "kept: CV ranking is Annex III 4(a).\nSecond line."
    again = render_report(comparison(), resolutions, HAIKU, EU_VERTEX)
    assert read_resolutions(again)[DISAGREE.id] == resolutions[DISAGREE.id]
    agreeing_now = compare((AGREE,), {AGREE.id: record(AGREE, answer())}, HAIKU, EU_VERTEX)
    later = render_report(agreeing_now, resolutions, HAIKU, EU_VERTEX)
    assert "## Resolved earlier, no longer disagreeing" in later
    assert read_resolutions(later) == {DISAGREE.id: resolutions[DISAGREE.id]}


def test_an_empty_resolution_reads_as_missing() -> None:
    text = render_report(comparison(), {}, HAIKU, EU_VERTEX)
    assert read_resolutions(text) == {DISAGREE.id: ""}


# --- the command ---------------------------------------------------------------------------------

runner = CliRunner()


@pytest.fixture
def files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    answers, report = tmp_path / "answers.jsonl", tmp_path / "label_disagreements.md"
    monkeypatch.setattr(label_filter, "ANSWERS_FILE", answers)
    monkeypatch.setattr(label_filter_report, "REPORT_FILE", report)
    monkeypatch.setattr(label_filter, "load_filtered_cases", lambda sets: (AGREE, DISAGREE))
    # The default route, whatever backend/.env sets.
    monkeypatch.setattr(cli, "get_settings", lambda: Settings(_env_file=None))  # pyright: ignore[reportCallIssue]
    return answers, report


def _write(answers: Path, *records: FilterRecord) -> None:
    answers.write_text("".join(f"{r.model_dump_json()}\n" for r in records), encoding="utf-8")


def test_dry_run_prints_the_plan_and_makes_no_call(files: tuple[Path, Path]) -> None:
    answers, report = files
    _write(answers, record(AGREE, answer()))
    result = runner.invoke(app, ["evaluate", "label-filter", "--dry-run"])
    assert result.exit_code == 0, result.output
    assert (
        "2 cases, 1 to label with anthropic/claude-haiku-4.5 on google-vertex/europe; "
        "at most $0.02 (cap $1.00)"
    ) in result.stdout
    assert not report.exists()


def test_a_run_with_nothing_to_label_writes_the_report(files: tuple[Path, Path]) -> None:
    answers, report = files
    _write(answers, *_two_records())
    result = runner.invoke(app, ["evaluate", "label-filter"])
    assert result.exit_code == 0, result.output
    assert "1 agree, 1 disagree, 0 not labelled" in result.stdout
    assert f"### {DISAGREE.id}" in report.read_text(encoding="utf-8")


def test_the_check_fails_until_every_disagreement_is_resolved(files: tuple[Path, Path]) -> None:
    answers, report = files
    _write(answers, *_two_records())
    assert runner.invoke(app, ["evaluate", "label-filter"]).exit_code == 0
    failing = runner.invoke(app, ["evaluate", "label-filter", "--check"])
    assert failing.exit_code == 1
    assert f"NO RESOLUTION: {DISAGREE.id}" in failing.output
    text = report.read_text(encoding="utf-8")
    report.write_text(
        text.replace("\n**Resolution:**\n", "\n**Resolution:** changed: see row 12.\n")
    )
    passing = runner.invoke(app, ["evaluate", "label-filter", "--check"])
    assert passing.exit_code == 0, passing.output


def test_the_check_fails_while_a_case_is_unlabelled(files: tuple[Path, Path]) -> None:
    answers, _ = files
    _write(answers, record(AGREE, answer()))
    result = runner.invoke(app, ["evaluate", "label-filter", "--check"])
    assert result.exit_code == 1
    assert f"NOT LABELLED: {DISAGREE.id}" in result.output


def test_a_set_with_someone_elses_labels_is_refused(files: tuple[Path, Path]) -> None:
    result = runner.invoke(app, ["evaluate", "label-filter", "--set", CaseSet.ACADEMIC.value])
    assert result.exit_code == 2
    assert "not an own-labelled set: academic" in result.output


def test_a_run_labels_the_open_cases_and_appends_them(
    files: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    from tests.eval.test_label_filter import CountingFilter

    answers, report = files
    _write(answers, record(AGREE, answer()))
    labeller = CountingFilter()
    monkeypatch.setattr(label_filter, "LabelFilter", lambda settings: labeller)
    result = runner.invoke(app, ["evaluate", "label-filter"])
    assert result.exit_code == 0, result.output
    assert labeller.calls == [DISAGREE.id]
    assert "1 labelled, 0 failed of 1; $0.0040, 100 tokens" in result.stdout
    assert set(label_filter.read_records(answers)) == {AGREE.id, DISAGREE.id}
    assert report.exists()
