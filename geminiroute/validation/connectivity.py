"""Connectivity and latency, via asyncio.

Measures TCP and, when the node claims TLS, TLS handshake timings separately —
a fast TCP connect with a slow TLS handshake is the signature of an overloaded
node.

This stage does not speak the node's proxy protocol. A server can complete a
TLS handshake and still proxy nothing, which is what the Gemini stage is for.
Concurrency is bounded by a Semaphore.
"""

from __future__ import annotations

import asyncio
import contextlib
import socket
import ssl
import time
from collections.abc import Iterable

from geminiroute.core.enums import ValidationStage
from geminiroute.core.models import LatencyResult, Node, ValidationResult
from geminiroute.observability.logging import get_logger

log = get_logger(__name__)

DEFAULT_TIMEOUT = 8.0
DEFAULT_CONCURRENCY = 100

# Node.security values that imply a TLS handshake on the outer connection.
TLS_SECURITIES = frozenset({"tls", "xtls", "reality"})


def _ms(start: float, end: float) -> float:
    return round((end - start) * 1000, 2)


def _tls_context() -> ssl.SSLContext:
    """A permissive TLS context.

    Verification is off by design: many working nodes use self-signed certs or
    a mismatched SNI. This probe measures reachability and sends no secret.
    """
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    return context


async def resolve(address: str, timeout: float) -> tuple[str | None, float | None]:
    """Resolve a hostname to an IP, returning (ip, dns_ms)."""
    loop = asyncio.get_running_loop()
    start = time.perf_counter()
    try:
        infos = await asyncio.wait_for(
            loop.getaddrinfo(address, None, type=socket.SOCK_STREAM), timeout
        )
    except (TimeoutError, socket.gaierror, OSError):
        return None, None
    if not infos:
        return None, None
    ip = str(infos[0][4][0])
    return ip, _ms(start, time.perf_counter())


async def probe(
    node: Node,
    timeout: float = DEFAULT_TIMEOUT,
) -> ValidationResult:
    """DNS -> TCP -> (TLS), timing each phase separately."""
    ip, dns_ms = await resolve(node.address, timeout)
    if ip is None:
        return ValidationResult(
            node_fingerprint=node.fingerprint,
            stage=ValidationStage.CONNECTIVITY,
            passed=False,
            error="dns resolution failed",
        )

    use_tls = node.security in TLS_SECURITIES
    server_hostname = node.params.get("sni") or node.params.get("host") or node.address

    overall_start = time.perf_counter()
    writer = None
    try:
        connect_start = time.perf_counter()
        reader_writer = await asyncio.wait_for(
            asyncio.open_connection(host=ip, port=node.port), timeout
        )
        _, writer = reader_writer
        connect_ms = _ms(connect_start, time.perf_counter())

        tls_ms: float | None = None
        if use_tls:
            tls_start = time.perf_counter()
            # start_tls upgrades the live connection in place, which is why
            # the plain connection is opened and timed first.
            await asyncio.wait_for(
                writer.start_tls(_tls_context(), server_hostname=server_hostname),
                timeout,
            )
            tls_ms = _ms(tls_start, time.perf_counter())

    except (TimeoutError, asyncio.TimeoutError):
        return ValidationResult(
            node_fingerprint=node.fingerprint,
            stage=ValidationStage.CONNECTIVITY,
            passed=False,
            error="timeout",
        )
    except (OSError, ssl.SSLError) as exc:
        return ValidationResult(
            node_fingerprint=node.fingerprint,
            stage=ValidationStage.CONNECTIVITY,
            passed=False,
            error=f"{type(exc).__name__}: {exc}",
        )
    finally:
        if writer is not None:
            writer.close()
            with contextlib.suppress(OSError, ssl.SSLError, asyncio.TimeoutError):
                await writer.wait_closed()

    latency = LatencyResult(
        dns_ms=dns_ms,
        connect_ms=connect_ms,
        tls_ms=tls_ms,
        total_ms=_ms(overall_start, time.perf_counter()),
    )
    return ValidationResult(
        node_fingerprint=node.fingerprint,
        stage=ValidationStage.CONNECTIVITY,
        passed=True,
        latency=latency,
    )


async def probe_all(
    nodes: Iterable[Node],
    concurrency: int = DEFAULT_CONCURRENCY,
    timeout: float = DEFAULT_TIMEOUT,
) -> list[ValidationResult]:
    """Probe many nodes with a bounded number of handshakes in flight."""
    semaphore = asyncio.Semaphore(concurrency)

    async def guarded(node: Node) -> ValidationResult:
        async with semaphore:
            return await probe(node, timeout)

    node_list = list(nodes)
    results = await asyncio.gather(*(guarded(n) for n in node_list))
    passed = sum(1 for r in results if r.passed)
    log.info("connectivity_batch_done", total=len(node_list), passed=passed)
    return results


def filter_by_connectivity(
    nodes: list[Node],
    results: list[ValidationResult],
    max_latency_ms: float | None = None,
) -> list[Node]:
    """Keep nodes that connected, optionally enforcing a latency ceiling.

    Applied to the measurements already taken rather than re-probing.
    """
    by_fingerprint = {r.node_fingerprint: r for r in results}
    survivors: list[Node] = []

    for node in nodes:
        result = by_fingerprint.get(node.fingerprint)
        if result is None or not result.passed:
            continue
        if max_latency_ms is not None:
            total = result.latency.total_ms if result.latency else None
            if total is None or total > max_latency_ms:
                continue
        survivors.append(node)

    return survivors
