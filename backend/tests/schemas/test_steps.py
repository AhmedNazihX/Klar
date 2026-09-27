import pytest
from pydantic import ValidationError

from aiact.schemas import OpenQuestion, Status, StepName, StepResult

QUESTION = OpenQuestion(
    question="Does ranking applicants count as profiling under Art. 6(3)?",
    readings=("Yes, so the exemption does not apply", "No, so the exemption may apply"),
)


def test_needs_more_information_without_missing_fact_is_rejected() -> None:
    with pytest.raises(ValidationError, match="missing_fact"):
        StepResult(step=StepName.SCOPE, decision="Unclear", status=Status.NEEDS_MORE_INFORMATION)


def test_legally_ambiguous_without_open_question_is_rejected() -> None:
    with pytest.raises(ValidationError, match="open_question"):
        StepResult(step=StepName.HIGH_RISK, decision="Unsettled", status=Status.LEGALLY_AMBIGUOUS)


def test_decided_step_with_an_open_question_is_rejected() -> None:
    with pytest.raises(ValidationError, match="decided step"):
        StepResult(step=StepName.HIGH_RISK, decision="High-risk", open_question=QUESTION)


def test_legally_ambiguous_with_open_question_is_accepted() -> None:
    step = StepResult(
        step=StepName.HIGH_RISK,
        decision="Unsettled",
        status=Status.LEGALLY_AMBIGUOUS,
        open_question=QUESTION,
    )
    assert step.open_question == QUESTION
