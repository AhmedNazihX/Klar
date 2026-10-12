"""The high-risk node's model answer (E5): one part per route (Annex III, the Art. 6(3) filter,
Annex I), fixed key facts each, and the fact each Annex route holds open in law (E19,
`open_in_law`) with its stricter value. `high_risk` applies Art. 6 to it; nothing here calls a
model or reads the corpus. Moved out of `high_risk` by E19 to keep that module near 800 lines.
"""

from collections.abc import Mapping
from enum import StrEnum

from pydantic import Field

from aiact.engine.nodes.key_facts import Answer, Settled
from aiact.engine.nodes.open_in_law import NOT_NAMED
from aiact.llm.replies import FollowUpQuestion as ReplyQuestion
from aiact.llm.replies import OpenQuestion as ReplyOpenQuestion
from aiact.schemas import EvidenceTag
from aiact.schemas.base import ContractModel


class Art63Condition(StrEnum):
    """The Art. 6(3) condition met, second subparagraph (a)-(d), or none."""

    NONE = "none"
    A = "a"
    B = "b"
    C = "c"
    D = "d"


class RouteSummary(ContractModel):
    """A route's answer as `key_facts.facts_used` reads it: its `fact` sums up the whole route,
    so it always counts as settled (an open fact is asked through the route's question)."""

    @property
    def is_known(self) -> bool:
        return True


class AnnexIIIOpenOn(StrEnum):
    NONE = NOT_NAMED
    USES = "uses"
    PUBLIC_AUTHORITY = "public_authority"


class AnnexIIIAnswer(RouteSummary):
    """The Annex III use. Enum fields carry no description: strict structured output rejects
    keywords next to a `$ref`; the prompt explains every field instead. Each route's
    `settled_in_law` and `open_question` come right after its facts, so the model answers them
    in that order every time; on the two Annex routes `open_on` follows, naming the key fact a
    question the law leaves open is about (E19, `open_in_law`)."""

    point: str | None
    uses: Answer
    public_authority: Answer
    settled_in_law: Settled
    open_question: ReplyOpenQuestion | None
    open_on: AnnexIIIOpenOn
    evidence: EvidenceTag
    fact: str = Field(min_length=1)
    fact_numbers: tuple[int, ...]
    examples: tuple[str, ...]


class Art63Answer(RouteSummary):
    condition: Art63Condition
    profiling: Answer
    settled_in_law: Settled
    open_question: ReplyOpenQuestion | None
    evidence: EvidenceTag
    fact: str = Field(min_length=1)
    fact_numbers: tuple[int, ...]


class AnnexIOpenOn(StrEnum):
    NONE = NOT_NAMED
    COVERED = "covered"
    SAFETY_COMPONENT_OR_PRODUCT = "safety_component_or_product"
    THIRD_PARTY_ASSESSMENT = "third_party_assessment"


class AnnexIAnswer(RouteSummary):
    point: str | None
    covered: Answer
    safety_component_or_product: Answer
    third_party_assessment: Answer
    settled_in_law: Settled
    open_question: ReplyOpenQuestion | None
    open_on: AnnexIOpenOn
    evidence: EvidenceTag
    fact: str = Field(min_length=1)
    fact_numbers: tuple[int, ...]


STRICT_VALUES: Mapping[str, Answer] = {
    "uses": Answer.YES,
    "public_authority": Answer.YES,
    "covered": Answer.YES,
    "safety_component_or_product": Answer.YES,
    "third_party_assessment": Answer.YES,
}
"""Each Annex route fact's stricter value (B2): the one that keeps the route high-risk."""


RouteAnswer = AnnexIIIAnswer | Art63Answer | AnnexIAnswer


class HighRiskAnswer(ContractModel):
    """The model's whole answer; also the JSON schema it must fill."""

    annex_iii: AnnexIIIAnswer
    art_6_3: Art63Answer
    annex_i: AnnexIAnswer
    question: ReplyQuestion | None
