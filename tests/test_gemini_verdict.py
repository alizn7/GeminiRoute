"""The Gemini stage's verdict logic, isolated from the network.
"""

import json

from geminiroute.validation.gemini import interpret


def ok_body() -> str:
    return json.dumps({"candidates": [{"content": {"parts": [{"text": "hi"}]}}]})


# ---- authenticated mode ----------------------------------------------------

def test_valid_response_passes() -> None:
    assert interpret(200, ok_body(), has_api_key=True).passed


def test_200_without_candidates_fails() -> None:
    verdict = interpret(200, json.dumps({"promptFeedback": {}}), has_api_key=True)
    assert not verdict.passed and verdict.error == "200 without candidates"


def test_200_with_unparseable_body_fails() -> None:
    """A captive portal answering 200 with HTML must not count as success."""
    assert not interpret(200, "<html>login</html>", has_api_key=True).passed


def test_rejected_api_key_is_reported_distinctly() -> None:
    """Otherwise a bad key looks like every node being broken."""
    verdict = interpret(403, "", has_api_key=True)
    assert not verdict.passed and "api key rejected" in (verdict.error or "")


# ---- keyless reachability mode ---------------------------------------------

def test_unauthenticated_403_counts_as_reachable() -> None:
    """Google rejecting us on the merits still proves the route reached Google."""
    assert interpret(403, "", has_api_key=False).passed


def test_unauthenticated_400_counts_as_reachable() -> None:
    assert interpret(400, "", has_api_key=False).passed


def test_proxy_auth_required_is_treated_as_blocked() -> None:
    assert not interpret(407, "", has_api_key=False).passed
    assert not interpret(407, "", has_api_key=True).passed


def test_legal_block_is_treated_as_blocked() -> None:
    assert not interpret(451, "", has_api_key=False).passed


def test_unexpected_status_fails_in_both_modes() -> None:
    assert not interpret(302, "", has_api_key=False).passed
    assert not interpret(302, "", has_api_key=True).passed


def test_free_port_returns_a_usable_loopback_port() -> None:
    """Ports are allocated per node: a terminated xray can hold its old port
    briefly, and reusing it would either fail to bind or look ready while
    pointing at a dying process."""
    import socket

    from geminiroute.validation.gemini import free_port

    port = free_port()
    assert 1024 < port <= 65535
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", port))          # must be genuinely free


def test_consecutive_free_ports_differ() -> None:
    from geminiroute.validation.gemini import free_port

    assert len({free_port() for _ in range(5)}) > 1
