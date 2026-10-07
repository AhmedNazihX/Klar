"""What the skeletons share: the sections the engine knows, pre-filled from the result (INIT >
Documentation drafting: "Sections the engine knows are pre-filled"), and short builders for the
sections a provision requires."""

from aiact.drafting.models import SectionStatus
from aiact.drafting.prefill import Fill
from aiact.drafting.skeletons.quotes import requirement
from aiact.drafting.templates import (
    DE,
    DUTY,
    EN,
    NO_STATED_FACTS,
    ClassificationSection,
    Question,
    RequirementSection,
    SectionSpec,
)

SYSTEM = ClassificationSection(
    "system", {EN: "The system", DE: "Das System"}, Fill.SYSTEM_FACTS, NO_STATED_FACTS
)

PREFILLED: tuple[SectionSpec, ...] = (SYSTEM, DUTY)
"""The facts the user stated about the system, then its class and the document's duty."""


def ask(key: str, en: str, de: str) -> Question:
    return Question(key, {EN: en, DE: de})


def required(
    key: str,
    heading: tuple[str, str],
    provision_id: str,
    *questions: Question,
    waits_for: SectionStatus = SectionStatus.QUESTIONS,
) -> RequirementSection:
    """The section `provision_id` requires, its heading given as (English, German)."""
    en, de = heading
    return RequirementSection(
        key, {EN: en, DE: de}, requirement(provision_id), questions, waits_for=waits_for
    )
