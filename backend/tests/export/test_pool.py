"""The render pool (P9): renders run in worker processes, a runaway one is stopped at its time
limit and its worker replaced, and a failure comes back as its error's type only."""

import os
import time
from collections.abc import Iterator

import pytest

from aiact.export.pool import RenderFailed, RenderPool, RenderTimeout, RenderWorker

TIMEOUT_SECONDS = 1.0
SECRET = "Confidential: the Hamburg pilot of Project Falcon"


@pytest.fixture
def pool() -> Iterator[RenderPool]:
    built = RenderPool(1, TIMEOUT_SECONDS)
    yield built
    built.close()


@pytest.fixture
def worker(pool: RenderPool) -> RenderWorker:
    taken = pool.try_acquire()
    assert taken is not None
    return taken


def test_a_render_runs_in_another_process(worker: RenderWorker) -> None:
    assert worker.run(os.getpid) != os.getpid()
    assert worker.run(len, "abc") == 3


def test_a_runaway_render_is_stopped_at_its_time_limit(worker: RenderWorker) -> None:
    started = time.monotonic()
    with pytest.raises(RenderTimeout):
        worker.run(time.sleep, 3_600)
    assert time.monotonic() - started < TIMEOUT_SECONDS + 5
    assert not worker.is_running, "the runaway render's process was killed"
    assert worker.run(len, "abcd") == 4, "a new process takes the next render"


def test_a_failed_render_comes_back_as_its_error_type_only(worker: RenderWorker) -> None:
    with pytest.raises(RenderFailed) as raised:
        worker.run(int, SECRET)
    assert str(raised.value) == "ValueError"
    assert SECRET not in repr(raised.value)
    assert worker.run(len, "ab") == 2, "the worker survives a failed render"


def test_every_worker_taken_gives_none_until_one_is_released(pool: RenderPool) -> None:
    worker = pool.try_acquire()
    assert worker is not None
    assert pool.try_acquire() is None
    pool.release(worker)
    assert pool.try_acquire() is worker


def test_close_stops_every_worker(pool: RenderPool, worker: RenderWorker) -> None:
    worker.run(len, "a")
    assert worker.is_running
    pool.close()
    assert not worker.is_running


@pytest.mark.parametrize(("size", "timeout"), [(0, 1.0), (1, 0.0)])
def test_a_pool_needs_a_worker_and_a_positive_time_limit(size: int, timeout: float) -> None:
    with pytest.raises(ValueError):
        RenderPool(size, timeout)
