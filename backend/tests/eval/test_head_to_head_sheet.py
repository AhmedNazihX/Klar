import random
from datetime import date
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from aiact.cli import app
from aiact.eval import head_to_head_sheet
from aiact.eval.head_to_head import Draw, make_draw, write_draw
from aiact.eval.head_to_head_sheet import (
    CHECKER_URL,
    MEANING_CLASS,
    SHEET_FILE,
    AnsweredBy,
    CheckerMeaning,
    HeadToHeadSheet,
    SheetError,
    check_sheet,
    load_sheet,
    render_template,
    spot_check_ids,
    write_template,
)
from aiact.schemas import RiskClass
from tests.eval.head_to_head_pool import POOL

R = RiskClass
TODAY = date(2026, 10, 20)
DRAW = make_draw(POOL, "a" * 40, seed=7, size=25)
FIRST, SECOND = DRAW.cases[0].case_id, DRAW.cases[1].case_id
HIGH_HEADING = "Your system is a high-risk AI system"
TRANSPARENCY_HEADING = "Transparency obligations apply"
RESULT = f"{HIGH_HEADING}\nYou must register it.\n{TRANSPARENCY_HEADING} under Article 50."
ANSWERS = [{"question": "Is it used in recruitment?", "answer": "Yes"}]


SPOT_IDS = spot_check_ids(DRAW)


def run_entry(case_id: str = FIRST, **fields: object) -> dict[str, object]:
    return {
        "case_id": case_id,
        "date": "2026-10-18",
        "answered_by": "agent",
        "checker_release": "6.5.1",
        "result_text": RESULT,
        "result_headings": [HIGH_HEADING],
        "answers": ANSWERS,
        **fields,
    }


def hand_entry(case_id: str, **fields: object) -> dict[str, object]:
    return run_entry(case_id, answered_by="hand", **fields)


def sheet_with(
    *runs: dict[str, object],
    headings: dict[str, str] | None = None,
    spot_checks: list[dict[str, object]] | None = None,
) -> dict:
    """A sheet: the given runs, every other drawn case pending, and the given spot-checks."""
    given = {run["case_id"] for run in runs}
    pending = [{"case_id": c.case_id} for c in DRAW.cases if c.case_id not in given]
    table = {HIGH_HEADING: "high_risk", TRANSPARENCY_HEADING: "transparency_only"}
    return {
        "headings": table if headings is None else headings,
        "cases": [*runs, *pending],
        "spot_checks": spot_checks or [],
    }


def write_sheet(path: Path, document: dict) -> Path:
    path.write_text(yaml.safe_dump(document, allow_unicode=True), encoding="utf-8")
    return path


def checked(tmp_path: Path, document: dict, draw: Draw = DRAW) -> HeadToHeadSheet:
    sheet = load_sheet(write_sheet(tmp_path / "sheet.yaml", document))
    check_sheet(sheet, draw, TODAY, tmp_path / "head_to_head")
    return sheet


def test_the_meaning_table_is_decision_036s() -> None:
    assert {meaning.value: risk_class for meaning, risk_class in MEANING_CLASS.items()} == {
        "prohibited_practice": RiskClass.PROHIBITED,
        "high_risk": RiskClass.HIGH_RISK,
        "transparency_only": RiskClass.LIMITED_RISK,
        "no_specific_duties": RiskClass.MINIMAL_RISK,
        "act_does_not_apply": RiskClass.OUT_OF_SCOPE,
        "cannot_determine": None,
    }
    assert CHECKER_URL == "https://ai-act-service-desk.ec.europa.eu/en/eu-ai-act-compliance-checker"
    assert SHEET_FILE.name == "head_to_head.yaml"


# --- the template ---------------------------------------------------------------------------------


def test_the_template_lists_every_drawn_case_pending(tmp_path: Path) -> None:
    path = tmp_path / "sheet.yaml"
    assert write_template(DRAW, path) is True
    sheet = load_sheet(path)
    check_sheet(sheet, DRAW, TODAY, tmp_path)
    assert [run.case_id for run in sheet.cases] == [case.case_id for case in DRAW.cases]
    assert [run.case_id for run in sheet.spot_checks] == list(SPOT_IDS)
    assert not any(run.is_run for run in (*sheet.cases, *sheet.spot_checks))
    assert sheet.headings == {}


def test_an_existing_sheet_is_never_overwritten(tmp_path: Path) -> None:
    path = tmp_path / "sheet.yaml"
    path.write_text("the user's runs", encoding="utf-8")
    assert write_template(DRAW, path) is False
    assert path.read_text(encoding="utf-8") == "the user's runs"


def test_the_template_explains_each_field_and_the_meanings() -> None:
    text = render_template(DRAW)
    fields = (
        "date",
        "answered_by",
        "checker_release",
        "result_text",
        "result_headings",
        "answers",
        "uncertain_questions",
        "screenshot",
    )
    for field in fields:
        assert f"#   {field} " in text
        assert f"    {field}: " in text
    assert "# headings:" in text
    assert "spot_checks holds the user's\n# hand runs (answered_by: hand)" in text
    assert "spot-check cases (seed 20261015" in text
    assert "agent (a blind agent, one per case) or hand (the user)" in text
    assert ", ".join(meaning.value for meaning in CheckerMeaning) in text
    assert CHECKER_URL in text


# --- the spot-check cases -------------------------------------------------------------------------


def test_the_spot_check_ids_follow_the_amendments_rule() -> None:
    """Decision 036's amendment, written out: seed 20261015, one choice per class in this order,
    over the sorted ids of the drawn cases of the class."""
    rng = random.Random(20261015)
    order = (R.OUT_OF_SCOPE, R.PROHIBITED, R.HIGH_RISK, R.LIMITED_RISK, R.MINIMAL_RISK)
    expected = tuple(
        rng.choice(sorted(c.case_id for c in DRAW.cases if c.risk_class is risk_class))
        for risk_class in order
    )
    assert expected == SPOT_IDS
    classes = {c.case_id: c.risk_class for c in DRAW.cases}
    assert [classes[case_id] for case_id in SPOT_IDS] == list(order)


def test_the_spot_check_ids_depend_on_the_seed(monkeypatch: pytest.MonkeyPatch) -> None:
    """Another seed picks other cases from this draw, so the test above pins the seed."""
    monkeypatch.setattr(head_to_head_sheet, "SPOT_CHECK_SEED", 1)
    assert spot_check_ids(DRAW) != SPOT_IDS


def test_a_draw_without_a_class_has_no_spot_check() -> None:
    lacking = DRAW.model_copy(
        update={"cases": tuple(c for c in DRAW.cases if c.risk_class is not R.LIMITED_RISK)}
    )
    with pytest.raises(SheetError, match="no drawn case of class limited_risk"):
        spot_check_ids(lacking)


# --- a filled sheet -------------------------------------------------------------------------------


def test_a_complete_run_validates_and_maps_to_its_class(tmp_path: Path) -> None:
    sheet = checked(tmp_path, sheet_with(run_entry()))
    run = sheet.cases[0]
    assert run.is_run and run.date == date(2026, 10, 18)
    assert run.answered_by is AnsweredBy.AGENT and run.checker_release == "6.5.1"
    assert sheet.checker_class(run) is RiskClass.HIGH_RISK


def test_an_uncertain_question_among_the_answers_is_accepted(tmp_path: Path) -> None:
    question = ANSWERS[0]["question"]
    sheet = checked(tmp_path, sheet_with(run_entry(uncertain_questions=[question])))
    assert sheet.cases[0].uncertain_questions == (question,)


@pytest.mark.parametrize(
    ("meanings", "expected"),
    [
        (["high_risk", "transparency_only"], RiskClass.HIGH_RISK),
        (["transparency_only", "no_specific_duties"], RiskClass.LIMITED_RISK),
        (["prohibited_practice", "high_risk"], RiskClass.PROHIBITED),
        (["act_does_not_apply"], RiskClass.OUT_OF_SCOPE),
        (["cannot_determine"], None),
        (["cannot_determine", "no_specific_duties"], RiskClass.MINIMAL_RISK),
        (["no_specific_duties", "transparency_only", "high_risk"], RiskClass.HIGH_RISK),
    ],
)
def test_the_strictest_heading_wins(
    tmp_path: Path, meanings: list[str], expected: RiskClass | None
) -> None:
    headings = {f"Heading {n}": meaning for n, meaning in enumerate(meanings)}
    entry = run_entry(result_text=" ".join(headings), result_headings=list(headings))
    sheet = checked(tmp_path, sheet_with(entry, headings=headings))
    assert sheet.checker_class(sheet.cases[0]) is expected


def test_a_heading_copied_across_a_line_break_still_matches(tmp_path: Path) -> None:
    entry = run_entry(result_text="Your system is a\n  high-risk AI system.")
    checked(tmp_path, sheet_with(entry))


@pytest.mark.parametrize(
    ("entry", "message"),
    [
        ({"case_id": FIRST, "result_text": "Copied"}, "missing date"),
        ({"case_id": FIRST, "answers": ANSWERS}, "missing date"),
        ({"case_id": FIRST, "result_headings": [HIGH_HEADING]}, "missing date"),
        ({"case_id": FIRST, "screenshot": "run.png"}, "missing date"),
        ({"case_id": FIRST, "answered_by": "agent"}, "missing date"),
        ({"case_id": FIRST, "checker_release": "6.5.1"}, "missing date"),
        ({"case_id": FIRST, "uncertain_questions": ["Q"]}, "missing date"),
        (run_entry(answered_by=None), "missing answered_by"),
        (run_entry(checker_release=None), "missing checker_release"),
        (run_entry(checker_release="  "), "checker_release"),
        (run_entry(answered_by="user"), "answered_by"),
        (
            run_entry(uncertain_questions=["Is it used in hiring?"]),
            "uncertain questions not among the answers: \\['Is it used in hiring\\?'\\]",
        ),
        (run_entry(answers=[]), "missing answers"),
        (run_entry(result_text="  "), "missing result_text"),
        (run_entry(result_headings=[]), "missing result_headings"),
        (run_entry(answers=[{"question": "Q", "answer": " "}]), "answer"),
        (run_entry(date="2026-02-30"), "date"),
        (run_entry(extra="x"), "extra"),
    ],
)
def test_an_incomplete_or_malformed_run_is_refused(
    tmp_path: Path, entry: dict[str, object], message: str
) -> None:
    with pytest.raises(SheetError, match=message):
        load_sheet(write_sheet(tmp_path / "sheet.yaml", sheet_with(entry)))


def test_a_heading_meaning_outside_the_table_is_a_bad_class(tmp_path: Path) -> None:
    document = sheet_with(run_entry(), headings={HIGH_HEADING: "high"})
    with pytest.raises(SheetError, match="headings"):
        load_sheet(write_sheet(tmp_path / "sheet.yaml", document))


@pytest.mark.parametrize("twin", [f" {HIGH_HEADING}  ", HIGH_HEADING.replace(" ", "  ", 1)])
def test_headings_differing_only_in_whitespace_are_refused(tmp_path: Path, twin: str) -> None:
    """Stripped, they would merge into one row silently, keeping one of the two meanings."""
    document = sheet_with(
        run_entry(), headings={HIGH_HEADING: "high_risk", twin: "no_specific_duties"}
    )
    with pytest.raises(SheetError, match="headings differing only in whitespace"):
        load_sheet(write_sheet(tmp_path / "sheet.yaml", document))


def test_a_repeated_key_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "sheet.yaml"
    path.write_text(f"headings: {{}}\ncases:\n  - case_id: {FIRST}\n    case_id: {SECOND}\n")
    with pytest.raises(SheetError, match="duplicate key"):
        load_sheet(path)


def test_a_missing_sheet_is_reported(tmp_path: Path) -> None:
    with pytest.raises(SheetError, match="can't read the sheet"):
        load_sheet(tmp_path / "absent.yaml")


@pytest.mark.parametrize(
    ("document", "message"),
    [
        (sheet_with(run_entry("cb-unknown")), "cb-unknown: unknown case id"),
        (
            {"headings": {}, "cases": [{"case_id": c.case_id} for c in DRAW.cases[1:]]},
            f"{FIRST}: drawn but missing",
        ),
        (sheet_with(run_entry(), {"case_id": FIRST}), f"{FIRST}: listed 2 times"),
        (sheet_with(run_entry(date="2026-10-21")), "date 2026-10-21 is in the future"),
        (sheet_with(run_entry(), headings={}), "has no row in headings"),
        (
            sheet_with(run_entry(result_text="It is high risk.")),
            "isn't in result_text verbatim",
        ),
        (
            sheet_with(run_entry(result_text=RESULT.upper())),
            "isn't in result_text verbatim",
        ),
        (sheet_with(run_entry(screenshot="../secret.png")), "isn't a plain image or PDF name"),
        (sheet_with(run_entry(screenshot="run.png")), "run.png isn't in"),
    ],
)
def test_a_sheet_that_doesnt_fit_the_draw_is_refused(
    tmp_path: Path, document: dict, message: str
) -> None:
    with pytest.raises(SheetError, match=message):
        checked(tmp_path, document)


def test_a_run_dated_today_is_accepted(tmp_path: Path) -> None:
    checked(tmp_path, sheet_with(run_entry(date=TODAY.isoformat())))


def test_every_problem_is_listed_at_once(tmp_path: Path) -> None:
    document = sheet_with(run_entry(date="2026-10-21", screenshot="run.png"), headings={})
    with pytest.raises(SheetError) as raised:
        checked(tmp_path, document)
    assert str(raised.value).count(";") == 2


def test_a_screenshot_next_to_the_sheet_is_accepted(tmp_path: Path) -> None:
    (tmp_path / "head_to_head").mkdir()
    (tmp_path / "head_to_head" / "run.png").write_bytes(b"png")
    checked(tmp_path, sheet_with(run_entry(screenshot="run.png")))


def test_an_unmapped_heading_cant_be_scored(tmp_path: Path) -> None:
    sheet = load_sheet(write_sheet(tmp_path / "s.yaml", sheet_with(run_entry(), headings={})))
    with pytest.raises(SheetError, match="no headings row"):
        sheet.checker_class(sheet.cases[0])


# --- the spot-checks ------------------------------------------------------------------------------


def test_hand_spot_checks_of_the_spot_check_cases_are_accepted(tmp_path: Path) -> None:
    spot_checks = [hand_entry(SPOT_IDS[0]), {"case_id": SPOT_IDS[1]}]
    sheet = checked(tmp_path, sheet_with(spot_checks=spot_checks))
    assert [run.answered_by for run in sheet.spot_checks] == [AnsweredBy.HAND, None]
    assert head_to_head_sheet.spot_checks_run(sheet) == 1


NOT_SPOT = next(c.case_id for c in DRAW.cases if c.case_id not in SPOT_IDS)


@pytest.mark.parametrize(
    ("spot_checks", "message"),
    [
        ([hand_entry(NOT_SPOT)], f"spot check {NOT_SPOT}: not one of the 5 spot-check cases"),
        ([{"case_id": NOT_SPOT}], f"spot check {NOT_SPOT}: not one of the 5 spot-check cases"),
        ([hand_entry("cb-unknown")], "spot check cb-unknown: unknown case id"),
        (
            [run_entry(SPOT_IDS[0])],
            f"spot check {SPOT_IDS[0]}: answered_by must be hand, not agent",
        ),
        (
            [hand_entry(SPOT_IDS[0]), {"case_id": SPOT_IDS[0]}],
            f"spot check {SPOT_IDS[0]}: listed 2 times",
        ),
        (
            [hand_entry(SPOT_IDS[0], date="2026-10-21")],
            f"spot check {SPOT_IDS[0]}: date 2026-10-21 is in the future",
        ),
        (
            [hand_entry(SPOT_IDS[0], result_headings=["Unknown heading"], result_text="x")],
            f"spot check {SPOT_IDS[0]}: heading 'Unknown heading' has no row",
        ),
    ],
)
def test_a_wrong_spot_check_is_refused(
    tmp_path: Path, spot_checks: list[dict[str, object]], message: str
) -> None:
    with pytest.raises(SheetError, match=message):
        checked(tmp_path, sheet_with(spot_checks=spot_checks))


def test_a_spot_check_run_needs_the_same_fields_as_a_case_run(tmp_path: Path) -> None:
    document = sheet_with(spot_checks=[hand_entry(SPOT_IDS[0], checker_release=None)])
    with pytest.raises(SheetError, match="missing checker_release"):
        load_sheet(write_sheet(tmp_path / "sheet.yaml", document))


# --- the check command ----------------------------------------------------------------------------


def _paths(tmp_path: Path, document: dict) -> list[str]:
    draw_path = tmp_path / "draw.json"
    write_draw(DRAW, draw_path)
    sheet = write_sheet(tmp_path / "sheet.yaml", document)
    return ["--draw-file", str(draw_path), "--sheet", str(sheet)]


def test_the_check_command_counts_the_runs(tmp_path: Path) -> None:
    """The command checks dates against the real today, so the run is dated well before it."""
    paths = _paths(tmp_path, sheet_with(run_entry(date="2026-01-05")))
    result = CliRunner().invoke(app, ["evaluate", "head-to-head", "check", *paths])
    complete = CliRunner().invoke(app, ["evaluate", "head-to-head", "check", *paths, "--complete"])
    assert result.exit_code == 0, result.output
    assert "Valid: 1 of 25 cases run, 0 of 5 spot-checks run" in result.output
    assert complete.exit_code == 1
    assert "some drawn cases aren't run yet" in complete.output
    assert "some spot-checks aren't run yet" in complete.output


EARLY = "2026-01-05"
"""A date well before the real today, which the command checks dates against."""
ALL_CASES_RUN = [run_entry(c.case_id, date=EARLY) for c in DRAW.cases]


def test_complete_needs_every_spot_check_run(tmp_path: Path) -> None:
    spot_checks = [hand_entry(case_id, date=EARLY) for case_id in SPOT_IDS[:4]]
    paths = _paths(tmp_path, sheet_with(*ALL_CASES_RUN, spot_checks=spot_checks))
    result = CliRunner().invoke(app, ["evaluate", "head-to-head", "check", *paths, "--complete"])
    assert result.exit_code == 1
    assert "Valid: 25 of 25 cases run, 4 of 5 spot-checks run" in result.output
    assert "some spot-checks aren't run yet" in result.output
    assert "some drawn cases aren't run yet" not in result.output


def test_complete_passes_with_every_case_and_spot_check_run(tmp_path: Path) -> None:
    spot_checks = [hand_entry(case_id, date=EARLY) for case_id in SPOT_IDS]
    paths = _paths(tmp_path, sheet_with(*ALL_CASES_RUN, spot_checks=spot_checks))
    result = CliRunner().invoke(app, ["evaluate", "head-to-head", "check", *paths, "--complete"])
    assert result.exit_code == 0, result.output
    assert "Valid: 25 of 25 cases run, 5 of 5 spot-checks run" in result.output


def test_the_check_command_reports_the_problems(tmp_path: Path) -> None:
    paths = _paths(tmp_path, sheet_with(run_entry("cb-unknown")))
    result = CliRunner().invoke(app, ["evaluate", "head-to-head", "check", *paths])
    assert result.exit_code == 1
    assert "cb-unknown: unknown case id" in result.output
