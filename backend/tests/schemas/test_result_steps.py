"""The step sequence: no check skipped, and the early ends of decision 010."""

import pytest
from pydantic import ValidationError

from aiact.schemas import RiskClass, Status, StepName
from tests.schemas.builders import (
    ambiguous,
    dumped_steps,
    ends_early,
    missing_fact,
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
