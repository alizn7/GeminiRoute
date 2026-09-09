import pytest

from geminiroute.core.enums import NodeStatus
from geminiroute.reliability.lifecycle import (
    IllegalTransitionError,
    can_transition,
    next_status,
    revive,
    transition,
)


def test_legal_transition_is_accepted() -> None:
    assert transition(NodeStatus.DISCOVERED, NodeStatus.VALIDATING) is NodeStatus.VALIDATING


def test_illegal_transition_raises() -> None:
    """Silently accepting one would corrupt the history reliability is built on."""
    with pytest.raises(IllegalTransitionError):
        transition(NodeStatus.DEAD, NodeStatus.HEALTHY)


def test_dead_can_only_go_to_recheck() -> None:
    assert can_transition(NodeStatus.DEAD, NodeStatus.RECHECK)
    assert not can_transition(NodeStatus.DEAD, NodeStatus.VALIDATING)


def test_passing_always_lands_on_healthy() -> None:
    result = next_status(NodeStatus.VALIDATING, passed=True, consecutive_fails=0)
    assert result is NodeStatus.HEALTHY


def test_first_failure_degrades_rather_than_kills() -> None:
    assert next_status(NodeStatus.HEALTHY, passed=False, consecutive_fails=1) is NodeStatus.DEGRADED


def test_third_failure_kills() -> None:
    assert next_status(NodeStatus.DEGRADED, passed=False, consecutive_fails=3) is NodeStatus.DEAD


def test_revive_only_affects_dead_nodes() -> None:
    assert revive(NodeStatus.DEAD) is NodeStatus.RECHECK
    assert revive(NodeStatus.HEALTHY) is NodeStatus.HEALTHY
