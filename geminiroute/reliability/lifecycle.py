"""Node lifecycle.

    DISCOVERED -> VALIDATING -> HEALTHY | DEGRADED | DEAD
    HEALTHY    -> DEGRADED (first failure)
    DEGRADED   -> HEALTHY (recovers) | DEAD (keeps failing)
    DEAD       -> RECHECK (backoff elapsed) -> HEALTHY | DEAD

Illegal transitions raise rather than being silently accepted, because they
would corrupt the history reliability scoring is computed from.
"""

from __future__ import annotations

from geminiroute.core.enums import NodeStatus
from geminiroute.retry.policy import MAX_CONSECUTIVE_FAILS

ALLOWED: dict[NodeStatus, frozenset[NodeStatus]] = {
    NodeStatus.DISCOVERED: frozenset({NodeStatus.VALIDATING, NodeStatus.DEAD}),
    NodeStatus.VALIDATING: frozenset(
        {NodeStatus.HEALTHY, NodeStatus.DEGRADED, NodeStatus.DEAD}
    ),
    NodeStatus.HEALTHY: frozenset({NodeStatus.VALIDATING, NodeStatus.DEGRADED}),
    NodeStatus.DEGRADED: frozenset(
        {NodeStatus.VALIDATING, NodeStatus.HEALTHY, NodeStatus.DEAD}
    ),
    NodeStatus.DEAD: frozenset({NodeStatus.RECHECK}),
    NodeStatus.RECHECK: frozenset({NodeStatus.HEALTHY, NodeStatus.DEAD}),
}


class IllegalTransitionError(ValueError):
    pass


def can_transition(current: NodeStatus, target: NodeStatus) -> bool:
    return target in ALLOWED.get(current, frozenset())


def transition(current: NodeStatus, target: NodeStatus) -> NodeStatus:
    if not can_transition(current, target):
        raise IllegalTransitionError(f"{current.value} -> {target.value} is not allowed")
    return target


def next_status(
    current: NodeStatus,
    passed: bool,
    consecutive_fails: int,
) -> NodeStatus:
    """Where a node lands after one validation round.

    `consecutive_fails` is the count after this round: a first failure is 1.
    """
    if passed:
        return NodeStatus.HEALTHY

    if consecutive_fails >= MAX_CONSECUTIVE_FAILS:
        return NodeStatus.DEAD

    return NodeStatus.DEGRADED


def revive(current: NodeStatus) -> NodeStatus:
    """Move a dead node back into the testing pool once its backoff elapsed."""
    if current is NodeStatus.DEAD:
        return NodeStatus.RECHECK
    return current
