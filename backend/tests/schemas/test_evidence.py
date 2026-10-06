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
    LawVersion,
    OpenQuestion,
    Reading,
    RiskClass,
    SettledBy,
    SettledByKind,
    SourceSpan,
)

SPAN = SourceSpan(start=0, end=4)


APPLIED = {"title": "Recruitment", "explanation": "It filters applicants.", "is_applied": True}
LENIENT = {"title": "A narrow task", "explanation": "It only copies CV fields."}


@pytest.mark.parametrize("readings", [[APPLIED], [APPLIED, LENIENT, LENIENT]])
def test_open_question_needs_exactly_two_readings(readings: list[dict[str, object]]) -> None:
    with pytest.raises(ValidationError, match="readings"):
        OpenQuestion.model_validate({"question": "Profiling?", "readings": readings})


@pytest.mark.parametrize(
    "readings",
    [
        [LENIENT, APPLIED],
        [APPLIED, {**LENIENT, "is_applied": True}],
        [{**APPLIED, "is_applied": False}, LENIENT],
    ],
)
def test_only_the_first_stricter_reading_is_applied(readings: list[dict[str, object]]) -> None:
    with pytest.raises(ValidationError, match="stricter"):
        OpenQuestion.model_validate({"question": "Profiling?", "readings": readings})


def test_a_reading_carries_its_title_class_quote_and_consequence() -> None:
    """The ResultAmbiguous artboard's reading card (E12): title, class pill, explanation, quote,
    consequence; the applied one is marked."""
    quote = Citation(
        provision_id="annex:III:4:a",
        document_id="ai-act-consolidated",
        law_version=LawVersion.AMENDED,
        document_status=DocumentStatus.CONSOLIDATED,
        language=Language.EN,
        quote="AI systems intended to be used for the recruitment or selection of natural persons",
    )
    stricter = Reading(
        title="Part of recruitment",
        risk_class=RiskClass.HIGH_RISK,
        explanation="The copied fields feed the shortlist HR uses to filter applicants.",
        citation=quote,
        consequence="If this holds, the high-risk duties apply from 2 December 2027.",
        is_applied=True,
    )
    lenient = Reading(title="A narrow procedural task", explanation="It only copies CV fields.")
    guidance = SettledBy(
        kind=SettledByKind.GUIDANCE,
        text="Final Commission guidelines on high-risk classification (still a draft, 19 May 2026)",
    )
    question = OpenQuestion(
        question="Is copying CV fields part of recruitment?",
        readings=(stricter, lenient),
        settled_by=(guidance,),
    )
    dumped = question.model_dump(mode="json")
    assert dumped["readings"][0]["risk_class"] == "high_risk"
    assert dumped["readings"][0]["citation"]["provision_id"] == "annex:III:4:a"
    assert dumped["readings"][1]["risk_class"] is None
    assert dumped["settled_by"] == [{"kind": "guidance", "text": guidance.text}]
    assert OpenQuestion.model_validate(dumped) == question


def test_settled_by_is_optional() -> None:
    question = OpenQuestion.model_validate({"question": "Open?", "readings": [APPLIED, LENIENT]})
    assert question.settled_by == ()


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


def test_plain_readings_become_untitled_ones_with_the_first_applied() -> None:
    question = OpenQuestion.model_validate({"question": "Open?", "readings": ("Yes.", "No.")})
    assert [(r.title, r.explanation, r.is_applied) for r in question.readings] == [
        (None, "Yes.", True),
        (None, "No.", False),
    ]


def test_three_plain_readings_are_still_rejected() -> None:
    with pytest.raises(ValidationError, match="readings"):
        OpenQuestion.model_validate({"question": "Open?", "readings": ["a", "b", "c"]})
