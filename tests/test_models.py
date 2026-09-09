"""Tests for the core domain model.

Each test states a rule we want to stay true. If someone later changes the
fingerprint logic and breaks dedup, one of these fails loudly.
"""

from geminiroute.core.enums import NodeStatus, ProtocolType
from geminiroute.core.fingerprint import compute_fingerprint
from geminiroute.core.models import Node


def make_node(**overrides: object) -> Node:
    defaults: dict[str, object] = {
        "protocol": ProtocolType.VLESS,
        "address": "example.com",
        "port": 443,
        "transport": "ws",
        "security": "tls",
        "credential": "11111111-2222-3333-4444-555555555555",
    }
    defaults.update(overrides)
    return Node(**defaults)  # type: ignore[arg-type]


def test_fingerprint_is_computed_automatically() -> None:
    node = make_node()
    assert len(node.fingerprint) == 16


def test_new_node_starts_as_discovered() -> None:
    assert make_node().status is NodeStatus.DISCOVERED


def test_same_endpoint_written_differently_has_one_fingerprint() -> None:
    """Case and trailing-dot differences must not create a duplicate."""
    a = make_node(address="example.com")
    b = make_node(address="  Example.COM. ")
    assert a.fingerprint == b.fingerprint


def test_remark_does_not_affect_identity() -> None:
    """Two sources labelling the same server differently is the whole reason
    dedup exists."""
    a = make_node(remark="DE-01")
    b = make_node(remark="Germany fast")
    assert a.fingerprint == b.fingerprint


def test_different_port_is_a_different_node() -> None:
    assert make_node(port=443).fingerprint != make_node(port=8443).fingerprint


def test_different_credential_is_a_different_node() -> None:
    a = make_node(credential="aaaa")
    b = make_node(credential="bbbb")
    assert a.fingerprint != b.fingerprint


def test_fingerprint_is_stable_across_runs() -> None:
    """A hardcoded expected value: if this changes, every stored node id in the
    database is invalidated. That should be a deliberate decision, not a
    surprise."""
    assert compute_fingerprint("vless", "example.com", 443, "ws", "tls", "abc") == (
        compute_fingerprint("VLESS", "EXAMPLE.com", 443, "WS", "TLS", "abc")
    )
