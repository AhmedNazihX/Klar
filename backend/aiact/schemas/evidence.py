"""What a step rests on: citations, facts and open legal questions."""

from typing import Self

from pydantic import Field, model_validator

from aiact.schemas.base import ContractModel
from aiact.schemas.enums import EvidenceTag, Language, LawVersion


class Citation(ContractModel):
    """One quoted provision. `english_only` marks guidance that has no official text in `de`."""

    provision_id: str = Field(min_length=1, description="For example `art:6:3` or `annex:III:4:a`.")
    document_id: str = Field(min_length=1)
    law_version: LawVersion
    language: Language = Field(description="The language of `quote`.")
    quote: str = Field(min_length=1)
    english_only: bool = False


class SourceSpan(ContractModel):
    """Character offsets `[start, end)` of a fact in the user's description."""

    start: int = Field(ge=0)
    end: int = Field(gt=0)

    @model_validator(mode="after")
    def _end_after_start(self) -> Self:
        if self.end <= self.start:
            raise ValueError("source span end must be greater than start")
        return self


class Fact(ContractModel):
    """A fact about the system and where it came from. Only stated facts point into the text."""

    text: str = Field(min_length=1)
    evidence: EvidenceTag
    source_span: SourceSpan | None = None


class OpenQuestion(ContractModel):
    """A question the law and guidance don't settle, with both possible readings."""

    question: str = Field(min_length=1)
    readings: tuple[str, str] = Field(description="The two possible readings, stricter first.")
