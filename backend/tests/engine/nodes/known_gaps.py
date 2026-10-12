"""Known gaps of the node replays: recorded cases whose outcome differs from their label (E3-E10).

Each gap names the reason and the wrong reading it documents (`reads`). A replay with a gap fails
when it starts matching its label (the entry is then removed), and fails too when it misses in
any other way than the documented one; otherwise it is an expected failure.

Also the replays a prompt change left stale until they are re-recorded, and E18's negative
fixtures.
"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

import pytest
from openrouter.utils.retries import PermanentError
from vcr.errors import CannotOverwriteExistingCassetteException

from aiact.engine import ClassificationFailedError
from aiact.engine.state import CheckOutcome
from aiact.eval.cases import BenchmarkCase, load_yaml_file
from tests.engine.nodes.corpus_recording import RecordingPendingError

E19_PROMPTS_RECORDING_PENDING = pytest.mark.xfail(
    strict=True,
    raises=(
        CannotOverwriteExistingCassetteException,
        PermanentError,
        RecordingPendingError,
        ClassificationFailedError,
    ),
    reason="recording pending (orchestrator): E19 changed the prohibited, high-risk and "
    "transparency prompts and response formats (the bar for an open question of law, `open_on` "
    "and the over-strictness rules), so the recorded requests are stale, and own/f has no "
    "recording yet; delete and re-record",
)
"""The one marker for every replay E19 made stale or added, until the orchestrator records
them (BACKLOG > E19). A replay fails on a stale recording in one of four ways, depending on
where it meets the changed request: VCR refuses the new request
(`CannotOverwriteExistingCassetteException`), the OpenRouter SDK gives up on the refused call
(`PermanentError`), a replay with no cassette at all stops before the call
(`RecordingPendingError`), or a whole classification run reports its failed check
(`ClassificationFailedError`); a stream that ends in an error event is turned into
`RecordingPendingError` by its test."""

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
