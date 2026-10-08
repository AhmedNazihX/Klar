"""Questions the interface asks the user; stable ids let answers be keyed across re-runs."""

from datetime import date
from typing import Self

from pydantic import Field, model_validator

from aiact.schemas.base import ContractModel
from aiact.schemas.enums import AnswerOption, HighRiskRoute, RiskClass
from aiact.schemas.evidence import Citation

SLUG_PATTERN = r"^[a-z][a-z0-9_]{0,63}$"
"""A short machine-readable id such as `ranks_people` or `citation_unverified`."""

YES_NO: tuple[AnswerOption, ...] = (AnswerOption.YES, AnswerOption.NO, AnswerOption.NOT_SURE)
"""The answers offered to a yes/no question."""

DESCRIPTION_QUESTION_IDS: tuple[str, ...] = ("what_it_decides", "who_it_affects", "bought_or_built")
"""The three questions a "needs a description" result asks, in this order (E13, decision 010
addendum): what the tool decides or suggests, who it affects, and whether it was bought or
built."""


class AnswerOutcome(ContractModel):
    """What a "yes" settles, where the step asking knows it: the class and, for high-risk, the
    route, the provision and the date the duties apply from (decision 026 items 13 and 18). A
    "no" has no such outcome: no class is predicted before the remaining checks run, so the
    interface shows the fixed sentence of decision 026 item 13 instead."""

    risk_class: RiskClass
    high_risk_route: HighRiskRoute | None = None
    provision_id: str | None = Field(
        default=None, description="The provision a yes rests on, for example `annex:I:A:11`."
    )
    duties_from: date | None = Field(
        default=None,
        description="The date the route's high-risk duties apply from under the Art. 113 of the "
        "result's law version (the original text's dates for an original-text run, E11); None "
        "when the AI Act itself sets no duties (an Annex I Section B product, Art. 2(2)).",
    )

    @model_validator(mode="after")
    def _route_only_for_high_risk(self) -> Self:
        if self.high_risk_route is not None and self.risk_class is not RiskClass.HIGH_RISK:
            raise ValueError("only a high_risk outcome has a high_risk_route")
        return self


class FollowUpQuestion(ContractModel):
    """A key-fact question. Its `id` keys the user's answer when the engine runs again."""

    id: str = Field(pattern=SLUG_PATTERN, description="Stable slug, for example `human_review`.")
    text: str = Field(min_length=1)
    about: str | None = Field(
        default=None, description="What the answer settles, for example a step or provision_id."
    )
    hint: str | None = Field(
        default=None,
        description="Why the answer matters, naming the provision it decides, or examples of an "
        "answer (a needs-a-description question), in the result's language.",
    )
    options: tuple[AnswerOption, ...] = Field(
        default=(),
        description="The answers offered: yes, no and not sure for a yes/no question; empty for "
        "a question answered in words.",
    )
    if_yes: AnswerOutcome | None = Field(
        default=None, description="What a yes settles, when the step knows it."
    )
    citations: tuple[Citation, ...] = Field(
        default=(),
        description="The provisions the question rests on, quoted; on a step's missing fact, "
        "each is one of the step's own (checked) citations.",
    )

    @model_validator(mode="after")
    def _options_fit_the_answer(self) -> Self:
        if self.options not in ((), YES_NO):
            raise ValueError("options are either empty or exactly yes, no and not sure")
        if self.if_yes is not None and not self.options:
            raise ValueError("if_yes needs a yes/no question")
        return self
