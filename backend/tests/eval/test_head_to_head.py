import subprocess
from collections import Counter
from pathlib import Path

import pytest
from typer.testing import CliRunner

from aiact.cli import app
from aiact.eval import head_to_head
from aiact.eval.cases import ART_6_3_FILTER, CaseLabel, CaseSet, load_cases
from aiact.eval.head_to_head import (
    DRAW_FILE,
    Draw,
    DrawError,
    DrawStep,
    case_steps,
    cases_at,
    draw_cases,
    drawable_class,
    load_draw,
    make_draw,
    step_counts,
    write_draw,
)
from aiact.eval.head_to_head_sheet import SHEET_FILE, load_sheet
from aiact.schemas import Language, RiskClass, Status
from tests.eval.head_to_head_pool import NOT_DRAWABLE, POOL, R, commission, make_case, own

COMMIT = "a" * 40
S = DrawStep


def test_the_draw_settings_are_pinned() -> None:
    assert head_to_head.LABELS_REF == "labels-v1"
    assert head_to_head.DRAW_SEED == 20261014
    assert head_to_head.DRAW_SIZE == 25
    assert head_to_head.STEP_MINIMUM == 2
    assert (head_to_head.MIN_DRAW_SIZE, head_to_head.MAX_DRAW_SIZE) == (20, 30)
    assert head_to_head.DRAW_SETS == (CaseSet.COMMISSION_B, CaseSet.OWN)
    assert [step.value for step in DrawStep] == [
        "scope",
        "prohibited",
        "annex_iii",
        "annex_i",
        "art_6_3",
        "transparency",
        "roles",
    ]


def test_the_draw_and_sheet_sit_in_the_folder_the_engine_lane_denies() -> None:
    """They name Pile B cases with their labels (docs/LAYOUT.md > eval/reports/pile_b)."""
    assert DRAW_FILE.parts[-4:] == ("eval", "reports", "pile_b", "head_to_head_draw.json")
    assert SHEET_FILE.parts[-4:] == ("eval", "reports", "pile_b", "head_to_head.yaml")


# --- steps and the pool ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("letter", "risk_class", "steps"),
    [
        ("a", R.MINIMAL_RISK, (S.TRANSPARENCY,)),
        ("b", R.MINIMAL_RISK, (S.SCOPE,)),
        ("c", R.MINIMAL_RISK, (S.PROHIBITED,)),
        ("d", R.HIGH_RISK, (S.ROLES,)),
        ("e", R.HIGH_RISK, (S.ANNEX_I,)),
        ("f", R.MINIMAL_RISK, (S.ANNEX_III,)),
        ("t", R.MINIMAL_RISK, ()),
    ],
)
def test_an_own_case_exercises_its_category_step(
    letter: str, risk_class: RiskClass, steps: tuple[DrawStep, ...]
) -> None:
    assert case_steps(own(letter, risk_class, 1)[0]) == steps


@pytest.mark.parametrize(
    ("risk_class", "steps"),
    [
        (R.OUT_OF_SCOPE, (S.SCOPE, S.ROLES)),
        (R.PROHIBITED, (S.PROHIBITED, S.ROLES)),
        (R.LIMITED_RISK, (S.TRANSPARENCY, S.ROLES)),
        (R.HIGH_RISK, (S.ROLES,)),
        (R.MINIMAL_RISK, (S.ROLES,)),
    ],
)
def test_a_class_only_one_step_gives_adds_that_step(
    risk_class: RiskClass, steps: tuple[DrawStep, ...]
) -> None:
    assert case_steps(own("d", risk_class, 1)[0]) == steps


@pytest.mark.parametrize(
    ("area", "steps"),
    [("annex_i", (S.ANNEX_I,)), ("annex_iii_4", (S.ANNEX_III,)), ("annex_iii_8", (S.ANNEX_III,))],
)
def test_a_commission_case_exercises_its_annex_area(area: str, steps: tuple[DrawStep, ...]) -> None:
    assert case_steps(commission(area, R.HIGH_RISK, 1)[0]) == steps


def test_an_area_tag_on_an_own_case_and_a_category_tag_on_a_commission_case_count_for_nothing() -> (
    None
):
    own_case = make_case("own-x-0", R.HIGH_RISK, tags=("area:annex_i",))
    rewrite = make_case("cb-x-0", R.HIGH_RISK, set_name=CaseSet.COMMISSION_B, tags=("category:b",))
    assert case_steps(own_case) == case_steps(rewrite) == ()


@pytest.mark.parametrize("basis", [ART_6_3_FILTER, f"{ART_6_3_FILTER}:d"])
def test_the_art_6_3_filter_as_basis_exercises_art_6_3(basis: str) -> None:
    case = commission("annex_iii_5", R.MINIMAL_RISK, 1, basis=basis)[0]
    assert case_steps(case) == (S.ANNEX_III, S.ART_6_3)


def test_a_lettered_art_6_3_citation_exercises_art_6_3_but_a_bare_one_does_not() -> None:
    lettered = make_case("own-f-0", R.MINIMAL_RISK, tags=("category:f",), citation=("art:6:3:a",))
    bare = make_case("own-f-1", R.HIGH_RISK, tags=("category:f",), citation=("art:6:3",))
    assert case_steps(lettered) == (S.ANNEX_III, S.ART_6_3)
    assert case_steps(bare) == (S.ANNEX_III,)


def test_only_english_decided_headline_cases_with_a_class_are_drawable() -> None:
    assert [drawable_class(case) for case in NOT_DRAWABLE] == [None] * len(NOT_DRAWABLE)
    assert drawable_class(own("a", R.LIMITED_RISK, 1)[0]) is R.LIMITED_RISK
    assert drawable_class(commission("annex_i", R.HIGH_RISK, 1)[0]) is R.HIGH_RISK


# --- the draw -------------------------------------------------------------------------------------


def test_the_draw_takes_an_even_share_per_class_and_the_step_minimum() -> None:
    drawn = draw_cases(POOL, seed=7, size=25)
    assert Counter(case.risk_class for case in drawn) == {risk_class: 5 for risk_class in R}
    covered = Counter(step for case in drawn for step in case.steps)
    assert all(covered[step] >= 2 for step in DrawStep)
    assert {case.case_id for case in drawn} <= {case.id for case in POOL if drawable_class(case)}


def test_an_uneven_size_tops_up_classes_by_seeded_choice() -> None:
    shares = sorted(Counter(case.risk_class for case in draw_cases(POOL, seed=7, size=22)).values())
    assert shares == [4, 4, 4, 5, 5]


def test_the_draw_is_seeded_and_sorted_by_set_then_id() -> None:
    first = draw_cases(POOL, seed=7, size=25)
    assert draw_cases(list(reversed(POOL)), seed=7, size=25) == first
    assert draw_cases(POOL, seed=8, size=25) != first
    keys = [(case.set_name is not CaseSet.COMMISSION_B, case.case_id) for case in first]
    assert keys == sorted(keys)


def test_each_drawn_case_records_its_class_and_steps() -> None:
    by_id = {case.id: case for case in POOL}
    for drawn in draw_cases(POOL, seed=7, size=25):
        assert drawn.steps == case_steps(by_id[drawn.case_id])
        assert drawn.risk_class is drawable_class(by_id[drawn.case_id])


def test_a_step_with_one_case_in_the_pool_stops_the_draw() -> None:
    pool = [case for case in POOL if S.ANNEX_I not in case_steps(case)]
    pool += commission("annex_i", R.HIGH_RISK, 1)
    with pytest.raises(DrawError, match="step annex_i: 1 of 2"):
        draw_cases(pool, seed=7, size=25)


def test_a_class_smaller_than_its_share_stops_the_draw() -> None:
    pool = [case for case in POOL if drawable_class(case) is not R.PROHIBITED]
    pool += own("c", R.PROHIBITED, 4)
    with pytest.raises(DrawError, match="prohibited: 4 cases in the pool for a share of 5"):
        draw_cases(pool, seed=7, size=25)


def test_an_empty_pool_stops_the_draw() -> None:
    with pytest.raises(DrawError, match="no case in the pool"):
        draw_cases(NOT_DRAWABLE, size=25)


def test_the_draw_file_states_the_rule_seed_and_labels() -> None:
    draw = make_draw(POOL, COMMIT, seed=7, size=25)
    assert (draw.labels_ref, draw.labels_commit, draw.seed, draw.size) == (
        "labels-v1",
        COMMIT,
        7,
        25,
    )
    assert draw.rule == head_to_head.DRAW_RULE
    assert draw.step_minimum == 2


@pytest.mark.parametrize("size", [19, 31])
def test_a_draw_outside_20_to_30_cases_is_refused(size: int) -> None:
    drawn = draw_cases(POOL, seed=7, size=25)
    with pytest.raises(ValueError, match="size"):
        Draw(
            labels_ref="labels-v1",
            labels_commit=COMMIT,
            seed=7,
            size=size,
            step_minimum=2,
            rule="r",
            cases=drawn,
        )


def test_a_draw_whose_cases_repeat_or_miss_the_size_is_refused() -> None:
    drawn = draw_cases(POOL, seed=7, size=25)
    fields = {"labels_ref": "x", "labels_commit": COMMIT, "seed": 7, "step_minimum": 2, "rule": "r"}
    with pytest.raises(ValueError, match="drawn once"):
        Draw(**fields, size=25, cases=(*drawn[:24], drawn[0]))
    with pytest.raises(ValueError, match="24 cases drawn for a size of 25"):
        Draw(**fields, size=25, cases=drawn[:24])


def test_the_draw_file_is_written_once(tmp_path: Path) -> None:
    path = tmp_path / "pile_b" / "draw.json"
    draw = make_draw(POOL, COMMIT, seed=7, size=25)
    assert write_draw(draw, path) is True
    assert write_draw(draw, path) is False
    assert load_draw(path) == draw
    with pytest.raises(DrawError, match="different draw"):
        write_draw(make_draw(POOL, COMMIT, seed=8, size=25), path)


def test_a_broken_draw_file_is_reported(tmp_path: Path) -> None:
    path = tmp_path / "draw.json"
    path.write_text('{"seed": 1}', encoding="utf-8")
    with pytest.raises(DrawError, match="not a valid draw"):
        load_draw(path)


# --- the labels at a tag --------------------------------------------------------------------------

CASE_YAML = """\
id: {id}
set_name: {set_name}
language: en
description: A made-up system.
label: {{risk_class: {risk_class}}}
label_citation: ["art:6:2"]
"""


def _git(repo: Path, *arguments: str) -> None:
    subprocess.run(["git", *arguments], cwd=repo, check=True, capture_output=True)


def _write_case(repo: Path, folder: str, case_id: str, risk_class: str) -> None:
    path = repo / "eval" / "cases" / folder / f"{case_id}.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    set_name = folder.split("/")[0]
    path.write_text(
        CASE_YAML.format(id=case_id, set_name=set_name, risk_class=risk_class), encoding="utf-8"
    )


def test_the_cases_are_read_as_they_were_at_the_tag(tmp_path: Path) -> None:
    """A label changed and a case added after the tag don't reach the draw."""
    _git(tmp_path, "init", "-q")
    _write_case(tmp_path, "own/a", "own-a-01", "limited_risk")
    _write_case(tmp_path, "commission_b/annex_i", "cb-001", "high_risk")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "-c", "user.name=t", "-c", "user.email=t@example.com", "commit", "-qm", "c")
    _git(tmp_path, "tag", "labels-test")
    _write_case(tmp_path, "own/a", "own-a-01", "minimal_risk")
    _write_case(tmp_path, "own/a", "own-a-02", "limited_risk")

    commit, cases = cases_at("labels-test", tmp_path)

    assert len(commit) == 40
    labels = {case.id: case.label for case in cases}
    assert labels == {
        "cb-001": CaseLabel(risk_class=R.HIGH_RISK),
        "own-a-01": CaseLabel(risk_class=R.LIMITED_RISK),
    }


@pytest.mark.parametrize("ref", ["", "--output=x", "no-such-tag"])
def test_a_bad_ref_is_refused(tmp_path: Path, ref: str) -> None:
    _git(tmp_path, "init", "-q")
    with pytest.raises(DrawError):
        cases_at(ref, tmp_path)


# --- the command ----------------------------------------------------------------------------------


def test_the_draw_command_writes_the_draw_and_a_sheet_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(head_to_head, "cases_at", lambda ref: (COMMIT, tuple(POOL)))
    draw_path, sheet = tmp_path / "draw.json", tmp_path / "sheet.yaml"
    arguments = ["evaluate", "head-to-head", "draw", "--output", str(draw_path)]
    arguments += ["--sheet", str(sheet), "--seed", "7"]

    first = CliRunner().invoke(app, arguments)
    sheet.write_text(sheet.read_text(encoding="utf-8") + "# the user's edit\n", encoding="utf-8")
    second = CliRunner().invoke(app, arguments)

    assert first.exit_code == 0, first.output
    assert "Drawn: 25 cases from labels-v1 (aaaaaaaaaaaa), seed 7" in first.output
    assert f"Written: {draw_path}" in first.output
    assert f"Unchanged: {draw_path}" in second.output
    assert f"Kept: {sheet}" in second.output
    assert sheet.read_text(encoding="utf-8").endswith("# the user's edit\n")
    assert [run.case_id for run in load_sheet(sheet).cases] == [
        case.case_id for case in load_draw(draw_path).cases
    ]


def test_the_draw_command_reports_a_pool_that_cant_be_drawn(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(head_to_head, "cases_at", lambda ref: (COMMIT, tuple(NOT_DRAWABLE)))
    arguments = ["evaluate", "head-to-head", "draw", "--output", str(tmp_path / "d.json")]
    result = CliRunner().invoke(app, [*arguments, "--sheet", str(tmp_path / "s.yaml")])
    assert result.exit_code == 1
    assert "Error: no case in the pool" in result.output


# --- the committed draw ---------------------------------------------------------------------------


def _committed_draw() -> Draw:
    if not DRAW_FILE.is_file():
        pytest.skip(f"{DRAW_FILE} is missing (this worktree leaves eval/reports/pile_b out)")
    return load_draw(DRAW_FILE)


def test_the_committed_draw_meets_decision_036() -> None:
    draw = _committed_draw()
    assert (draw.labels_ref, draw.seed, draw.size) == ("labels-v1", 20261014, 25)
    assert draw.labels_commit == "be072f05768902eac8c6244bf367269a43dd0ee5"
    assert draw.rule == head_to_head.DRAW_RULE
    assert all(count >= 2 for count in step_counts(draw).values())
    assert Counter(case.risk_class for case in draw.cases) == {risk_class: 5 for risk_class in R}


def test_every_committed_draw_case_is_still_an_english_decided_case() -> None:
    """The labels may change after labels-v1 only with a LABEL_CHANGES row; the draw stays."""
    draw = _committed_draw()
    current = {case.id: case for s in head_to_head.DRAW_SETS for case in load_cases(s)}
    for drawn in draw.cases:
        case = current[drawn.case_id]
        assert case.set_name is drawn.set_name
        assert case.language is Language.EN
        assert isinstance(case.label, CaseLabel) and case.label.status is Status.DECIDED
