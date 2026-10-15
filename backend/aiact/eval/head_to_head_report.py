"""The head-to-head report (V10a, decision 036): `REPORT_FILE`, written from the answer sheet,
the draw and the cases' current labels.

Each column (the checker's and the engine's) is scored by `column_scores` with the engine's own
scorers, `metrics.class_match` (risk-class accuracy) and `metrics.class_too_low` (false low risk),
over the cases it has an answer for, on all drawn cases and on each set's. The checker column is
the sheet's `cases` (the agent's runs); the user's hand spot-checks are set beside them, class and
differing answers, and never scored (decision 036's amendment). The engine column (V10b) comes from
one stored run of exactly the drawn cases (`engine_column`: a completed held-out run of
`HEAD_TO_HEAD_BENCHMARK`, read from `eval_runs` / `eval_case_results`), scored against the same
current labels; without it the column is empty. A drawn case whose classifier call failed in that
run is left out of the engine's score (counted apart, never as a miss), and the report says how
many. `render --run-id` also writes the column it read to `ENGINE_FILE`, so the report can be
rendered again offline (and its up-to-date test can run) without the database.
"""

import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from uuid import UUID

import psycopg
from pydantic import ValidationError

from aiact.eval.appliedai_review_report import _cell
from aiact.eval.cases import CASES_DIR, BenchmarkCase, CaseLabel, load_cases
from aiact.eval.head_to_head import (
    DRAW_SETS,
    HEAD_TO_HEAD_BENCHMARK,
    HEAD_TO_HEAD_DIR,
    Draw,
    DrawnCase,
    DrawStep,
)
from aiact.eval.head_to_head_sheet import (
    CHECKER_URL,
    MEANING_CLASS,
    SCREENSHOT_DIR,
    SPOT_CHECK_COUNT,
    SPOT_CHECK_SEED,
    AnsweredBy,
    CheckerRun,
    HeadToHeadSheet,
    SheetError,
    spot_check_ids,
)
from aiact.eval.metrics import Rate, class_match, class_too_low, rate
from aiact.eval.report import RunInfo, load_run_info, load_stored_cases, reported_run_problem
from aiact.eval.runner import RunStatus
from aiact.schemas.base import ContractModel
from aiact.schemas.enums import RiskClass

REPORT_FILE = HEAD_TO_HEAD_DIR / "head_to_head.md"
ENGINE_FILE = HEAD_TO_HEAD_DIR / "head_to_head_engine.json"
PENDING = ""
"""A cell of a case not run yet (or an engine column not filled yet)."""
NO_CLASS = "none (can't determine)"
NOT_ASKED = "(not asked)"
"""A spot-check cell for a question only the other run was asked."""
BACKTICKS = re.compile(r"`+")

ColumnClasses = Mapping[str, RiskClass | None]
"""One column's class per case id (the checker's, or the engine's); a missing id is a case it
hasn't answered, None an answer with no class."""


class EngineRunError(ValueError):
    """The stored run can't fill the engine column; the message names counts, never a case id."""


@dataclass(frozen=True)
class EngineColumn:
    """The engine column: its classes from one stored run, which the report names."""

    run: RunInfo
    classes: ColumnClasses
    failed: int = 0
    """Drawn cases whose classifier call failed in the run: left out of `classes`."""


class ColumnScores(ContractModel):
    """One column's scores over the cases it answered."""

    answered: int
    risk_class_accuracy: Rate
    false_low_risk: Rate


def column_scores(cases: Iterable[BenchmarkCase], classes: ColumnClasses) -> ColumnScores:
    """Risk-class accuracy and the false-low-risk rate of one column's classes (no class is a
    miss, as for the engine), over the cases with an entry in `classes`."""
    answered = [case for case in cases if case.id in classes]
    return ColumnScores(
        answered=len(answered),
        risk_class_accuracy=rate(answered, lambda case: class_match(case, classes[case.id])),
        false_low_risk=rate(answered, lambda case: class_too_low(case, classes[case.id])),
    )


def checker_classes(sheet: HeadToHeadSheet) -> dict[str, RiskClass | None]:
    """The checker's class per case it was run on."""
    return {run.case_id: sheet.checker_class(run) for run in sheet.cases if run.is_run}


def current_cases(draw: Draw, cases_dir: Path = CASES_DIR) -> dict[str, BenchmarkCase]:
    """The drawn cases as labelled now (a label changed since the draw has its LABEL_CHANGES
    row); a drawn case that is gone raises, with a count only (the ids are Pile B's)."""
    loaded = {case.id: case for case_set in DRAW_SETS for case in load_cases(case_set, cases_dir)}
    missing = [case.case_id for case in draw.cases if case.case_id not in loaded]
    if missing:
        raise SheetError(f"{len(missing)} drawn cases are no longer in eval/cases")
    return {case.case_id: loaded[case.case_id] for case in draw.cases}


def engine_column(conn: psycopg.Connection, run_id: UUID, draw: Draw) -> EngineColumn:
    """The engine's class per drawn case from stored run `run_id`, which must be a completed
    held-out run of exactly the drawn cases (`aiact evaluate run --cases-from-draw`)."""
    run = load_run_info(conn, run_id)
    _check_engine_run(run)
    stored = load_stored_cases(conn, run_id)
    stored_ids = {row.outcome.case.id for row in stored}
    drawn_ids = {case.case_id for case in draw.cases}
    if stored_ids != drawn_ids:
        raise EngineRunError(
            f"run {run_id} holds {len(stored_ids & drawn_ids)} of the {len(drawn_ids)} drawn "
            f"cases and {len(stored_ids - drawn_ids)} other cases; it must hold exactly the draw"
        )
    classes = {
        row.outcome.case.id: row.outcome.result.risk_class
        for row in stored
        if row.outcome.result is not None
    }
    return EngineColumn(run=run, classes=classes, failed=len(stored) - len(classes))


def _check_engine_run(run: RunInfo) -> None:
    wanted = "the head-to-head draw (`aiact evaluate run --cases-from-draw`)"
    problem = reported_run_problem(run, HEAD_TO_HEAD_BENCHMARK, wanted)
    if problem is not None:
        raise EngineRunError(problem)


class EngineFile(ContractModel):
    """`ENGINE_FILE`: the engine column as `render --run-id` read it, with the run facts the
    report prints; `classes` has a class (or null) per drawn case answered, `failed` the drawn
    cases whose classifier call failed."""

    run_id: UUID
    classifier: str | None
    model: str | None
    exclude_mode: str | None
    git_sha: str
    started_at: datetime
    classes: dict[str, RiskClass | None]
    failed: tuple[str, ...] = ()


def write_engine_file(engine: EngineColumn, draw: Draw, path: Path = ENGINE_FILE) -> None:
    """Write the engine column, its cases in draw order."""
    order = [case.case_id for case in draw.cases]
    run = engine.run
    data = EngineFile(
        run_id=run.id,
        classifier=run.classifier,
        model=run.model,
        exclude_mode=run.exclude_mode,
        git_sha=run.git_sha,
        started_at=run.started_at,
        classes={
            case_id: engine.classes[case_id] for case_id in order if case_id in engine.classes
        },
        failed=tuple(case_id for case_id in order if case_id not in engine.classes),
    )
    _check_engine_ids(data, draw)
    path.write_text(data.model_dump_json(indent=2) + "\n", encoding="utf-8")


def load_engine_file(path: Path, draw: Draw) -> EngineColumn:
    """The engine column from `path`; refused unless it fits the schema and holds exactly the
    drawn cases (the messages give counts, never a case id)."""
    try:
        data = EngineFile.model_validate_json(path.read_text(encoding="utf-8"))
    except ValidationError as exc:
        # The count only: pydantic's text quotes the input, Pile B case ids included.
        raise EngineRunError(
            f"{path}: not a valid engine column ({exc.error_count()} errors)"
        ) from None
    _check_engine_ids(data, draw)
    run = RunInfo(
        id=data.run_id,
        benchmark=HEAD_TO_HEAD_BENCHMARK,
        git_sha=data.git_sha,
        started_at=data.started_at,
        model=data.model,
        classifier=data.classifier,
        exclude_mode=data.exclude_mode,
        status=RunStatus.COMPLETED.value,
    )
    return EngineColumn(run=run, classes=data.classes, failed=len(data.failed))


def _check_engine_ids(data: EngineFile, draw: Draw) -> None:
    drawn = {case.case_id for case in draw.cases}
    held = [*data.classes, *data.failed]
    if len(held) != len(set(held)) or set(held) != drawn:
        raise EngineRunError(
            f"the engine column holds {len(set(held) & drawn)} of the {len(drawn)} drawn cases, "
            f"{len(set(held) - drawn)} other cases and {len(held) - len(set(held))} repeats; it "
            "must hold exactly the draw"
        )


# --- rendering ------------------------------------------------------------------------------------


def render_report(
    sheet: HeadToHeadSheet,
    draw: Draw,
    cases: Mapping[str, BenchmarkCase],
    engine: EngineColumn | None = None,
) -> str:
    """The report's markdown; `engine` (V10b) fills the engine column, else it stays empty."""
    runs = {run.case_id: run for run in sheet.cases}
    checker = checker_classes(sheet)
    engine_classes = engine.classes if engine else None
    lines = [
        *_intro(draw, sheet, engine),
        *_scores(list(cases.values()), checker, engine_classes),
        *_case_table(draw, runs, cases, checker, engine_classes),
        *_headings_table(sheet),
        *_spot_check(sheet, draw, runs, cases),
        *_limitations(draw, cases),
        *_answers(draw, runs),
    ]
    return "\n".join(lines).rstrip("\n") + "\n"


def _intro(draw: Draw, sheet: HeadToHeadSheet, engine: EngineColumn | None) -> list[str]:
    return [
        "# Head-to-head: the Commission's AI Act Service Desk checker",
        "",
        "Generated by `aiact evaluate head-to-head render` (V10a, decision 036) from "
        "`head_to_head.yaml`; edit that file, never this one.",
        f"Cases: {draw.size} drawn from the `{draw.labels_ref}` labels "
        f"(`{draw.labels_commit[:12]}`) by seed {draw.seed}, stratified by risk class with at "
        f"least {draw.step_minimum} cases per engine step (`head_to_head_draw.json` states the "
        "rule).",
        _answered_line(sheet),
        "Checker: the European Commission's AI Act Service Desk compliance checker "
        f"({CHECKER_URL}), in beta; its results are quoted verbatim per case, with the date run.",
        *([_engine_line(engine)] if engine else []),
        "Scoring (decision 036): each result maps to one risk class, the strictest of its "
        'headings; "can\'t determine" gives no class and counts as a miss. Role and Annex point '
        "aren't compared. Own cases are development cases (decision 018).",
        "Classifications are guidance, not legal advice.",
        "",
    ]


def _answered_line(sheet: HeadToHeadSheet) -> str:
    """Who answered the runs and which checker releases they saw, from the sheet itself."""
    by_agent = sum(run.answered_by is AnsweredBy.AGENT for run in sheet.cases)
    by_hand = sum(run.answered_by is AnsweredBy.HAND for run in sheet.spot_checks)
    done = [run for run in (*sheet.cases, *sheet.spot_checks) if run.is_run]
    releases = sorted({run.checker_release for run in done if run.checker_release})
    seen = ", ".join(releases) if releases else "none yet"
    return (
        f"Answered (decision 036, amendment 2026-10-14): {by_agent} of {len(sheet.cases)} cases "
        "by an agent that saw only the case's description (one fresh agent per case), scored; "
        f"{by_hand} of {SPOT_CHECK_COUNT} spot-checks by hand (below), not scored. Checker "
        f"question release seen: {seen}."
    )


def _engine_line(engine: EngineColumn) -> str:
    run = engine.run
    failed = (
        f"; drawn cases whose run failed, left out of its score: {engine.failed}"
        if engine.failed
        else ""
    )
    return (
        f"Engine: stored run `{run.id}` (classifier `{run.classifier}`, model `{run.model}`, "
        f"exclude mode {run.exclude_mode}, git `{run.git_sha[:12]}`, started "
        f"{run.started_at.date().isoformat()}), scored against the same current labels{failed}."
    )


def _scores(
    cases: Sequence[BenchmarkCase], checker: ColumnClasses, engine: ColumnClasses | None
) -> list[str]:
    """Each column on all drawn cases, then on each set's (Commission Pile B, own)."""
    columns = [("Commission checker", checker)]
    if engine is not None:
        columns.append(("Engine", engine))
    groups = [("", cases)] + [
        (f", {case_set.value} cases", [case for case in cases if case.set_name is case_set])
        for case_set in DRAW_SETS
    ]
    lines = [
        "## Scores",
        "",
        "| Column | Cases answered | Risk-class accuracy | False-low-risk rate |",
        "| --- | ---: | ---: | ---: |",
        *(
            _score_row(f"{name}{suffix}", group, classes)
            for name, classes in columns
            for suffix, group in groups
        ),
    ]
    if engine is None:
        lines.append("| Engine | not filled yet (V10b) | | |")
    return [*lines, ""]


def _score_row(name: str, cases: Sequence[BenchmarkCase], classes: ColumnClasses) -> str:
    scores = column_scores(cases, classes)
    return (
        f"| {name} | {scores.answered} of {len(cases)} | "
        f"{scores.risk_class_accuracy.with_counts} | {scores.false_low_risk.with_counts} |"
    )


def _case_table(
    draw: Draw,
    runs: Mapping[str, CheckerRun],
    cases: Mapping[str, BenchmarkCase],
    checker: ColumnClasses,
    engine: ColumnClasses | None,
) -> list[str]:
    header = (
        "| Case | Set | Steps | Our label | Checker headings | Checker class | Match | "
        "Engine class | Engine match | Run on |"
    )
    rows = [
        _case_row(drawn, runs[drawn.case_id], cases[drawn.case_id], checker, engine or {})
        for drawn in draw.cases
    ]
    return ["## Cases", "", header, "|" + " --- |" * 10, *rows, ""]


def _case_row(
    drawn: DrawnCase,
    run: CheckerRun,
    case: BenchmarkCase,
    checker: ColumnClasses,
    engine: ColumnClasses,
) -> str:
    cells = (
        f"`{drawn.case_id}`",
        drawn.set_name.value,
        ", ".join(step.value for step in drawn.steps),
        _label_cell(drawn, case),
        _cell("; ".join(run.result_headings)),
        *_class_cells(case, checker),
        *_class_cells(case, engine),
        run.date.isoformat() if run.date else "not run yet",
    )
    return "| " + " | ".join(cells) + " |"


def _label_cell(drawn: DrawnCase, case: BenchmarkCase) -> str:
    label = case.label
    now = label.risk_class if isinstance(label, CaseLabel) else None
    if now is drawn.risk_class:
        return drawn.risk_class.value
    return f"{now.value if now else 'no class'} (at draw: {drawn.risk_class.value})"


def _class_cells(case: BenchmarkCase, classes: ColumnClasses) -> tuple[str, str]:
    if case.id not in classes:
        return PENDING, PENDING
    risk_class = classes[case.id]
    is_match = class_match(case, risk_class)
    match = PENDING if is_match is None else ("yes" if is_match else "no")
    return (risk_class.value if risk_class else NO_CLASS), match


def _headings_table(sheet: HeadToHeadSheet) -> list[str]:
    rows = [
        f"| {_cell(heading)} | {meaning.value} | "
        f"{(risk_class.value if (risk_class := MEANING_CLASS[meaning]) else NO_CLASS)} |"
        for heading, meaning in sheet.headings.items()
    ]
    body = rows or ["| (none yet: add the first case's headings) | | |"]
    return [
        "## Checker headings and their class",
        "",
        "| Checker heading | Meaning | Class |",
        "| --- | --- | --- |",
        *body,
        "",
    ]


def _spot_check(
    sheet: HeadToHeadSheet,
    draw: Draw,
    runs: Mapping[str, CheckerRun],
    cases: Mapping[str, BenchmarkCase],
) -> list[str]:
    hand = {run.case_id: run for run in sheet.spot_checks}
    pairs = [(runs[case_id], hand.get(case_id)) for case_id in spot_check_ids(draw)]
    compared = [
        (agent, by_hand)
        for agent, by_hand in pairs
        if by_hand is not None and _both_run(agent, by_hand)
    ]
    agree = sum(sheet.checker_class(a) == sheet.checker_class(h) for a, h in compared)
    return [
        "## Spot-check",
        "",
        f"{SPOT_CHECK_COUNT} cases, one per risk class, picked by seed {SPOT_CHECK_SEED} "
        "(decision 036, amendment 2026-10-14), are run by the user by hand as well, blind to the "
        "agent's answers. These hand runs aren't scored.",
        "",
        f"{agree} of {len(compared)} agree on the class.",
        "",
        "| Case | Our label | Agent class | Hand class | Agree |",
        "| --- | --- | --- | --- | --- |",
        *(_spot_row(sheet, agent, by_hand, cases[agent.case_id]) for agent, by_hand in pairs),
        "",
        *(line for agent, by_hand in pairs for line in _spot_section(agent, by_hand)),
    ]


def _both_run(agent: CheckerRun, by_hand: CheckerRun) -> bool:
    return agent.is_run and by_hand.is_run


def _spot_row(
    sheet: HeadToHeadSheet, agent: CheckerRun, by_hand: CheckerRun | None, case: BenchmarkCase
) -> str:
    label = case.label.risk_class if isinstance(case.label, CaseLabel) else None
    agent_class = _run_class(sheet, agent)
    hand_class = _run_class(sheet, by_hand)
    agree = PENDING
    if by_hand is not None and _both_run(agent, by_hand):
        agree = "yes" if sheet.checker_class(agent) == sheet.checker_class(by_hand) else "no"
    cells = (
        f"`{agent.case_id}`",
        label.value if label else "no class",
        agent_class,
        hand_class,
        agree,
    )
    return "| " + " | ".join(cells) + " |"


def _run_class(sheet: HeadToHeadSheet, run: CheckerRun | None) -> str:
    if run is None or not run.is_run:
        return "not run yet"
    risk_class = sheet.checker_class(run)
    return risk_class.value if risk_class else NO_CLASS


def _spot_section(agent: CheckerRun, by_hand: CheckerRun | None) -> list[str]:
    title = f"### Spot-check `{agent.case_id}`"
    if by_hand is None or not _both_run(agent, by_hand):
        return [title, "", "Not compared yet: both runs are needed.", ""]
    differing = _differing_answers(agent, by_hand)
    body = (
        [
            "Answers that differ, verbatim:",
            "",
            "| Question | Agent's answer | Hand answer |",
            "| --- | --- | --- |",
            *(f"| {_cell(q)} | {_cell(a)} | {_cell(h)} |" for q, a, h in differing),
        ]
        if differing
        else ["Every answer is the same."]
    )
    return [title, "", *body, "", *_run_section(by_hand, "#### The hand run")]


def _differing_answers(agent: CheckerRun, by_hand: CheckerRun) -> list[tuple[str, str, str]]:
    """The questions answered differently, or asked in one run only, in the agent's order then
    the hand run's."""
    given = {answer.question: answer.answer for answer in agent.answers}
    hand = {answer.question: answer.answer for answer in by_hand.answers}
    questions = [*given, *(question for question in hand if question not in given)]
    return [
        (question, given.get(question, NOT_ASKED), hand.get(question, NOT_ASKED))
        for question in questions
        if given.get(question) != hand.get(question)
    ]


def _limitations(draw: Draw, cases: Mapping[str, BenchmarkCase]) -> list[str]:
    dated = [
        f"`{drawn.case_id}` (judged on {case.as_of.isoformat()})"
        for drawn in draw.cases
        if (case := cases[drawn.case_id]).as_of is not None
    ]
    roles = [f"`{drawn.case_id}`" for drawn in draw.cases if DrawStep.ROLES in drawn.steps]
    lines = [
        "## Limitations",
        "",
        "- The checker is a beta and its outcomes may change; each case gives the date it was run.",
        f"- The roles step is in the draw ({', '.join(roles)}), but a class-only score can't show "
        "it: roles aren't compared, and these cases' classes don't depend on the role.",
        "- On borderline descriptions the checker's class turns on how the answerer reads "
        '"is it an AI system?" and "does it interact with people?" (decision 036, runs and '
        "spot-check outcome).",
    ]
    if dated:
        lines.append(
            "- These labels depend on a date (for example the 2025-26 amendments' prohibitions), "
            f"which the checker may not cover: {', '.join(dated)}."
        )
    return [*lines, ""]


def _answers(draw: Draw, runs: Mapping[str, CheckerRun]) -> list[str]:
    sections = [_run_section(runs[drawn.case_id]) for drawn in draw.cases]
    return ["## Runs", "", *(line for section in sections for line in section)]


def _run_section(run: CheckerRun, title: str | None = None) -> list[str]:
    title = title or f"### `{run.case_id}`"
    if run.date is None:
        return [title, "", "Not run yet.", ""]
    uncertain = set(run.uncertain_questions)
    fence = _fence(run.result_text or "")
    screenshot = (
        [f"- Screenshot: [{run.screenshot}]({SCREENSHOT_DIR.name}/{run.screenshot})"]
        if run.screenshot
        else []
    )
    return [
        title,
        "",
        f"- Run on: {run.date.isoformat()}",
        f"- Answered by: {run.answered_by.value if run.answered_by else 'not given'}",
        f"- Checker question release: {run.checker_release or 'not given'}",
        *screenshot,
        "",
        "Result, verbatim:",
        "",
        f"{fence}text",
        (run.result_text or "").strip(),
        fence,
        "",
        "| Question | Answer | Uncertain |",
        "| --- | --- | --- |",
        *(
            f"| {_cell(a.question)} | {_cell(a.answer)} | "
            f"{'yes' if a.question in uncertain else PENDING} |"
            for a in run.answers
        ),
        "",
    ]


def _fence(text: str) -> str:
    """A code fence longer than any backtick run in `text`, so the text can't close it."""
    longest = max((len(run) for run in BACKTICKS.findall(text)), default=0)
    return "`" * max(3, longest + 1)
