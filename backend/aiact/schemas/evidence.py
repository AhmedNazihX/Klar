"""What a step rests on: citations, facts and open legal questions."""

from typing import Self

from pydantic import Field, model_validator

from aiact.schemas.base import ContractModel
from aiact.schemas.enums import DocumentStatus, EvidenceTag, Language, LawVersion


class Citation(ContractModel):
    """One quoted provision. `english_only` marks guidance that has no official text in `de`."""

    provision_id: str = Field(min_length=1, description="For example `art:6:3` or `annex:III:4:a`.")
    document_id: str = Field(
        min_length=1,
        description="The cited document's manifest `doc_key` (`data/manifest.yaml`), for "
        "example `ai-act-consolidated` or `guide-prohibited`; the citation checks resolve it "
        "against the corpus `documents.doc_key`.",
    )
    law_version: LawVersion | None = Field(
        default=None,
        description="The AI Act text quoted; None for guidance, which belongs to neither text.",
    )
    document_status: DocumentStatus | None = Field(
        default=None, description="Lets draft guidance be labelled as a draft."
    )
    language: Language = Field(description="The language of `quote`.")
    quote: str = Field(min_length=1)
    english_only: bool = False
    changed_by_omnibus: bool = Field(
        default=False,
        description="The quoted amended text is one the Digital Omnibus changed: the provision, "
        "a part of it or the provision it belongs to was replaced, inserted, deleted or amended "
        "(INIT > Corpus rules). Never set on the original text.",
    )


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

    @model_validator(mode="after")
    def _span_iff_stated(self) -> Self:
        is_stated = self.evidence is EvidenceTag.STATED
        if is_stated != (self.source_span is not None):
            raise ValueError(
                "a stated fact needs a source_span; inferred or assumed facts have none"
            )
        return self


class OpenQuestion(ContractModel):
    """A question the law and guidance don't settle, with both possible readings."""

    question: str = Field(min_length=1)
    # A variable-length tuple, so the JSON Schema uses minItems/maxItems rather than prefixItems.
    readings: tuple[str, ...] = Field(
        min_length=2, max_length=2, description="The two possible readings, stricter first."
    )
