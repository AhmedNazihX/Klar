"""Documentation drafting (INIT > Documentation drafting): the short deployer documents drafted
from a classification result and the user's interview answers, and the three automatic checks
(P8a). Every draft is labelled DRAFT and carries the "guidance, not legal advice" notice."""

from aiact.drafting.checks import (
    CHECK_LABELS,
    CheckName,
    CheckResult,
    check_facts_match,
    check_nothing_invented,
    check_sections_present,
    run_checks,
)
from aiact.drafting.deployer import (
    Answers,
    UnknownQuestionError,
    deployer_templates_for,
    draft_deployer_documents,
    draft_document,
)
from aiact.drafting.models import DraftDocument, DraftSection, DraftStatus, Provenance
from aiact.drafting.templates import DEPLOYER_TEMPLATES, TEMPLATES, DocumentTemplate

__all__ = [
    "CHECK_LABELS",
    "DEPLOYER_TEMPLATES",
    "TEMPLATES",
    "Answers",
    "CheckName",
    "CheckResult",
    "DocumentTemplate",
    "DraftDocument",
    "DraftSection",
    "DraftStatus",
    "Provenance",
    "UnknownQuestionError",
    "check_facts_match",
    "check_nothing_invented",
    "check_sections_present",
    "deployer_templates_for",
    "draft_deployer_documents",
    "draft_document",
    "run_checks",
]
