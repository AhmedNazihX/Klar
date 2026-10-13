"""`stale_recording_pending` turns a failed classification run into `RecordingPendingError` only
when a stale or missing recording stopped it; any other node error must still fail the replay.
`raise_if_recording_stale` does the same for a streamed run, which ends in an error event."""

import pytest

from aiact.engine import ClassificationFailedError, ClassifyEvent, ErrorEvent, StepStartedEvent
from aiact.engine.usage import RunUsage
from aiact.schemas import StepName
from tests.engine.nodes.corpus_recording import RecordingPendingError
from tests.engine.nodes.known_gaps import (
    STALE_RECORDING_ERRORS,
    is_stale_recording,
    raise_if_recording_stale,
    stale_recording_pending,
)


def failed_run(cause: BaseException) -> ClassificationFailedError:
    """A run stopped in the high-risk node by `cause`, chained as `run_classification` does."""
    try:
        raise ClassificationFailedError("high_risk", RunUsage(), None) from cause
    except ClassificationFailedError as error:
        return error


def wrapped(cause: BaseException) -> BaseException:
    """`cause` raised from inside another error, one level down the `__cause__` chain."""
    try:
        raise ValueError("the node's own wrapper") from cause
    except ValueError as error:
        return error


def test_a_classification_failure_is_never_a_stale_recording_by_itself() -> None:
    assert ClassificationFailedError not in STALE_RECORDING_ERRORS


@pytest.mark.parametrize(
    "cause",
    [
        pytest.param(RecordingPendingError("no cassette"), id="pending"),
        pytest.param(wrapped(RecordingPendingError("no cassette")), id="pending-deeper"),
    ],
)
def test_a_run_a_stale_recording_stopped_is_pending(cause: BaseException) -> None:
    run = failed_run(cause)
    assert is_stale_recording(run)
    pending = pytest.raises(RecordingPendingError, match="high_risk")
    with pending as raised, stale_recording_pending():
        raise run
    assert raised.value.__cause__ is run


@pytest.mark.parametrize(
    "cause",
    [
        pytest.param(KeyError("annex_point"), id="key-error"),
        pytest.param(wrapped(KeyError("annex_point")), id="key-error-deeper"),
    ],
)
def test_a_run_any_other_node_error_stopped_fails_as_it_was(cause: BaseException) -> None:
    run = failed_run(cause)
    assert not is_stale_recording(run)
    with pytest.raises(ClassificationFailedError) as raised, stale_recording_pending():
        raise run
    assert raised.value is run


def test_errors_outside_a_run_pass_through_unchanged() -> None:
    with pytest.raises(KeyError), stale_recording_pending():
        raise KeyError("annex_point")


STOPPED = ErrorEvent(step="scope", message="classification failed")
STARTED = StepStartedEvent(step=StepName.SCOPE)
STALE_LOG = "classification stopped in scope: CannotOverwriteExistingCassetteException"
STALE = "the scope recording is stale"


def test_a_stream_stopped_by_a_stale_recording_is_pending() -> None:
    with pytest.raises(RecordingPendingError, match=STALE):
        raise_if_recording_stale([STARTED, STOPPED], STALE_LOG, STALE)


@pytest.mark.parametrize(
    ("events", "log"),
    [
        ([STARTED, STOPPED], "classification stopped in scope: ValueError"),
        ([STOPPED, STARTED], STALE_LOG),
        ([], STALE_LOG),
    ],
    ids=["error-without-stale-log", "stale-log-without-final-error", "no-events"],
)
def test_other_streams_are_not_pending(events: list[ClassifyEvent], log: str) -> None:
    raise_if_recording_stale(events, log, STALE)
