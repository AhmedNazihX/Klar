"""Key-fact answers the engine model gives a check, and the facts a step shows for them (E3, E7).

A check asks the model fixed key-fact questions and applies the Act's rules to the answers in
code. Each answer carries its evidence tag, the answer as one short fact, and the numbers of the
extracted facts it rests on.
"""

from collections.abc import Sequence
from enum import StrEnum
from typing import Protocol

from pydantic import Field

from aiact.schemas import EvidenceTag, Fact
from aiact.schemas.base import ContractModel


class Answer(StrEnum):
    YES = "yes"
    NO = "no"
    UNKNOWN = "unknown"


class KeyFact(ContractModel):
    """One key-fact answer. Enum fields carry no description: strict structured output rejects
    keywords next to a `$ref`; the prompt explains every field instead."""

    answer: Answer
    evidence: EvidenceTag
    fact: str = Field(min_length=1)
    fact_numbers: tuple[int, ...]

    @property
    def is_known(self) -> bool:
        return self.answer is not Answer.UNKNOWN


class CitedFact(Protocol):
    """What `facts_used` reads from an answer: its tag, its fact, the facts it cites, and
    whether it settled anything (an unknown answer is a question, not a fact)."""

    @property
    def evidence(self) -> EvidenceTag: ...
    @property
    def fact(self) -> str: ...
    @property
    def fact_numbers(self) -> tuple[int, ...]: ...
    @property
    def is_known(self) -> bool: ...


def facts_used(used: Sequence[CitedFact], facts: Sequence[Fact]) -> tuple[Fact, ...]:
    """The extracted facts an answer cites, or the answer itself as an inferred or assumed fact
    (a stated fact must point into the description, and only the facts node sets spans)."""
    result: dict[str, Fact] = {}
    for answer in used:
        if not answer.is_known:
            continue
        cited = [facts[n - 1] for n in answer.fact_numbers if 0 < n <= len(facts)]
        if cited and answer.evidence is not EvidenceTag.ASSUMED:
            result.update((fact.text, fact) for fact in cited)
            continue
        is_assumed = answer.evidence is EvidenceTag.ASSUMED
        evidence = EvidenceTag.ASSUMED if is_assumed else EvidenceTag.INFERRED
        result.setdefault(answer.fact, Fact(text=answer.fact, evidence=evidence))
    return tuple(result.values())
