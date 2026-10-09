"""The inventory report (P25; artboard `YourData`, "Report (PDF): inventory, results and
duties"): every tool of the user's inventory with its class, status, role and first duty date,
then each tool's duties, as a `Paper`.

A whole inventory of full results would not fit the API's body cap (a recorded result is about
30 kB), so each tool comes as the summary its stored result gives: the class, status, role, law
version and date, and each duty's short label, article and timing, in the report's language.
These are the user's own stored data. A duty's label is the obligations table's, found by the
tool's class, roles (its role and the one it also has), the duty's article and the law version
(`aiact.report.duties`); a posted duty the table lacks is left out and counted, as in the report
for a lawyer, so no posted label is ever printed (decision 031). The report quotes no text of the
Act and names provisions in the report's citation style. The dates follow the inventory screen
(`tool_duties_from`), from the duties the table has only, with the table's route and
informational markings and each duty's posted date and Art. 111(2) marking: a posted duty the
table lacks is counted, never dated, so a tool none of whose duties the table has gets an empty
date cell. A prohibited tool's line says to stop using or supplying it.
"""

from collections.abc import Mapping
from datetime import date
from typing import ClassVar, NamedTuple

from pydantic import Field

from aiact.export import Block, Heading, Note, Paper, Paragraph, Table
from aiact.obligations.list import ObligationEntry
from aiact.report import texts
from aiact.report.common import (
    MAX_NAME_CHARS,
    Name,
    after_duties,
    class_name,
    day,
    duty_cells,
    duty_header,
    footer,
    stop_line,
    tool_duties_from,
)
from aiact.report.duties import DutyTiming, table_entry
from aiact.schemas import HighRiskRoute, Language, LawVersion, LegacyStatus, RiskClass, Role, Status
from aiact.schemas.base import ContractModel
from aiact.schemas.obligations import ARTICLE_PATTERN

MAX_LABEL_CHARS = 1_000
TOOL_WIDTHS = (2.6, 2.0, 1.8, 1.3, 1.8)
DUTY_WIDTHS = (3.0, 1.0, 1.3)


class InventoryDuty(ContractModel):
    """One duty of a tool's stored result, as the report lists it."""

    label: str = Field(
        min_length=1,
        max_length=MAX_LABEL_CHARS,
        description="The duty's short label in the report's language (`label_en`, `label_de`).",
    )
    article: str = Field(pattern=ARTICLE_PATTERN, max_length=MAX_NAME_CHARS)
    applies_from: date
    legacy: LegacyStatus | None = None


class InventoryTool(ContractModel):
    """One tool of the inventory and the summary of its latest stored result; a tool with no
    result Klar can read has no class."""

    MAX_DUTIES: ClassVar[int] = 100
    """Well above the most duties a result lists (a provider that also deploys)."""

    name: Name | None = Field(
        default=None, description='Null when the user gave none: "Your tool".'
    )
    risk_class: RiskClass | None = None
    status: Status | None = None
    role: Role | None = None
    also_role: Role | None = Field(
        default=None, description="The tool's second role, when the result gives one."
    )
    law_version: LawVersion | None = None
    as_of: date | None = Field(
        default=None, description="The date the result applies the law as of."
    )
    duties: tuple[InventoryDuty, ...] = Field(default=(), max_length=MAX_DUTIES)


class ListedDuty(NamedTuple):
    """A tool's duty as a report shows it: the table's label and what dates it."""

    label: str
    timing: DutyTiming


class _Duties(NamedTuple):
    """A tool's duties the table has, and how many posted ones it lacks."""

    found: tuple[ListedDuty, ...]
    left_out: int


def inventory_report(
    tools: tuple[InventoryTool, ...],
    *,
    language: Language,
    prepared_on: date,
    company: str | None = None,
) -> Paper:
    """The inventory as a report in `language`: the overview table, then each tool's duties."""
    count = texts.TOOL_COUNT[len(tools) == 1][language].format(count=len(tools))
    prepared = texts.PREPARED[language].format(date=day(prepared_on, language))
    listed = tuple((tool, _duties(tool, language)) for tool in tools)
    return Paper(
        language=language,
        kicker=texts.INVENTORY_KICKER[language],
        title=company or texts.INVENTORY_TITLE[language],
        lines=(f"{prepared} {count}",),
        blocks=(
            Note(texts.INVENTORY_NOTE[language]),
            *_overview(listed, language),
            *(block for tool, duties in listed for block in _tool_duties(tool, duties, language)),
        ),
        footer=footer(language),
    )


def _duties(tool: InventoryTool, language: Language) -> _Duties:
    listed = (listed_duty(tool, posted, language) for posted in tool.duties)
    found = tuple(duty for duty in listed if duty is not None)
    return _Duties(found=found, left_out=len(tool.duties) - len(found))


def listed_duty(tool: InventoryTool, duty: InventoryDuty, language: Language) -> ListedDuty | None:
    """The duty as a report lists it, when the table has it; else None (left out, counted)."""
    entry = _entry(tool, duty)
    return None if entry is None else _found(duty, entry, language)


def _entry(tool: InventoryTool, duty: InventoryDuty) -> ObligationEntry | None:
    """The table's entry for the duty, when the table has it for this tool's class, roles and
    law version; else None."""
    roles = tuple(role for role in (tool.role, tool.also_role) if role is not None)
    if tool.risk_class is None or not roles or tool.law_version is None:
        return None
    return table_entry(
        duty.article,
        (duty.label,),
        risk_class=tool.risk_class,
        roles=roles,
        law_version=tool.law_version,
    )


def _found(duty: InventoryDuty, entry: ObligationEntry, language: Language) -> ListedDuty:
    """A duty the table has: the table's label and route and informational markings, with the
    posted date and Art. 111(2) marking."""
    timing = DutyTiming(
        article=duty.article,
        applies_from=duty.applies_from,
        legacy=duty.legacy,
        is_route_duty=isinstance(entry.applies_from, Mapping),
        is_informational=entry.is_informational,
        route=_route(entry, duty.applies_from),
    )
    return ListedDuty(
        label=entry.label_de if language is Language.DE else entry.label_en, timing=timing
    )


def _route(entry: ObligationEntry, applies_from: date) -> HighRiskRoute | None:
    """The route whose table date the posted duty carries, for a duty the table dates per
    route; None for another duty, or a date that is no route's (an Art. 111(2) one)."""
    if not isinstance(entry.applies_from, Mapping):
        return None
    routes = [route for route, start in entry.applies_from.items() if start == applies_from]
    return routes[0] if len(routes) == 1 else None


def tool_law(tool: InventoryTool, language: Language) -> tuple[Paragraph, ...]:
    """The law text the tool's result was checked under, and as of when; nothing without one."""
    if tool.law_version is None or tool.as_of is None:
        return ()
    line = texts.TOOL_LAW[tool.law_version is LawVersion.AMENDED][language]
    return (Paragraph(line.format(as_of=day(tool.as_of, language))),)


def tool_name(tool: InventoryTool, language: Language) -> str:
    """The tool's name, or "Your tool" in the report's language."""
    return tool.name or texts.UNNAMED_TOOL[language]


def _overview(
    listed: tuple[tuple[InventoryTool, _Duties], ...], language: Language
) -> tuple[Block, ...]:
    if not listed:
        return (Paragraph(texts.NO_TOOLS[language]),)
    rows = tuple(
        (
            tool_name(tool, language),
            class_name(tool.risk_class, tool.status, language),
            texts.STATUS_NAMES[tool.status][language] if tool.status else texts.NOTHING,
            texts.ROLE_NAMES[tool.role][language] if tool.role else texts.NOTHING,
            _duties_from(tool, duties, language),
        )
        for tool, duties in listed
    )
    header = tuple(column[language] for column in texts.INVENTORY_HEADER)
    return (Table(header, rows, TOOL_WIDTHS),)


def _duties_from(tool: InventoryTool, duties: _Duties, language: Language) -> str:
    """When the tool's duties apply, from the duties the table has only; an empty cell when it
    lists duties but the table has none of them (they are counted, never dated)."""
    if duties.left_out and not duties.found and tool.risk_class is not RiskClass.PROHIBITED:
        return texts.NOTHING
    return tool_duties_from(tool.risk_class, tuple(duty.timing for duty in duties.found), language)


def _tool_duties(tool: InventoryTool, duties: _Duties, language: Language) -> tuple[Block, ...]:
    """A classified tool's heading, the law it was checked under, and its duties; a prohibited
    tool's says to stop using or supplying it first. Then how many posted duties the table
    lacks, when any; "no specific duties" only when the result lists none at all."""
    if tool.risk_class is None:
        return ()
    heading = Heading(tool_name(tool, language))
    closing = after_duties(
        has_duties=bool(duties.found),
        left_out=duties.left_out,
        risk_class=tool.risk_class,
        language=language,
    )
    opening = (heading, *tool_law(tool, language), *stop_line(tool.risk_class, language))
    if not duties.found:
        return (*opening, *closing)
    rows = tuple(duty_cells(duty.label, duty.timing, language) for duty in duties.found)
    return (*opening, Table(duty_header(language), rows, DUTY_WIDTHS), *closing)
