"""A rate limit per client address (P1; `.claude/rules/api.md` > Abuse and cost).

Each key gets `limit` requests in a window of `WINDOW_SECONDS` that starts with its first
request; once the window has passed, the key starts a new one. Expired windows are swept at
most once per window length, so the memory held is about one entry per address seen in the last
two windows. The state lives in the process: with several workers, each counts on its own (the
deployment's proxy can add a shared limit, S3).
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
    """Counts requests per key in windows of `window_seconds`."""

    def __init__(
        self,
        limit: int,
        *,
        window_seconds: float = WINDOW_SECONDS,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if limit < 1:
            raise ValueError("a rate limit allows at least one request per window")
        self.limit = limit
        self._window_seconds = window_seconds
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
            if window is None or now - window.started >= self._window_seconds:
                window = _Window(started=now, used=0)
            if window.used >= self.limit:
                return max(1, math.ceil(window.started + self._window_seconds - now))
            self._windows[key] = _Window(started=window.started, used=window.used + 1)
            return None

    def _sweep(self, now: float) -> None:
        """Drop the windows that have ended, once per window length."""
        if now - self._swept < self._window_seconds:
            return
        self._swept = now
        self._windows = {
            key: window
            for key, window in self._windows.items()
            if now - window.started < self._window_seconds
        }
