"""The step sequence: no check skipped, and the early ends of decision 010."""

import pytest
from pydantic import ValidationError

from aiact.schemas import STEP_ORDER, ClassificationResult, RiskClass, Status, StepName
from tests.schemas.builders import (
    DESCRIPTION_QUESTIONS,
    ambiguous,
    dumped_steps,
    ends_early,
    missing_fact,
    needs_description,
    rebuild,
    steps_with,
    unverified,
)
from tests.schemas.worked_example import worked_example_result

UNCERTAIN = {"legally_ambiguous": ambiguous, "missing_fact": missing_fact}


# prohibited


def test_decided_prohibited_with_steps_after_art_5_is_rejected() -> None:
    with pytest.raises(ValidationError, match="needs the steps"):
        rebuild(worked_example_result(), risk_class=RiskClass.PROHIBITED)


def test_decided_prohibited_ending_at_art_5_is_accepted() -> None:
    result = ends_early(RiskClass.PROHIBITED, dumped_steps(2), Status.DECIDED)
    assert result.steps[-1].step is StepName.PROHIBITED
    assert result.role is None


def test_prohibited_with_unverified_art_5_step_may_end_early() -> None:
    steps = steps_with(unverified(StepName.PROHIBITED), 2)
    result = ends_early(RiskClass.PROHIBITED, steps, Status.NEEDS_MORE_INFORMATION)
    assert result.steps[-1].error == "citation_unverified"


@pytest.mark.parametrize("kind", UNCERTAIN)
def test_uncertain_art_5_stopping_early_is_rejected(kind: str) -> None:
    step = UNCERTAIN[kind](StepName.PROHIBITED)
    with pytest.raises(ValidationError, match="needs the steps"):
        ends_early(RiskClass.PROHIBITED, steps_with(step, 2), step.status)


@pytest.mark.parametrize("kind", UNCERTAIN)
def test_uncertain_art_5_runs_the_remaining_checks(kind: str) -> None:
    step = UNCERTAIN[kind](StepName.PROHIBITED)
    result = rebuild(
        worked_example_result(),
        risk_class=RiskClass.PROHIBITED,
        status=step.status,
        steps=steps_with(step),
    )
    assert [s.step for s in result.steps] == list(StepName)


# out_of_scope


def test_out_of_scope_ending_after_decided_scope_is_accepted() -> None:
    result = ends_early(RiskClass.OUT_OF_SCOPE, dumped_steps(1), Status.DECIDED)
    assert [step.step for step in result.steps] == [StepName.SCOPE]


def test_out_of_scope_with_unverified_scope_step_is_accepted() -> None:
    steps = steps_with(unverified(StepName.SCOPE), 1)
    result = ends_early(RiskClass.OUT_OF_SCOPE, steps, Status.NEEDS_MORE_INFORMATION)
    assert result.steps[0].error == "citation_unverified"


@pytest.mark.parametrize("kind", UNCERTAIN)
@pytest.mark.parametrize("count", [1, None])
def test_out_of_scope_with_uncertain_scope_step_is_rejected(kind: str, count: int | None) -> None:
    step = UNCERTAIN[kind](StepName.SCOPE)
    with pytest.raises(ValidationError, match="needs a decided scope step"):
        ends_early(RiskClass.OUT_OF_SCOPE, steps_with(step, count), step.status)


def test_out_of_scope_running_further_checks_is_rejected() -> None:
    with pytest.raises(ValidationError, match="needs the steps"):
        ends_early(RiskClass.OUT_OF_SCOPE, dumped_steps(), Status.DECIDED)


# no check skipped


def test_incomplete_steps_are_rejected() -> None:
    with pytest.raises(ValidationError, match="needs the steps"):
        rebuild(worked_example_result(), steps=dumped_steps(3), role=None)


def test_skipped_step_is_rejected() -> None:
    steps = dumped_steps()
    del steps[2]
    with pytest.raises(ValidationError, match="none skipped"):
        rebuild(worked_example_result(), steps=steps)


def test_steps_out_of_order_are_rejected() -> None:
    with pytest.raises(ValidationError, match="check order"):
        rebuild(worked_example_result(), steps=list(reversed(dumped_steps())))


def test_duplicate_steps_are_rejected() -> None:
    first = dumped_steps(1)[0]
    with pytest.raises(ValidationError, match="check order"):
        rebuild(worked_example_result(), steps=[first, first])


# needs a description (E13): no steps, no class


def test_a_needs_description_result_has_no_steps_and_no_class() -> None:
    result = needs_description()
    assert result.steps == ()
    assert result.risk_class is None
    assert result.needs_description
    assert result.status is Status.NEEDS_MORE_INFORMATION


def test_a_needs_description_result_round_trips_through_json() -> None:
    result = needs_description()
    assert ClassificationResult.model_validate_json(result.model_dump_json()) == result


def test_a_result_with_steps_is_not_a_needs_description_result() -> None:
    assert not worked_example_result().needs_description


@pytest.mark.parametrize("risk_class", list(RiskClass))
def test_no_steps_with_a_class_is_rejected(risk_class: RiskClass) -> None:
    with pytest.raises(ValidationError, match="a result with no steps has no class"):
        needs_description(risk_class=risk_class)


@pytest.mark.parametrize("count", range(1, len(STEP_ORDER) + 1))
def test_no_class_with_steps_is_rejected(count: int) -> None:
    """Only a refused check (decision 030) leaves a result with steps without a class."""
    with pytest.raises(ValidationError, match="has a class unless the model provider refused"):
        needs_description(steps=dumped_steps(count), status=Status.DECIDED)


@pytest.mark.parametrize("status", [Status.DECIDED, Status.LEGALLY_AMBIGUOUS])
def test_a_needs_description_result_is_needs_more_information(status: Status) -> None:
    with pytest.raises(ValidationError, match="imply status needs_more_information"):
        needs_description(status=status)


@pytest.mark.parametrize("left_out", range(len(DESCRIPTION_QUESTIONS)))
def test_a_needs_description_result_asks_all_three_questions(left_out: int) -> None:
    asked = tuple(q for i, q in enumerate(DESCRIPTION_QUESTIONS) if i != left_out)
    with pytest.raises(ValidationError, match="needs-a-description result asks"):
        needs_description(follow_up_questions=asked)


@pytest.mark.parametrize(
    "field",
    [
        {"annex_point": "annex:III:4:a"},
        {"transparency_duties": ("art:50:1",)},
        {"legal_review": "Have this result reviewed by a lawyer."},
        {"deciding_facts": worked_example_result().deciding_facts},
        {"obligations": worked_example_result().obligations},
    ],
)
def test_a_needs_description_result_has_no_class_fields(field: dict[str, object]) -> None:
    with pytest.raises(ValidationError, match="needs-a-description result has no"):
        needs_description(**field)


def test_a_needs_description_result_has_no_role() -> None:
    with pytest.raises(ValidationError, match="role is set exactly"):
        needs_description(role="deployer")


@pytest.mark.parametrize("count", range(1, len(STEP_ORDER)))
def test_other_short_step_lists_are_still_rejected(count: int) -> None:
    """Only the three early ends are allowed: a high-risk result with any shorter list fails."""
    with pytest.raises(ValidationError, match="needs the steps"):
        rebuild(worked_example_result(), steps=dumped_steps(count), role=None, obligations=())


def test_a_result_stored_before_e13_still_loads() -> None:
    """Stored results always carry a class and at least one step."""
    stored = worked_example_result().model_dump(mode="json")
    assert ClassificationResult.model_validate(stored).risk_class is RiskClass.HIGH_RISK
