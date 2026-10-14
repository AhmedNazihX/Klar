"""Known gaps of the node replays: recorded cases whose outcome differs from their label (E3-E10).

Each gap names the reason and the wrong reading it documents (`reads`). A replay with a gap fails
when it starts matching its label (the entry is then removed), and fails too when it misses in
any other way than the documented one; otherwise it is an expected failure.

Also how a whole run, or a streamed one, that met a stale recording is told apart from a node
error, and E18's negative fixtures.
"""

from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

import pytest
from openrouter.utils.retries import PermanentError
from vcr.errors import CannotOverwriteExistingCassetteException

from aiact.engine import ClassificationFailedError, ClassifyEvent, ErrorEvent
from aiact.engine.state import CheckOutcome
from aiact.eval.cases import BenchmarkCase, load_yaml_file
from tests.engine.nodes.corpus_recording import RecordingPendingError

STALE_RECORDING_ERRORS = (
    CannotOverwriteExistingCassetteException,
    PermanentError,
    RecordingPendingError,
)
"""How a replay fails on a stale or missing recording: VCR refuses the new request, the
OpenRouter SDK gives up on the refused call, or a replay with no cassette at all stops before
the call (a stream that ends in an error event is turned into `RecordingPendingError` by its
test)."""


E21_PROMPT_RECORDING_PENDING = pytest.mark.xfail(
    strict=True,
    raises=STALE_RECORDING_ERRORS,
    reason="recording pending (orchestrator): E21 changed the high-risk prompt (the H4 rule: a "
    "tool that ranks critical-infrastructure assets for longer-term investment or renewal "
    "planning, without monitoring them in operation, is no safety component of it), so the "
    "recorded requests are stale, and E21's gas-main fixture has none yet; delete and re-record",
)
"""The replays whose recorded request carries the high-risk prompt E21 changed, until the
orchestrator re-records them (BACKLOG > E21)."""


def is_stale_recording(error: BaseException) -> bool:
    """Whether `error`, or an error in its `__cause__` chain, is a stale or missing recording."""
    seen: BaseException | None = error
    while seen is not None:
        if isinstance(seen, STALE_RECORDING_ERRORS):
            return True
        seen = seen.__cause__
    return False


@contextmanager
def stale_recording_pending() -> Iterator[None]:
    """Re-raise a classification run a stale or missing recording stopped as
    `RecordingPendingError`, the marker's error; any other failure as it was."""
    try:
        yield
    except ClassificationFailedError as error:
        if not is_stale_recording(error):
            raise
        raise RecordingPendingError(f"the {error.step} node met a stale recording") from error


STALE_RECORDING_LOG = "CannotOverwriteExistingCassetteException"
"""What the engine logs when a node's request isn't in the recording (only its type's name)."""


def raise_if_recording_stale(events: list[ClassifyEvent], log: str, stale: str) -> None:
    """A stale recording stops a streamed run in an error event and the engine only logs its
    cause, so name it here: `RecordingPendingError` (saying `stale`) rather than an assertion on
    the stream."""
    if events and isinstance(events[-1], ErrorEvent) and STALE_RECORDING_LOG in log:
        raise RecordingPendingError(stale)


NEGATIVE_CASES_DIR = Path(__file__).resolve().parents[2] / "fixtures" / "negative_cases"
"""E18's negative fixtures: cases written from the Act's conditions for a provision that does
not apply, never from a benchmark example, and never scored."""


def negative_cases(cause: str) -> list[BenchmarkCase]:
    """The negative fixtures tagged `cause:<cause>` (for example `t1`)."""
    paths = sorted(NEGATIVE_CASES_DIR.glob("*.yaml"))
    cases = [case for path in paths for case in load_yaml_file(path)]
    return [case for case in cases if f"cause:{cause}" in case.tags]


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
