"""One check of the staged engine and what it decided."""

from enum import StrEnum
from typing import Self

from pydantic import Field, model_validator

from aiact.schemas.base import ContractModel
from aiact.schemas.enums import Status
from aiact.schemas.evidence import Citation, Fact, OpenQuestion
from aiact.schemas.questions import SLUG_PATTERN, FollowUpQuestion


class StepName(StrEnum):
    """The checks in the Act's fixed order (INIT > How it works)."""

    SCOPE = "scope"
    PROHIBITED = "prohibited"
    HIGH_RISK = "high_risk"
    TRANSPARENCY = "transparency"
    ROLE_OBLIGATIONS = "role_obligations"


STEP_ORDER: tuple[StepName, ...] = tuple(StepName)
"""The engine's check order; a result lists its steps in this order."""

PROVIDER_REFUSAL = "provider_refusal"
"""The `error` of a step the model provider's content filter refused (decision 029): the check
was not assessed, and a person must review it."""


class StepResult(ContractModel):
    """The outcome of one check. An uncertain status names what is missing or open."""

    step: StepName
    decision: str = Field(min_length=1)
    facts_used: tuple[Fact, ...] = ()
    citations: tuple[Citation, ...] = ()
    status: Status = Status.DECIDED
    missing_fact: FollowUpQuestion | None = Field(
        default=None, description="The question that would supply the missing fact."
    )
    open_question: OpenQuestion | None = None
    error: str | None = Field(
        default=None,
        pattern=SLUG_PATTERN,
        description="A machine-readable failure code, for example `citation_unverified`.",
    )

    @model_validator(mode="after")
    def _status_names_its_gap(self) -> Self:
        if self.status is Status.NEEDS_MORE_INFORMATION and not (self.missing_fact or self.error):
            raise ValueError("a needs_more_information step must set its missing_fact or error")
        if self.status is Status.LEGALLY_AMBIGUOUS and self.open_question is None:
            raise ValueError("a legally_ambiguous step must set its open_question")
        if self.status is Status.DECIDED and (
            self.missing_fact or self.open_question or self.error
        ):
            raise ValueError("a decided step has no missing_fact, open_question or error")
        return self
