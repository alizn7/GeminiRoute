"""Connectivity tests against a real local socket. Nothing touches the internet.
"""

import asyncio
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio

from geminiroute.core.enums import ProtocolType
from geminiroute.core.models import Node
from geminiroute.validation import connectivity


def node(port: int, security: str = "") -> Node:
    return Node(
        protocol=ProtocolType.VLESS, address="127.0.0.1", port=port,
        security=security, credential="uuid", raw="vless://x",
    )


@pytest_asyncio.fixture
async def listening_port() -> AsyncIterator[int]:
    async def handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        writer.close()

    server = await asyncio.start_server(handle, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    async with server:
        yield port


@pytest.mark.asyncio
async def test_open_port_passes_and_records_timings(listening_port: int) -> None:
    result = await connectivity.probe(node(listening_port))
    assert result.passed
    assert result.latency is not None
    assert result.latency.connect_ms is not None
    assert result.latency.total_ms is not None


@pytest.mark.asyncio
async def test_no_tls_phase_is_timed_for_a_plain_node(listening_port: int) -> None:
    result = await connectivity.probe(node(listening_port, security=""))
    assert result.latency is not None and result.latency.tls_ms is None


@pytest.mark.asyncio
async def test_closed_port_fails_without_raising() -> None:
    result = await connectivity.probe(node(9), timeout=2.0)
    assert not result.passed and result.error


@pytest.mark.asyncio
async def test_unresolvable_hostname_is_reported_as_dns_failure() -> None:
    bad = Node(protocol=ProtocolType.VLESS, address="no-such-host.invalid",
               port=443, credential="uuid", raw="vless://x")
    result = await connectivity.probe(bad, timeout=3.0)
    assert not result.passed
    assert result.error == "dns resolution failed"


@pytest.mark.asyncio
async def test_batch_returns_one_result_per_node(listening_port: int) -> None:
    nodes = [node(listening_port), node(9)]
    results = await connectivity.probe_all(nodes, concurrency=5, timeout=2.0)
    assert len(results) == 2
    assert sum(1 for r in results if r.passed) == 1


@pytest.mark.asyncio
async def test_latency_ceiling_filters_slow_nodes(listening_port: int) -> None:
    nodes = [node(listening_port)]
    results = await connectivity.probe_all(nodes, timeout=2.0)
    assert connectivity.filter_by_connectivity(nodes, results, max_latency_ms=10000)
    assert connectivity.filter_by_connectivity(nodes, results, max_latency_ms=0.0001) == []
