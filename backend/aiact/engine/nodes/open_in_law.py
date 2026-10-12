"""A question of law the model holds open, read on its stricter side in code (E19, user decision 3
option B), shared by the prohibited and high-risk checks.

Each practice or route the model marks unsettled in law names the key fact the question is about
(`open_on`). Code then sets that fact to its stricter value from the check's table, so the
model's own answer to it never decides anything: only another fact's settled "no" (or an
exception's settled "yes") can still rule the practice or route out. One the model marks
unsettled without naming a fact stays open whatever its facts say, since any of them may be the
lenient side of the question.
"""

from collections.abc import Mapping
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


def open_field(part: OpenOn) -> str | None:
    """The key fact `part` holds open in law, or None when it is settled or names none."""
    if part.settled_in_law is Settled.YES or part.open_on.value == NOT_NAMED:
        return None
    return part.open_on.value


def held_strict[P: HeldOpen](part: P, strict: Mapping[str, object]) -> P:
    """`part` with the fact it holds open set to its stricter value in `strict`, as a new copy;
    unchanged when it holds none open."""
    field = open_field(part)
    if field is None:
        return part
    return part.model_copy(update={field: strict[field]})


def stays_open(part: OpenOn, reading: Answer) -> bool:
    """Whether the question `part` holds open in law still decides anything, given its reading
    with the open fact held strict: never for a settled part; for one that names its open fact,
    unless another fact rules it out (the reading is "no"); always for one that names none."""
    if part.settled_in_law is Settled.YES:
        return False
    return open_field(part) is None or reading is not Answer.NO
