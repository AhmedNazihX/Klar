"""A duty the result's role and class bring with them (rows: supabase/seed/obligations.yaml)."""

from datetime import date

from pydantic import Field, model_validator

from aiact.schemas.base import ContractModel
from aiact.schemas.enums import HighRiskRoute, LegacyStatus, ObligationGroup

DOCUMENT_KEY_PATTERN = r"^[a-z0-9]+(_[a-z0-9]+)*$"
"""A drafting template id, e.g. `art_26_2_oversight` (aiact.drafting.templates)."""

STORED_TEXT_FIELDS = ("duty_de", "label_en", "label_de")
"""The texts C9 added, which a duty stored before C9 lacks."""


class Obligation(ContractModel):
    """One duty with its article reference and the date it applies from.

    Each duty carries its texts in both languages, so a screen can switch language without a
    new lookup: a short plain label (an action, for the checklists) and the formal duty (for the
    report).
    """

    duty: str = Field(min_length=1, description="The formal duty, in English.")
    duty_de: str = Field(
        min_length=1, description="The formal duty in German, in the official German text's terms."
    )
    label_en: str = Field(
        min_length=1,
        description='A short plain label, as an action: "Keep the logs it creates for at least '
        'six months".',
    )
    label_de: str = Field(min_length=1, description="The short label in German.")
    group: ObligationGroup | None = Field(
        default=None,
        description="The provider layout's group (`build`, `prove`, `after_launch`); set on "
        "every high-risk provider duty and only on duties a provider has. A duty shared with "
        "another role keeps it there too (so a provider that also uses the system gets the duty "
        "once); only the provider layout shows it.",
    )
    document: str | None = Field(
        default=None,
        pattern=DOCUMENT_KEY_PATTERN,
        description="The drafting template that answers this duty (e.g. `art_26_2_oversight`), "
        "if any.",
    )
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

    @model_validator(mode="before")
    @classmethod
    def _fill_the_texts_of_a_stored_duty(cls, data: object) -> object:
        """A duty stored before C9 (a saved result or benchmark run) has no labels, German duty,
        group or document: they come from the current table's entry for its article (fields
        it stored win), else its English `duty` stands in for the three texts and it gets no
        group or document. Engine results always carry them, from the table."""
        if not isinstance(data, dict) or all(field in data for field in STORED_TEXT_FIELDS):
            return data
        article, duty = data.get("article"), data.get("duty")
        if not isinstance(article, str) or not isinstance(duty, str) or not duty:
            return data
        # Imported here: the obligations table module imports these schemas.
        from aiact.obligations.list import texts_for_stored_duty

        return {**texts_for_stored_duty(article, duty), **data}
