"""The inventory report (P25; artboard `YourData`, "Report (PDF): inventory, results and
duties"): every tool of the user's inventory with its class, status, role and first duty date,
then each tool's duties, as a `Paper`.

A whole inventory of full results would not fit the API's body cap (a recorded result is about
30 kB), so each tool comes as the summary its stored result gives: the class, status, role, law
version and date, and each duty's short label, article and timing, in the report's language.
These are the user's own stored data, shown as given; the report quotes no text of the Act and
names provisions in the report's citation style (decision 031).
"""

from datetime import date
from typing import Annotated, ClassVar

from pydantic import Field, StringConstraints

from aiact.export import Block, Heading, Note, Paper, Paragraph, Table
from aiact.provision_names import article_provision_name
from aiact.report import texts
from aiact.report.common import class_name, day, duties_from, duty_timing, footer
from aiact.schemas import Language, LawVersion, LegacyStatus, RiskClass, Role, Status
from aiact.schemas.base import ContractModel

ARTICLE_PATTERN = r"^art:[0-9]+[a-z]?(:[A-Za-z0-9]+)*$"
"""An obligation's article, as the result contract writes it (`Obligation.article`)."""
MAX_NAME_CHARS = 200
MAX_LABEL_CHARS = 1_000
TOOL_WIDTHS = (2.6, 2.0, 1.8, 1.3, 1.8)
DUTY_WIDTHS = (3.0, 1.0, 1.3)

Name = Annotated[str, StringConstraints(min_length=1, max_length=MAX_NAME_CHARS)]


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
    law_version: LawVersion | None = None
    as_of: date | None = Field(
        default=None, description="The date the result applies the law as of."
    )
    duties: tuple[InventoryDuty, ...] = Field(default=(), max_length=MAX_DUTIES)


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
    return Paper(
        language=language,
        kicker=texts.INVENTORY_KICKER[language],
        title=company or texts.INVENTORY_TITLE[language],
        lines=(f"{prepared} {count}",),
        blocks=(
            Note(texts.INVENTORY_NOTE[language]),
            *_overview(tools, language),
            *(block for tool in tools for block in _tool_duties(tool, language)),
        ),
        footer=footer(language),
    )


def _tool_name(tool: InventoryTool, language: Language) -> str:
    return tool.name or texts.UNNAMED_TOOL[language]


def _overview(tools: tuple[InventoryTool, ...], language: Language) -> tuple[Block, ...]:
    if not tools:
        return (Paragraph(texts.NO_TOOLS[language]),)
    rows = tuple(
        (
            _tool_name(tool, language),
            class_name(tool.risk_class, tool.status, language),
            texts.STATUS_NAMES[tool.status][language] if tool.status else texts.NOTHING,
            texts.ROLE_NAMES[tool.role][language] if tool.role else texts.NOTHING,
            _first_date(tool, language),
        )
        for tool in tools
    )
    header = tuple(column[language] for column in texts.INVENTORY_HEADER)
    return (Table(header, rows, TOOL_WIDTHS),)


def _first_date(tool: InventoryTool, language: Language) -> str:
    if tool.risk_class is None:
        return texts.NOTHING
    return duties_from(((duty.applies_from, duty.legacy) for duty in tool.duties), language)


def _tool_duties(tool: InventoryTool, language: Language) -> tuple[Block, ...]:
    """A classified tool's heading, the law it was checked under, and its duties."""
    if tool.risk_class is None:
        return ()
    law = ()
    if tool.law_version is not None and tool.as_of is not None:
        line = texts.TOOL_LAW[tool.law_version is LawVersion.AMENDED][language]
        law = (Paragraph(line.format(as_of=day(tool.as_of, language))),)
    heading = Heading(_tool_name(tool, language))
    if not tool.duties:
        return (heading, *law, Paragraph(texts.NO_DUTIES[language]))
    rows = tuple(
        (
            duty.label,
            article_provision_name(duty.article, language),
            duty_timing(duty.applies_from, duty.legacy, language),
        )
        for duty in tool.duties
    )
    header = (*(column[language] for column in texts.DUTY_HEADER), texts.FROM_HEADER[language])
    return (heading, *law, Table(header, rows, DUTY_WIDTHS))
