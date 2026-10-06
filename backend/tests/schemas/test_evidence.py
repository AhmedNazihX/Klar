import pytest
from pydantic import ValidationError

from aiact.schemas import (
    DISCLAIMER,
    DISCLAIMER_DE,
    DISCLAIMER_EN,
    Citation,
    DocumentStatus,
    EvidenceTag,
    Fact,
    Language,
    OpenQuestion,
    SourceSpan,
)

SPAN = SourceSpan(start=0, end=4)


def test_open_question_needs_exactly_two_readings() -> None:
    with pytest.raises(ValidationError):
        OpenQuestion.model_validate({"question": "Profiling?", "readings": ["Yes"]})
    with pytest.raises(ValidationError):
        OpenQuestion.model_validate({"question": "Profiling?", "readings": ["Yes", "No", "Maybe"]})


def test_source_span_end_must_follow_start() -> None:
    with pytest.raises(ValidationError, match="greater than start"):
        SourceSpan(start=5, end=5)


def test_stated_fact_without_span_is_rejected() -> None:
    with pytest.raises(ValidationError, match="source_span"):
        Fact(text="The tool ranks applicants", evidence=EvidenceTag.STATED)


@pytest.mark.parametrize("evidence", [EvidenceTag.INFERRED, EvidenceTag.ASSUMED])
def test_unstated_fact_with_span_is_rejected(evidence: EvidenceTag) -> None:
    with pytest.raises(ValidationError, match="source_span"):
        Fact(text="The tool is used in the EU", evidence=evidence, source_span=SPAN)


def test_guidance_citation_has_no_law_version_and_can_be_a_draft() -> None:
    citation = Citation(
        provision_id="guide:guide-high-risk-annex-iii:ex:015",
        document_id="guide-high-risk-annex-iii",
        document_status=DocumentStatus.DRAFT,
        language=Language.EN,
        quote="An example of a system that is not high-risk",
        english_only=True,
    )
    assert citation.law_version is None
    assert citation.document_status is DocumentStatus.DRAFT


def test_disclaimer_exists_per_language() -> None:
    assert DISCLAIMER[Language.EN] == DISCLAIMER_EN
    assert DISCLAIMER[Language.DE] == DISCLAIMER_DE
    assert set(DISCLAIMER) == set(Language)
    assert "not legal advice" in DISCLAIMER_EN
    assert "keine Rechtsberatung" in DISCLAIMER_DE
