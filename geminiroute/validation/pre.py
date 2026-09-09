"""Pre-validation: pure functions over a Node, no network.

Rejecting private/loopback/link-local addresses is a safety property, not just
a cleanliness one: without it the validator would probe the machine it runs on.
"""

from __future__ import annotations

import ipaddress
import re
from dataclasses import dataclass

from geminiroute.core.enums import ValidationStage
from geminiroute.core.models import Node, ValidationResult

# A hostname label: alphanumerics and hyphens, not starting or ending with one.
_LABEL = r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?"
_HOSTNAME_RE = re.compile(rf"^{_LABEL}(?:\.{_LABEL})*$")

# Hostnames that appear constantly in template/example configs.
PLACEHOLDER_HOSTS = frozenset(
    {
        "example.com",
        "example.org",
        "example.net",
        "localhost",
        "your-domain.com",
        "yourdomain.com",
        "test.com",
        "a.com",
    }
)

MIN_PORT = 1
MAX_PORT = 65535


@dataclass(frozen=True)
class PreCheck:
    """Why a node was rejected, or None if it passed."""

    passed: bool
    error: str | None = None


def _address_problem(address: str) -> str | None:
    if not address:
        return "empty address"

    try:
        ip = ipaddress.ip_address(address)
    except ValueError:
        # Not an IP, so it must be a plausible hostname.
        if len(address) > 253 or not _HOSTNAME_RE.match(address):
            return "invalid hostname"
        if address in PLACEHOLDER_HOSTS:
            return "placeholder hostname"
        if "." not in address:
            return "hostname has no dot"
        return None

    if ip.is_loopback:
        return "loopback address"
    # Order matters: `ipaddress` also reports link-local ranges as private, so
    # the more specific check has to come first or the error message lies.
    if ip.is_link_local:
        return "link-local address"
    if ip.is_private:
        return "private address"
    if ip.is_multicast or ip.is_reserved or ip.is_unspecified:
        return "non-routable address"
    return None


def check(node: Node) -> PreCheck:
    """Structural validation of a single node. Never touches the network."""
    problem = _address_problem(node.address)
    if problem is not None:
        return PreCheck(False, problem)

    if not MIN_PORT <= node.port <= MAX_PORT:
        return PreCheck(False, f"port out of range: {node.port}")

    if not node.credential:
        return PreCheck(False, "missing credential")

    if not node.raw:
        # Unpublishable without the original line, so useless even if it works.
        return PreCheck(False, "missing raw config")

    return PreCheck(True)


def validate(node: Node) -> ValidationResult:
    result = check(node)
    return ValidationResult(
        node_fingerprint=node.fingerprint,
        stage=ValidationStage.PRE,
        passed=result.passed,
        error=result.error,
    )


def filter_nodes(nodes: list[Node]) -> tuple[list[Node], list[ValidationResult]]:
    """Split into survivors, plus a result for every node.

    Rejections are returned too: without them, `validation_history` cannot
    explain where the collected lines went.
    """
    survivors: list[Node] = []
    results: list[ValidationResult] = []

    for node in nodes:
        result = validate(node)
        results.append(result)
        if result.passed:
            survivors.append(node)

    return survivors, results
