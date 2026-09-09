"""Normalizer tests.

If `test_explicit_defaults_and_omitted_defaults_collapse` goes red, dedup is
broken and the pipeline validates the same server twice.
"""

from geminiroute.core.enums import ProtocolType
from geminiroute.core.models import Node
from geminiroute.normalization.normalizer import normalize, normalize_all
from geminiroute.parsing.registry import parse_line

UUID = "11111111-2222-3333-4444-555555555555"


def test_explicit_defaults_and_omitted_defaults_collapse() -> None:
    """The reason this stage exists."""
    terse = parse_line(f"vless://{UUID}@example.com:443#node-a")
    verbose = parse_line(f"vless://{UUID}@EXAMPLE.com.:443?type=tcp&security=none#node-b")
    assert terse is not None and verbose is not None

    # Before normalization they look like two different nodes...
    assert terse.fingerprint != verbose.fingerprint

    # ...and after it, they are correctly one.
    assert normalize(terse).fingerprint == normalize(verbose).fingerprint


def test_fingerprint_is_recomputed_not_carried_over() -> None:
    node = Node(protocol=ProtocolType.VLESS, address="example.com", port=443, transport="")
    before = node.fingerprint
    after = normalize(node).fingerprint
    assert before != after  # transport "" became "tcp", so identity changed


def test_transport_aliases_are_unified() -> None:
    def transport_of(value: str) -> str:
        node = Node(ProtocolType.VLESS, "example.com", 443, transport=value)
        return normalize(node).transport

    assert transport_of("") == "tcp"
    assert transport_of("RAW") == "tcp"
    assert transport_of("h2") == "http"
    assert transport_of("WebSocket") == "ws"
    assert transport_of("grpc") == "grpc"  # unknown values pass through, just lowercased


def test_security_aliases_are_unified() -> None:
    def security_of(value: str) -> str:
        node = Node(ProtocolType.VLESS, "example.com", 443, security=value)
        return normalize(node).security

    assert security_of("") == "none"
    assert security_of("FALSE") == "none"
    assert security_of("TLS") == "tls"
    assert security_of("reality") == "reality"


def test_address_is_canonicalised() -> None:
    node = Node(ProtocolType.VLESS, "  [Example.COM.] ", 443)
    assert normalize(node).address == "example.com"


def test_empty_params_are_dropped_and_keys_sorted() -> None:
    node = Node(
        ProtocolType.VLESS,
        "example.com",
        443,
        params={"SNI": "cdn.example.com", "path": "  ", "alpn": "h2"},
    )
    result = normalize(node)
    assert list(result.params) == ["alpn", "sni"]
    assert result.params["sni"] == "cdn.example.com"


def test_param_values_keep_their_case() -> None:
    """A path is case-sensitive on the server; lowercasing it would break the node."""
    node = Node(ProtocolType.VLESS, "example.com", 443, params={"path": "/API/v1"})
    assert normalize(node).params["path"] == "/API/v1"


def test_remark_whitespace_is_collapsed() -> None:
    node = Node(ProtocolType.VLESS, "example.com", 443, remark="  DE   01\n")
    assert normalize(node).remark == "DE 01"


def test_normalize_does_not_mutate_the_input() -> None:
    node = Node(ProtocolType.VLESS, "EXAMPLE.com", 443)
    normalize(node)
    assert node.address == "EXAMPLE.com"


def test_normalize_all_handles_a_list() -> None:
    nodes = [
        Node(ProtocolType.VLESS, "A.com", 443),
        Node(ProtocolType.VLESS, "B.com", 443),
    ]
    assert [n.address for n in normalize_all(nodes)] == ["a.com", "b.com"]
