"""The head-to-head answer sheet (V10a, decision 036 and its amendment of 2026-10-14): the runs of
the Commission checker, in `SHEET_FILE`. `cases` holds one entry per drawn case, answered by a
blind agent and scored; `spot_checks` holds the user's hand runs of the `SPOT_CHECK_COUNT` seeded
spot-check cases (`spot_check_ids`), shown beside the agent's but never scored.

Per run: the date run, who answered (`AnsweredBy`), the checker's question release, the checker's
result verbatim, the result's headings, the questions the checker asked with the answers given, the
questions the description didn't settle (`uncertain_questions`, each one of the answers'), and
optionally a screenshot's file name. The sheet's `headings` table maps each exact heading the
checker shows to what it means (`CheckerMeaning`); `MEANING_CLASS` turns a meaning into one
`RiskClass` by decision 036's fixed table, the strictest when a result shows several. A heading's
row is added after the first case shows it, before any case is scored.

`check_sheet` validates the sheet against the draw: an unknown or missing case id, a run without
its date, a date in the future, a heading the table lacks or the result text doesn't contain, a
screenshot that isn't a plain file name in `SCREENSHOT_DIR` or isn't there, and a spot-check entry
for a case that isn't a spot-check case, listed twice, or not answered by hand. A meaning outside
`CheckerMeaning` (a bad class), or two headings rows that differ only in whitespace, fail parsing.
"""

import datetime as dt
import json
import random
import re
from collections import Counter
from collections.abc import Mapping
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Self

import yaml
from pydantic import Field, StringConstraints, ValidationError, model_validator

from aiact.eval.cases import _UniqueKeyLoader
from aiact.eval.head_to_head import HEAD_TO_HEAD_DIR, Draw
from aiact.eval.metrics import RISK_RANK
from aiact.schemas.base import ContractModel
from aiact.schemas.enums import RiskClass

SHEET_FILE = HEAD_TO_HEAD_DIR / "head_to_head.yaml"
SCREENSHOT_DIR = HEAD_TO_HEAD_DIR / "head_to_head"
SCREENSHOT_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*\.(png|jpg|jpeg|webp|pdf)$")
CHECKER_URL = "https://ai-act-service-desk.ec.europa.eu/en/eu-ai-act-compliance-checker"

SPOT_CHECK_SEED = 20261015
"""Decision 036's amendment: fixed before any agent run."""
SPOT_CHECK_CLASSES = (
    RiskClass.OUT_OF_SCOPE,
    RiskClass.PROHIBITED,
    RiskClass.HIGH_RISK,
    RiskClass.LIMITED_RISK,
    RiskClass.MINIMAL_RISK,
)
"""One spot-check case per class, picked in this order."""
SPOT_CHECK_COUNT = len(SPOT_CHECK_CLASSES)

NonEmptyText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class CheckerMeaning(StrEnum):
    """What a checker result heading means (decision 036's table, by meaning)."""

    PROHIBITED_PRACTICE = "prohibited_practice"
    HIGH_RISK = "high_risk"
    """High-risk under Annex I or III, with or without transparency duties."""
    TRANSPARENCY_ONLY = "transparency_only"
    """Art. 50 transparency duties only."""
    NO_SPECIFIC_DUTIES = "no_specific_duties"
    """AI literacy only, or no specific duties."""
    ACT_DOES_NOT_APPLY = "act_does_not_apply"
    CANNOT_DETERMINE = "cannot_determine"


MEANING_CLASS: Mapping[CheckerMeaning, RiskClass | None] = {
    CheckerMeaning.PROHIBITED_PRACTICE: RiskClass.PROHIBITED,
    CheckerMeaning.HIGH_RISK: RiskClass.HIGH_RISK,
    CheckerMeaning.TRANSPARENCY_ONLY: RiskClass.LIMITED_RISK,
    CheckerMeaning.NO_SPECIFIC_DUTIES: RiskClass.MINIMAL_RISK,
    CheckerMeaning.ACT_DOES_NOT_APPLY: RiskClass.OUT_OF_SCOPE,
    CheckerMeaning.CANNOT_DETERMINE: None,
}
"""Decision 036's fixed table; "can't determine" gives no class, a miss as for the engine."""


class AnsweredBy(StrEnum):
    """Who answered the checker's questions for a run."""

    AGENT = "agent"
    HAND = "hand"


class SheetError(ValueError):
    """The sheet can't be read, or doesn't fit the draw; the message lists every problem."""


class CheckerAnswer(ContractModel):
    """One question the checker asked and the answer given, both verbatim."""

    question: NonEmptyText
    answer: NonEmptyText


class CheckerRun(ContractModel):
    """One case's entry: empty until the case is run, then complete."""

    case_id: NonEmptyText
    date: dt.date | None = None
    answered_by: AnsweredBy | None = None
    checker_release: NonEmptyText | None = None
    """The question release the checker page names, for example "6.5.1"."""
    result_text: str | None = None
    result_headings: tuple[NonEmptyText, ...] = ()
    answers: tuple[CheckerAnswer, ...] = ()
    uncertain_questions: tuple[NonEmptyText, ...] = ()
    """Questions the description didn't settle; each is one of `answers`' questions."""
    screenshot: str | None = None

    @property
    def is_run(self) -> bool:
        return self.date is not None

    @model_validator(mode="after")
    def _empty_or_complete(self) -> Self:
        if not self.is_run:
            if any(self._run_fields()):
                raise ValueError(f"{self.case_id}: missing date (the day the checker was run)")
            return self
        missing = [
            name
            for name, value in (
                ("answered_by", self.answered_by),
                ("checker_release", self.checker_release),
                ("result_text", (self.result_text or "").strip()),
                ("result_headings", self.result_headings),
                ("answers", self.answers),
            )
            if not value
        ]
        if missing:
            raise ValueError(f"{self.case_id}: run on {self.date} but missing {', '.join(missing)}")
        asked = {answer.question for answer in self.answers}
        unasked = [question for question in self.uncertain_questions if question not in asked]
        if unasked:
            raise ValueError(
                f"{self.case_id}: uncertain questions not among the answers: {unasked}"
            )
        return self

    def _run_fields(self) -> tuple[object, ...]:
        """Every field a run fills besides its date and case id."""
        return (
            self.answered_by,
            self.checker_release,
            self.result_text,
            self.result_headings,
            self.answers,
            self.uncertain_questions,
            self.screenshot,
        )


class HeadToHeadSheet(ContractModel):
    """The content of `SHEET_FILE`."""

    headings: dict[NonEmptyText, CheckerMeaning] = Field(default_factory=dict)
    cases: tuple[CheckerRun, ...]
    """The scored runs, one per drawn case (the agent's, by decision 036's amendment)."""
    spot_checks: tuple[CheckerRun, ...] = ()
    """The user's hand runs of the spot-check cases; never scored."""

    @model_validator(mode="before")
    @classmethod
    def _headings_differ_beyond_whitespace(cls, data: object) -> object:
        """Refuse two headings rows that differ only in whitespace: stripping would merge them
        silently, keeping one meaning."""
        headings = data.get("headings") if isinstance(data, dict) else None
        if not isinstance(headings, dict):
            return data
        folded = Counter(_plain(str(heading)) for heading in headings)
        repeated = [heading for heading, n in folded.items() if n > 1]
        if repeated:
            raise ValueError(f"headings differing only in whitespace: {repeated}")
        return data

    def checker_class(self, run: CheckerRun) -> RiskClass | None:
        """The class a run's headings map to, the strictest of them; None when none gives one
        (can't determine) or the case isn't run yet. A heading without a row raises: the table
        is filled before any case is scored (`check_sheet`)."""
        unmapped = [heading for heading in run.result_headings if heading not in self.headings]
        if unmapped:
            raise SheetError(f"{run.case_id}: no headings row for {unmapped}")
        classes = [MEANING_CLASS[self.headings[heading]] for heading in run.result_headings]
        found = [risk_class for risk_class in classes if risk_class is not None]
        return max(found, key=RISK_RANK.__getitem__) if found else None


def load_sheet(path: Path = SHEET_FILE) -> HeadToHeadSheet:
    """Parse the sheet; duplicate keys, bad YAML or a field that doesn't validate raise."""
    try:
        document: object = yaml.load(path.read_text(encoding="utf-8"), Loader=_UniqueKeyLoader)
    except (OSError, yaml.YAMLError, ValueError) as exc:
        raise SheetError(f"{path}: can't read the sheet: {exc}") from exc
    try:
        return HeadToHeadSheet.model_validate(document)
    except ValidationError as exc:
        raise SheetError(f"{path}: {exc}") from exc


def spot_check_ids(draw: Draw) -> tuple[str, ...]:
    """The spot-check cases, by decision 036's amendment: one `random.Random(SPOT_CHECK_SEED)`,
    one `choice` per class in `SPOT_CHECK_CLASSES` order, over the sorted ids of the drawn cases
    of that class (their class at the draw)."""
    rng = random.Random(SPOT_CHECK_SEED)
    return tuple(rng.choice(_drawn_ids(draw, risk_class)) for risk_class in SPOT_CHECK_CLASSES)


def _drawn_ids(draw: Draw, risk_class: RiskClass) -> list[str]:
    ids = sorted(case.case_id for case in draw.cases if case.risk_class is risk_class)
    if not ids:
        raise SheetError(f"no drawn case of class {risk_class.value} to spot-check")
    return ids


def spot_checks_run(sheet: HeadToHeadSheet) -> int:
    """How many spot-check entries are run (a checked sheet lists each spot-check case once)."""
    return sum(run.is_run for run in sheet.spot_checks)


def check_sheet(
    sheet: HeadToHeadSheet, draw: Draw, today: dt.date, screenshot_dir: Path = SCREENSHOT_DIR
) -> None:
    """Raise `SheetError` listing every way the sheet doesn't fit the draw (module docstring)."""
    problems = [
        *_id_problems(sheet, draw),
        *_spot_check_problems(sheet, draw),
        *(
            problem
            for run in sheet.cases
            for problem in _run_problems(run, sheet, today, screenshot_dir)
        ),
        *(
            f"spot check {problem}"
            for run in sheet.spot_checks
            for problem in _run_problems(run, sheet, today, screenshot_dir)
        ),
    ]
    if problems:
        raise SheetError("; ".join(problems))


def _id_problems(sheet: HeadToHeadSheet, draw: Draw) -> list[str]:
    counts = Counter(run.case_id for run in sheet.cases)
    drawn = draw.by_id()
    return [
        *(f"{case_id}: listed {n} times" for case_id, n in counts.items() if n > 1),
        *(
            f"{case_id}: unknown case id (not in the draw)"
            for case_id in counts
            if case_id not in drawn
        ),
        *(
            f"{case_id}: drawn but missing from the sheet"
            for case_id in drawn
            if case_id not in counts
        ),
    ]


def _spot_check_problems(sheet: HeadToHeadSheet, draw: Draw) -> list[str]:
    if not sheet.spot_checks:
        return []
    counts = Counter(run.case_id for run in sheet.spot_checks)
    drawn = draw.by_id()
    wanted = spot_check_ids(draw)
    return [
        *(f"spot check {case_id}: listed {n} times" for case_id, n in counts.items() if n > 1),
        *(
            f"spot check {case_id}: unknown case id (not in the draw)"
            if case_id not in drawn
            else f"spot check {case_id}: not one of the {SPOT_CHECK_COUNT} spot-check cases"
            for case_id in counts
            if case_id not in wanted
        ),
        *(
            f"spot check {run.case_id}: answered_by must be hand, not {run.answered_by.value}"
            for run in sheet.spot_checks
            if run.answered_by is not None and run.answered_by is not AnsweredBy.HAND
        ),
    ]


def _run_problems(
    run: CheckerRun, sheet: HeadToHeadSheet, today: dt.date, screenshot_dir: Path
) -> list[str]:
    if run.date is None:
        return []
    text = _plain(run.result_text or "")
    return [
        *([f"{run.case_id}: date {run.date} is in the future"] if run.date > today else []),
        *(
            f"{run.case_id}: heading {heading!r} has no row in headings"
            for heading in run.result_headings
            if heading not in sheet.headings
        ),
        *(
            f"{run.case_id}: heading {heading!r} isn't in result_text verbatim"
            for heading in run.result_headings
            if _plain(heading) not in text
        ),
        *_screenshot_problems(run, screenshot_dir),
    ]


def _screenshot_problems(run: CheckerRun, screenshot_dir: Path) -> list[str]:
    if run.screenshot is None:
        return []
    if not SCREENSHOT_NAME.fullmatch(run.screenshot):
        return [f"{run.case_id}: screenshot {run.screenshot!r} isn't a plain image or PDF name"]
    if not (screenshot_dir / run.screenshot).is_file():
        return [f"{run.case_id}: screenshot {run.screenshot} isn't in {screenshot_dir}"]
    return []


def _plain(text: str) -> str:
    """Whitespace folded to single spaces, so a heading copied across a line break still counts."""
    return " ".join(text.split())


# --- the template ---------------------------------------------------------------------------------

TEMPLATE_HEADER = f"""\
# Head-to-head (V10a, decision 036 and its amendment of 2026-10-14): the Commission's AI Act
# Service Desk checker.
# Checker: {CHECKER_URL}
# The cases come from head_to_head_draw.json (seed and rule there). For each case, the checker's
# questions are answered from the case's description (eval/cases/<set>/) only, then filled in:
#   date                 the day it was run (YYYY-MM-DD)
#   answered_by          agent (a blind agent, one per case) or hand (the user)
#   checker_release      the question release the checker page names, for example "6.5.1"
#   result_text          the checker's result, copied verbatim
#   result_headings      each outcome heading the result shows, exactly as written there
#   answers              every question the checker asked, with the answer given, verbatim:
#                        - question: "..."
#                          answer: "..."
#   uncertain_questions  optional: the questions the description didn't settle, each copied from
#                        answers
#   screenshot           optional: a file name in head_to_head/ next to this file
# cases holds the scored runs, one per drawn case (the agent's). spot_checks holds the user's
# hand runs (answered_by: hand) of the {SPOT_CHECK_COUNT} spot-check cases (seed {SPOT_CHECK_SEED},
# one per class), run blind to the agent's answers and never scored; the report sets them beside
# the agent's.
# headings: give every heading a run shows a row, its exact text and what it means, before any
# case is scored, for example:
#   headings:
#     "Exact heading text from the checker": high_risk
# Meanings: {", ".join(meaning.value for meaning in CheckerMeaning)}.
# Check:  uv run aiact evaluate head-to-head check   (--complete: every case and spot-check run)
# Report: uv run aiact evaluate head-to-head render
"""


def _pending_entry(case_id: str) -> str:
    return (
        f"  - case_id: {json.dumps(case_id)}\n"
        "    date: null\n"
        "    answered_by: null\n"
        "    checker_release: null\n"
        "    result_text: null\n"
        "    result_headings: []\n"
        "    answers: []\n"
        "    uncertain_questions: []\n"
        "    screenshot: null\n"
    )


def render_template(draw: Draw) -> str:
    """A sheet with every drawn case pending, in draw order, then the spot-check cases pending."""
    cases = "".join(_pending_entry(case.case_id) for case in draw.cases)
    spot_checks = "".join(_pending_entry(case_id) for case_id in spot_check_ids(draw))
    return f"{TEMPLATE_HEADER}headings: {{}}\ncases:\n{cases}spot_checks:\n{spot_checks}"


def write_template(draw: Draw, path: Path = SHEET_FILE) -> bool:
    """Write the pending sheet; `False` when a sheet is already there (it holds the runs, so it is
    never overwritten)."""
    if path.exists():
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_template(draw), encoding="utf-8")
    return True
