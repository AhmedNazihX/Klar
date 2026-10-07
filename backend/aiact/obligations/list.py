"""`list_obligations`: the duties and dates for a role and risk class (story C7; INIT > Scope).

The table lives in `supabase/seed/obligations.yaml`, which is also the source of the database seed
(`aiact.obligations.seed`). No model is involved: this is a plain lookup. Each duty carries the
screens' texts (C9): a short label in English and German, the formal duty in German, the provider
layout's group and the drafting template it links to.

Art. 111(2) (C7b, decision 022) is applied on top of the table: a high-risk system placed on the
market or put into service before its route's Chapter III date keeps its class, but its high-risk
duties (the rows dated per route) apply only after a significant change to its design or
intended purpose on or after that date, or, for a system meant for public authorities, from
2 Aug 2030 for its providers and deployers (the article's own words).
"""

from collections.abc import Mapping
from datetime import date
from functools import cache
from pathlib import Path
from typing import Self

import yaml
from pydantic import Field, ValidationError, model_validator

from aiact.schemas import (
    DISCLAIMER,
    HighRiskRoute,
    Language,
    LawVersion,
    LegacyStatus,
    Obligation,
    ObligationGroup,
    RiskClass,
    Role,
)
from aiact.schemas.base import ContractModel
from aiact.schemas.obligations import DOCUMENT_KEY_PATTERN
from aiact.settings import BACKEND_DIR

OBLIGATIONS_FILE = BACKEND_DIR.parent / "supabase" / "seed" / "obligations.yaml"
"""The committed obligations table."""

KEY_PATTERN = r"^[a-z0-9]+(-[a-z0-9]+)*$"

CHAPTER_III_DATES: Mapping[HighRiskRoute, date] = {
    HighRiskRoute.ANNEX_III: date(2027, 12, 2),
    HighRiskRoute.ANNEX_I: date(2028, 8, 2),
}
"""The date Chapter III applies from on each route (Art. 113(c)(i) and (ii)); the table's route
dates are these, and Art. 111(2) counts a legacy system from them."""

PUBLIC_AUTHORITY_DEADLINE = date(2030, 8, 2)
"""Art. 111(2), second sentence: providers and deployers of legacy high-risk systems meant for
public authorities comply by this date; importers and distributors keep the first sentence's
rule."""

LEGACY_ARTICLE = "art:111:2"
PUBLIC_AUTHORITY_ROLES = frozenset({Role.PROVIDER, Role.DEPLOYER})
"""The roles the 2030 date names. The German recital 177 agrees ("Betreiber"); only the English
recital's "operators" is wider, an outlier the user set aside on 2026-10-01."""
SUBSTANTIAL_MODIFICATION_ARTICLE = "art:3:23"
"""What a significant change means under Art. 111(2) (recital 177: equivalent in substance)."""


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
    duty_de: str = Field(min_length=1)
    label_en: str = Field(min_length=1)
    label_de: str = Field(min_length=1)
    group: ObligationGroup | None = None
    document: str | None = Field(default=None, pattern=DOCUMENT_KEY_PATTERN)
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
        self._check_group()
        if isinstance(self.applies_from, Mapping):
            if not self.applies_from:
                raise ValueError(f"{self.key}: applies_from needs at least one route")
            if set(self.risk_classes) != {RiskClass.HIGH_RISK}:
                raise ValueError(f"{self.key}: dates per route are only for high-risk-only entries")
        if RiskClass.OUT_OF_SCOPE in self.risk_classes:
            raise ValueError(f"{self.key}: an out_of_scope system has no obligations")
        return self

    def _check_group(self) -> None:
        """A group is for provider duties, and every high-risk provider duty has one."""
        is_provider = Role.PROVIDER in self.roles
        if self.group is not None and not is_provider:
            raise ValueError(f"{self.key}: a group is only for provider duties")
        if self.group is None and is_provider and RiskClass.HIGH_RISK in self.risk_classes:
            raise ValueError(f"{self.key}: a high-risk provider duty needs a group")

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
                    duty_de=entry.duty_de,
                    label_en=entry.label_en,
                    label_de=entry.label_de,
                    group=entry.group,
                    document=entry.document,
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


def legacy_status(
    *, placed_before: bool, significantly_changed: bool, for_public_authority: bool
) -> LegacyStatus | None:
    """Art. 111(2) for a high-risk system: None when it was placed on the market or put into
    service on or after its route's Chapter III date (`placed_before` False), or its design
    changes significantly from that date; then its duties apply as usual."""
    if not placed_before or significantly_changed:
        return None
    return LegacyStatus.PUBLIC_AUTHORITY if for_public_authority else LegacyStatus.UNCHANGED


def _with_legacy(obligation: Obligation, role: Role, legacy: LegacyStatus | None) -> Obligation:
    """The duty as Art. 111(2) leaves it: only the high-risk rows, the ones dated per route, are
    marked; the public-authority date replaces `applies_from` for providers and deployers, and an
    importer or distributor of such a system gets the ordinary marking."""
    if legacy is None or obligation.high_risk_route is None:
        return obligation
    if legacy is LegacyStatus.PUBLIC_AUTHORITY and role in PUBLIC_AUTHORITY_ROLES:
        update = {"legacy": legacy, "applies_from": PUBLIC_AUTHORITY_DEADLINE}
        return obligation.model_copy(update=update)
    return obligation.model_copy(update={"legacy": LegacyStatus.UNCHANGED})


class ObligationList(ContractModel):
    """The duties `list_obligations` found, with the law version they come from and the notice."""

    law_version: LawVersion
    obligations: tuple[Obligation, ...]
    disclaimer: str


def list_obligations(
    role: Role | str,
    risk_class: RiskClass | str,
    route: HighRiskRoute | str | None = None,
    law_version: LawVersion | str = LawVersion.AMENDED,
    table: ObligationTable | None = None,
    *,
    language: Language | str = Language.EN,
    legacy: LegacyStatus | str | None = None,
) -> ObligationList:
    """The duties of `role` for a system of `risk_class`, in table order.

    For a high-risk system, `route` picks the dates of that route (Annex III or Annex I); without
    it, route-dependent duties appear once per route, each tagged with its `high_risk_route`.
    Duties that exist on one route only are left out for the other. Plain strings are accepted
    for the enums; an unknown value raises ValueError, and a law version the table doesn't hold
    raises UnknownLawVersionError. `language` picks the notice's language (each duty carries its
    label and formal wording in both English and German). `legacy` (see `legacy_status`) marks
    the high-risk duties of a system Art. 111(2) covers; the class and the other duties stay as
    they are.
    """
    role, risk_class, version = Role(role), RiskClass(risk_class), LawVersion(law_version)
    status = LegacyStatus(legacy) if legacy is not None else None
    notice = DISCLAIMER[Language(language)]
    wanted_route = HighRiskRoute(route) if route is not None else None
    source = table or default_table()
    if source.law_version != version:
        raise UnknownLawVersionError(
            f"the obligations table holds the {source.law_version.value} text, not {version.value}"
        )
    obligations = tuple(
        _with_legacy(row.obligation, role, status)
        for row in source.rows()
        if row.role == role
        and row.risk_class == risk_class
        and (wanted_route is None or row.obligation.high_risk_route in (None, wanted_route))
    )
    return ObligationList(
        law_version=source.law_version, obligations=obligations, disclaimer=notice
    )
