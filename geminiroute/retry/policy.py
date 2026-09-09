"""Retry and backoff.

Exponential with a ceiling: 5m, 30m, 2h, 6h, 24h. Three consecutive failures
mark a node dead. Backoff is about spending a run's fixed budget on nodes most
likely to be alive.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

MAX_CONSECUTIVE_FAILS = 3
BACKOFF_MINUTES = (5, 30, 120, 360, 1440)  # 5m, 30m, 2h, 6h, 24h ceiling


@dataclass(frozen=True)
class RetryDecision:
    should_retry: bool
    next_retry_at: datetime | None
    give_up: bool


def backoff_minutes(consecutive_fails: int) -> int:
    """Minutes to wait after N consecutive failures (N >= 1)."""
    if consecutive_fails < 1:
        return 0
    index = min(consecutive_fails - 1, len(BACKOFF_MINUTES) - 1)
    return BACKOFF_MINUTES[index]


def decide(consecutive_fails: int, now: datetime | None = None) -> RetryDecision:
    """What to do after `consecutive_fails` failures in a row."""
    now = now or datetime.now(UTC)
    if consecutive_fails <= 0:
        return RetryDecision(should_retry=False, next_retry_at=None, give_up=False)

    delay = backoff_minutes(consecutive_fails)
    return RetryDecision(
        should_retry=True,
        next_retry_at=now + timedelta(minutes=delay),
        give_up=consecutive_fails >= MAX_CONSECUTIVE_FAILS,
    )


def is_due(next_retry_at: datetime | None, now: datetime | None = None) -> bool:
    """Should this node be tested in the current run?

    No scheduled retry means always due: new nodes and healthy ones.
    """
    if next_retry_at is None:
        return True
    return (now or datetime.now(UTC)) >= next_retry_at
