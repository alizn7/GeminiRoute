"""Node identity.

The fingerprint decides whether two configs are the same usable endpoint. Only
fields that affect whether the node works are hashed; the remark is excluded
because sources label the same server differently.

Changing this function invalidates every stored node id. Treat it as a schema
change, not an implementation detail.
"""

import hashlib

FINGERPRINT_LENGTH = 16


def compute_fingerprint(
    protocol: str,
    address: str,
    port: int,
    transport: str = "",
    security: str = "",
    credential: str = "",
) -> str:
    """Return a short, stable, deterministic id for a node.

    `credential` is the uuid (VLESS/VMess), password (Trojan) or
    method:password (Shadowsocks). It is part of the identity: the same
    host:port with a revoked uuid is not the same usable node.
    """
    parts = [
        protocol.strip().lower(),
        address.strip().lower().rstrip("."),
        str(int(port)),
        transport.strip().lower(),
        security.strip().lower(),
        credential.strip(),
    ]
    raw = "|".join(parts)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return digest[:FINGERPRINT_LENGTH]
