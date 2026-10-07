"""The result contract: risk classes, statuses and the classification result (F3)."""

from aiact.schemas.disclaimer import DISCLAIMER, DISCLAIMER_DE, DISCLAIMER_EN
from aiact.schemas.enums import (
    AnswerOption,
    DocumentStatus,
    EvidenceTag,
    HighRiskRoute,
    Language,
    LawVersion,
    LegacyStatus,
    ObligationGroup,
    RiskClass,
    Role,
    SettledByKind,
    Status,
)
from aiact.schemas.evidence import Citation, Fact, OpenQuestion, Reading, SettledBy, SourceSpan
from aiact.schemas.law_text import LAW_TEXTS, LawText
from aiact.schemas.obligations import Obligation
from aiact.schemas.questions import YES_NO, AnswerOutcome, FollowUpQuestion
from aiact.schemas.result import ClassificationResult
from aiact.schemas.steps import PROVIDER_REFUSAL, STEP_ORDER, StepName, StepResult

__all__ = [
    "DISCLAIMER",
    "DISCLAIMER_DE",
    "DISCLAIMER_EN",
    "LAW_TEXTS",
    "PROVIDER_REFUSAL",
    "STEP_ORDER",
    "YES_NO",
    "AnswerOption",
    "AnswerOutcome",
    "Citation",
    "ClassificationResult",
    "DocumentStatus",
    "EvidenceTag",
    "Fact",
    "FollowUpQuestion",
    "HighRiskRoute",
    "Language",
    "LawText",
    "LawVersion",
    "LegacyStatus",
    "Obligation",
    "ObligationGroup",
    "OpenQuestion",
    "Reading",
    "RiskClass",
    "Role",
    "SettledBy",
    "SettledByKind",
    "SourceSpan",
    "Status",
    "StepName",
    "StepResult",
]
