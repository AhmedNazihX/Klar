import pytest
from pydantic import ValidationError

from aiact.schemas import (
    Citation,
    FollowUpQuestion,
    Language,
    LawVersion,
    OpenQuestion,
    Status,
    StepName,
    StepResult,
)
from tests.schemas.builders import open_question

QUESTION = open_question(
    "Does ranking applicants count as profiling under Art. 6(3)?",
    "Yes, so the exemption does not apply",
    "No, so the exemption may apply",
)
MISSING = FollowUpQuestion(id="eu_use", text="Is the tool used in the EU?")


def test_needs_more_information_without_missing_fact_or_error_is_rejected() -> None:
    with pytest.raises(ValidationError, match="missing_fact or error"):
        StepResult(step=StepName.SCOPE, decision="Unclear", status=Status.NEEDS_MORE_INFORMATION)


def test_needs_more_information_with_missing_fact_is_accepted() -> None:
    step = StepResult(
        step=StepName.SCOPE,
        decision="Unclear",
        status=Status.NEEDS_MORE_INFORMATION,
        missing_fact=MISSING,
    )
    assert step.missing_fact is not None
    assert step.missing_fact.id == "eu_use"


def test_needs_more_information_with_error_is_accepted() -> None:
    step = StepResult(
        step=StepName.HIGH_RISK,
        decision="A citation could not be verified",
        status=Status.NEEDS_MORE_INFORMATION,
        error="citation_unverified",
    )
    assert step.error == "citation_unverified"


def test_error_must_be_a_code() -> None:
    with pytest.raises(ValidationError, match="pattern"):
        StepResult(
            step=StepName.HIGH_RISK,
            decision="Failed",
            status=Status.NEEDS_MORE_INFORMATION,
            error="Citation could not be verified",
        )


def test_legally_ambiguous_without_open_question_is_rejected() -> None:
    with pytest.raises(ValidationError, match="open_question"):
        StepResult(step=StepName.HIGH_RISK, decision="Unsettled", status=Status.LEGALLY_AMBIGUOUS)


@pytest.mark.parametrize(
    "gap",
    [{"open_question": QUESTION}, {"missing_fact": MISSING}, {"error": "citation_unverified"}],
)
def test_decided_step_with_a_gap_is_rejected(gap: dict[str, object]) -> None:
    with pytest.raises(ValidationError, match="decided step"):
        StepResult.model_validate({"step": "high_risk", "decision": "High-risk", **gap})


def test_legally_ambiguous_with_open_question_is_accepted() -> None:
    step = StepResult(
        step=StepName.HIGH_RISK,
        decision="Unsettled",
        status=Status.LEGALLY_AMBIGUOUS,
        open_question=QUESTION,
    )
    assert step.open_question == QUESTION


# --- Quotes in the questions (E12) ---------------------------------------------------------------

ART_6_1 = Citation(
    provision_id="art:6:1",
    document_id="ai-act-consolidated",
    law_version=LawVersion.AMENDED,
    language=Language.EN,
    quote="An AI system shall be considered to be high-risk where both of the following...",
)
ANNEX_I_ENTRY = ART_6_1.model_copy(update={"provision_id": "annex:I:A:11", "quote": "11. MDR"})


def quoting(*citations: Citation | None) -> OpenQuestion:
    """`QUESTION` with its readings quoting `citations` in order."""
    readings = tuple(
        reading.model_copy(update={"citation": citation})
        for reading, citation in zip(QUESTION.readings, citations, strict=True)
    )
    return QUESTION.model_copy(update={"readings": readings})


def test_readings_and_the_missing_fact_may_quote_the_steps_own_citations() -> None:
    step = StepResult(
        step=StepName.HIGH_RISK,
        decision="Unsettled",
        status=Status.LEGALLY_AMBIGUOUS,
        citations=(ART_6_1, ANNEX_I_ENTRY),
        open_question=quoting(ART_6_1, None),
        missing_fact=MISSING.model_copy(update={"citations": (ANNEX_I_ENTRY, ART_6_1)}),
    )
    assert step.open_question is not None
    assert step.open_question.readings[0].citation == ART_6_1


@pytest.mark.parametrize(
    "gap",
    [
        {"open_question": quoting(ART_6_1, ANNEX_I_ENTRY)},
        {"open_question": quoting(ART_6_1, ART_6_1.model_copy(update={"quote": "Changed."}))},
        {
            "open_question": quoting(ART_6_1, None),
            "missing_fact": MISSING.model_copy(update={"citations": (ANNEX_I_ENTRY,)}),
        },
    ],
)
def test_a_quote_the_step_doesnt_cite_is_rejected(gap: dict[str, object]) -> None:
    """Every quote a step shows is one of its citations, so E9's check covers it."""
    with pytest.raises(ValidationError, match="quotes a citation the step doesn't list"):
        StepResult.model_validate(
            {
                "step": "high_risk",
                "decision": "Unsettled",
                "status": "legally_ambiguous",
                "citations": (ART_6_1,),
                **gap,
            }
        )
