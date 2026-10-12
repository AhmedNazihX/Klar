"""E19's recording-pending marker takes a failed classification run only when a stale or missing
recording stopped it; any other node error must still fail the replay."""

import pytest

from aiact.engine import ClassificationFailedError
from aiact.engine.usage import RunUsage
from tests.engine.nodes.corpus_recording import RecordingPendingError
from tests.engine.nodes.known_gaps import (
    E19_PROMPTS_RECORDING_PENDING,
    STALE_RECORDING_ERRORS,
    is_stale_recording,
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


def test_the_marker_expects_only_stale_recording_errors() -> None:
    assert E19_PROMPTS_RECORDING_PENDING.kwargs["raises"] == STALE_RECORDING_ERRORS
    assert ClassificationFailedError not in STALE_RECORDING_ERRORS
    assert E19_PROMPTS_RECORDING_PENDING.kwargs["strict"] is True


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
