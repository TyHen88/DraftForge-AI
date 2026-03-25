from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass


@dataclass
class RateLimitResult:
    allowed: bool
    retry_after_seconds: int


class SlidingWindowRateLimiter:
    def __init__(self, max_requests: int, window_seconds: int) -> None:
        self._max_requests = max_requests
        self._window_seconds = window_seconds
        self._requests_by_key: dict[str, deque[float]] = {}

    def check(self, key: str) -> RateLimitResult:
        now = time.time()
        window_start = now - self._window_seconds

        q = self._requests_by_key.get(key)
        if q is None:
            q = deque()
            self._requests_by_key[key] = q

        while q and q[0] < window_start:
            q.popleft()

        if len(q) < self._max_requests:
            q.append(now)
            return RateLimitResult(allowed=True, retry_after_seconds=0)

        retry_after = int(max(1, (q[0] + self._window_seconds) - now))
        return RateLimitResult(allowed=False, retry_after_seconds=retry_after)

