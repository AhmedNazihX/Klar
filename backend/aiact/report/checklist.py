"""The obligations checklist (P24; artboard `Obligations`, "Take the checklist with you"): every
duty of every classified tool with its provision, its date and whether the user ticked it off,
as a `Paper`.

Each tool comes as the inventory report's summary of its stored result (`InventoryTool`), each
duty with its ticked state. The labels are the obligations table's, found as in the inventory
report (`listed_duty`): a posted duty the table lacks is left out and counted, so no posted label
is ever printed (decision 031). The ticked state is the user's own: the counts say how many duties
they ticked off, and the checklist says that Klar doesn't check the work (decision 026 item 9).
A duty with nothing to tick off is listed without a state and never counted, as on the screen:
an informational one, or one the screen sent without a state (`is_done` null: a duty stored
before duties carried their key, which the screen can't tick). The dates are the stored results'
own, as on the inventory report. The rest of a tool's block is the inventory report's
(`common`): its stop line, its duty cells and what closes its list.
"""

from datetime import date
from typing import NamedTuple

from pydantic import Field

from aiact.export import Block, Heading, Note, Paper, Paragraph, Table
from aiact.report import texts
from aiact.report.common import (
    after_duties,
    class_name,
    day,
    duty_cells,
    duty_header,
    footer,
    stop_line,
)
from aiact.report.inventory import (
    InventoryDuty,
    InventoryTool,
    ListedDuty,
    listed_duty,
    tool_name,
)
from aiact.schemas import Language, Status

CHECKLIST_WIDTHS = (0.9, 3.0, 1.0, 1.3)


class ChecklistDuty(InventoryDuty):
    """A tool's duty, and whether the user ticked it off."""

    is_done: bool | None = Field(
        default=False,
        description="The user ticked the duty off; null when it has nothing to tick off (a "
        "duty without its key, stored before duties carried one), so it isn't counted.",
    )


class ChecklistTool(InventoryTool):
    """A tool of the inventory, its stored result summarised, each duty with its ticked state."""

    # A narrower duty type: the model is frozen, so nothing can put a plain InventoryDuty back.
    duties: tuple[ChecklistDuty, ...] = Field(  # pyright: ignore[reportIncompatibleVariableOverride]
        default=(), max_length=InventoryTool.MAX_DUTIES
    )


class _Ticked(NamedTuple):
    """A duty the table has, and its ticked state; None when it has nothing to tick off."""

    duty: ListedDuty
    is_done: bool | None


class _Progress(NamedTuple):
    done: int
    total: int


def checklist_report(
    tools: tuple[ChecklistTool, ...],
    *,
    language: Language,
    prepared_on: date,
    company: str | None = None,
) -> Paper:
    """The checklist in `language`: the overall progress, then each classified tool with its
    progress and its duties' ticked state. A tool without a class has no duties to list."""
    listed = tuple((tool, _ticked(tool, language)) for tool in tools if tool.risk_class)
    overall = _progress(tuple(duty for _, duties in listed for duty in duties))
    prepared = texts.PREPARED[language].format(date=day(prepared_on, language))
    done = texts.DONE_COUNT[language].format(done=overall.done, total=overall.total)
    tool_blocks = tuple(
        block for tool, duties in listed for block in _tool_blocks(tool, duties, language)
    )
    return Paper(
        language=language,
        kicker=texts.CHECKLIST_KICKER[language],
        title=company or texts.CHECKLIST_TITLE[language],
        lines=(f"{prepared} {done}",),
        blocks=(
            Note(f"{texts.NOT_CHECKED_WORK[language]} {texts.CHECKLIST_NOTE[language]}"),
            *(tool_blocks or (Paragraph(texts.NO_TOOLS[language]),)),
        ),
        footer=footer(language),
    )


def _ticked(tool: ChecklistTool, language: Language) -> tuple[_Ticked, ...]:
    found = ((listed_duty(tool, duty, language), duty.is_done) for duty in tool.duties)
    return tuple(
        _Ticked(duty, None if duty.timing.is_informational else is_done)
        for duty, is_done in found
        if duty is not None
    )


def _progress(duties: tuple[_Ticked, ...]) -> _Progress:
    """Ticked duties of those with something to tick off."""
    states = tuple(duty.is_done for duty in duties if duty.is_done is not None)
    return _Progress(done=sum(states), total=len(states))


def _tool_blocks(
    tool: ChecklistTool, duties: tuple[_Ticked, ...], language: Language
) -> tuple[Block, ...]:
    """A tool's heading, its class, role and progress, its stop line or what an assumed class
    says, its duties and what closes the list."""
    progress = _progress(duties)
    summary = class_name(tool.risk_class, tool.status, language)
    if tool.role is not None:
        summary = f"{summary}, {texts.ROLE_NAMES[tool.role][language]}"
    done = texts.DONE_COUNT[language].format(done=progress.done, total=progress.total)
    stricter = (
        ()
        if tool.status in (None, Status.DECIDED)
        else (Paragraph(texts.STRICTER_READING[language]),)
    )
    opening = (
        Heading(tool_name(tool, language)),
        Paragraph(f"{summary}. {done}"),
        *stop_line(tool.risk_class, language),
        *stricter,
    )
    closing = after_duties(
        has_duties=bool(duties),
        left_out=len(tool.duties) - len(duties),
        risk_class=tool.risk_class,
        language=language,
    )
    if not duties:
        return (*opening, *closing)
    return (*opening, _table(duties, language), *closing)


def _table(duties: tuple[_Ticked, ...], language: Language) -> Table:
    """The inventory report's duty rows, each after its ticked state (none when it has nothing
    to tick off)."""
    rows = tuple(
        (
            texts.NOTHING
            if ticked.is_done is None
            else texts.DONE_STATES[ticked.is_done][language],
            *duty_cells(ticked.duty.label, ticked.duty.timing, language),
        )
        for ticked in duties
    )
    return Table((texts.STATE_HEADER[language], *duty_header(language)), rows, CHECKLIST_WIDTHS)
