"""Helpers that derive valid and invalid variants of the worked example."""

from aiact.schemas import (
    DESCRIPTION_QUESTION_IDS,
    PROVIDER_REFUSAL,
    ClassificationResult,
    FollowUpQuestion,
    OpenQuestion,
    Reading,
    RiskClass,
    Status,
    StepName,
    StepResult,
)
from aiact.schemas.result import derived_status
from tests.schemas.worked_example import EU_USE_QUESTION, worked_example_result


def open_question(question: str, stricter: str, lenient: str) -> OpenQuestion:
    """A contract open question whose two readings carry only a title and their text, the
    stricter one applied."""
    readings = (
        Reading(title="Stricter reading", explanation=stricter, is_applied=True),
        Reading(title="Lenient reading", explanation=lenient),
    )
    return OpenQuestion(question=question, readings=readings)


OPEN_QUESTION = open_question(
    "Does the law settle this point?",
    "Yes, the stricter reading applies",
    "No, the lenient reading applies",
)

StepDump = dict[str, object]


def rebuild(result: ClassificationResult, **changes: object) -> ClassificationResult:
    """Validate a changed copy (model_copy would skip the validators). A new law version gets
    its own law-text label, unless `changes` gives one."""
    dropped = {"law_text"} if "law_version" in changes else set()
    return ClassificationResult.model_validate({**result.model_dump(exclude=dropped), **changes})


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


def refused(name: StepName) -> StepResult:
    """A step the model provider's content filter refused (decision 029); uses the worked
    example's `eu_use` question, so the follow-up rule holds."""
    return StepResult(
        step=name,
        decision="The provider's content filter blocked this description.",
        status=Status.NEEDS_MORE_INFORMATION,
        missing_fact=EU_USE_QUESTION,
        error=PROVIDER_REFUSAL,
    )


def stored_before_decision_030(
    result: ClassificationResult, name: StepName = StepName.HIGH_RISK
) -> ClassificationResult:
    """`result` as decision 029 stored it with its `name` check refused: the step refused and
    listed in `not_assessed`, the class and its findings kept."""
    steps = [refused(name) if step.step is name else step for step in result.steps]
    questions = {q.id: q for q in (*result.follow_up_questions, EU_USE_QUESTION)}
    return rebuild(
        result,
        steps=[step.model_dump() for step in steps],
        status=derived_status(steps),
        not_assessed=(name,),
        follow_up_questions=tuple(q.model_dump() for q in questions.values()),
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


DESCRIPTION_QUESTIONS = tuple(
    FollowUpQuestion(id=question_id, text=f"Question {number}?")
    for number, question_id in enumerate(DESCRIPTION_QUESTION_IDS, start=1)
)
"""The three needs-a-description questions, with placeholder texts."""


def needs_description(**changes: object) -> ClassificationResult:
    """The worked example turned into a needs-a-description result (E13): no steps, no class,
    the three description questions."""
    fields: dict[str, object] = {
        "steps": [],
        "risk_class": None,
        "status": Status.NEEDS_MORE_INFORMATION,
        "role": None,
        "annex_point": None,
        "transparency_duties": (),
        "deciding_facts": (),
        "obligations": (),
        "legal_review": None,
        "follow_up_questions": DESCRIPTION_QUESTIONS,
    }
    return rebuild(worked_example_result(), **fields | changes)
