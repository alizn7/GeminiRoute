"""Node -> Xray configuration.

Python cannot speak VLESS, VMess or Trojan, so Gemini validation runs each node
through a local xray process:

    Node -> xray config with a SOCKS5 inbound -> start xray
         -> request through 127.0.0.1:<port> -> stop xray

Everything here is a pure function producing a dict. A wrong field does not
raise; it produces a config that starts fine and proxies nothing.
"""

from __future__ import annotations

from typing import Any

from geminiroute.core.enums import ProtocolType
from geminiroute.core.models import Node
from geminiroute.validation.pre import is_usable_hostname


class UnsupportedNodeError(ValueError):
    """The node cannot be expressed as an xray outbound."""


# uTLS fingerprints xray accepts. Anything else makes it reject the whole
# config, so an unknown value is dropped rather than passed through — the node
# still works, it just does not mimic a specific browser.
KNOWN_FINGERPRINTS = frozenset({
    "chrome", "firefox", "safari", "ios", "android", "edge", "360", "qq",
    "random", "randomized", "randomizednoalpn", "unsafe",
})

# ALPN values that mean anything to a TLS stack. Sources put junk here.
KNOWN_ALPN = frozenset({"h2", "http/1.1", "h3"})


def _server_name(node: Node) -> str:
    """The SNI to present, or empty when the sources supplied junk.

    Same guard as the connectivity probe: a hostname with an empty or over-long
    label is not encodable, and passing it on only moves the failure later.
    """
    for candidate in (node.params.get("sni"), node.params.get("host"), node.address):
        if candidate and is_usable_hostname(candidate):
            return candidate
    return ""


def _stream_settings(node: Node, allow_insecure: bool = True) -> dict[str, Any]:
    """Transport + TLS layer, shared by every protocol."""
    params = node.params
    network = node.transport or "tcp"
    settings: dict[str, Any] = {"network": network}

    security = node.security if node.security not in ("", "none") else "none"
    # Xray dropped "xtls" as a standalone security layer; XTLS is now expressed
    # as tls plus a flow on the user. Passing "xtls" makes xray refuse the
    # config outright.
    if security == "xtls":
        security = "tls"
    settings["security"] = security

    if security == "tls":
        tls: dict[str, Any] = {"serverName": _server_name(node)}
        # Many working nodes use self-signed certs or a mismatched SNI, so we
        # want this on — but recent xray builds removed the field and reject any
        # config containing it. Whether to emit it is decided by probing the
        # binary at startup, not assumed.
        if allow_insecure:
            tls["allowInsecure"] = True
        fingerprint = params.get("fp", "").strip().lower()
        if fingerprint in KNOWN_FINGERPRINTS:
            tls["fingerprint"] = fingerprint

        alpn = [
            value.strip().lower()
            for value in params.get("alpn", "").split(",")
            if value.strip().lower() in KNOWN_ALPN
        ]
        if alpn:
            tls["alpn"] = alpn
        settings["tlsSettings"] = tls

    elif security == "reality":
        if not params.get("pbk"):
            raise UnsupportedNodeError("reality node without a public key")
        settings["realitySettings"] = {
            "serverName": _server_name(node),
            "fingerprint": params.get("fp", "chrome"),
            "publicKey": params["pbk"],
            "shortId": params.get("sid", ""),
            "spiderX": params.get("spx", "/"),
        }

    if network == "ws":
        ws: dict[str, Any] = {"path": params.get("path", "/")}
        if params.get("host"):
            ws["headers"] = {"Host": params["host"]}
        settings["wsSettings"] = ws

    elif network == "grpc":
        settings["grpcSettings"] = {
            "serviceName": params.get("servicename", ""),
            "multiMode": params.get("mode", "") == "multi",
        }

    elif network == "httpupgrade":
        upgrade: dict[str, Any] = {"path": params.get("path", "/")}
        if params.get("host"):
            upgrade["host"] = params["host"]
        settings["httpupgradeSettings"] = upgrade

    elif network in ("xhttp", "http"):
        # Xray removed the standalone HTTP/2 transport and migrated it to
        # XHTTP; a config with httpSettings is refused outright. An h2 node is
        # therefore expressed as xhttp in stream-one mode, which is the
        # migration path xray's own error message names.
        settings["network"] = "xhttp"
        xhttp: dict[str, Any] = {
            "path": params.get("path", "/"),
            "mode": params.get("mode") or ("stream-one" if network == "http" else "auto"),
        }
        if params.get("host"):
            xhttp["host"] = params["host"].split(",")[0].strip()
        settings["xhttpSettings"] = xhttp

    return settings


def _outbound_settings(node: Node) -> dict[str, Any]:
    """The protocol-specific half of the outbound."""
    if node.protocol is ProtocolType.VLESS:
        user: dict[str, Any] = {"id": node.credential, "encryption": "none"}
        if node.params.get("flow"):
            user["flow"] = node.params["flow"]
        return {"vnext": [{"address": node.address, "port": node.port, "users": [user]}]}

    if node.protocol is ProtocolType.VMESS:
        try:
            alter_id = int(node.params.get("aid", "0") or 0)
        except ValueError:
            alter_id = 0
        return {
            "vnext": [
                {
                    "address": node.address,
                    "port": node.port,
                    "users": [
                        {
                            "id": node.credential,
                            "alterId": alter_id,
                            "security": node.params.get("scy") or "auto",
                        }
                    ],
                }
            ]
        }

    if node.protocol is ProtocolType.TROJAN:
        return {
            "servers": [
                {"address": node.address, "port": node.port, "password": node.credential}
            ]
        }

    if node.protocol is ProtocolType.SHADOWSOCKS:
        method, separator, password = node.credential.partition(":")
        if not separator:
            raise UnsupportedNodeError("shadowsocks credential is not method:password")
        return {
            "servers": [
                {
                    "address": node.address,
                    "port": node.port,
                    "method": method,
                    "password": password,
                }
            ]
        }

    raise UnsupportedNodeError(f"unsupported protocol: {node.protocol}")


def build_config(
    node: Node, socks_port: int, allow_insecure: bool = True
) -> dict[str, Any]:
    """A complete xray config: SOCKS5 in on localhost, the node out.

    `listen` is pinned to 127.0.0.1: an open SOCKS port on a CI runner would
    be an open relay.
    """
    return {
        "log": {"loglevel": "error"},
        "inbounds": [
            {
                "tag": "socks-in",
                "listen": "127.0.0.1",
                "port": socks_port,
                "protocol": "socks",
                "settings": {"auth": "noauth", "udp": False},
            }
        ],
        "outbounds": [
            {
                "tag": "proxy",
                "protocol": node.protocol.value,
                "settings": _outbound_settings(node),
                "streamSettings": _stream_settings(node, allow_insecure),
            }
        ],
    }
