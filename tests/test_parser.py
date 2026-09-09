"""Parser tests: a happy path and a failure path per protocol.
"""

import base64
import json

from geminiroute.core.enums import ProtocolType
from geminiroute.parsing.registry import get_parser, parse_line, parse_lines, supported_schemes

UUID = "11111111-2222-3333-4444-555555555555"
VLESS = f"vless://{UUID}@Example.com:443?type=ws&security=tls&sni=cdn.example.com#DE-01"


def vmess_link(**overrides: object) -> str:
    payload: dict[str, object] = {
        "v": "2",
        "ps": "NL-02",
        "add": "node.example.net",
        "port": "8443",
        "id": UUID,
        "aid": "0",
        "net": "ws",
        "type": "none",
        "host": "node.example.net",
        "path": "/ray",
        "tls": "tls",
    }
    payload.update(overrides)
    encoded = base64.b64encode(json.dumps(payload).encode()).decode()
    return "vmess://" + encoded.rstrip("=")  # sources usually strip the padding


# --------------------------------------------------------------- vless -----


def test_vless_happy_path() -> None:
    node = parse_line(VLESS)
    assert node is not None
    assert node.protocol is ProtocolType.VLESS
    assert node.address == "example.com"  # urlsplit lowercases the host
    assert node.port == 443
    assert node.credential == UUID
    assert node.transport == "ws"
    assert node.security == "tls"
    assert node.remark == "DE-01"


def test_vless_promotes_type_and_security_out_of_params() -> None:
    """`type` and `security` are identity fields, so they must not be left
    sitting in the generic params bag as well."""
    node = parse_line(VLESS)
    assert node is not None
    assert "type" not in node.params
    assert "security" not in node.params
    assert node.params["sni"] == "cdn.example.com"


def test_vless_remark_is_percent_decoded() -> None:
    node = parse_line(f"vless://{UUID}@example.com:443#%F0%9F%87%A9%F0%9F%87%AA%20Berlin")
    assert node is not None
    assert node.remark == "🇩🇪 Berlin"


def test_vless_ipv6_brackets_are_stripped() -> None:
    node = parse_line(f"vless://{UUID}@[2001:db8::1]:443#v6")
    assert node is not None
    assert node.address == "2001:db8::1"


def test_vless_missing_port_returns_none() -> None:
    """Guessing 443 here would invent a node that may not exist."""
    assert parse_line(f"vless://{UUID}@example.com#no-port") is None


def test_vless_invalid_port_returns_none() -> None:
    assert parse_line(f"vless://{UUID}@example.com:abc#bad") is None
    assert parse_line(f"vless://{UUID}@example.com:70000#bad") is None


def test_vless_missing_host_or_uuid_returns_none() -> None:
    assert parse_line(f"vless://{UUID}@:443#nohost") is None
    assert parse_line("vless://@example.com:443#nouuid") is None


# --------------------------------------------------------------- vmess -----


def test_vmess_happy_path_without_base64_padding() -> None:
    node = parse_line(vmess_link())
    assert node is not None
    assert node.protocol is ProtocolType.VMESS
    assert node.address == "node.example.net"
    assert node.port == 8443
    assert node.transport == "ws"
    assert node.security == "tls"
    assert node.params["path"] == "/ray"
    assert node.params["header_type"] == "none"  # renamed to avoid clashing with transport
    assert node.remark == "NL-02"


def test_vmess_port_given_as_int_also_works() -> None:
    node = parse_line(vmess_link(port=2087))
    assert node is not None
    assert node.port == 2087


def test_vmess_undecodable_payload_returns_none() -> None:
    assert parse_line("vmess://!!!not-base64!!!") is None


def test_vmess_valid_base64_but_not_json_returns_none() -> None:
    encoded = base64.b64encode(b"just some text").decode()
    assert parse_line("vmess://" + encoded) is None


def test_vmess_missing_required_fields_returns_none() -> None:
    assert parse_line(vmess_link(add="")) is None
    assert parse_line(vmess_link(id="")) is None
    assert parse_line(vmess_link(port="not-a-number")) is None


# -------------------------------------------------------------- trojan -----


def test_trojan_happy_path() -> None:
    node = parse_line("trojan://s3cr3t@example.org:443?security=tls&type=tcp#TR")
    assert node is not None
    assert node.protocol is ProtocolType.TROJAN
    assert node.credential == "s3cr3t"
    assert node.port == 443


def test_trojan_password_is_percent_decoded() -> None:
    node = parse_line("trojan://p%40ss%20word@example.org:443#TR")
    assert node is not None
    assert node.credential == "p@ss word"


# ------------------------------------------------------------ registry -----


def test_registry_dispatches_by_scheme() -> None:
    assert get_parser(VLESS) is not None
    assert get_parser("ss://whatever") is None
    assert get_parser("not a uri at all") is None


def test_supported_schemes_is_reported() -> None:
    assert supported_schemes() == ("trojan", "vless", "vmess")


def test_parse_lines_skips_junk_comments_and_blanks() -> None:
    lines = [
        "# a comment",
        "",
        VLESS,
        "total garbage",
        vmess_link(),
        "ss://not-yet-supported@example.com:8388",
        f"vless://{UUID}@example.com:abc#broken",
        "   ",
    ]
    nodes = parse_lines(lines)
    assert len(nodes) == 2
    assert {n.protocol for n in nodes} == {ProtocolType.VLESS, ProtocolType.VMESS}
