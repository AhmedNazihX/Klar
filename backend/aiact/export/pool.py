"""Files rendered in a few worker processes, each render stopped after a time limit (P9).

What a render costs depends on the text in a way no cap on its shape bounds: thousands of short
lines, lone carriage returns, a letter carrying thousands of combining marks each took a minute
or more. So the cost is bounded by time: a render runs in one of `size` worker processes (the
export slots), and one that runs past `timeout_seconds` is stopped, its process killed and
replaced on next use, and `RenderTimeout` raised. `try_acquire` never waits: with every worker
busy it gives `None`.

A worker is started on first use, in a fresh interpreter (`spawn`: the API runs threads, which a
fork would copy mid-lock), and imports the renderers before it reports ready, so the time limit
counts the render only. Nothing a worker sends back on failure carries the text it rendered: only
the error's type. A render that raised `RenderTooLong` (a PDF table row taller than a page) is
raised as `RenderTooLong` here too, so a route can tell the user's text from a renderer bug.
"""

import logging
import multiprocessing
import queue
import threading
from collections.abc import Callable
from multiprocessing.connection import Connection
from multiprocessing.context import SpawnContext, SpawnProcess
from typing import cast

logger = logging.getLogger(__name__)

READY = "ready"
START_TIMEOUT_SECONDS = 60.0
"""How long a new worker may take to start and import the renderers."""
STOP_TIMEOUT_SECONDS = 5.0


class RenderTimeout(Exception):
    """A render ran past its time limit and was stopped."""


class RenderFailed(Exception):
    """A render raised, or its worker died; the message is the error's type only."""


class WorkerNotStarted(RenderFailed):
    """A new worker didn't start in time: nothing was rendered."""


class RenderTooLong(Exception):
    """The paper can't be drawn: a table row is taller than a page (the renderer's own answer,
    `aiact.export.pdf`)."""


def _serve(connection: Connection) -> None:
    """A worker's loop: run each `(function, args)` it is sent and send back `(True, value)`, or
    `(False, error type)`; `None` ends it."""
    import aiact.export  # noqa: F401  (the renderers, imported before the first render is timed)

    connection.send(READY)
    while (job := connection.recv()) is not None:
        function, args = job
        try:
            connection.send((True, function(*args)))
        except Exception as exc:  # sent back as its type, never its text
            connection.send((False, type(exc).__name__))


class RenderWorker:
    """One worker process, used by one request at a time (the pool hands it out)."""

    def __init__(self, context: SpawnContext, timeout_seconds: float) -> None:
        self._context = context
        self._timeout = timeout_seconds
        self._process: SpawnProcess | None = None
        self._connection: Connection | None = None
        self._stopping = threading.Lock()

    @property
    def timeout_seconds(self) -> float:
        """How long a render may run before it is stopped."""
        return self._timeout

    @property
    def is_running(self) -> bool:
        process = self._process  # read once: another thread's `stop` may take it
        return process is not None and process.is_alive()

    def run[*Args, Value](self, function: Callable[[*Args], Value], *args: *Args) -> Value:
        """`function(*args)` in the worker process; `RenderTimeout` past the time limit (the
        process is stopped), `RenderTooLong` if it raised that, `RenderFailed` if it raised
        anything else or the worker died (`WorkerNotStarted` if it never started)."""
        connection = self._started()
        try:
            connection.send((function, args))
            if not connection.poll(self._timeout):
                self.stop()
                raise RenderTimeout
            is_done, value = connection.recv()
        except (EOFError, OSError) as exc:
            self.stop()
            raise RenderFailed(type(exc).__name__) from None
        if not is_done:
            raise RenderTooLong if value == RenderTooLong.__name__ else RenderFailed(value)
        return cast(Value, value)

    def stop(self) -> None:
        """Kill the process (a running render included); the next `run` starts a new one. Safe
        to call from two threads at once (the app's shutdown and the request holding the
        worker): one of them takes the process, the other finds none."""
        with self._stopping:
            process, connection = self._process, self._connection
            self._process, self._connection = None, None
        if connection is not None:
            connection.close()
        if process is None:
            return
        process.kill()
        process.join(STOP_TIMEOUT_SECONDS)
        if process.exitcode is None:
            logger.error(
                "a render worker didn't exit %s seconds after it was killed", STOP_TIMEOUT_SECONDS
            )
            return
        process.close()

    def _started(self) -> Connection:
        if self._connection is not None and self.is_running:
            return self._connection
        self.stop()
        parent, child = self._context.Pipe()
        process = self._context.Process(target=_serve, args=(child,), daemon=True)
        process.start()
        child.close()
        self._process, self._connection = process, parent
        if not parent.poll(START_TIMEOUT_SECONDS) or parent.recv() != READY:
            self.stop()
            raise WorkerNotStarted("the worker didn't start")
        return parent


class RenderPool:
    """`size` render workers; each request takes one with `try_acquire` and gives it back with
    `release`."""

    def __init__(self, size: int, timeout_seconds: float) -> None:
        if size < 1:
            raise ValueError("a render pool has at least one worker")
        if timeout_seconds <= 0:
            raise ValueError("a render's time limit is positive")
        context = multiprocessing.get_context("spawn")
        self._workers = tuple(RenderWorker(context, timeout_seconds) for _ in range(size))
        self._idle: queue.SimpleQueue[RenderWorker] = queue.SimpleQueue()
        for worker in self._workers:
            self._idle.put(worker)

    def try_acquire(self) -> RenderWorker | None:
        """A free worker, or `None` when every one is busy; never waits."""
        try:
            return self._idle.get_nowait()
        except queue.Empty:
            return None

    def release(self, worker: RenderWorker) -> None:
        self._idle.put(worker)

    def close(self) -> None:
        """Stop every worker process (the app's shutdown)."""
        for worker in self._workers:
            worker.stop()
