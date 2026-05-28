from __future__ import annotations

from writer_ai_assistant.rate_limit import SlidingWindowRateLimiter


def test_allows_up_to_limit_then_blocks() -> None:
    limiter = SlidingWindowRateLimiter(max_requests=3, window_seconds=60)

    for _ in range(3):
        assert limiter.check("user-1").allowed is True

    blocked = limiter.check("user-1")
    assert blocked.allowed is False
    assert blocked.retry_after_seconds >= 1


def test_keys_are_independent() -> None:
    limiter = SlidingWindowRateLimiter(max_requests=1, window_seconds=60)

    assert limiter.check("user-a").allowed is True
    assert limiter.check("user-a").allowed is False
    # A different key has its own window.
    assert limiter.check("user-b").allowed is True
