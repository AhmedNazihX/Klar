import json
from datetime import UTC, date, datetime
from pathlib import Path
from uuid import UUID

import psycopg
import pytest
from typer.testing import CliRunner

from aiact.cli import app
from aiact.eval import head_to_head_report, records
from aiact.eval.cases import AppliedAILabel, BenchmarkCase, CaseSet
from aiact.eval.head_to_head import DRAW_FILE, DrawStep, load_draw, make_draw, write_draw
from aiact.eval.head_to_head_report import (
    ENGINE_FILE,
    REPORT_FILE,
    EngineColumn,
    EngineRunError,
    column_scores,
    current_cases,
    load_engine_file,
    render_report,
    write_engine_file,
)
from aiact.eval.head_to_head_sheet import (
    SHEET_FILE,
    CheckerAnswer,
    CheckerRun,
    HeadToHeadSheet,
    check_sheet,
    load_sheet,
    spot_check_ids,
)
from aiact.eval.metrics import Rate, class_match, class_too_low
from aiact.eval.report import RunInfo
from aiact.schemas import Language, Status
from tests.eval.head_to_head_pool import POOL, R, make_case

DRAW = make_draw(POOL, "b" * 40, seed=7, size=25)
CASES = {case.id: case for case in POOL}
DRAWN = {case.case_id: CASES[case.case_id] for case in DRAW.cases}
HIGH = next(c.case_id for c in DRAW.cases if c.risk_class is R.HIGH_RISK)
PROHIBITED = next(c.case_id for c in DRAW.cases if c.risk_class is R.PROHIBITED)
HIGH_HEADING = "High-risk AI system"
UNSURE_HEADING = "We could not determine"
HEADINGS = {HIGH_HEADING: "high_risk", UNSURE_HEADING: "cannot_determine"}


def run(case_id: str, heading: str, **fields: object) -> CheckerRun:
    return CheckerRun.model_validate(
        {
            "case_id": case_id,
            "date": "2026-10-18",
            "answered_by": "agent",
            "checker_release": "6.5.1",
            "result_text": f"{heading}. More text.",
            "result_headings": [heading],
            "answers": [{"question": "Who uses it?", "answer": "A bank"}],
            **fields,
        }
    )


def sheet(*runs: CheckerRun, spot_checks: tuple[CheckerRun, ...] = ()) -> HeadToHeadSheet:
    given = {r.case_id for r in runs}
    pending = [CheckerRun(case_id=c.case_id) for c in DRAW.cases if c.case_id not in given]
    return HeadToHeadSheet.model_validate(
        {"headings": HEADINGS, "cases": [*runs, *pending], "spot_checks": spot_checks}
    )


FILLED = sheet(run(HIGH, HIGH_HEADING), run(PROHIBITED, UNSURE_HEADING))


# --- the scorers shared with the engine -----------------------------------------------------------


@pytest.mark.parametrize(
    ("label", "answer", "expected"),
    [
        (R.HIGH_RISK, R.HIGH_RISK, True),
        (R.HIGH_RISK, R.LIMITED_RISK, False),
        (R.HIGH_RISK, None, False),
        (R.OUT_OF_SCOPE, R.OUT_OF_SCOPE, True),
    ],
)
def test_class_match_scores_a_bare_class(label: R, answer: R | None, expected: bool) -> None:
    assert class_match(make_case("own-x", label), answer) is expected


def test_class_match_skips_ambiguous_and_thin_labels_and_refuses_appliedai() -> None:
    ambiguous = make_case("own-x", R.HIGH_RISK, status=Status.LEGALLY_AMBIGUOUS)
    thin = make_case("own-t", None, status=Status.NEEDS_MORE_INFORMATION)
    appliedai = BenchmarkCase(
        id="ai-1",
        set_name=CaseSet.APPLIEDAI,
        language=Language.EN,
        description="A made-up system.",
        label=AppliedAILabel.HIGH,
    )
    assert class_match(ambiguous, R.HIGH_RISK) is None
    assert class_match(thin, R.HIGH_RISK) is None
    with pytest.raises(ValueError, match="appliedAI"):
        class_match(appliedai, R.HIGH_RISK)


@pytest.mark.parametrize(
    ("label", "answer", "expected"),
    [
        (R.HIGH_RISK, R.MINIMAL_RISK, True),
        (R.PROHIBITED, R.HIGH_RISK, True),
        (R.HIGH_RISK, R.PROHIBITED, False),
        (R.HIGH_RISK, R.HIGH_RISK, False),
        (R.HIGH_RISK, None, None),
        (R.MINIMAL_RISK, R.OUT_OF_SCOPE, None),
    ],
)
def test_class_too_low_is_the_false_low_risk_rule(
    label: R, answer: R | None, expected: bool | None
) -> None:
    assert class_too_low(make_case("own-x", label), answer) is expected


def test_a_column_is_scored_over_the_cases_it_answered() -> None:
    cases = [
        make_case("own-high", R.HIGH_RISK),
        make_case("own-min", R.MINIMAL_RISK),
        make_case("own-pro", R.PROHIBITED),
        make_case("own-unasked", R.HIGH_RISK),
    ]
    classes = {"own-high": R.HIGH_RISK, "own-min": None, "own-pro": R.HIGH_RISK}
    scores = column_scores(cases, classes)
    assert scores.answered == 3
    assert scores.risk_class_accuracy == Rate(hits=1, total=3)
    assert scores.false_low_risk == Rate(hits=1, total=2)


# --- the report -----------------------------------------------------------------------------------


def _row(text: str, case_id: str) -> str:
    return next(line for line in text.splitlines() if line.startswith(f"| `{case_id}` |"))


def test_the_report_scores_the_checker_and_leaves_the_engine_empty() -> None:
    text = render_report(FILLED, DRAW, DRAWN)
    assert "| Commission checker | 2 of 25 | 50.0% (1/2) | 0.0% (0/1) |" in text
    assert "| Engine | not filled yet (V10b) | | |" in text
    assert _row(text, HIGH).endswith(
        f"| high_risk | {HIGH_HEADING} | high_risk | yes |  |  | 2026-10-18 |"
    )
    assert _row(text, PROHIBITED).endswith(
        f"| prohibited | {UNSURE_HEADING} | none (can't determine) | no |  |  | 2026-10-18 |"
    )
    pending = next(c.case_id for c in DRAW.cases if c.case_id not in (HIGH, PROHIBITED))
    assert _row(text, pending).endswith("|  |  |  |  |  | not run yet |")


def test_the_report_carries_the_method_credit_and_notice() -> None:
    text = render_report(FILLED, DRAW, DRAWN)
    assert text.startswith("# Head-to-head: the Commission's AI Act Service Desk checker\n")
    assert "seed 7" in text and "`labels-v1` labels (`bbbbbbbbbbbb`)" in text
    assert "https://ai-act-service-desk.ec.europa.eu/en/eu-ai-act-compliance-checker" in text
    assert "Own cases are development cases (decision 018)." in text
    assert "Classifications are guidance, not legal advice." in text
    assert f"| {HIGH_HEADING} | high_risk | high_risk |" in text
    assert f"| {UNSURE_HEADING} | cannot_determine | none (can't determine) |" in text


def test_the_runs_quote_the_result_and_answers_verbatim() -> None:
    result_text = "Line one | with a pipe\n```\ncode\n```"
    filled = sheet(
        run(
            HIGH,
            HIGH_HEADING,
            result_text=f"{HIGH_HEADING}\n{result_text}",
            answers=[CheckerAnswer(question="Is it | used?", answer="Yes,\nalways")],
            screenshot="high.png",
        )
    )
    text = render_report(filled, DRAW, DRAWN)
    section = text.split(f"### `{HIGH}`", 1)[1].split("### ", 1)[0]
    assert f"````text\n{HIGH_HEADING}\n{result_text}\n````" in section
    assert "| Is it \\| used? | Yes, always |  |" in section
    assert "- Screenshot: [high.png](head_to_head/high.png)" in section
    assert "- Run on: 2026-10-18" in section
    assert "- Answered by: agent\n- Checker question release: 6.5.1" in section
    pending = next(c.case_id for c in DRAW.cases if c.case_id != HIGH)
    assert f"### `{pending}`\n\nNot run yet." in text


def test_an_uncertain_question_is_marked_in_its_runs_answers() -> None:
    filled = sheet(run(HIGH, HIGH_HEADING, uncertain_questions=["Who uses it?"]))
    section = render_report(filled, DRAW, DRAWN).split(f"### `{HIGH}`", 1)[1]
    assert "| Question | Answer | Uncertain |" in section
    assert "| Who uses it? | A bank | yes |" in section


def hand(case_id: str, heading: str, **fields: object) -> CheckerRun:
    return run(case_id, heading, answered_by="hand", **fields)


SPOT = spot_check_ids(DRAW)
SAME, DIFFERENT, UNRUN = SPOT[0], SPOT[1], SPOT[2]


def test_the_intro_says_who_answered_and_which_release_from_the_sheet() -> None:
    filled = sheet(
        run(HIGH, HIGH_HEADING),
        run(PROHIBITED, UNSURE_HEADING),
        spot_checks=(hand(SAME, HIGH_HEADING, checker_release="6.5.2"),),
    )
    text = render_report(filled, DRAW, DRAWN)
    assert (
        "Answered (decision 036, amendment 2026-10-14): 2 of 25 cases by an agent that saw only "
        "the case's description (one fresh agent per case), scored; 1 of 5 spot-checks by hand "
        "(below), not scored. Checker question release seen: 6.5.1, 6.5.2." in text
    )
    assert "answered by hand from its description" not in text
    empty = HeadToHeadSheet(cases=tuple(CheckerRun(case_id=c.case_id) for c in DRAW.cases))
    assert "0 of 25 cases by an agent" in render_report(empty, DRAW, DRAWN)
    assert "; 0 of 5 spot-checks by hand" in render_report(empty, DRAW, DRAWN)
    assert "Checker question release seen: none yet." in render_report(empty, DRAW, DRAWN)


def test_the_spot_check_section_compares_the_classes_and_the_answers() -> None:
    hand_answers = [
        {"question": "Who uses it?", "answer": "A school"},
        {"question": "Is it biometric?", "answer": "No"},
    ]
    filled = sheet(
        run(SAME, HIGH_HEADING),
        run(DIFFERENT, HIGH_HEADING),
        run(UNRUN, HIGH_HEADING),
        spot_checks=(
            hand(SAME, HIGH_HEADING, answers=hand_answers),
            hand(DIFFERENT, UNSURE_HEADING),
        ),
    )
    text = render_report(filled, DRAW, DRAWN)
    section = text.split("## Spot-check\n", 1)[1].split("## Limitations", 1)[0]
    label = {c.case_id: c.risk_class.value for c in DRAW.cases}
    assert "picked by seed 20261015" in section
    assert "1 of 2 agree on the class." in section
    assert f"| `{SAME}` | {label[SAME]} | high_risk | high_risk | yes |" in section
    assert (
        f"| `{DIFFERENT}` | {label[DIFFERENT]} | high_risk | none (can't determine) | no |"
        in section
    )
    assert f"| `{UNRUN}` | {label[UNRUN]} | high_risk | not run yet |  |" in section
    same = section.split(f"### Spot-check `{SAME}`", 1)[1].split("### Spot-check", 1)[0]
    assert "| Who uses it? | A bank | A school |" in same
    assert "| Is it biometric? | (not asked) | No |" in same
    assert "#### The hand run" in same and "- Answered by: hand" in same
    different = section.split(f"### Spot-check `{DIFFERENT}`", 1)[1].split("### Spot", 1)[0]
    assert "Every answer is the same." in different
    unrun = section.split(f"### Spot-check `{UNRUN}`", 1)[1]
    assert unrun.startswith("\n\nNot compared yet: both runs are needed.")
    assert section.count("### Spot-check `") == 5


ENGINE_RUN = RunInfo(
    id=UUID("00000000-0000-4000-8000-000000000001"),
    benchmark="head_to_head",
    git_sha="0123456789abcdef0123456789abcdef01234567",
    started_at=datetime(2026, 10, 15, 9, 30, tzinfo=UTC),
    model="openai/gpt-6-luna",
    classifier="engine",
    exclude_mode="heldout",
    status="completed",
)


def test_an_engine_column_fills_the_engine_cells_and_names_its_run() -> None:
    engine = EngineColumn(run=ENGINE_RUN, classes={HIGH: R.MINIMAL_RISK})
    text = render_report(FILLED, DRAW, DRAWN, engine=engine)
    assert "| Engine | 1 of 25 | 0.0% (0/1) | 100.0% (1/1) |" in text
    assert "not filled yet" not in text
    assert _row(text, HIGH).endswith("| high_risk | yes | minimal_risk | no | 2026-10-18 |")
    assert (
        "Engine: stored run `00000000-0000-4000-8000-000000000001` (classifier `engine`, model "
        "`openai/gpt-6-luna`, exclude mode heldout, git `0123456789ab`, started 2026-10-15), "
        "scored against the same current labels.\n" in text
    )


def test_the_engine_line_counts_the_cases_that_failed_in_the_run() -> None:
    engine = EngineColumn(run=ENGINE_RUN, classes={HIGH: R.HIGH_RISK}, failed=2)
    text = render_report(FILLED, DRAW, DRAWN, engine=engine)
    assert (
        "scored against the same current labels; drawn cases whose run failed, left out of its "
        "score: 2." in text
    )


def test_each_column_is_also_scored_per_set() -> None:
    """HIGH is a Commission case and PROHIBITED an own one: each set's rows count only its own."""
    assert (DRAWN[HIGH].set_name, DRAWN[PROHIBITED].set_name) == (CaseSet.COMMISSION_B, CaseSet.OWN)
    engine = EngineColumn(run=ENGINE_RUN, classes={HIGH: R.MINIMAL_RISK})
    text = render_report(FILLED, DRAW, DRAWN, engine=engine)
    scores = text.split("## Scores\n", 1)[1].split("## Cases", 1)[0]
    assert scores.splitlines() == [
        "",
        "| Column | Cases answered | Risk-class accuracy | False-low-risk rate |",
        "| --- | ---: | ---: | ---: |",
        "| Commission checker | 2 of 25 | 50.0% (1/2) | 0.0% (0/1) |",
        "| Commission checker, commission_b cases | 1 of 6 | 100.0% (1/1) | 0.0% (0/1) |",
        "| Commission checker, own cases | 1 of 19 | 0.0% (0/1) | n/a (0/0) |",
        "| Engine | 1 of 25 | 0.0% (0/1) | 100.0% (1/1) |",
        "| Engine, commission_b cases | 1 of 6 | 0.0% (0/1) | 100.0% (1/1) |",
        "| Engine, own cases | 0 of 19 | n/a (0/0) | n/a (0/0) |",
        "",
    ]


def test_a_label_changed_since_the_draw_shows_both() -> None:
    changed = {**DRAWN, HIGH: make_case(HIGH, R.MINIMAL_RISK)}
    text = render_report(FILLED, DRAW, changed)
    assert "| minimal_risk (at draw: high_risk) |" in _row(text, HIGH)


def test_a_date_dependent_label_is_listed_as_a_limitation() -> None:
    dated = DRAWN[PROHIBITED].model_copy(update={"as_of": date(2026, 12, 15)})
    text = render_report(FILLED, DRAW, {**DRAWN, PROHIBITED: dated})
    assert f"`{PROHIBITED}` (judged on 2026-12-15)" in text
    assert "judged on" not in render_report(FILLED, DRAW, DRAWN)


def test_the_roles_cases_are_named_as_a_limitation_of_a_class_only_score() -> None:
    roles = [f"`{c.case_id}`" for c in DRAW.cases if DrawStep.ROLES in c.steps]
    limitations = render_report(FILLED, DRAW, DRAWN).split("## Limitations", 1)[1]
    assert roles
    assert f"- The roles step is in the draw ({', '.join(roles)}), but a class-only" in limitations


def test_the_answerers_reading_on_borderline_descriptions_is_a_limitation() -> None:
    limitations = render_report(FILLED, DRAW, DRAWN).split("## Limitations", 1)[1]
    assert (
        "- On borderline descriptions the checker's class turns on how the answerer reads "
        '"is it an AI system?" and "does it interact with people?" (decision 036, runs and '
        "spot-check outcome).\n" in limitations
    )


def test_an_empty_headings_table_says_what_to_add() -> None:
    empty = HeadToHeadSheet(cases=tuple(CheckerRun(case_id=c.case_id) for c in DRAW.cases))
    assert "| (none yet: add the first case's headings) | | |" in render_report(empty, DRAW, DRAWN)


def test_the_current_cases_must_still_hold_every_drawn_case(tmp_path: Path) -> None:
    for case_set in ("own", "commission_b"):
        (tmp_path / case_set).mkdir()
    (tmp_path / "own" / "a.yaml").write_text(
        f"id: {HIGH}\nset_name: own\nlanguage: en\ndescription: x\n"
        'label: {risk_class: high_risk}\nlabel_citation: ["art:6:2"]\n',
        encoding="utf-8",
    )
    with pytest.raises(ValueError) as raised:
        current_cases(DRAW, tmp_path)
    assert str(raised.value) == "24 drawn cases are no longer in eval/cases"
    assert not any(case.case_id in str(raised.value) for case in DRAW.cases)


# --- the render command ---------------------------------------------------------------------------


def test_the_render_command_writes_the_report(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(head_to_head_report, "current_cases", lambda draw: DRAWN)
    arguments, output = write_sheet_files(tmp_path), tmp_path / "r.md"
    result = CliRunner().invoke(
        app, ["evaluate", "head-to-head", "render", *arguments, "--output", str(output)]
    )
    assert result.exit_code == 0, result.output
    expected = render_report(load_sheet(tmp_path / "s.yaml"), DRAW, DRAWN)
    assert output.read_text(encoding="utf-8") == expected


def test_the_render_command_refuses_a_sheet_that_doesnt_fit(tmp_path: Path) -> None:
    draw_path, sheet_path, output = tmp_path / "d.json", tmp_path / "s.yaml", tmp_path / "r.md"
    write_draw(DRAW, draw_path)
    sheet_path.write_text("headings: {}\ncases:\n  - case_id: cb-unknown\n", encoding="utf-8")
    arguments = ["--draw-file", str(draw_path), "--sheet", str(sheet_path)]
    result = CliRunner().invoke(
        app, ["evaluate", "head-to-head", "render", *arguments, "--output", str(output)]
    )
    assert result.exit_code == 1
    assert "cb-unknown: unknown case id" in result.output
    assert not output.exists()


def write_sheet_files(tmp_path: Path) -> list[str]:
    draw_path, sheet_path = tmp_path / "d.json", tmp_path / "s.yaml"
    write_draw(DRAW, draw_path)
    sheet_path.write_text(
        "headings: {}\ncases:\n" + "".join(f"  - case_id: {c.case_id}\n" for c in DRAW.cases),
        encoding="utf-8",
    )
    engine_path = tmp_path / "e.json"
    return [
        *("--draw-file", str(draw_path), "--sheet", str(sheet_path)),
        *("--engine-file", str(engine_path)),
    ]


SECRET_URL = "postgresql://postgres:hunter2@db.example:5432/postgres"
RUN_ID = "00000000-0000-4000-8000-000000000002"


def test_render_with_a_run_id_reports_a_database_error_without_the_url(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def connect() -> object:
        raise psycopg.OperationalError(f"could not connect to {SECRET_URL}")

    monkeypatch.setattr(head_to_head_report, "current_cases", lambda draw: DRAWN)
    monkeypatch.setattr(records, "connect", connect)
    output = tmp_path / "r.md"
    result = CliRunner().invoke(
        app,
        [
            *("evaluate", "head-to-head", "render", *write_sheet_files(tmp_path)),
            *("--output", str(output), "--run-id", RUN_ID),
        ],
    )
    assert result.exit_code == 1
    assert "Error: database error (OperationalError); check DATABASE_URL" in result.stderr
    assert "hunter2" not in result.output
    assert not output.exists()


@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        ((), "give either --set or --cases-from-draw"),
        (("--set", "own", "--cases-from-draw"), "give either --set or --cases-from-draw"),
        (("--cases-from-draw", "--subset", "5"), "--cases-from-draw runs every drawn case"),
    ],
)
def test_a_run_needs_exactly_one_case_source_and_the_whole_draw(
    arguments: tuple[str, ...], message: str
) -> None:
    result = CliRunner().invoke(
        app, ["evaluate", "run", "--classifier", "dummy", "--exclude-mode", "all", *arguments]
    )
    assert result.exit_code == 2
    assert f"Error: {message}" in result.stderr


# --- the engine column's committed copy -----------------------------------------------------------


def test_the_engine_file_round_trips_with_failed_cases(tmp_path: Path) -> None:
    classes = {c.case_id: R.HIGH_RISK for c in DRAW.cases if c.case_id != PROHIBITED}
    engine = EngineColumn(run=ENGINE_RUN, classes={**classes, HIGH: None}, failed=1)
    path = tmp_path / "e.json"
    write_engine_file(engine, DRAW, path)
    loaded = load_engine_file(path, DRAW)
    assert loaded == engine
    assert render_report(FILLED, DRAW, DRAWN, loaded) == render_report(FILLED, DRAW, DRAWN, engine)


def test_render_without_a_run_id_keeps_the_engine_column_from_the_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(head_to_head_report, "current_cases", lambda draw: DRAWN)
    engine = EngineColumn(run=ENGINE_RUN, classes={c.case_id: R.HIGH_RISK for c in DRAW.cases})
    write_engine_file(engine, DRAW, tmp_path / "e.json")
    arguments, output = write_sheet_files(tmp_path), tmp_path / "r.md"
    result = CliRunner().invoke(
        app, ["evaluate", "head-to-head", "render", *arguments, "--output", str(output)]
    )
    assert result.exit_code == 0, result.output
    text = output.read_text(encoding="utf-8")
    assert "Engine: stored run `00000000-0000-4000-8000-000000000001`" in text
    assert "| Engine | 25 of 25 |" in text
    assert text == render_report(load_sheet(tmp_path / "s.yaml"), DRAW, DRAWN, engine)


def _engine_json(classes: dict[str, str], failed: list[str] | None = None) -> str:
    return json.dumps(
        {
            "run_id": str(ENGINE_RUN.id),
            "classifier": "engine",
            "model": "openai/gpt-6-luna",
            "exclude_mode": "heldout",
            "git_sha": ENGINE_RUN.git_sha,
            "started_at": "2026-10-15T09:30:00Z",
            "classes": classes,
            "failed": failed or [],
        }
    )


DRAWN_IDS = [c.case_id for c in DRAW.cases]


@pytest.mark.parametrize(
    ("classes", "failed", "message"),
    [
        (DRAWN_IDS[1:], [], "holds 24 of the 25 drawn cases, 0 other cases and 0 repeats"),
        ([*DRAWN_IDS, "cb-other"], [], "holds 25 of the 25 drawn cases, 1 other cases and 0"),
        (DRAWN_IDS, DRAWN_IDS[:1], "holds 25 of the 25 drawn cases, 0 other cases and 1 repeats"),
    ],
)
def test_an_engine_file_that_isnt_exactly_the_draw_is_refused(
    tmp_path: Path, classes: list[str], failed: list[str], message: str
) -> None:
    path = tmp_path / "e.json"
    path.write_text(_engine_json(dict.fromkeys(classes, "high_risk"), failed), encoding="utf-8")
    with pytest.raises(EngineRunError) as raised:
        load_engine_file(path, DRAW)
    assert message in str(raised.value)
    assert not any(case_id in str(raised.value) for case_id in DRAWN_IDS)


def test_an_engine_file_off_the_schema_is_refused_without_its_content(tmp_path: Path) -> None:
    path = tmp_path / "e.json"
    path.write_text(_engine_json(dict.fromkeys(DRAWN_IDS, "very_risky")), encoding="utf-8")
    with pytest.raises(EngineRunError) as raised:
        load_engine_file(path, DRAW)
    assert "not a valid engine column (25 errors)" in str(raised.value)
    assert "very_risky" not in str(raised.value)
    assert not any(case_id in str(raised.value) for case_id in DRAWN_IDS)


def test_render_refuses_an_engine_file_that_isnt_the_draw(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(head_to_head_report, "current_cases", lambda draw: DRAWN)
    arguments, output = write_sheet_files(tmp_path), tmp_path / "r.md"
    (tmp_path / "e.json").write_text(
        _engine_json(dict.fromkeys(DRAWN_IDS[1:], "high_risk")), encoding="utf-8"
    )
    result = CliRunner().invoke(
        app, ["evaluate", "head-to-head", "render", *arguments, "--output", str(output)]
    )
    assert result.exit_code == 1
    assert "holds 24 of the 25 drawn cases" in result.stderr
    assert not output.exists()


# --- the committed files --------------------------------------------------------------------------


def test_the_committed_sheet_fits_the_draw_and_the_report_is_up_to_date() -> None:
    """The report is generated: a sheet edited without `render` afterwards fails here."""
    if not DRAW_FILE.is_file():
        pytest.skip(f"{DRAW_FILE} is missing (this worktree leaves eval/reports/pile_b out)")
    draw = load_draw(DRAW_FILE)
    filled = load_sheet(SHEET_FILE)
    check_sheet(filled, draw, date.today())
    engine = load_engine_file(ENGINE_FILE, draw) if ENGINE_FILE.is_file() else None
    expected = render_report(filled, draw, current_cases(draw), engine)
    assert REPORT_FILE.read_text(encoding="utf-8") == expected
