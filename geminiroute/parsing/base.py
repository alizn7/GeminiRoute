"""Parser contract and shared URI parsing.

Contract: a parser never raises. Malformed config returns None.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from urllib.parse import parse_qsl, unquote, urlsplit

from geminiroute.core.enums import ProtocolType
from geminiroute.core.models import Node


class Parser(ABC):
    """One implementation per protocol, dispatched by the registry."""

    protocol: ProtocolType
    scheme: str

    @abstractmethod
    def parse(self, raw: str) -> Node | None:
        """Turn one raw config line into a Node, or None if it is malformed."""


@dataclass(frozen=True)
class UriParts:
    """The pieces of a `scheme://credential@host:port?params#remark` link."""

    credential: str
    address: str
    port: int
    params: dict[str, str]
    remark: str


def split_uri(raw: str, scheme: str) -> UriParts | None:
    """Parse a `scheme://credential@host:port?params#remark` link."""
    raw = raw.strip()
    if not raw.lower().startswith(f"{scheme}://"):
        return None

    try:
        parts = urlsplit(raw)
        port = parts.port  # raises ValueError on "abc" or on out-of-range
    except ValueError:
        return None

    if port is None:
        # No default port for these protocols; guessing would invent a node.
        return None

    host = parts.hostname  # already lowercased; IPv6 brackets already stripped
    if not host:
        return None

    credential = unquote(parts.username or "")
    if not credential:
        return None

    params = {k.lower(): v for k, v in parse_qsl(parts.query, keep_blank_values=False)}
    remark = unquote(parts.fragment).strip()

    return UriParts(
        credential=credential,
        address=host,
        port=port,
        params=params,
        remark=remark,
    )


def node_from_uri_parts(protocol: ProtocolType, parts: UriParts, raw: str) -> Node:
    """Build a Node, promoting `type` and `security` out of params.

    Those two are part of the node's identity and go into the fingerprint;
    everything else stays in the `params` bag.
    """
    params = dict(parts.params)
    transport = params.pop("type", "")
    security = params.pop("security", "")

    return Node(
        protocol=protocol,
        address=parts.address,
        port=parts.port,
        transport=transport,
        security=security,
        credential=parts.credential,
        params=params,
        remark=parts.remark,
        raw=raw.strip(),
    )
