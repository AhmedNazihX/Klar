"""The fixed vocabularies of a result (INIT > How it works)."""

from enum import StrEnum


class RiskClass(StrEnum):
    """The headline class. Every result carries exactly one."""

    OUT_OF_SCOPE = "out_of_scope"
    PROHIBITED = "prohibited"
    HIGH_RISK = "high_risk"
    LIMITED_RISK = "limited_risk"
    MINIMAL_RISK = "minimal_risk"


class Status(StrEnum):
    """Whether a step or result is settled. The two uncertain values are not risk classes."""

    DECIDED = "decided"
    NEEDS_MORE_INFORMATION = "needs_more_information"
    LEGALLY_AMBIGUOUS = "legally_ambiguous"


class EvidenceTag(StrEnum):
    """Where a fact came from; used instead of a numeric confidence score."""

    STATED = "stated"
    INFERRED = "inferred"
    ASSUMED = "assumed"


class Role(StrEnum):
    """The operator role the obligations follow from (Art. 3, 16, 23-26)."""

    PROVIDER = "provider"
    DEPLOYER = "deployer"
    IMPORTER = "importer"
    DISTRIBUTOR = "distributor"


class HighRiskRoute(StrEnum):
    """How a system became high-risk; the two routes have different dates (Art. 113(c))."""

    ANNEX_III = "annex_iii"
    ANNEX_I = "annex_i"


class LegacyStatus(StrEnum):
    """How Art. 111(2) treats a high-risk system placed on the market or put into service before
    its route's Chapter III date, with no significant change planned from that date."""

    UNCHANGED = "legacy_unchanged"
    """Its high-risk duties apply only after a significant change to its design or purpose."""
    PUBLIC_AUTHORITY = "legacy_public_authority"
    """Meant for public authorities: every operator complies by 2 Aug 2030."""


class LawVersion(StrEnum):
    """The AI Act text a result relies on: as published in 2024, or as amended by the Omnibus."""

    ORIGINAL = "original"
    AMENDED = "amended"


class DocumentStatus(StrEnum):
    """The status of a corpus document (matches F4's `documents.status`)."""

    FINAL = "final"
    DRAFT = "draft"
    CONSOLIDATED = "consolidated"


class Language(StrEnum):
    """The languages the assistant answers and quotes in."""

    EN = "en"
    DE = "de"
