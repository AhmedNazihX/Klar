"""A drafted document: its sections, where each section's content came from, and its status.

Every document is labelled DRAFT and carries the "guidance, not legal advice" notice (INIT >
Documentation drafting). A section with no paragraphs is shown as "To fill in"; a skeleton's
section also quotes the requirement it answers (P8b), and the vendor message's finding quotes
each Art. 5(1) point the result decided on, from the corpus (P28; decision 031).
"""

from collections.abc import Iterable
from datetime import date
from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from aiact.schemas import DISCLAIMER, Citation, Language, LawVersion
from aiact.schemas.base import ContractModel
from aiact.schemas.questions import SLUG_PATTERN

TEMPLATE_PATTERN = r"^[a-z0-9]+(_[a-z0-9]+)*$"
"""A template id, as `interview_answers.template` stores it, for example `art_26_7_workers`."""

QuestionKey = Annotated[str, Field(pattern=SLUG_PATTERN)]
"""An interview question's key, as `interview_answers.question_key` stores it."""


class DocumentKind(StrEnum):
    """What a document is, which says how the screen words its interview and lays it out: a
    skeleton gets the section-by-section layout (artboard `DocSkeleton`)."""

    NOTICE = "notice"
    RECORD = "record"
    DISCLOSURE = "disclosure"
    SKELETON = "skeleton"
    LETTER = "letter"


class Provenance(StrEnum):
    """Where a section's content comes from; the interface shows it as a tag on the section."""

    CLASSIFICATION = "classification"
    """Pre-filled from the classification result ("From your classification")."""
    INTERVIEW = "interview"
    """The user's interview answers, word for word ("From your interview answers")."""
    TEMPLATE = "template"
    """The template's own fixed wording, such as the duty the document answers; no tag."""


class DraftStatus(StrEnum):
    """A document's state on the documents list: "Needs N answers" or "Ready to review"."""

    NEEDS_ANSWERS = "needs_answers"
    READY_TO_REVIEW = "ready_to_review"


class SectionStatus(StrEnum):
    """A section's state, as the DocSkeleton artboard shows it beside the section."""

    DRAFTED = "drafted"
    """Nothing left to answer: pre-filled, fixed wording, or every question answered."""
    QUESTIONS = "questions"
    """"N questions": the interview still asks the section's `unanswered` questions."""
    TO_FILL_IN = "to_fill_in"
    """The provider's own description, such as its log of changes, is still to be given."""
    NEEDS_EVIDENCE = "needs_evidence"
    """It still waits for records the provider holds, such as test reports or standards."""
    GENERATED_LAST = "generated_last"
    """Drawn up once everything else is done: the EU declaration of conformity."""


class SizeClass(StrEnum):
    """The company profile's size class (P19's `inventories.size_class`), passed in by the
    caller: derived from the profile's bands, never from the description."""

    SME = "sme"
    SMC = "smc"
    NONE = "none"


class DraftSection(ContractModel):
    """One section of a drafted document. No paragraphs means it is still "To fill in"."""

    key: str = Field(pattern=SLUG_PATTERN)
    heading: str = Field(min_length=1)
    provenance: Provenance
    paragraphs: tuple[str, ...] = ()
    question_keys: tuple[QuestionKey, ...] = Field(
        default=(),
        description="The interview questions whose answers fill the section, in the order "
        "asked; interview sections only.",
    )
    unanswered: tuple[QuestionKey, ...] = Field(
        default=(), description="The questions of `question_keys` still to answer, in order."
    )
    status: SectionStatus
    requirement: Citation | None = Field(
        default=None,
        description="The requirement the section answers, quoted word for word from the AI Act "
        '(skeletons only); shown above the "To fill in" marker.',
    )
    quotes: tuple[Citation, ...] = Field(
        default=(),
        description="The provisions a pre-filled section quotes, word for word from the corpus "
        "at the result's law version and date, in the document's language, never from the "
        "result: the Art. 5(1) points of the vendor message's finding.",
    )

    @model_validator(mode="after")
    def _well_formed(self) -> Self:
        if any(not paragraph.strip() for paragraph in self.paragraphs):
            raise ValueError("a paragraph must not be blank")
        is_interview = self.provenance is Provenance.INTERVIEW
        if is_interview != bool(self.question_keys):
            raise ValueError("question_keys are set exactly on interview sections")
        if [key for key in self.question_keys if key in self.unanswered] != list(self.unanswered):
            raise ValueError("unanswered lists some of the section's questions, in their order")
        if (self.status is SectionStatus.DRAFTED) == bool(self.unanswered):
            raise ValueError("a section is drafted exactly when no question is unanswered")
        return self


def unanswered_count(sections: Iterable[DraftSection]) -> int:
    """How many interview questions are still unanswered."""
    return sum(len(section.unanswered) for section in sections)


def status_for(unanswered: int) -> DraftStatus:
    return DraftStatus.NEEDS_ANSWERS if unanswered else DraftStatus.READY_TO_REVIEW


class DraftDocument(ContractModel):
    """A document drafted from a classification result and the user's answers."""

    template: str = Field(pattern=TEMPLATE_PATTERN)
    title: str = Field(min_length=1)
    article: str = Field(min_length=1, description="The duty it answers, e.g. `art:26:7`.")
    language: Language
    label: Literal["DRAFT"] = "DRAFT"
    note: str | None = Field(
        default=None,
        description="A line under the title: for an SME or a small mid-cap, that a simplified "
        "technical documentation form is expected (P8b).",
    )
    sections: tuple[DraftSection, ...] = Field(min_length=1)
    unanswered: int = Field(ge=0, description="Interview questions still to answer.")
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
                f"{unanswered} interview questions are unanswered, not {self.unanswered}"
            )
        expected = status_for(unanswered)
        if self.status is not expected:
            raise ValueError(f"a draft with {unanswered} unanswered questions is {expected.value}")
        return self
