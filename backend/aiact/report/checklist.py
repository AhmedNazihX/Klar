"""The obligations checklist (P24; artboard `Obligations`, "Take the checklist with you"): every
duty of every classified tool with its provision, its date and whether the user ticked it off,
as a `Paper`.

Each tool comes as the inventory report's summary of its stored result (`InventoryTool`), each
duty with its ticked state. The labels are the obligations table's, found as in the inventory
report (`listed_duty`): a posted duty the table lacks is left out and counted, so no posted label
is ever printed (decision 031). The ticked state is the user's own: the counts say how many duties
they ticked off, and the checklist says that Klar doesn't check the work (decision 026 item 9).
An informational duty has nothing to tick off: it is listed without a state and never counted.
The dates are the stored results' own, as on the inventory report.
"""

from datetime import date
from typing import NamedTuple

from pydantic import Field

from aiact.export import Block, Heading, Note, Paper, Paragraph, Table
from aiact.provision_names import article_provision_name
from aiact.report import texts
from aiact.report.common import class_name, day, duty_timing, footer, left_out_note
from aiact.report.inventory import (
    InventoryDuty,
    InventoryTool,
    ListedDuty,
    listed_duty,
    tool_name,
)
from aiact.schemas import Language, RiskClass, Status

CHECKLIST_WIDTHS = (0.9, 3.0, 1.0, 1.3)


class ChecklistDuty(InventoryDuty):
    """A tool's duty, and whether the user ticked it off."""

    is_done: bool = Field(default=False, description="The user ticked the duty off.")


class ChecklistTool(InventoryTool):
    """A tool of the inventory, its stored result summarised, each duty with its ticked state."""

    # A narrower duty type: the model is frozen, so nothing can put a plain InventoryDuty back.
    duties: tuple[ChecklistDuty, ...] = Field(  # pyright: ignore[reportIncompatibleVariableOverride]
        default=(), max_length=InventoryTool.MAX_DUTIES
    )


class _Ticked(NamedTuple):
    """A duty the table has, and whether the user ticked it off."""

    duty: ListedDuty
    is_done: bool


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
    return tuple(_Ticked(duty, is_done) for duty, is_done in found if duty is not None)


def _progress(duties: tuple[_Ticked, ...]) -> _Progress:
    """Ticked and tickable duties: an informational one has nothing to tick off."""
    tickable = tuple(duty for duty in duties if not duty.duty.timing.is_informational)
    return _Progress(done=sum(duty.is_done for duty in tickable), total=len(tickable))


def _tool_blocks(
    tool: ChecklistTool, duties: tuple[_Ticked, ...], language: Language
) -> tuple[Block, ...]:
    """A tool's heading, its class, role and progress, what a prohibited or assumed class says
    first, its duties and how many posted duties the table lacks."""
    progress = _progress(duties)
    summary = class_name(tool.risk_class, tool.status, language)
    if tool.role is not None:
        summary = f"{summary}, {texts.ROLE_NAMES[tool.role][language]}"
    done = texts.DONE_COUNT[language].format(done=progress.done, total=progress.total)
    lines: list[Block] = [Heading(tool_name(tool, language)), Paragraph(f"{summary}. {done}")]
    if tool.risk_class is RiskClass.PROHIBITED:
        lines.append(Paragraph(f"{texts.STOP_USING[language]}."))
    if tool.status not in (None, Status.DECIDED):
        lines.append(Paragraph(texts.STRICTER_READING[language]))
    notes = left_out_note(len(tool.duties) - len(duties), language)
    if not duties:
        return (*lines, *(notes or (Paragraph(texts.NO_DUTIES[language]),)))
    return (*lines, _table(duties, language), *notes)


def _table(duties: tuple[_Ticked, ...], language: Language) -> Table:
    """One row per duty: its ticked state (none for an informational one), label, provision and
    date."""
    rows = tuple(
        (
            texts.NOTHING
            if ticked.duty.timing.is_informational
            else texts.DONE_STATES[ticked.is_done][language],
            ticked.duty.label,
            article_provision_name(ticked.duty.timing.article, language),
            duty_timing(ticked.duty.timing.applies_from, ticked.duty.timing.legacy, language),
        )
        for ticked in duties
    )
    header = (
        texts.STATE_HEADER[language],
        *(column[language] for column in texts.DUTY_HEADER),
        texts.FROM_HEADER[language],
    )
    return Table(header, rows, CHECKLIST_WIDTHS)
