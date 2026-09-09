"""Domain enumerations.

Members subclass `str` so they compare equal to their value and serialise
without a custom JSON encoder.
"""

from enum import Enum


class ProtocolType(str, Enum):
    VLESS = "vless"
    VMESS = "vmess"
    TROJAN = "trojan"
    SHADOWSOCKS = "shadowsocks"


class NodeStatus(str, Enum):
    """Lifecycle of a node.

    DISCOVERED -> VALIDATING -> HEALTHY | DEGRADED | DEAD
    DEAD -> RECHECK -> HEALTHY | DEAD
    """

    DISCOVERED = "discovered"
    VALIDATING = "validating"
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    DEAD = "dead"
    RECHECK = "recheck"


class ValidationStage(str, Enum):
    """Which filter in the funnel produced a result."""

    PRE = "pre"
    CONNECTIVITY = "connectivity"
    LATENCY = "latency"
    GEO = "geo"
    GEMINI = "gemini"
