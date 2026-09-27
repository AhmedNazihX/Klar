import pytest
from pydantic import ValidationError

from aiact.schemas import (
    ClassificationResult,
    FollowUpQuestion,
    RiskClass,
    Role,
    Status,
    StepName,
)
from tests.schemas.builders import (
    ambiguous,
    dumped_steps,
    ends_early,
    missing_fact,
    rebuild,
    steps_with,
)
from tests.schemas.worked_example import OBLIGATIONS, worked_example_result


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


# class-specific fields


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


@pytest.mark.parametrize(
    "field",
    [
        {"obligations": OBLIGATIONS},
        {"annex_point": "annex:III:4:a"},
        {"transparency_duties": ("art:50:1",)},
    ],
)
def test_out_of_scope_with_class_fields_is_rejected(field: dict[str, object]) -> None:
    result = ends_early(RiskClass.OUT_OF_SCOPE, dumped_steps(1), Status.DECIDED)
    with pytest.raises(ValidationError, match="out_of_scope result has no"):
        rebuild(result, **field)


# role


def test_role_step_without_role_is_rejected() -> None:
    with pytest.raises(ValidationError, match="role is set exactly"):
        rebuild(worked_example_result(), role=None)


def test_role_without_role_step_is_rejected() -> None:
    result = ends_early(RiskClass.OUT_OF_SCOPE, dumped_steps(1), Status.DECIDED)
    with pytest.raises(ValidationError, match="role is set exactly"):
        rebuild(result, role=Role.DEPLOYER)


def test_role_switch_reason_without_role_is_rejected() -> None:
    result = ends_early(RiskClass.OUT_OF_SCOPE, dumped_steps(1), Status.DECIDED)
    with pytest.raises(ValidationError, match="role_switch_reason needs a role"):
        rebuild(result, role_switch_reason="Rebranded the system")


# status derived from the steps


@pytest.mark.parametrize("status", [Status.NEEDS_MORE_INFORMATION, Status.LEGALLY_AMBIGUOUS])
def test_uncertain_result_without_an_uncertain_step_is_rejected(status: Status) -> None:
    with pytest.raises(ValidationError, match="steps imply status decided"):
        rebuild(worked_example_result(), status=status)


def test_decided_result_with_an_uncertain_step_is_rejected() -> None:
    steps = steps_with(ambiguous(StepName.HIGH_RISK))
    with pytest.raises(ValidationError, match="steps imply status legally_ambiguous"):
        rebuild(worked_example_result(), steps=steps)


def test_ambiguous_step_outranks_missing_information() -> None:
    steps = steps_with(missing_fact(StepName.SCOPE))
    steps[2] = ambiguous(StepName.HIGH_RISK).model_dump()
    with pytest.raises(ValidationError, match="steps imply status legally_ambiguous"):
        rebuild(worked_example_result(), status=Status.NEEDS_MORE_INFORMATION, steps=steps)
    result = rebuild(worked_example_result(), status=Status.LEGALLY_AMBIGUOUS, steps=steps)
    assert result.status is Status.LEGALLY_AMBIGUOUS


def test_needs_more_information_result_with_its_step_is_accepted() -> None:
    steps = steps_with(missing_fact(StepName.SCOPE))
    result = rebuild(worked_example_result(), status=Status.NEEDS_MORE_INFORMATION, steps=steps)
    missing = result.steps[0].missing_fact
    assert missing is not None
    assert missing.id == "eu_use"


# follow-up questions


def test_duplicate_follow_up_ids_are_rejected() -> None:
    good = worked_example_result()
    question = good.follow_up_questions[0].model_dump()
    with pytest.raises(ValidationError, match="ids must be unique"):
        rebuild(good, follow_up_questions=[question, question])


def test_missing_fact_absent_from_follow_ups_is_rejected() -> None:
    good = worked_example_result()
    steps = steps_with(missing_fact(StepName.SCOPE))
    with pytest.raises(ValidationError, match="must appear"):
        rebuild(
            good,
            status=Status.NEEDS_MORE_INFORMATION,
            steps=steps,
            follow_up_questions=good.follow_up_questions[:1],
        )


def test_missing_fact_with_different_follow_up_text_is_rejected() -> None:
    good = worked_example_result()
    reworded = FollowUpQuestion(id="eu_use", text="Where is the tool used?")
    with pytest.raises(ValidationError, match="same text"):
        rebuild(
            good,
            status=Status.NEEDS_MORE_INFORMATION,
            steps=steps_with(missing_fact(StepName.SCOPE)),
            follow_up_questions=(good.follow_up_questions[0], reworded),
        )


@pytest.mark.parametrize("bad_id", ["", "Ranks_People", "ranks-people", "1st", "a" * 65])
def test_follow_up_id_must_be_a_slug(bad_id: str) -> None:
    with pytest.raises(ValidationError, match="pattern"):
        FollowUpQuestion(id=bad_id, text="Does the tool rank people?")
