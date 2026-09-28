"""Helpers that derive valid and invalid variants of the worked example."""

from aiact.schemas import (
    ClassificationResult,
    OpenQuestion,
    RiskClass,
    Status,
    StepName,
    StepResult,
)
from tests.schemas.worked_example import EU_USE_QUESTION, worked_example_result

OPEN_QUESTION = OpenQuestion(
    question="Does the law settle this point?",
    readings=("Yes, the stricter reading applies", "No, the lenient reading applies"),
)

StepDump = dict[str, object]


def rebuild(result: ClassificationResult, **changes: object) -> ClassificationResult:
    """Validate a changed copy (model_copy would skip the validators)."""
    return ClassificationResult.model_validate({**result.model_dump(), **changes})


def dumped_steps(count: int | None = None) -> list[StepDump]:
    return [step.model_dump() for step in worked_example_result().steps[:count]]


def ambiguous(name: StepName) -> StepResult:
    return StepResult(
        step=name,
        decision="The law doesn't settle this",
        status=Status.LEGALLY_AMBIGUOUS,
        open_question=OPEN_QUESTION,
    )


def missing_fact(name: StepName) -> StepResult:
    """Uses the worked example's `eu_use` question, so the follow-up rule holds."""
    return StepResult(
        step=name,
        decision="A deciding fact is missing",
        status=Status.NEEDS_MORE_INFORMATION,
        missing_fact=EU_USE_QUESTION,
    )


def unverified(name: StepName) -> StepResult:
    """A step E9 marked after routing: a citation failed verification."""
    return StepResult(
        step=name,
        decision="Decided, but a citation could not be verified",
        status=Status.NEEDS_MORE_INFORMATION,
        error="citation_unverified",
    )


def steps_with(step: StepResult, count: int | None = None) -> list[StepDump]:
    """The worked example's first `count` steps, with `step` replacing the one of its name."""
    return [
        step.model_dump() if dump["step"] is step.step else dump for dump in dumped_steps(count)
    ]


def ends_early(
    risk_class: RiskClass, steps: list[StepDump], status: Status
) -> ClassificationResult:
    """The worked example turned into an early-ending result, without role or class fields."""
    return rebuild(
        worked_example_result(),
        risk_class=risk_class,
        status=status,
        steps=steps,
        role=None,
        annex_point=None,
        obligations=(),
    )
