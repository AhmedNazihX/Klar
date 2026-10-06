"""Known gaps of the node replays: recorded cases whose outcome differs from their label (E3-E10).

Each gap names the reason and the wrong reading it documents (`reads`). A replay with a gap fails
when it starts matching its label (the entry is then removed), and fails too when it misses in
any other way than the documented one; otherwise it is an expected failure.
"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass

import pytest

from aiact.engine.state import CheckOutcome
from aiact.eval.cases import BenchmarkCase
from aiact.schemas import PROVIDER_REFUSAL


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


def refused(outcome: CheckOutcome, _case: BenchmarkCase) -> bool:
    """The provider's content filter refused the reply (decision 029)."""
    return outcome.step.error == PROVIDER_REFUSAL
