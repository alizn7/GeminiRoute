"""Canonicalisation, so that equivalent configs produce equal fingerprints.

    vless://uuid@example.com:443#a                     (defaults omitted)
    vless://uuid@EXAMPLE.com:443?type=tcp&security=none#b

`normalize` returns a NEW Node with `fingerprint=""` so `__post_init__`
recomputes it. Normalising in place would leave a fingerprint derived from the
pre-canonical values and silently break dedup.

This stage canonicalises only; rejecting nodes is the pre-validator's job.
"""

from dataclasses import replace

from geminiroute.core.models import Node

DEFAULT_TRANSPORT = "tcp"
DEFAULT_SECURITY = "none"

# Different sources spell the same transport differently.
TRANSPORT_ALIASES: dict[str, str] = {
    "": DEFAULT_TRANSPORT,
    "raw": DEFAULT_TRANSPORT,
    "none": DEFAULT_TRANSPORT,
    "h2": "http",
    "websocket": "ws",
}

SECURITY_ALIASES: dict[str, str] = {
    "": DEFAULT_SECURITY,
    "0": DEFAULT_SECURITY,
    "false": DEFAULT_SECURITY,
}


def normalize_address(address: str) -> str:
    """Lowercase, trim, drop the FQDN trailing dot, strip IPv6 brackets."""
    return address.strip().strip("[]").rstrip(".").lower()


def normalize_transport(transport: str) -> str:
    value = transport.strip().lower()
    return TRANSPORT_ALIASES.get(value, value)


def normalize_security(security: str) -> str:
    value = security.strip().lower()
    return SECURITY_ALIASES.get(value, value)


def normalize_params(params: dict[str, str]) -> dict[str, str]:
    """Lowercase keys, trim values, drop empties, sort for a stable order.

    Values are NOT lowercased: `/API` is not the same endpoint as `/api`.
    """
    cleaned = {
        key.strip().lower(): str(value).strip()
        for key, value in params.items()
        if str(value).strip()
    }
    return dict(sorted(cleaned.items()))


def normalize(node: Node) -> Node:
    """Return the canonical form of a node, with a recomputed fingerprint."""
    return replace(
        node,
        address=normalize_address(node.address),
        transport=normalize_transport(node.transport),
        security=normalize_security(node.security),
        credential=node.credential.strip(),
        params=normalize_params(node.params),
        remark=" ".join(node.remark.split()),
        fingerprint="",  # forces __post_init__ to recompute
    )


def normalize_all(nodes: list[Node]) -> list[Node]:
    return [normalize(node) for node in nodes]
