"""Connectivity and latency, via asyncio.

Measures TCP and, when the node claims TLS, TLS handshake timings separately —
a fast TCP connect with a slow TLS handshake is the signature of an overloaded
node.

DNS is resolved as its own phase before any connecting, for three reasons:
`getaddrinfo` is blocking and runs on a thread pool, a `wait_for` timeout does
not actually free that thread, and the same hostname appears many times across
a source list. Resolving unique hostnames once, on a dedicated pool, keeps the
blocking work from starving the connect phase.

This stage does not speak the node's proxy protocol. A server can complete a
TLS handshake and still proxy nothing, which is what the Gemini stage is for.
"""

from __future__ import annotations

import asyncio
import contextlib
import ipaddress
import socket
import ssl
import time
from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor

from geminiroute.core.enums import ValidationStage
from geminiroute.core.models import LatencyResult, Node, ValidationResult
from geminiroute.observability.logging import get_logger

log = get_logger(__name__)

DEFAULT_TIMEOUT = 8.0
DEFAULT_CONCURRENCY = 100
DEFAULT_DNS_CONCURRENCY = 64
DEFAULT_DNS_TIMEOUT = 3.0
PROGRESS_EVERY = 500
MIN_PROGRESS_STEPS = 10

TLS_SECURITIES = frozenset({"tls", "xtls", "reality"})

# (ip, dns_ms); ip is None when the name does not resolve.
Resolution = tuple[str | None, float | None]


def _ms(start: float, end: float) -> float:
    return round((end - start) * 1000, 2)


def _abort(writer: asyncio.StreamWriter) -> None:
    """Drop the connection without waiting for a graceful shutdown.

    `writer.close()` + `await writer.wait_closed()` waits for the peer's TLS
    close_notify, which a dead or misbehaving server never sends. Awaiting that
    holds a semaphore slot indefinitely and stalls the whole batch. A probe has
    nothing to flush, so aborting is both correct and safe.
    """
    with contextlib.suppress(OSError, ssl.SSLError, AttributeError, RuntimeError):
        writer.transport.abort()
    with contextlib.suppress(OSError, ssl.SSLError, RuntimeError):
        writer.close()


def _tls_context() -> ssl.SSLContext:
    """A permissive TLS context.

    Verification is off by design: many working nodes use self-signed certs or
    a mismatched SNI. This probe measures reachability and sends no secret.
    """
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    return context


def _blocking_resolve(address: str) -> str | None:
    try:
        infos = socket.getaddrinfo(address, None, type=socket.SOCK_STREAM)
    except (socket.gaierror, OSError):
        return None
    return str(infos[0][4][0]) if infos else None


async def resolve_all(
    addresses: Iterable[str],
    concurrency: int = DEFAULT_DNS_CONCURRENCY,
    timeout: float = DEFAULT_DNS_TIMEOUT,
) -> dict[str, Resolution]:
    """Resolve unique hostnames once, on a pool sized for blocking work.

    A timed-out lookup leaves its thread running — the pool is deliberately
    larger than the CPU count so those stragglers cannot starve the rest.
    """
    unique = sorted({a for a in addresses if a})
    resolved: dict[str, Resolution] = {}
    pending: list[str] = []

    for address in unique:
        try:
            ipaddress.ip_address(address)
        except ValueError:
            pending.append(address)
        else:
            resolved[address] = (address, 0.0)  # already an IP; no lookup needed

    if not pending:
        return resolved

    loop = asyncio.get_running_loop()
    semaphore = asyncio.Semaphore(concurrency)
    executor = ThreadPoolExecutor(max_workers=concurrency, thread_name_prefix="dns")

    async def one(address: str) -> tuple[str, Resolution]:
        async with semaphore:
            start = time.perf_counter()
            try:
                ip = await asyncio.wait_for(
                    loop.run_in_executor(executor, _blocking_resolve, address), timeout
                )
            except (TimeoutError, OSError):
                return address, (None, None)
            if ip is None:
                return address, (None, None)
            return address, (ip, _ms(start, time.perf_counter()))

    for address, resolution in await asyncio.gather(*(one(a) for a in pending)):
        resolved[address] = resolution

    # Do not wait on stragglers: a hung getaddrinfo would block shutdown.
    executor.shutdown(wait=False, cancel_futures=True)

    failed = sum(1 for r in resolved.values() if r[0] is None)
    log.info("dns_done", unique=len(unique), looked_up=len(pending), failed=failed)
    return resolved


async def probe(
    node: Node,
    timeout: float = DEFAULT_TIMEOUT,
    resolution: Resolution | None = None,
) -> ValidationResult:
    """TCP and, when claimed, TLS. Pass `resolution` to skip the DNS phase."""

    def failure(error: str) -> ValidationResult:
        return ValidationResult(
            node_fingerprint=node.fingerprint,
            stage=ValidationStage.CONNECTIVITY,
            passed=False,
            error=error,
        )

    if resolution is None:
        resolution = (await resolve_all([node.address])).get(node.address, (None, None))
    ip, dns_ms = resolution
    if ip is None:
        return failure("dns resolution failed")

    use_tls = node.security in TLS_SECURITIES
    server_hostname = node.params.get("sni") or node.params.get("host") or node.address

    overall_start = time.perf_counter()
    writer = None
    try:
        connect_start = time.perf_counter()
        _, writer = await asyncio.wait_for(
            asyncio.open_connection(host=ip, port=node.port), timeout
        )
        connect_ms = _ms(connect_start, time.perf_counter())

        tls_ms: float | None = None
        if use_tls:
            tls_start = time.perf_counter()
            # start_tls upgrades the live connection in place, which is why
            # the plain connection is opened and timed first.
            await asyncio.wait_for(
                writer.start_tls(_tls_context(), server_hostname=server_hostname), timeout
            )
            tls_ms = _ms(tls_start, time.perf_counter())

    except TimeoutError:
        return failure("timeout")
    except (OSError, ssl.SSLError) as exc:
        return failure(f"{type(exc).__name__}: {exc}")
    finally:
        if writer is not None:
            _abort(writer)

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
    resolutions: dict[str, Resolution] | None = None,
) -> list[ValidationResult]:
    """Probe many nodes: resolve every unique host once, then connect."""
    node_list = list(nodes)
    if not node_list:
        return []

    if resolutions is None:
        resolutions = await resolve_all(n.address for n in node_list)

    semaphore = asyncio.Semaphore(concurrency)
    step = max(1, min(PROGRESS_EVERY, len(node_list) // MIN_PROGRESS_STEPS or 1))
    done = 0

    async def guarded(node: Node) -> ValidationResult:
        nonlocal done
        async with semaphore:
            try:
                result = await asyncio.wait_for(
                    probe(node, timeout, resolutions.get(node.address, (None, None))),
                    timeout * 2 + 1,
                )
            except TimeoutError:
                result = ValidationResult(
                    node_fingerprint=node.fingerprint,
                    stage=ValidationStage.CONNECTIVITY,
                    passed=False,
                    error="probe exceeded its budget",
                )
        done += 1
        if done % step == 0:
            log.info("connectivity_progress", done=done, total=len(node_list))
        return result

    results = await asyncio.gather(*(guarded(n) for n in node_list))
    log.info(
        "connectivity_batch_done",
        total=len(node_list),
        passed=sum(1 for r in results if r.passed),
    )
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
