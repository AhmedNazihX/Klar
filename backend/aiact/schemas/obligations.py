"""A duty the result's role and class bring with them (rows: supabase/seed/obligations.yaml)."""

from datetime import date

from pydantic import Field

from aiact.schemas.base import ContractModel
from aiact.schemas.enums import HighRiskRoute


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
    relief_note: str | None = Field(
        default=None, description="Relief for SMEs, start-ups and small mid-caps (SMCs), if any."
    )
    note: str | None = None
