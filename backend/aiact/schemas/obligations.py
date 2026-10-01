"""A duty the result's role and class bring with them (rows: supabase/seed/obligations.yaml)."""

from datetime import date

from pydantic import Field

from aiact.schemas.base import ContractModel
from aiact.schemas.enums import HighRiskRoute, LegacyStatus


class Obligation(ContractModel):
    """One duty with its article reference and the date it applies from."""

    duty: str = Field(min_length=1)
    article: str = Field(
        min_length=1, pattern=r"^art:[0-9]+[a-z]?(:[A-Za-z0-9]+)*$", description="E.g. `art:26:1`."
    )
    applies_from: date
    high_risk_route: HighRiskRoute | None = Field(
        default=None,
        description="The high-risk route `applies_from` belongs to; None when the date is the same "
        "for every route (or the class is not high-risk).",
    )
    applies_if: str | None = Field(
        default=None,
        description="The condition under which the duty applies; None when it applies to every "
        "system of this role and class.",
    )
    is_informational: bool = Field(
        default=False,
        description="True when the row informs (e.g. a distributor of a prohibited system) rather "
        "than stating a formal duty the Act puts on this role.",
    )
    legacy: LegacyStatus | None = Field(
        default=None,
        description="Art. 111(2) for a system on the market or in use before its route's date: "
        "`legacy_unchanged` means the duty applies only after a significant change to the "
        "system's design or purpose; "
        "`legacy_public_authority` means it applies from 2 Aug 2030 (`applies_from`). None when "
        "the system is not such a legacy system or the duty is not a high-risk one.",
    )
    relief_note: str | None = Field(
        default=None, description="Relief for SMEs, start-ups and small mid-caps (SMCs), if any."
    )
    note: str | None = None
