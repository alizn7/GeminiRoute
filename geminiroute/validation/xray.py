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


class UnsupportedNodeError(ValueError):
    """The node cannot be expressed as an xray outbound."""


def _stream_settings(node: Node) -> dict[str, Any]:
    """Transport + TLS layer, shared by every protocol."""
    params = node.params
    network = node.transport or "tcp"
    settings: dict[str, Any] = {"network": network}

    security = node.security if node.security not in ("", "none") else "none"
    settings["security"] = security

    if security in ("tls", "xtls"):
        tls: dict[str, Any] = {
            "serverName": params.get("sni") or params.get("host") or node.address,
            # Many working nodes use self-signed certs or a mismatched SNI.
            "allowInsecure": True,
        }
        if params.get("fp"):
            tls["fingerprint"] = params["fp"]
        if params.get("alpn"):
            tls["alpn"] = [a.strip() for a in params["alpn"].split(",") if a.strip()]
        settings["tlsSettings"] = tls

    elif security == "reality":
        if not params.get("pbk"):
            raise UnsupportedNodeError("reality node without a public key")
        settings["realitySettings"] = {
            "serverName": params.get("sni", ""),
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

    elif network == "http":  # h2
        http: dict[str, Any] = {"path": params.get("path", "/")}
        if params.get("host"):
            http["host"] = [h.strip() for h in params["host"].split(",") if h.strip()]
        settings["httpSettings"] = http

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


def build_config(node: Node, socks_port: int) -> dict[str, Any]:
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
                "streamSettings": _stream_settings(node),
            }
        ],
    }
