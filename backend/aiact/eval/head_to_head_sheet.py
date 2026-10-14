"""The head-to-head answer sheet (V10a, decision 036): the user's hand runs of the Commission
checker, one entry per drawn case, in `SHEET_FILE`.

Per case the user writes the date run, the checker's result verbatim, the result's headings, the
questions the checker asked with the answers given, and optionally a screenshot's file name. The
sheet's `headings` table maps each exact heading the checker shows to what it means
(`CheckerMeaning`); `MEANING_CLASS` turns a meaning into one `RiskClass` by decision 036's fixed
table, the strictest when a result shows several. The user adds a heading's row after the first
case shows it, before any case is scored.

`check_sheet` validates the sheet against the draw: an unknown or missing case id, a run without
its date, a date in the future, a heading the table lacks or the result text doesn't contain, a
screenshot that isn't a plain file name in `SCREENSHOT_DIR` or isn't there. A meaning outside
`CheckerMeaning` (a bad class) fails parsing.
"""

import datetime as dt
import json
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
    result_text: str | None = None
    result_headings: tuple[NonEmptyText, ...] = ()
    answers: tuple[CheckerAnswer, ...] = ()
    screenshot: str | None = None

    @property
    def is_run(self) -> bool:
        return self.date is not None

    @model_validator(mode="after")
    def _empty_or_complete(self) -> Self:
        if not self.is_run:
            if self.result_text or self.result_headings or self.answers or self.screenshot:
                raise ValueError(f"{self.case_id}: missing date (the day the checker was run)")
            return self
        missing = [
            name
            for name, value in (
                ("result_text", (self.result_text or "").strip()),
                ("result_headings", self.result_headings),
                ("answers", self.answers),
            )
            if not value
        ]
        if missing:
            raise ValueError(f"{self.case_id}: run on {self.date} but missing {', '.join(missing)}")
        return self


class HeadToHeadSheet(ContractModel):
    """The content of `SHEET_FILE`."""

    headings: dict[NonEmptyText, CheckerMeaning] = Field(default_factory=dict)
    cases: tuple[CheckerRun, ...]

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


def check_sheet(
    sheet: HeadToHeadSheet, draw: Draw, today: dt.date, screenshot_dir: Path = SCREENSHOT_DIR
) -> None:
    """Raise `SheetError` listing every way the sheet doesn't fit the draw (module docstring)."""
    problems = [
        *_id_problems(sheet, draw),
        *(
            problem
            for run in sheet.cases
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
# Head-to-head (V10a, decision 036): the Commission's AI Act Service Desk checker, run by hand.
# Checker: {CHECKER_URL}
# The cases come from head_to_head_draw.json (seed and rule there). For each case, answer the
# checker's questions from the case's description (eval/cases/<set>/), then fill in:
#   date             the day you ran it (YYYY-MM-DD)
#   result_text      the checker's result, copied verbatim
#   result_headings  each outcome heading the result shows, exactly as written there
#   answers          every question the checker asked, with your answer, verbatim:
#                    - question: "..."
#                      answer: "..."
#   screenshot       optional: a file name in head_to_head/ next to this file
# headings: give every heading a case shows a row, its exact text and what it means, before any
# case is scored, for example:
#   headings:
#     "Exact heading text from the checker": high_risk
# Meanings: {", ".join(meaning.value for meaning in CheckerMeaning)}.
# Check:  uv run aiact evaluate head-to-head check
# Report: uv run aiact evaluate head-to-head render
"""


def render_template(draw: Draw) -> str:
    """A sheet with every drawn case pending, in draw order."""
    entries = "".join(
        f"  - case_id: {json.dumps(case.case_id)}\n"
        "    date: null\n"
        "    result_text: null\n"
        "    result_headings: []\n"
        "    answers: []\n"
        "    screenshot: null\n"
        for case in draw.cases
    )
    return f"{TEMPLATE_HEADER}headings: {{}}\ncases:\n{entries}"


def write_template(draw: Draw, path: Path = SHEET_FILE) -> bool:
    """Write the pending sheet; `False` when a sheet is already there (it holds the user's runs,
    so it is never overwritten)."""
    if path.exists():
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_template(draw), encoding="utf-8")
    return True
