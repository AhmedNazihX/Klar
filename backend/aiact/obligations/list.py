"""`list_obligations`: the duties and dates for a role and risk class (story C7; INIT > Scope).

The table lives in `supabase/seed/obligations.yaml`, which is also the source of the database seed
(`aiact.obligations.seed`). No model is involved: this is a plain lookup.
"""

from collections.abc import Mapping
from datetime import date
from functools import cache
from pathlib import Path
from typing import Self

import yaml
from pydantic import Field, ValidationError, model_validator

from aiact.schemas import HighRiskRoute, LawVersion, Obligation, RiskClass, Role
from aiact.schemas.base import ContractModel
from aiact.settings import BACKEND_DIR

OBLIGATIONS_FILE = BACKEND_DIR.parent / "supabase" / "seed" / "obligations.yaml"
"""The committed obligations table."""

KEY_PATTERN = r"^[a-z0-9]+(-[a-z0-9]+)*$"


class ObligationsError(ValueError):
    """The obligations file is missing, unreadable or breaks the table's rules."""


class UnknownLawVersionError(ObligationsError):
    """The table has no rows for the requested law version."""


class ObligationEntry(ContractModel):
    """One duty in the YAML: it may cover several roles and classes, and one date per route."""

    key: str = Field(pattern=KEY_PATTERN)
    roles: tuple[Role, ...] = Field(min_length=1)
    risk_classes: tuple[RiskClass, ...] = Field(min_length=1)
    duty: str = Field(min_length=1)
    article: str = Field(min_length=1)
    applies_from: date | Mapping[HighRiskRoute, date]
    applies_if: str | None = None
    is_informational: bool = False
    relief_note: str | None = None
    note: str | None = None

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        for name, values in (("roles", self.roles), ("risk_classes", self.risk_classes)):
            if len(set(values)) != len(values):
                raise ValueError(f"{self.key}: repeated value in {name}")
        if isinstance(self.applies_from, Mapping):
            if not self.applies_from:
                raise ValueError(f"{self.key}: applies_from needs at least one route")
            if set(self.risk_classes) != {RiskClass.HIGH_RISK}:
                raise ValueError(f"{self.key}: dates per route are only for high-risk-only entries")
        if RiskClass.OUT_OF_SCOPE in self.risk_classes:
            raise ValueError(f"{self.key}: an out_of_scope system has no obligations")
        return self

    def dated(self) -> tuple[tuple[HighRiskRoute | None, date], ...]:
        """The (route, date) pairs; route None when the date is the same for every route."""
        if isinstance(self.applies_from, Mapping):
            return tuple(sorted(self.applies_from.items()))
        return ((None, self.applies_from),)


class ObligationRow(ContractModel):
    """One row of the expanded table: one role, one class, one date."""

    key: str
    role: Role
    risk_class: RiskClass
    obligation: Obligation


class ObligationTable(ContractModel):
    """The whole table, with the law version and the date its contents were checked."""

    law_version: LawVersion
    checked_on: date
    dates_reviewed: bool
    obligations: tuple[ObligationEntry, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _unique_keys(self) -> Self:
        keys = [entry.key for entry in self.obligations]
        duplicates = sorted({key for key in keys if keys.count(key) > 1})
        if duplicates:
            raise ValueError(f"duplicate obligation keys: {', '.join(duplicates)}")
        return self

    def rows(self) -> tuple[ObligationRow, ...]:
        """Every entry expanded to one row per role, class and route, in file order."""
        return tuple(
            ObligationRow(
                key=entry.key,
                role=role,
                risk_class=risk_class,
                obligation=Obligation(
                    duty=entry.duty,
                    article=entry.article,
                    applies_from=applies_from,
                    high_risk_route=route,
                    applies_if=entry.applies_if,
                    is_informational=entry.is_informational,
                    relief_note=entry.relief_note,
                    note=entry.note,
                ),
            )
            for entry in self.obligations
            for role in entry.roles
            for risk_class in entry.risk_classes
            for route, applies_from in entry.dated()
        )


def load_table(path: Path = OBLIGATIONS_FILE) -> ObligationTable:
    """Read and validate the obligations YAML."""
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        raise ObligationsError(f"cannot read {path}: {error}") from error
    try:
        return ObligationTable.model_validate(raw)
    except ValidationError as error:
        raise ObligationsError(f"invalid obligations file {path}: {error}") from error


@cache
def default_table() -> ObligationTable:
    """The committed table, read once."""
    return load_table()


class ObligationList(ContractModel):
    """The duties `list_obligations` found, with the law version they come from."""

    law_version: LawVersion
    obligations: tuple[Obligation, ...]


def list_obligations(
    role: Role | str,
    risk_class: RiskClass | str,
    route: HighRiskRoute | str | None = None,
    law_version: LawVersion | str = LawVersion.AMENDED,
    table: ObligationTable | None = None,
) -> ObligationList:
    """The duties of `role` for a system of `risk_class`, in table order.

    For a high-risk system, `route` picks the dates of that route (Annex III or Annex I); without
    it, route-dependent duties appear once per route, each tagged with its `high_risk_route`.
    Duties that exist on one route only are left out for the other. Plain strings are accepted
    for the enums; an unknown value raises ValueError, and a law version the table doesn't hold
    raises UnknownLawVersionError.
    """
    role, risk_class, version = Role(role), RiskClass(risk_class), LawVersion(law_version)
    wanted_route = HighRiskRoute(route) if route is not None else None
    source = table or default_table()
    if source.law_version != version:
        raise UnknownLawVersionError(
            f"the obligations table holds the {source.law_version.value} text, not {version.value}"
        )
    obligations = tuple(
        row.obligation
        for row in source.rows()
        if row.role == role
        and row.risk_class == risk_class
        and (wanted_route is None or row.obligation.high_risk_route in (None, wanted_route))
    )
    return ObligationList(law_version=source.law_version, obligations=obligations)
