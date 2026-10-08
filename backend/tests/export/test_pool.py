"""The render pool (P9): renders run in worker processes, a runaway one is stopped at its time
limit and its worker replaced, and a failure comes back as its error's type only."""

import os
import threading
import time
from collections.abc import Iterator

import pytest

from aiact.export.pool import RenderFailed, RenderPool, RenderTimeout, RenderWorker

TIMEOUT_SECONDS = 1.0
STOP_BOUND_SECONDS = 10.0
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
    # Run in a thread with a bound of its own, so a broken time limit fails the test rather than
    # hanging it for the hour the render asks for.
    raised: list[BaseException] = []

    def runaway() -> None:
        try:
            worker.run(time.sleep, 3_600)
        except BaseException as exc:
            raised.append(exc)

    thread = threading.Thread(target=runaway, daemon=True)
    thread.start()
    thread.join(TIMEOUT_SECONDS + 5)
    assert not thread.is_alive(), "the render wasn't stopped at its time limit"
    assert [type(exc) for exc in raised] == [RenderTimeout]
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


def test_two_threads_stopping_one_worker_at_once_both_return(
    worker: RenderWorker, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The app's shutdown and the request holding the worker can stop it at the same moment: one
    of them stops the process, the other finds it gone (no error from a closed process)."""
    worker.run(len, "a")
    process = worker._process  # pyright: ignore[reportPrivateUsage]
    assert process is not None
    join = process.join

    def slow_join(timeout: float | None = None) -> None:
        time.sleep(0.3)  # the other thread arrives while this one waits for the process
        join(timeout)

    monkeypatch.setattr(process, "join", slow_join)
    raised: list[BaseException] = []

    def stop() -> None:
        try:
            worker.stop()
        except BaseException as exc:
            raised.append(exc)

    threads = [threading.Thread(target=stop) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(STOP_BOUND_SECONDS)
    assert raised == []
    assert not worker.is_running


def test_a_process_that_outlives_its_kill_still_leaves_the_worker_reset(
    worker: RenderWorker, monkeypatch: pytest.MonkeyPatch
) -> None:
    worker.run(len, "a")
    process = worker._process  # pyright: ignore[reportPrivateUsage]
    assert process is not None
    monkeypatch.setattr(process, "kill", lambda: None)
    monkeypatch.setattr(process, "join", lambda timeout=None: None)
    try:
        worker.stop()  # the process is still alive after the "kill": no ValueError from close()
        assert worker._process is None  # pyright: ignore[reportPrivateUsage]
        assert worker.run(len, "ab") == 2, "the next render starts a new process"
    finally:
        monkeypatch.undo()
        process.kill()
        process.join(STOP_BOUND_SECONDS)
        process.close()


@pytest.mark.parametrize(("size", "timeout"), [(0, 1.0), (1, 0.0)])
def test_a_pool_needs_a_worker_and_a_positive_time_limit(size: int, timeout: float) -> None:
    with pytest.raises(ValueError):
        RenderPool(size, timeout)
