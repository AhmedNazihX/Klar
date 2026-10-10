"""Known gaps of the node replays: recorded cases whose outcome differs from their label (E3-E10).

Each gap names the reason and the wrong reading it documents (`reads`). A replay with a gap fails
when it starts matching its label (the entry is then removed), and fails too when it misses in
any other way than the documented one; otherwise it is an expected failure.

A replay whose recorded request the engine provider refused now sends it to the second model
(decision 033), whose reply isn't recorded yet: `refusal_route_pending` marks it until it is.
"""

from collections.abc import Callable, Collection, Mapping
from dataclasses import dataclass

import pytest
from vcr.errors import CannotOverwriteExistingCassetteException

from aiact.engine.state import CheckOutcome
from aiact.eval.cases import BenchmarkCase


@dataclass(frozen=True)
class KnownGap:
    reason: str
    reads: Callable[[CheckOutcome, BenchmarkCase], bool]
    """The documented wrong reading; any other miss fails the replay."""


def expect_known_gap(
    gaps: Mapping[str, KnownGap],
    outcome: CheckOutcome,
    case: BenchmarkCase,
    *,
    matches: bool,
    shown: object,
) -> None:
    """Nothing for a case without a gap. For one with a gap: fail when it now matches, assert it
    reads as documented (`shown` is the diagnostic), then xfail with the reason."""
    gap = gaps.get(case.id)
    if gap is None:
        return
    if matches:
        pytest.fail(f"{case.id} now matches its label; remove it from KNOWN_GAPS")
    assert gap.reads(outcome, case), shown
    pytest.xfail(gap.reason)


NOT_ASSESSED = {
    "en": "The model provider's content filter blocked this description, so it could not be "
    "assessed automatically. No risk class is given: a person must review the description.",
    "de": "Der Inhaltsfilter des Modellanbieters hat diese Beschreibung blockiert, daher konnte "
    "sie nicht automatisch geprüft werden. Es wird keine Risikoklasse angegeben: Ein Mensch muss "
    "die Beschreibung prüfen.",
}
"""Every refused step's decision, by language (decision 030): written out, not imported."""


REFUSAL_ROUTE_PENDING = pytest.mark.xfail(
    strict=True,
    raises=CannotOverwriteExistingCassetteException,
    reason="recording pending: the engine provider refused this request, and the second model's "
    "reply (decision 033) isn't recorded yet; record it, then drop this mark",
)
"""Fails only on the unrecorded second call; once recorded, the replay passes and the strict
mark fails, so it is dropped."""


def refusal_route_pending(
    case_id: str, refused: Collection[str]
) -> tuple[pytest.MarkDecorator, ...]:
    """`REFUSAL_ROUTE_PENDING` for a case in `refused`, else no mark."""
    return (REFUSAL_ROUTE_PENDING,) if case_id in refused else ()
