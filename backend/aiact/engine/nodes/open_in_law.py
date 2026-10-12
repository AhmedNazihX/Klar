"""A question of law the model holds open, read on its stricter side in code (E19, user decision 3
option B), shared by the prohibited and high-risk checks. One rule for both:

- **Raised.** A point (an Art. 5 practice, an Annex III or Annex I route) is raised unless its
  gate, the first condition it reads, is "no". A gate answered "no" rules the point out whatever
  `settled_in_law` and `open_on` say, unless the question is open on the gate itself.
- **Held strict.** Each part the model marks unsettled in law names the key fact the question is
  about (`open_on`). Code sets that fact to its stricter value from the check's table, so the
  model's own answer to it never decides anything.
- **Still open.** A raised point stays open unless another of its facts rules it out. One the
  model marks unsettled without naming a fact stays open, since any of its facts may be the
  lenient side of the question; a name no point of the part reads counts as no name. When one
  answer part serves several points, the question belongs to the points that read the fact it
  names: the others are decided on their facts.
"""

from collections.abc import Collection, Mapping
from enum import StrEnum
from typing import Any, Protocol, Self

from aiact.engine.nodes.key_facts import Answer, Settled

NOT_NAMED = "none"
"""The `open_on` value of a part settled in law, or of one the model leaves unnamed."""


class OpenOn(Protocol):
    """What a part's openness is read from: whether it is settled, and the fact it holds open."""

    @property
    def settled_in_law(self) -> Settled: ...
    @property
    def open_on(self) -> StrEnum: ...


class HeldOpen(OpenOn, Protocol):
    """A model answer part that names its open fact, copied with an update (a pydantic model)."""

    def model_copy(
        self, *, update: Mapping[str, Any] | None = None, deep: bool = False
    ) -> Self: ...


def open_field(part: OpenOn, facts: Collection[str]) -> str | None:
    """The key fact `part` holds open in law, if one of its points reads it (`facts`); None when
    it is settled, names none, or names a fact none of its points reads (read as no name)."""
    field = part.open_on.value
    if part.settled_in_law is Settled.YES or field not in facts:
        return None
    return field


def held_strict[P: HeldOpen](part: P, strict: Mapping[str, object], facts: Collection[str]) -> P:
    """`part` with the fact it holds open (`open_field`) set to its stricter value in `strict`,
    as a new copy; unchanged when it holds none open."""
    field = open_field(part, facts)
    if field is None:
        return part
    return part.model_copy(update={field: strict[field]})


def raised(part: OpenOn, gate_field: str, gate: Answer, facts: Collection[str]) -> bool:
    """Whether a point is raised: its gate (`gate_field`, answered `gate`) isn't "no", or the
    question is open on the gate, which held strict raises it."""
    return gate is not Answer.NO or open_field(part, facts) == gate_field


def stays_open(part: OpenOn, reading: Answer, own: Collection[str], facts: Collection[str]) -> bool:
    """Whether the question `part` holds open in law still decides a raised point, given its
    reading with the open fact held strict. `own` are the facts the point reads, `facts` those
    every point of the part reads (the same for a part read by one point). Never for a settled
    part, nor for one open on a fact only another point of the part reads; for one open on a
    fact of its own, unless another fact rules the point out (the reading is "no"); always for
    one that names none."""
    if part.settled_in_law is Settled.YES:
        return False
    field = open_field(part, facts)
    if field is None:
        return True
    return field in own and reading is not Answer.NO
