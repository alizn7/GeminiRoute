"""Domain models.

Plain stdlib dataclasses: `core` imports nothing outside the standard library,
which is what keeps every other layer testable without a network or database.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime

from geminiroute.core.enums import NodeStatus, ProtocolType, ValidationStage
from geminiroute.core.fingerprint import compute_fingerprint


def _utcnow() -> datetime:
    """Timezone-aware UTC now. (`datetime.utcnow()` is deprecated in 3.12.)"""
    return datetime.now(UTC)


@dataclass(frozen=True)
class Source:
    """A place we collect raw configs from."""

    name: str
    type: str  # "github" | "raw" | ...
    url: str
    enabled: bool = True


@dataclass
class Node:
    """One endpoint we can test and, if healthy, publish."""

    protocol: ProtocolType
    address: str
    port: int
    transport: str = ""
    security: str = ""
    credential: str = ""
    params: dict[str, str] = field(default_factory=dict)
    remark: str = ""
    source_names: list[str] = field(default_factory=list)
    status: NodeStatus = NodeStatus.DISCOVERED
    fingerprint: str = ""

    # Original config line, republished verbatim by the generator. Not part
    # of the identity.
    raw: str = ""

    def __post_init__(self) -> None:
        # Derived, never passed in by hand, so it cannot drift from its fields.
        if not self.fingerprint:
            self.fingerprint = compute_fingerprint(
                protocol=self.protocol.value,
                address=self.address,
                port=self.port,
                transport=self.transport,
                security=self.security,
                credential=self.credential,
            )


@dataclass(frozen=True)
class LatencyResult:
    """Timing breakdown of a single connectivity check, in milliseconds."""

    dns_ms: float | None = None
    connect_ms: float | None = None
    tls_ms: float | None = None
    total_ms: float | None = None


@dataclass(frozen=True)
class GeoInfo:
    country: str | None = None
    city: str | None = None
    asn: str | None = None
    isp: str | None = None


@dataclass(frozen=True)
class ValidationResult:
    """The outcome of one stage of the funnel for one node."""

    node_fingerprint: str
    stage: ValidationStage
    passed: bool
    latency: LatencyResult | None = None
    geo: GeoInfo | None = None
    error: str | None = None
    checked_at: datetime = field(default_factory=_utcnow)


@dataclass(frozen=True)
class Score:
    node_fingerprint: str
    latency_score: float
    gemini_score: float
    reliability_score: float
    connection_score: float
    final_score: float
