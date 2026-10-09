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
(`tool_duties_from`), from the duties the table has: a prohibited tool's line says to stop using
or supplying it.
"""

from collections.abc import Mapping
from datetime import date
from typing import ClassVar, NamedTuple

from pydantic import Field

from aiact.export import Block, Heading, Note, Paper, Paragraph, Table
from aiact.provision_names import article_provision_name
from aiact.report import texts
from aiact.report.common import (
    MAX_NAME_CHARS,
    Name,
    class_name,
    day,
    duty_timing,
    footer,
    tool_duties_from,
)
from aiact.report.duties import DutyTiming, table_entry
from aiact.schemas import Language, LawVersion, LegacyStatus, RiskClass, Role, Status
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


class _Duty(NamedTuple):
    """A tool's duty as the report shows it: the table's label and what dates it."""

    label: str
    timing: DutyTiming


class _Duties(NamedTuple):
    """A tool's duties the table has, and how many posted ones it lacks."""

    found: tuple[_Duty, ...]
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
    found = tuple(
        duty for duty in (_duty(tool, posted, language) for posted in tool.duties) if duty
    )
    return _Duties(found=found, left_out=len(tool.duties) - len(found))


def _duty(tool: InventoryTool, duty: InventoryDuty, language: Language) -> _Duty | None:
    """The duty with the table's label and markings, when the table has it for this tool's
    class, roles and law version; else None."""
    roles = tuple(role for role in (tool.role, tool.also_role) if role is not None)
    if tool.risk_class is None or not roles or tool.law_version is None:
        return None
    entry = table_entry(
        duty.article,
        (duty.label,),
        risk_class=tool.risk_class,
        roles=roles,
        law_version=tool.law_version,
    )
    if entry is None:
        return None
    timing = DutyTiming(
        article=duty.article,
        applies_from=duty.applies_from,
        legacy=duty.legacy,
        is_route_duty=isinstance(entry.applies_from, Mapping),
        is_informational=entry.is_informational,
    )
    return _Duty(label=entry.label_de if language is Language.DE else entry.label_en, timing=timing)


def _tool_name(tool: InventoryTool, language: Language) -> str:
    return tool.name or texts.UNNAMED_TOOL[language]


def _overview(
    listed: tuple[tuple[InventoryTool, _Duties], ...], language: Language
) -> tuple[Block, ...]:
    if not listed:
        return (Paragraph(texts.NO_TOOLS[language]),)
    rows = tuple(
        (
            _tool_name(tool, language),
            class_name(tool.risk_class, tool.status, language),
            texts.STATUS_NAMES[tool.status][language] if tool.status else texts.NOTHING,
            texts.ROLE_NAMES[tool.role][language] if tool.role else texts.NOTHING,
            tool_duties_from(
                tool.risk_class, tuple(duty.timing for duty in duties.found), language
            ),
        )
        for tool, duties in listed
    )
    header = tuple(column[language] for column in texts.INVENTORY_HEADER)
    return (Table(header, rows, TOOL_WIDTHS),)


def _tool_duties(tool: InventoryTool, duties: _Duties, language: Language) -> tuple[Block, ...]:
    """A classified tool's heading, the law it was checked under, and its duties; a prohibited
    tool's says to stop using or supplying it first. Then how many posted duties the table
    lacks, when any."""
    if tool.risk_class is None:
        return ()
    law: tuple[Block, ...] = ()
    if tool.law_version is not None and tool.as_of is not None:
        line = texts.TOOL_LAW[tool.law_version is LawVersion.AMENDED][language]
        law = (Paragraph(line.format(as_of=day(tool.as_of, language))),)
    if tool.risk_class is RiskClass.PROHIBITED:
        law = (*law, Paragraph(f"{texts.STOP_USING[language]}."))
    heading = Heading(_tool_name(tool, language))
    left_out = duties.left_out
    notes = (
        (Paragraph(texts.LEFT_OUT[left_out == 1][language].format(count=left_out)),)
        if left_out
        else ()
    )
    if not duties.found:
        if tool.risk_class is RiskClass.PROHIBITED:
            return (heading, *law, *notes)
        return (heading, *law, Paragraph(texts.NO_DUTIES[language]), *notes)
    rows = tuple(
        (
            duty.label,
            article_provision_name(duty.timing.article, language),
            duty_timing(duty.timing.applies_from, duty.timing.legacy, language),
        )
        for duty in duties.found
    )
    header = (*(column[language] for column in texts.DUTY_HEADER), texts.FROM_HEADER[language])
    return (heading, *law, Table(header, rows, DUTY_WIDTHS), *notes)
