"""The API's limits per process (P1; `.claude/rules/api.md` > Abuse and cost): a rate limit per
client address, and a cap on the classifications running at once.

`RateLimiter`: each key gets `limit` requests in a window of `WINDOW_SECONDS` that starts with
its first request; once the window has passed, the key starts a new one. Expired windows are
swept at most once per window, so the memory held is about one entry per address seen in the
last two windows. With several workers, each counts on its own (a shared limit is S3's).
"""

import math
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass

WINDOW_SECONDS = 60.0


@dataclass(frozen=True)
class _Window:
    started: float
    used: int


class RateLimiter:
    """Counts requests per key in windows of `WINDOW_SECONDS`."""

    def __init__(self, limit: int, *, clock: Callable[[], float] = time.monotonic) -> None:
        if limit < 1:
            raise ValueError("a rate limit allows at least one request per window")
        self.limit = limit
        self._clock = clock
        self._lock = threading.Lock()
        self._windows: dict[str, _Window] = {}
        self._swept = clock()

    def acquire(self, key: str) -> int | None:
        """Count one request for `key`. None when it is allowed; otherwise the whole seconds
        until its window ends, for the `Retry-After` header (at least 1)."""
        now = self._clock()
        with self._lock:
            self._sweep(now)
            window = self._windows.get(key)
            if window is None or now - window.started >= WINDOW_SECONDS:
                window = _Window(started=now, used=0)
            if window.used >= self.limit:
                return max(1, math.ceil(window.started + WINDOW_SECONDS - now))
            self._windows[key] = _Window(started=window.started, used=window.used + 1)
            return None

    def _sweep(self, now: float) -> None:
        """Drop the windows that have ended, once per window length."""
        if now - self._swept < WINDOW_SECONDS:
            return
        self._swept = now
        self._windows = {
            key: window
            for key, window in self._windows.items()
            if now - window.started < WINDOW_SECONDS
        }


class ConcurrencyLimit:
    """At most `limit` holders at once; `try_acquire` never waits."""

    def __init__(self, limit: int) -> None:
        if limit < 1:
            raise ValueError("a concurrency limit allows at least one holder")
        self._free = threading.BoundedSemaphore(limit)

    def try_acquire(self) -> bool:
        return self._free.acquire(blocking=False)

    def release(self) -> None:
        self._free.release()
