"""A duty the result's role and class bring with them.

Minimal for now: story C7 defines the obligation rows and may extend this model.
"""

from datetime import date

from pydantic import Field

from aiact.schemas.base import ContractModel


class Obligation(ContractModel):
    """One duty with its article reference and the date it applies from."""

    duty: str = Field(min_length=1)
    article: str = Field(min_length=1, description="For example `art:26:1`.")
    applies_from: date
    note: str | None = None
