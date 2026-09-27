import pytest
from pydantic import ValidationError

from aiact.schemas import FollowUpQuestion, OpenQuestion, Status, StepName, StepResult

QUESTION = OpenQuestion(
    question="Does ranking applicants count as profiling under Art. 6(3)?",
    readings=("Yes, so the exemption does not apply", "No, so the exemption may apply"),
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
