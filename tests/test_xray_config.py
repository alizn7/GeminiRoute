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


def test_unknown_fingerprint_is_dropped_not_passed_through() -> None:
    """An unrecognised fingerprint makes xray reject the whole config; the node
    still works without it."""
    n = node(params={"sni": "x.com", "fp": "netscape-navigator"})
    tls = build_config(n, 1)["outbounds"][0]["streamSettings"]["tlsSettings"]
    assert "fingerprint" not in tls


def test_known_fingerprint_survives_and_is_lowercased() -> None:
    n = node(params={"sni": "x.com", "fp": "Chrome"})
    tls = build_config(n, 1)["outbounds"][0]["streamSettings"]["tlsSettings"]
    assert tls["fingerprint"] == "chrome"


def test_junk_alpn_entries_are_filtered_out() -> None:
    n = node(params={"sni": "x.com", "alpn": "h2,garbage,http/1.1"})
    tls = build_config(n, 1)["outbounds"][0]["streamSettings"]["tlsSettings"]
    assert tls["alpn"] == ["h2", "http/1.1"]


def test_alpn_is_omitted_when_nothing_valid_remains() -> None:
    n = node(params={"sni": "x.com", "alpn": "nonsense"})
    tls = build_config(n, 1)["outbounds"][0]["streamSettings"]["tlsSettings"]
    assert "alpn" not in tls


def test_xtls_security_is_expressed_as_tls() -> None:
    """Xray removed xtls as a standalone security layer; it is tls plus a flow."""
    stream = build_config(node(security="xtls"), 1)["outbounds"][0]["streamSettings"]
    assert stream["security"] == "tls"
    assert "tlsSettings" in stream


def test_allow_insecure_is_emitted_when_supported() -> None:
    tls = build_config(node(), 1, allow_insecure=True)["outbounds"][0]["streamSettings"][
        "tlsSettings"
    ]
    assert tls["allowInsecure"] is True


def test_allow_insecure_is_omitted_when_the_binary_rejects_it() -> None:
    """Recent xray builds removed the field and refuse any config containing
    it, which killed every TLS node with no obvious cause."""
    tls = build_config(node(), 1, allow_insecure=False)["outbounds"][0]["streamSettings"][
        "tlsSettings"
    ]
    assert "allowInsecure" not in tls
    assert tls["serverName"] == "cdn.example.net"


def test_httpupgrade_settings_are_emitted() -> None:
    n = node(transport="httpupgrade", params={"path": "/up", "host": "cdn.example.net"})
    stream = build_config(n, 1)["outbounds"][0]["streamSettings"]
    assert stream["httpupgradeSettings"] == {"path": "/up", "host": "cdn.example.net"}


def test_xhttp_settings_are_emitted_with_a_default_mode() -> None:
    n = node(transport="xhttp", params={"path": "/x"})
    stream = build_config(n, 1)["outbounds"][0]["streamSettings"]
    assert stream["xhttpSettings"]["path"] == "/x"
    assert stream["xhttpSettings"]["mode"] == "auto"


def test_h2_transport_is_migrated_to_xhttp() -> None:
    """Xray removed the standalone HTTP/2 transport; emitting httpSettings gets
    the whole config refused."""
    n = node(transport="http", params={"path": "/h2", "host": "cdn.example.net"})
    stream = build_config(n, 1)["outbounds"][0]["streamSettings"]
    assert stream["network"] == "xhttp"
    assert "httpSettings" not in stream
    assert stream["xhttpSettings"]["mode"] == "stream-one"
    assert stream["xhttpSettings"]["path"] == "/h2"


def test_h2_host_list_is_reduced_to_one_value() -> None:
    """httpSettings took a list of hosts; xhttpSettings takes a single string."""
    n = node(transport="http", params={"host": "a.example.net,b.example.net"})
    stream = build_config(n, 1)["outbounds"][0]["streamSettings"]
    assert stream["xhttpSettings"]["host"] == "a.example.net"


def test_explicit_mode_overrides_the_migration_default() -> None:
    n = node(transport="http", params={"path": "/h2", "mode": "packet-up"})
    stream = build_config(n, 1)["outbounds"][0]["streamSettings"]
    assert stream["xhttpSettings"]["mode"] == "packet-up"


def test_unencodable_sni_falls_back_to_the_address() -> None:
    """Passing junk through only moves the failure to dial time."""
    n = node(params={"sni": "a..b"})
    tls = build_config(n, 1)["outbounds"][0]["streamSettings"]["tlsSettings"]
    assert tls["serverName"] == "check.example.net" or tls["serverName"] == n.address


def test_reality_server_name_is_validated_too() -> None:
    n = node(security="reality",
             params={"sni": "trailing.", "pbk": "KEY", "host": "cdn.example.net"})
    reality = build_config(n, 1)["outbounds"][0]["streamSettings"]["realitySettings"]
    assert reality["serverName"] == "cdn.example.net"
