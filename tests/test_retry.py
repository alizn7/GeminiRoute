from datetime import datetime, timedelta, timezone

from geminiroute.retry.policy import MAX_CONSECUTIVE_FAILS, backoff_minutes, decide, is_due

NOW = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)


def test_backoff_follows_the_documented_schedule() -> None:
    assert backoff_minutes(1) == 5
    assert backoff_minutes(2) == 30
    assert backoff_minutes(3) == 120


def test_backoff_is_capped() -> None:
    assert backoff_minutes(50) == backoff_minutes(5) == 1440


def test_no_failures_means_no_retry_scheduled() -> None:
    decision = decide(0, now=NOW)
    assert not decision.should_retry and decision.next_retry_at is None


def test_first_failure_schedules_five_minutes_out() -> None:
    decision = decide(1, now=NOW)
    assert decision.next_retry_at == NOW + timedelta(minutes=5)
    assert not decision.give_up


def test_third_failure_gives_up() -> None:
    assert decide(MAX_CONSECUTIVE_FAILS, now=NOW).give_up


def test_node_with_no_schedule_is_always_due() -> None:
    assert is_due(None, now=NOW)


def test_node_is_not_due_before_its_backoff_elapses() -> None:
    assert not is_due(NOW + timedelta(minutes=5), now=NOW)
    assert is_due(NOW - timedelta(seconds=1), now=NOW)
