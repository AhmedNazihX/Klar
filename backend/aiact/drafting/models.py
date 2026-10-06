"""A drafted document: its sections, where each section's content came from, and its status.

Every document is labelled DRAFT and carries the "guidance, not legal advice" notice (INIT >
Documentation drafting). A section with no paragraphs is shown as "To fill in".
"""

from collections.abc import Iterable
from datetime import date
from enum import StrEnum
from typing import Literal, Self

from pydantic import Field, model_validator

from aiact.schemas import DISCLAIMER, Language, LawVersion
from aiact.schemas.base import ContractModel
from aiact.schemas.questions import SLUG_PATTERN

TEMPLATE_PATTERN = r"^[a-z0-9]+(_[a-z0-9]+)*$"
"""A template id, as `interview_answers.template` stores it, for example `art_26_7_workers`."""


class Provenance(StrEnum):
    """Where a section's content comes from; the interface shows it as a tag on the section."""

    CLASSIFICATION = "classification"
    """Pre-filled from the classification result ("From your classification")."""
    INTERVIEW = "interview"
    """The user's interview answer, word for word ("From your interview answers")."""
    TEMPLATE = "template"
    """The template's own fixed wording, such as the duty the document answers; no tag."""


class DraftStatus(StrEnum):
    """A document's state on the documents list: "Needs N answers" or "Ready to review"."""

    NEEDS_ANSWERS = "needs_answers"
    READY_TO_REVIEW = "ready_to_review"


class DraftSection(ContractModel):
    """One section of a drafted document. No paragraphs means it is still "To fill in"."""

    key: str = Field(pattern=SLUG_PATTERN)
    heading: str = Field(min_length=1)
    provenance: Provenance
    paragraphs: tuple[str, ...] = ()
    question_key: str | None = Field(
        default=None,
        pattern=SLUG_PATTERN,
        description="The interview question whose answer fills the section; interview only.",
    )

    @property
    def is_filled(self) -> bool:
        return bool(self.paragraphs)

    @model_validator(mode="after")
    def _well_formed(self) -> Self:
        if any(not paragraph.strip() for paragraph in self.paragraphs):
            raise ValueError("a paragraph must not be blank")
        is_interview = self.provenance is Provenance.INTERVIEW
        if is_interview != (self.question_key is not None):
            raise ValueError("question_key is set exactly on interview sections")
        return self


def unanswered_count(sections: Iterable[DraftSection]) -> int:
    """How many interview sections are still "To fill in"."""
    return sum(
        1
        for section in sections
        if section.provenance is Provenance.INTERVIEW and not section.is_filled
    )


def status_for(unanswered: int) -> DraftStatus:
    return DraftStatus.NEEDS_ANSWERS if unanswered else DraftStatus.READY_TO_REVIEW


class DraftDocument(ContractModel):
    """A short document drafted from a classification result and the user's answers."""

    template: str = Field(pattern=TEMPLATE_PATTERN)
    title: str = Field(min_length=1)
    article: str = Field(min_length=1, description="The duty it answers, e.g. `art:26:7`.")
    language: Language
    label: Literal["DRAFT"] = "DRAFT"
    sections: tuple[DraftSection, ...] = Field(min_length=1)
    unanswered: int = Field(ge=0, description="Interview sections still to fill in.")
    status: DraftStatus
    law_version: LawVersion = Field(description="The AI Act text of the result drafted from.")
    as_of: date = Field(description="The result's law date.")
    disclaimer: str

    @model_validator(mode="after")
    def _status_and_notice(self) -> Self:
        if self.disclaimer != DISCLAIMER[self.language]:
            raise ValueError("a draft carries the disclaimer in its own language")
        unanswered = unanswered_count(self.sections)
        if self.unanswered != unanswered:
            raise ValueError(
                f"{unanswered} interview sections are unanswered, not {self.unanswered}"
            )
        expected = status_for(unanswered)
        if self.status is not expected:
            raise ValueError(f"a draft with {unanswered} unanswered sections is {expected.value}")
        return self
