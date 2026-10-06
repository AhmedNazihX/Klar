"""The events a streamed classification sends while it runs (E10; decision 026, Classify).

In order: `facts` once the facts node is done; for each check, `step_started` then `step` (the
check's `StepResult`, and for the high-risk check the Annex points it settled on); then either
`result` or, when a node failed, `error`, which names the node and is the last event. A run that
sent `error` never sends a class ("Klar never guesses a class when a check fails").
"""

from typing import Annotated, Literal

from pydantic import Field

from aiact.schemas import (
    ClassificationResult,
    Fact,
    FollowUpQuestion,
    Language,
    StepName,
    StepResult,
)
from aiact.schemas.base import ContractModel


class FactsEvent(ContractModel):
    """The facts the description states, implies or leaves assumed, and the questions they
    raise; the interface shows these while the checks run."""

    event: Literal["facts"] = "facts"
    facts: tuple[Fact, ...]
    follow_up_questions: tuple[FollowUpQuestion, ...]


class StepStartedEvent(ContractModel):
    """A check started: the interface marks it running."""

    event: Literal["step_started"] = "step_started"
    step: StepName


class StepEvent(ContractModel):
    """A check finished, with its step as the result will show it."""

    event: Literal["step"] = "step"
    step: StepResult
    matches: tuple[str, ...] = ()
    """The closest matches the check weighed, for the running list: the Annex points the
    high-risk step cites (`annex:III:4:a`), whatever it decided; empty for the other checks."""


class ErrorEvent(ContractModel):
    """A node failed, so the run stopped without a result."""

    event: Literal["error"] = "error"
    step: str
    """The node that failed: `facts`, a check's name, or `finalize`."""
    message: str


class ResultEvent(ContractModel):
    event: Literal["result"] = "result"
    result: ClassificationResult


ClassifyEvent = Annotated[
    FactsEvent | StepStartedEvent | StepEvent | ErrorEvent | ResultEvent,
    Field(discriminator="event"),
]


STOPPED: dict[Language, str] = {
    Language.EN: "The {step} check could not finish, so Klar gives no class. Please try again.",
    Language.DE: "Die Prüfung „{step}“ konnte nicht abgeschlossen werden, daher nennt Klar keine "
    "Klasse. Bitte versuchen Sie es erneut.",
}
"""The error event's message, in the run's language."""


def matches(step: StepResult) -> tuple[str, ...]:
    """The Annex points a high-risk step cites, in its order; none for other steps."""
    if step.step is not StepName.HIGH_RISK:
        return ()
    cited = (c.provision_id for c in step.citations if c.provision_id.startswith("annex:"))
    return tuple(dict.fromkeys(cited))


def error_event(node: str, language: Language) -> ErrorEvent:
    return ErrorEvent(step=node, message=STOPPED[language].format(step=node))
