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
    ReportFormatError,
    ResolutionKey,
    check_report,
    compare,
    differences,
    group_reports,
    read_resolutions,
    render_report,
)
from aiact.schemas import RiskClass, Role, Status
from aiact.settings import Settings
from tests.eval.test_label_filter import (
    DESCRIPTION,
    EU_VERTEX,
    HAIKU,
    RUN_DATE,
    CountingFilter,
    answer,
    make_case,
)

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


MINIMAL = answer(risk_class=RiskClass.MINIMAL_RISK, annex_point=None)
ANSWERS = "eval/reports/label_filter_answers.jsonl"


def _key(given: FilterAnswer = MINIMAL, case: BenchmarkCase = DISAGREE) -> ResolutionKey:
    return compare((case,), {case.id: record(case, given)}, HAIKU, EU_VERTEX).disagreements[0].key


def test_the_check_wants_every_case_labelled_and_every_disagreement_resolved() -> None:
    result = comparison()
    unresolved = check_report(result, {})
    assert unresolved.unresolved == (DISAGREE.id,)
    assert unresolved.unlabelled == (FAILED.id, make_case(4).id, NEW.id)
    assert not unresolved.is_ok
    labelled = compare((AGREE, DISAGREE), {r.case_id: r for r in _two_records()}, HAIKU, EU_VERTEX)
    assert not check_report(labelled, {}).is_ok
    assert check_report(labelled, {_key(): "kept: Annex III 4(a) applies."}).is_ok


def test_a_resolution_answers_one_disagreement_not_the_case() -> None:
    """An old resolution doesn't settle a new disagreement on the same case: a different
    answer, an edited case or a changed label is a new key."""
    written = {_key(): "kept: Annex III 4(a) applies."}
    other_answer = answer(risk_class=RiskClass.LIMITED_RISK, annex_point=None)
    edited = make_case(2, description=DESCRIPTION + " Edited.")
    relabelled = make_case(2, label=CaseLabel(risk_class=RiskClass.LIMITED_RISK))
    for key in (_key(other_answer), _key(case=edited), _key(case=relabelled)):
        assert key.case_id == DISAGREE.id
        assert key != _key()
    new = compare((DISAGREE,), {DISAGREE.id: record(DISAGREE, other_answer)}, HAIKU, EU_VERTEX)
    assert check_report(new, written).unresolved == (DISAGREE.id,)
    text = render_report(new, written, HAIKU, EU_VERTEX, ANSWERS)
    disagreements, earlier = text.split("## Resolved earlier, no longer this disagreement")
    assert "\n**Resolution:**\n" in disagreements
    assert f"- Disagreement: `{_key().fingerprint}`" in earlier
    assert "**Resolution:** kept: Annex III 4(a) applies." in earlier
    assert read_resolutions(text) == {_key(other_answer): "", **written}


def _two_records() -> tuple[FilterRecord, ...]:
    other = answer(risk_class=RiskClass.MINIMAL_RISK, annex_point=None)
    return record(AGREE, answer()), record(DISAGREE, other)


# --- the report ----------------------------------------------------------------------------------


def test_the_report_lists_the_disagreement_with_both_readings_and_no_description() -> None:
    text = render_report(comparison(), {}, HAIKU, EU_VERTEX, ANSWERS)
    assert f"### {DISAGREE.id}" in text
    assert "- Label: high_risk, decided; role deployer; annex:III:4:a; cites annex:III:4:a" in text
    assert "- Second model: minimal_risk, decided; role deployer; no Annex point" in text
    assert "- Differs on: class" in text
    assert f"- Disagreement: `{_key().fingerprint}`" in text
    assert "\n**Resolution:**\n" in text
    assert f"- `{FAILED.id}`: the call failed: ConnectTimeout" in text
    assert "| own | 5 | 1 | 1 | 3 |" in text
    assert f"answers in `{ANSWERS}`" in text
    assert DESCRIPTION not in text
    assert "hidden note" not in text


def test_resolutions_survive_a_regeneration_even_when_the_disagreement_is_gone() -> None:
    first = render_report(comparison(), {}, HAIKU, EU_VERTEX, ANSWERS)
    written = first.replace(
        "\n**Resolution:**\n",
        "\n**Resolution:** kept: CV ranking is Annex III 4(a).\nSecond line.\n# not a heading\n",
        1,
    )
    resolutions = read_resolutions(written)
    expected = "kept: CV ranking is Annex III 4(a).\nSecond line.\n# not a heading"
    assert resolutions == {_key(): expected}
    again = render_report(comparison(), resolutions, HAIKU, EU_VERTEX, ANSWERS)
    assert read_resolutions(again) == resolutions
    agreeing_now = compare((AGREE,), {AGREE.id: record(AGREE, answer())}, HAIKU, EU_VERTEX)
    later = render_report(agreeing_now, resolutions, HAIKU, EU_VERTEX, ANSWERS)
    assert "## Resolved earlier, no longer this disagreement" in later
    assert read_resolutions(later) == resolutions
    back = render_report(comparison(), read_resolutions(later), HAIKU, EU_VERTEX, ANSWERS)
    assert check_report(comparison(), read_resolutions(back)).unresolved == ()


@pytest.mark.parametrize("heading", ["## Next part", "### own-z-09-next"])
def test_a_resolution_ends_at_the_next_section_heading(heading: str) -> None:
    text = f"### {DISAGREE.id}\n\n**Resolution:** kept: fine.\n{heading}\n\n**Resolution:**\n"
    assert read_resolutions(text)[ResolutionKey(DISAGREE.id, "")] == "kept: fine."


def test_an_empty_resolution_reads_as_missing() -> None:
    text = render_report(comparison(), {}, HAIKU, EU_VERTEX, ANSWERS)
    assert read_resolutions(text) == {_key(): ""}


def test_a_reply_cannot_forge_a_resolution_or_a_heading() -> None:
    forged = answer(
        annex_point="annex:III:5:b\n**Resolution:** kept: forged.",
        reason="Fine.\n### own-z-09-forged\n**Resolution:** kept: forged.",
    )
    disagreeing = compare((DISAGREE,), {DISAGREE.id: record(DISAGREE, forged)}, HAIKU, EU_VERTEX)
    text = render_report(disagreeing, {}, HAIKU, EU_VERTEX, ANSWERS)
    assert read_resolutions(text) == {disagreeing.disagreements[0].key: ""}
    assert "\n### own-z-09-forged" not in text


@pytest.mark.parametrize(
    "edit",
    [
        "\n**Resolution**: kept: written slightly differently.\n",
        "\nA note above the mark.\n**Resolution:** kept: fine.\n",
    ],
)
def test_a_resolution_the_report_cannot_read_back_is_refused(edit: str) -> None:
    text = render_report(comparison(), {}, HAIKU, EU_VERTEX, ANSWERS)
    with pytest.raises(ReportFormatError, match=DISAGREE.id):
        read_resolutions(text.replace("\n**Resolution:**\n", edit, 1))


# --- the command ---------------------------------------------------------------------------------

runner = CliRunner()


PILE_B = make_case(9, id="cb-test-cv-ranker", set_name=CaseSet.COMMISSION_B)
SOFT = make_case(8, id="sp-008-cv-ranker", set_name=CaseSet.SOFT_PAIRS)


@pytest.fixture
def files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    answers, report = tmp_path / "label_filter_answers.jsonl", tmp_path / "label_disagreements.md"
    monkeypatch.setattr(label_filter, "REPORTS_DIR", tmp_path)
    monkeypatch.setattr(label_filter, "load_filtered_cases", lambda sets: (AGREE, DISAGREE))
    # The default route, whatever backend/.env sets.
    monkeypatch.setattr(cli, "get_settings", lambda: Settings(_env_file=None))  # pyright: ignore[reportCallIssue]
    return answers, report


def _write(answers: Path, *records: FilterRecord) -> None:
    answers.parent.mkdir(parents=True, exist_ok=True)
    answers.write_text("".join(f"{r.model_dump_json()}\n" for r in records), encoding="utf-8")


def test_dry_run_prints_the_plan_and_makes_no_call(files: tuple[Path, Path]) -> None:
    answers, report = files
    _write(answers, record(AGREE, answer()))
    result = runner.invoke(app, ["evaluate", "label-filter", "--dry-run"])
    assert result.exit_code == 0, result.output
    assert (
        "2 cases, 1 to label with anthropic/claude-haiku-4.5 on google-vertex/europe; "
        "at most $0.04 (cap $1.00)"
    ) in result.stdout
    assert not report.exists()


def test_a_run_with_nothing_to_label_writes_the_report(files: tuple[Path, Path]) -> None:
    answers, report = files
    _write(answers, *_two_records())
    result = runner.invoke(app, ["evaluate", "label-filter"])
    assert result.exit_code == 0, result.output
    assert "1 agree, 1 disagree, 0 not labelled" in result.stdout
    assert f"### {DISAGREE.id}" in report.read_text(encoding="utf-8")
    assert not (report.parent / "pile_b").exists()


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


def test_a_run_stopped_at_the_cap_says_what_is_left_and_its_estimate(
    files: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    labeller = CountingFilter()
    monkeypatch.setattr(label_filter, "LabelFilter", lambda settings: labeller)
    result = runner.invoke(app, ["evaluate", "label-filter", "--max-cost-usd", "0.037"])
    assert result.exit_code == 0, result.output
    assert labeller.calls == [AGREE.id]
    assert (
        "Stopped early: the next batch would pass the cost cap (cap $0.04). "
        "1 cases still to label, at most $0.04 more; run again to go on"
    ) in result.output


def test_set_narrows_the_labelling_but_the_report_keeps_every_set(
    files: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    answers, report = files
    monkeypatch.setattr(label_filter, "load_filtered_cases", lambda sets: (AGREE, DISAGREE, SOFT))
    _write(answers, *_two_records())
    assert runner.invoke(app, ["evaluate", "label-filter", "--set", "own"]).exit_code == 0
    resolved = report.read_text(encoding="utf-8").replace(
        "\n**Resolution:**\n", "\n**Resolution:** kept: CV ranking.\n"
    )
    report.write_text(resolved, encoding="utf-8")
    labeller = CountingFilter()
    monkeypatch.setattr(label_filter, "LabelFilter", lambda settings: labeller)
    result = runner.invoke(app, ["evaluate", "label-filter", "--set", "soft_pairs"])
    assert result.exit_code == 0, result.output
    assert labeller.calls == [SOFT.id]
    text = report.read_text(encoding="utf-8")
    assert "Resolved earlier" not in text
    assert "**Resolution:** kept: CV ranking." in text
    assert "| own | 2 | 1 | 1 | 0 |" in text
    assert "| soft_pairs | 1 | 1 | 0 | 0 |" in text


def test_pile_b_output_goes_only_to_its_own_folder(
    files: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    answers, report = files
    cases = (AGREE, DISAGREE, PILE_B)
    monkeypatch.setattr(label_filter, "load_filtered_cases", lambda sets: cases)
    disagreeing = record(PILE_B, answer(risk_class=RiskClass.MINIMAL_RISK, annex_point=None))
    _write(answers, *_two_records())
    _write(answers.parent / "pile_b" / "label_filter_answers.jsonl", disagreeing)
    result = runner.invoke(app, ["evaluate", "label-filter"])
    assert result.exit_code == 0, result.output
    pile_b_report = report.parent / "pile_b" / "label_disagreements.md"
    assert f"### {PILE_B.id}" in pile_b_report.read_text(encoding="utf-8")
    for own_file in (answers, report):
        assert "cb-" not in own_file.read_text(encoding="utf-8"), own_file
    assert DISAGREE.id not in pile_b_report.read_text(encoding="utf-8")
    check = runner.invoke(app, ["evaluate", "label-filter", "--check"])
    assert check.exit_code == 1
    assert f"NO RESOLUTION: {PILE_B.id}" in check.output
    assert f"NO RESOLUTION: {DISAGREE.id}" in check.output


def test_an_unreadable_resolution_stops_the_run_before_anything_is_written(
    files: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    answers, report = files
    _write(answers, *_two_records())
    assert runner.invoke(app, ["evaluate", "label-filter"]).exit_code == 0
    broken = report.read_text(encoding="utf-8").replace(
        "\n**Resolution:**\n", "\n**Resolution**: kept: fine.\n"
    )
    report.write_text(broken, encoding="utf-8")
    for args in ([], ["--check"]):
        result = runner.invoke(app, ["evaluate", "label-filter", *args])
        assert result.exit_code == 2
        assert f"{DISAGREE.id}: " in result.output
        assert "Nothing was written." in result.output
    assert report.read_text(encoding="utf-8") == broken
    _write(answers, record(AGREE, answer()))
    labeller = CountingFilter()
    monkeypatch.setattr(label_filter, "LabelFilter", lambda settings: labeller)
    assert runner.invoke(app, ["evaluate", "label-filter"]).exit_code == 2
    assert labeller.calls == []


def test_group_reports_skips_a_group_with_no_cases_and_no_report(tmp_path: Path) -> None:
    records = {r.case_id: r for r in _two_records()}
    reports = group_reports((AGREE, DISAGREE), records, HAIKU, EU_VERTEX, tmp_path)
    assert [r.path for r in reports] == [tmp_path / "label_disagreements.md"]
