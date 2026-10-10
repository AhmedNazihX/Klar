"""What a Q&A answer is: its kind, its text, the provisions it rests on, the law version and the
notice (P7)."""

from datetime import date
from enum import StrEnum
from typing import Literal

from pydantic import Field

from aiact.schemas import Citation, Language, LawVersion
from aiact.schemas.base import ContractModel


class AnswerKind(StrEnum):
    """Whether the question was answered, and why not when it wasn't."""

    ANSWERED = "answered"
    """Answered from the provisions it cites."""
    OUTSIDE_CORPUS = "outside_corpus"
    """The AI Act and the Commission's guidance don't answer it: another law, or off-topic."""
    COMPLIANCE = "compliance"
    """It asks whether someone complies; Klar never says (INIT > Ethical considerations)."""
    REFUSED = "refused"
    """The provider's content filter refused the question, and the second model did too
    (decision 033): asking the same question again wouldn't help."""


class QaAnswer(ContractModel):
    """One answer, with the provisions it rests on (none when it isn't `answered`)."""

    kind: AnswerKind
    answer: str = Field(
        min_length=1,
        description="Plain text, paragraphs separated by a blank line; for a question not "
        "answered, the fixed reason in the question's language.",
    )
    citations: tuple[Citation, ...] = Field(
        description="The provisions the answer rests on, in the order cited; at least one when "
        "`kind` is `answered`, none otherwise."
    )
    language: Language
    law_version: LawVersion
    as_of: date | None = Field(
        description="The date the amended text was read on; None for the original text."
    )
    disclaimer: str = Field(min_length=1)


class ModelReply(ContractModel):
    """What the model fills in: the kind, the answer and the numbers of the sources it cites."""

    kind: Literal[AnswerKind.ANSWERED, AnswerKind.OUTSIDE_CORPUS, AnswerKind.COMPLIANCE]
    """The model's own verdict; `refused` is never its to give."""
    answer: str
    cited: tuple[int, ...]
    """The numbers of the sources the answer rests on, as the prompt lists them (1 is the first)."""
