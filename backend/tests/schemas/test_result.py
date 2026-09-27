import pytest
from pydantic import ValidationError

from aiact.schemas import (
    ClassificationResult,
    FollowUpQuestion,
    OpenQuestion,
    RiskClass,
    Role,
    Status,
    StepName,
    StepResult,
)
from tests.schemas.worked_example import worked_example_result

ART_5_QUESTION = OpenQuestion(
    question="Does ranking applicants by inferred emotion fall under Art. 5(1)(f)?",
    readings=("Yes, the practice is prohibited", "No, the practice is not covered"),
)


def rebuild(result: ClassificationResult, **changes: object) -> ClassificationResult:
    """Validate a changed copy (model_copy would skip the validators)."""
    return ClassificationResult.model_validate({**result.model_dump(), **changes})


def dumped_steps(result: ClassificationResult, count: int | None = None) -> list[dict[str, object]]:
    return [step.model_dump() for step in result.steps[:count]]


def ambiguous_art_5_steps(result: ClassificationResult) -> list[dict[str, object]]:
    """The worked example's steps with an ambiguous Art. 5 step."""
    art_5 = StepResult(
        step=StepName.PROHIBITED,
        decision="Unsettled whether the practice is prohibited",
        status=Status.LEGALLY_AMBIGUOUS,
        open_question=ART_5_QUESTION,
    )
    steps = dumped_steps(result)
    steps[1] = art_5.model_dump()
    return steps


def test_worked_example_is_a_valid_high_risk_deployer_result() -> None:
    result = worked_example_result()
    assert result.risk_class is RiskClass.HIGH_RISK
    assert result.role is Role.DEPLOYER
    assert result.annex_point == "annex:III:4:a"
    assert result.status is Status.DECIDED
    assert [step.step for step in result.steps] == list(StepName)


def test_result_round_trips_through_json() -> None:
    result = worked_example_result()
    assert ClassificationResult.model_validate_json(result.model_dump_json()) == result


def test_result_is_immutable() -> None:
    result = worked_example_result()
    with pytest.raises(ValidationError, match="frozen"):
        result.risk_class = RiskClass.MINIMAL_RISK  # pyright: ignore[reportAttributeAccessIssue]


def test_unknown_field_is_rejected() -> None:
    with pytest.raises(ValidationError, match="extra"):
        rebuild(worked_example_result(), confidence=0.9)


# limited_risk


def test_limited_risk_without_transparency_duties_is_rejected() -> None:
    with pytest.raises(ValidationError, match="transparency_duties"):
        rebuild(worked_example_result(), risk_class=RiskClass.LIMITED_RISK)


def test_limited_risk_with_transparency_duties_is_accepted() -> None:
    result = rebuild(
        worked_example_result(),
        risk_class=RiskClass.LIMITED_RISK,
        transparency_duties=("art:50:1",),
    )
    assert result.transparency_duties == ("art:50:1",)


# step sequence and early ends


def test_decided_prohibited_with_steps_after_art_5_is_rejected() -> None:
    with pytest.raises(ValidationError, match=r"after the Art\. 5 check"):
        rebuild(worked_example_result(), risk_class=RiskClass.PROHIBITED)


def test_decided_prohibited_ending_at_art_5_is_accepted() -> None:
    good = worked_example_result()
    result = rebuild(good, risk_class=RiskClass.PROHIBITED, steps=dumped_steps(good, 2), role=None)
    assert result.steps[-1].step is StepName.PROHIBITED
    assert result.role is None


def test_ambiguous_art_5_keeps_running_the_remaining_checks() -> None:
    good = worked_example_result()
    result = rebuild(
        good,
        risk_class=RiskClass.PROHIBITED,
        status=Status.LEGALLY_AMBIGUOUS,
        steps=ambiguous_art_5_steps(good),
    )
    assert [step.step for step in result.steps] == list(StepName)


def test_ambiguous_art_5_stopping_early_is_rejected() -> None:
    good = worked_example_result()
    with pytest.raises(ValidationError, match="needs the steps"):
        rebuild(
            good,
            risk_class=RiskClass.PROHIBITED,
            status=Status.LEGALLY_AMBIGUOUS,
            steps=ambiguous_art_5_steps(good)[:2],
            role=None,
        )


def test_out_of_scope_ending_after_scope_is_accepted() -> None:
    good = worked_example_result()
    result = rebuild(
        good, risk_class=RiskClass.OUT_OF_SCOPE, steps=dumped_steps(good, 1), role=None
    )
    assert [step.step for step in result.steps] == [StepName.SCOPE]


def test_out_of_scope_running_further_checks_is_rejected() -> None:
    with pytest.raises(ValidationError, match="needs the steps"):
        rebuild(worked_example_result(), risk_class=RiskClass.OUT_OF_SCOPE)


def test_incomplete_steps_are_rejected() -> None:
    good = worked_example_result()
    with pytest.raises(ValidationError, match="needs the steps"):
        rebuild(good, steps=dumped_steps(good, 3), role=None)


def test_skipped_step_is_rejected() -> None:
    good = worked_example_result()
    steps = dumped_steps(good)
    del steps[2]
    with pytest.raises(ValidationError, match="none skipped"):
        rebuild(good, steps=steps)


def test_steps_out_of_order_are_rejected() -> None:
    good = worked_example_result()
    with pytest.raises(ValidationError, match="check order"):
        rebuild(good, steps=list(reversed(dumped_steps(good))))


def test_duplicate_steps_are_rejected() -> None:
    good = worked_example_result()
    steps = [good.steps[0].model_dump(), good.steps[0].model_dump()]
    with pytest.raises(ValidationError, match="check order"):
        rebuild(good, steps=steps)


# role


def test_role_step_without_role_is_rejected() -> None:
    with pytest.raises(ValidationError, match="role is set exactly"):
        rebuild(worked_example_result(), role=None)


def test_role_without_role_step_is_rejected() -> None:
    good = worked_example_result()
    with pytest.raises(ValidationError, match="role is set exactly"):
        rebuild(good, risk_class=RiskClass.OUT_OF_SCOPE, steps=dumped_steps(good, 1))


def test_role_switch_reason_without_role_is_rejected() -> None:
    good = worked_example_result()
    with pytest.raises(ValidationError, match="role_switch_reason needs a role"):
        rebuild(
            good,
            risk_class=RiskClass.OUT_OF_SCOPE,
            steps=dumped_steps(good, 1),
            role=None,
            role_switch_reason="Rebranded the system",
        )


# uncertain status


@pytest.mark.parametrize("status", [Status.NEEDS_MORE_INFORMATION, Status.LEGALLY_AMBIGUOUS])
def test_uncertain_result_without_an_uncertain_step_is_rejected(status: Status) -> None:
    with pytest.raises(ValidationError, match="needs a step with that status"):
        rebuild(worked_example_result(), status=status)


def test_needs_more_information_result_with_its_step_is_accepted() -> None:
    good = worked_example_result()
    question = FollowUpQuestion(id="eu_use", text="Is the tool used in the EU?", about="scope")
    scope = StepResult(
        step=StepName.SCOPE,
        decision="Unclear whether the tool is used in the EU",
        status=Status.NEEDS_MORE_INFORMATION,
        missing_fact=question,
    )
    steps = [scope.model_dump(), *dumped_steps(good)[1:]]
    result = rebuild(good, status=Status.NEEDS_MORE_INFORMATION, steps=steps)
    assert result.steps[0].missing_fact == question


# follow-up questions


def test_duplicate_follow_up_ids_are_rejected() -> None:
    good = worked_example_result()
    question = good.follow_up_questions[0].model_dump()
    with pytest.raises(ValidationError, match="ids must be unique"):
        rebuild(good, follow_up_questions=[question, question])


@pytest.mark.parametrize("bad_id", ["", "Ranks_People", "ranks-people", "1st", "a" * 65])
def test_follow_up_id_must_be_a_slug(bad_id: str) -> None:
    with pytest.raises(ValidationError, match="pattern"):
        FollowUpQuestion(id=bad_id, text="Does the tool rank people?")
