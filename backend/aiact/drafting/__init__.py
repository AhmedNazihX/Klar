"""Documentation drafting (INIT > Documentation drafting): the short deployer documents drafted
from a classification result and the user's interview answers, and the three automatic checks
(P8a); the skeletons of the heavy documents, each required section quoting its requirement
(P8b); the short vendor letters for a prohibited or a legally ambiguous result (P28). Every
draft is labelled DRAFT and carries the "guidance, not legal advice" notice."""

from aiact.drafting.checks import (
    CHECK_LABELS,
    CheckName,
    CheckResult,
    check_facts_match,
    check_nothing_invented,
    check_sections_present,
    run_checks,
)
from aiact.drafting.deployer import deployer_templates_for, draft_deployer_documents
from aiact.drafting.draft import Answers, UnknownQuestionError, draft_document
from aiact.drafting.models import (
    DraftDocument,
    DraftSection,
    DraftStatus,
    Provenance,
    SectionStatus,
    SizeClass,
)
from aiact.drafting.prefill import DutyDateError
from aiact.drafting.registry import TEMPLATES
from aiact.drafting.skeletons import (
    SKELETON_TEMPLATES,
    draft_skeletons,
    skeleton_templates_for,
)
from aiact.drafting.templates import DEPLOYER_TEMPLATES, DocumentTemplate
from aiact.drafting.vendor_letters.draft import (
    NoVendorLetterError,
    draft_vendor_letter,
    vendor_letter_for,
)
from aiact.drafting.vendor_letters.quotes import LawQuotes, UnknownPointError, quoted_points
from aiact.drafting.vendor_letters.templates import VENDOR_LETTER_TEMPLATES

__all__ = [
    "CHECK_LABELS",
    "DEPLOYER_TEMPLATES",
    "SKELETON_TEMPLATES",
    "TEMPLATES",
    "VENDOR_LETTER_TEMPLATES",
    "Answers",
    "CheckName",
    "CheckResult",
    "DocumentTemplate",
    "DraftDocument",
    "DraftSection",
    "DraftStatus",
    "DutyDateError",
    "LawQuotes",
    "NoVendorLetterError",
    "Provenance",
    "SectionStatus",
    "SizeClass",
    "UnknownPointError",
    "UnknownQuestionError",
    "check_facts_match",
    "check_nothing_invented",
    "check_sections_present",
    "deployer_templates_for",
    "draft_deployer_documents",
    "draft_document",
    "draft_skeletons",
    "draft_vendor_letter",
    "quoted_points",
    "run_checks",
    "skeleton_templates_for",
    "vendor_letter_for",
]
