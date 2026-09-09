"""Xray config generation.

A wrong field here does not raise; it produces a config that starts fine and
proxies nothing, surfacing hours later as "0 nodes passed".
"""

import pytest

from geminiroute.core.enums import ProtocolType
from geminiroute.core.models import Node
from geminiroute.validation.xray import UnsupportedNodeError, build_config


def node(protocol: ProtocolType = ProtocolType.VLESS, **kwargs: object) -> Node:
    defaults: dict[str, object] = {
        "protocol": protocol,
        "address": "node.example.net",
        "port": 443,
        "transport": "ws",
        "security": "tls",
        "credential": "uuid-value",
        "params": {"sni": "cdn.example.net", "path": "/ray", "host": "cdn.example.net"},
    }
    defaults.update(kwargs)
    return Node(**defaults)  # type: ignore[arg-type]


def test_socks_inbound_is_bound_to_localhost_only() -> None:
    """An open SOCKS port on a shared runner would be an open relay."""
    inbound = build_config(node(), 24001)["inbounds"][0]
    assert inbound["listen"] == "127.0.0.1"
    assert inbound["port"] == 24001


def test_vless_outbound_shape() -> None:
    outbound = build_config(node(), 24001)["outbounds"][0]
    assert outbound["protocol"] == "vless"
    vnext = outbound["settings"]["vnext"][0]
    assert vnext["address"] == "node.example.net"
    assert vnext["users"][0] == {"id": "uuid-value", "encryption": "none"}


def test_vless_flow_is_carried_through() -> None:
    n = node(params={"flow": "xtls-rprx-vision"})
    user = build_config(n, 1)["outbounds"][0]["settings"]["vnext"][0]["users"][0]
    assert user["flow"] == "xtls-rprx-vision"


def test_vmess_alter_id_is_an_int_even_when_the_source_gave_a_string() -> None:
    n = node(ProtocolType.VMESS, params={"aid": "64", "scy": "auto"})
    user = build_config(n, 1)["outbounds"][0]["settings"]["vnext"][0]["users"][0]
    assert user["alterId"] == 64 and isinstance(user["alterId"], int)


def test_vmess_garbage_alter_id_falls_back_to_zero() -> None:
    n = node(ProtocolType.VMESS, params={"aid": "not-a-number"})
    user = build_config(n, 1)["outbounds"][0]["settings"]["vnext"][0]["users"][0]
    assert user["alterId"] == 0


def test_trojan_uses_password_not_id() -> None:
    server = build_config(node(ProtocolType.TROJAN), 1)["outbounds"][0]["settings"]["servers"][0]
    assert server["password"] == "uuid-value"


def test_shadowsocks_splits_method_and_password() -> None:
    n = node(ProtocolType.SHADOWSOCKS, credential="aes-256-gcm:hunter2",
             transport="", security="")
    server = build_config(n, 1)["outbounds"][0]["settings"]["servers"][0]
    assert server["method"] == "aes-256-gcm"
    assert server["password"] == "hunter2"


def test_shadowsocks_without_a_colon_is_rejected() -> None:
    n = node(ProtocolType.SHADOWSOCKS, credential="no-colon")
    with pytest.raises(UnsupportedNodeError):
        build_config(n, 1)


def test_websocket_settings_are_emitted() -> None:
    stream = build_config(node(), 1)["outbounds"][0]["streamSettings"]
    assert stream["network"] == "ws"
    assert stream["wsSettings"]["path"] == "/ray"
    assert stream["wsSettings"]["headers"]["Host"] == "cdn.example.net"


def test_grpc_settings_are_emitted() -> None:
    n = node(transport="grpc", params={"servicename": "GunService"})
    stream = build_config(n, 1)["outbounds"][0]["streamSettings"]
    assert stream["grpcSettings"]["serviceName"] == "GunService"


def test_tls_uses_sni_and_tolerates_self_signed_certificates() -> None:
    tls = build_config(node(), 1)["outbounds"][0]["streamSettings"]["tlsSettings"]
    assert tls["serverName"] == "cdn.example.net"
    assert tls["allowInsecure"] is True


def test_plain_node_has_security_none_and_no_tls_block() -> None:
    stream = build_config(node(security="", transport="tcp"), 1)["outbounds"][0]["streamSettings"]
    assert stream["security"] == "none"
    assert "tlsSettings" not in stream


def test_reality_requires_a_public_key() -> None:
    with pytest.raises(UnsupportedNodeError):
        build_config(node(security="reality", params={"sni": "x.com"}), 1)


def test_reality_settings_are_emitted_when_complete() -> None:
    n = node(security="reality", params={"sni": "x.com", "pbk": "KEY", "sid": "ab", "fp": "chrome"})
    reality = build_config(n, 1)["outbounds"][0]["streamSettings"]["realitySettings"]
    assert reality["publicKey"] == "KEY"
    assert reality["shortId"] == "ab"
