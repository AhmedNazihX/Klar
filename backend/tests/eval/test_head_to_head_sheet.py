from datetime import date
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from aiact.cli import app
from aiact.eval.head_to_head import Draw, make_draw, write_draw
from aiact.eval.head_to_head_sheet import (
    CHECKER_URL,
    MEANING_CLASS,
    SHEET_FILE,
    CheckerMeaning,
    HeadToHeadSheet,
    SheetError,
    check_sheet,
    load_sheet,
    render_template,
    write_template,
)
from aiact.schemas import RiskClass
from tests.eval.head_to_head_pool import POOL

TODAY = date(2026, 10, 20)
DRAW = make_draw(POOL, "a" * 40, seed=7, size=25)
FIRST, SECOND = DRAW.cases[0].case_id, DRAW.cases[1].case_id
HIGH_HEADING = "Your system is a high-risk AI system"
TRANSPARENCY_HEADING = "Transparency obligations apply"
RESULT = f"{HIGH_HEADING}\nYou must register it.\n{TRANSPARENCY_HEADING} under Article 50."
ANSWERS = [{"question": "Is it used in recruitment?", "answer": "Yes"}]


def run_entry(case_id: str = FIRST, **fields: object) -> dict[str, object]:
    return {
        "case_id": case_id,
        "date": "2026-10-18",
        "result_text": RESULT,
        "result_headings": [HIGH_HEADING],
        "answers": ANSWERS,
        **fields,
    }


def sheet_with(*runs: dict[str, object], headings: dict[str, str] | None = None) -> dict:
    """A sheet: the given runs, every other drawn case pending."""
    given = {run["case_id"] for run in runs}
    pending = [{"case_id": c.case_id} for c in DRAW.cases if c.case_id not in given]
    table = {HIGH_HEADING: "high_risk", TRANSPARENCY_HEADING: "transparency_only"}
    return {"headings": table if headings is None else headings, "cases": [*runs, *pending]}


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
    assert not any(run.is_run for run in sheet.cases)
    assert sheet.headings == {}


def test_an_existing_sheet_is_never_overwritten(tmp_path: Path) -> None:
    path = tmp_path / "sheet.yaml"
    path.write_text("the user's runs", encoding="utf-8")
    assert write_template(DRAW, path) is False
    assert path.read_text(encoding="utf-8") == "the user's runs"


def test_the_template_explains_each_field_and_the_meanings() -> None:
    text = render_template(DRAW)
    for field in ("date", "result_text", "result_headings", "answers", "screenshot", "headings"):
        assert f"#   {field}" in text or f"# {field}:" in text
    assert ", ".join(meaning.value for meaning in CheckerMeaning) in text
    assert CHECKER_URL in text


# --- a filled sheet -------------------------------------------------------------------------------


def test_a_complete_run_validates_and_maps_to_its_class(tmp_path: Path) -> None:
    sheet = checked(tmp_path, sheet_with(run_entry()))
    run = sheet.cases[0]
    assert run.is_run and run.date == date(2026, 10, 18)
    assert sheet.checker_class(run) is RiskClass.HIGH_RISK


@pytest.mark.parametrize(
    ("meanings", "expected"),
    [
        (["high_risk", "transparency_only"], RiskClass.HIGH_RISK),
        (["transparency_only", "no_specific_duties"], RiskClass.LIMITED_RISK),
        (["prohibited_practice", "high_risk"], RiskClass.PROHIBITED),
        (["act_does_not_apply"], RiskClass.OUT_OF_SCOPE),
        (["cannot_determine"], None),
        (["cannot_determine", "no_specific_duties"], RiskClass.MINIMAL_RISK),
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
        (sheet_with(run_entry(screenshot="../secret.png")), "isn't a plain image or PDF name"),
        (sheet_with(run_entry(screenshot="run.png")), "run.png isn't in"),
    ],
)
def test_a_sheet_that_doesnt_fit_the_draw_is_refused(
    tmp_path: Path, document: dict, message: str
) -> None:
    with pytest.raises(SheetError, match=message):
        checked(tmp_path, document)


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
    assert "Valid: 1 of 25 cases run" in result.output
    assert complete.exit_code == 1
    assert "some drawn cases aren't run yet" in complete.output


def test_the_check_command_reports_the_problems(tmp_path: Path) -> None:
    paths = _paths(tmp_path, sheet_with(run_entry("cb-unknown")))
    result = CliRunner().invoke(app, ["evaluate", "head-to-head", "check", *paths])
    assert result.exit_code == 1
    assert "cb-unknown: unknown case id" in result.output
