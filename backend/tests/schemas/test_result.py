import pytest
from pydantic import ValidationError

from aiact.schemas import (
    ClassificationResult,
    RiskClass,
    Role,
    Status,
    StepName,
    StepResult,
)
from tests.schemas.worked_example import worked_example_result


def rebuild(result: ClassificationResult, **changes: object) -> ClassificationResult:
    """Validate a changed copy (model_copy would skip the validators)."""
    return ClassificationResult.model_validate({**result.model_dump(), **changes})


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


def test_prohibited_with_steps_after_art_5_is_rejected() -> None:
    with pytest.raises(ValidationError, match=r"after the Art\. 5 check"):
        rebuild(worked_example_result(), risk_class=RiskClass.PROHIBITED)


def test_prohibited_ending_at_art_5_is_accepted() -> None:
    good = worked_example_result()
    steps = [step.model_dump() for step in good.steps[:2]]
    result = rebuild(good, risk_class=RiskClass.PROHIBITED, steps=steps)
    assert result.steps[-1].step is StepName.PROHIBITED


def test_steps_out_of_order_are_rejected() -> None:
    good = worked_example_result()
    steps = [step.model_dump() for step in reversed(good.steps)]
    with pytest.raises(ValidationError, match="check order"):
        rebuild(good, steps=steps)


def test_duplicate_steps_are_rejected() -> None:
    good = worked_example_result()
    steps = [good.steps[0].model_dump(), good.steps[0].model_dump()]
    with pytest.raises(ValidationError, match="check order"):
        rebuild(good, steps=steps)


@pytest.mark.parametrize("status", [Status.NEEDS_MORE_INFORMATION, Status.LEGALLY_AMBIGUOUS])
def test_uncertain_result_without_an_uncertain_step_is_rejected(status: Status) -> None:
    with pytest.raises(ValidationError, match="needs a step with that status"):
        rebuild(worked_example_result(), status=status)


def test_needs_more_information_result_with_its_step_is_accepted() -> None:
    good = worked_example_result()
    scope = StepResult(
        step=StepName.SCOPE,
        decision="Unclear whether the tool is used in the EU",
        status=Status.NEEDS_MORE_INFORMATION,
        missing_fact="Whether the tool is used in the EU",
    )
    steps = [scope.model_dump(), *(step.model_dump() for step in good.steps[1:])]
    result = rebuild(good, status=Status.NEEDS_MORE_INFORMATION, steps=steps)
    assert result.steps[0].missing_fact == "Whether the tool is used in the EU"
