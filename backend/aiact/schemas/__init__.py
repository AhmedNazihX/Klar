"""The result contract: risk classes, statuses and the classification result (F3)."""

from aiact.schemas.disclaimer import DISCLAIMER, DISCLAIMER_DE, DISCLAIMER_EN
from aiact.schemas.enums import EvidenceTag, Language, LawVersion, RiskClass, Role, Status
from aiact.schemas.evidence import Citation, Fact, OpenQuestion, SourceSpan
from aiact.schemas.obligations import Obligation
from aiact.schemas.result import ClassificationResult
from aiact.schemas.steps import STEP_ORDER, StepName, StepResult

__all__ = [
    "DISCLAIMER",
    "DISCLAIMER_DE",
    "DISCLAIMER_EN",
    "STEP_ORDER",
    "Citation",
    "ClassificationResult",
    "EvidenceTag",
    "Fact",
    "Language",
    "LawVersion",
    "Obligation",
    "OpenQuestion",
    "RiskClass",
    "Role",
    "SourceSpan",
    "Status",
    "StepName",
    "StepResult",
]
