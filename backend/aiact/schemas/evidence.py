"""What a step rests on: citations, facts and open legal questions."""

from typing import Self

from pydantic import Field, model_validator

from aiact.schemas.base import ContractModel
from aiact.schemas.enums import (
    DocumentStatus,
    EvidenceTag,
    Language,
    LawVersion,
    RiskClass,
    SettledByKind,
)


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


class Reading(ContractModel):
    """One possible reading of an open question of law (E12): what it is called, the class it
    gives, why, the provision it rests on, and what follows if it holds."""

    title: str = Field(min_length=1)
    risk_class: RiskClass | None = Field(
        default=None,
        description="The class this reading gives on its own check, for example `high_risk` for "
        "the stricter reading of a high-risk question. None when it gives no class by itself: "
        "the remaining checks decide (shown as, for example, not high-risk on this point), or "
        "the question is about a duty or the role, not the class.",
    )
    explanation: str = Field(min_length=1)
    citation: Citation | None = Field(
        default=None, description="The provision the reading rests on: one of its step's citations."
    )
    consequence: str | None = Field(default=None, description="What follows if the reading holds.")
    is_applied: bool = Field(
        default=False,
        description="The working assumption: the stricter reading, applied until a lawyer or "
        "the user's answer settles the question.",
    )


class SettledBy(ContractModel):
    """Something that would settle an open question. Guidance is named as it stands (for example
    a draft); naming it never promises that the result is checked again (decision 026 item 4)."""

    kind: SettledByKind
    text: str = Field(min_length=1)


class OpenQuestion(ContractModel):
    """A question the law and guidance don't settle, with both possible readings."""

    question: str = Field(min_length=1)
    # A variable-length tuple, so the JSON Schema uses minItems/maxItems rather than prefixItems.
    readings: tuple[Reading, ...] = Field(
        min_length=2,
        max_length=2,
        description="The two possible readings, stricter first; the stricter one is applied.",
    )
    settled_by: tuple[SettledBy, ...] = Field(
        default=(), description="What would settle the question, when the step knows it."
    )

    @model_validator(mode="after")
    def _stricter_reading_applied(self) -> Self:
        if [reading.is_applied for reading in self.readings] != [True, False]:
            raise ValueError("the first (stricter) reading is applied, and only it")
        return self
