"""Storage tests against a real in-memory SQLite database.
"""

from geminiroute.core.enums import NodeStatus, ProtocolType, ValidationStage
from geminiroute.core.models import LatencyResult, Node, Score, Source, ValidationResult
from geminiroute.storage.sqlite_repo import SqliteRepository


def repo() -> SqliteRepository:
    return SqliteRepository(":memory:")


def node(address: str = "a.example.net", sources: list[str] | None = None) -> Node:
    return Node(
        protocol=ProtocolType.VLESS, address=address, port=443,
        transport="ws", security="tls", credential="uuid",
        params={"sni": "x.example.net"}, remark="DE-01",
        source_names=list(sources or ["s1"]), raw="vless://uuid@a.example.net:443",
    )


def test_node_round_trips_intact() -> None:
    r = repo()
    original = node()
    r.upsert_nodes([original])
    loaded = r.get_node(original.fingerprint)
    assert loaded is not None
    assert loaded.address == original.address
    assert loaded.params == original.params
    assert loaded.raw == original.raw
    assert loaded.protocol is ProtocolType.VLESS


def test_upsert_is_idempotent() -> None:
    r = repo()
    r.upsert_nodes([node()])
    r.upsert_nodes([node()])
    assert len(r.list_nodes()) == 1


def test_reliability_counts_only_gemini_stage() -> None:
    """Connectivity passes are far more common; counting them would inflate
    every node's reliability toward 1.0 and make the score meaningless."""
    r = repo()
    n = node()
    r.upsert_nodes([n])
    r.record_results([
        ValidationResult(n.fingerprint, ValidationStage.CONNECTIVITY, True),
        ValidationResult(n.fingerprint, ValidationStage.CONNECTIVITY, True),
        ValidationResult(n.fingerprint, ValidationStage.GEMINI, True),
        ValidationResult(n.fingerprint, ValidationStage.GEMINI, False),
    ])
    assert r.reliability(n.fingerprint) == (1, 2)


def test_reliability_of_an_unknown_node_is_empty() -> None:
    assert repo().reliability("nope") == (0, 0)


def test_status_and_failure_count_are_updated() -> None:
    r = repo()
    n = node()
    r.upsert_nodes([n])
    r.update_status(n.fingerprint, NodeStatus.DEGRADED, 2, None)
    assert r.get_consecutive_fails(n.fingerprint) == 2
    loaded = r.get_node(n.fingerprint)
    assert loaded is not None and loaded.status is NodeStatus.DEGRADED


def test_latency_is_stored_with_history() -> None:
    r = repo()
    n = node()
    r.upsert_nodes([n])
    r.record_results([
        ValidationResult(n.fingerprint, ValidationStage.GEMINI, True,
                         latency=LatencyResult(total_ms=123.4))
    ])
    row = r._connection.execute("SELECT latency_ms FROM validation_history").fetchone()
    assert row["latency_ms"] == 123.4


def test_scores_are_saved_onto_the_node() -> None:
    r = repo()
    n = node()
    r.upsert_nodes([n])
    r.save_scores([Score(n.fingerprint, 1.0, 1.0, 1.0, 1.0, 0.87)])
    row = r._connection.execute("SELECT final_score FROM nodes").fetchone()
    assert row["final_score"] == 0.87


def test_sources_upsert_and_update() -> None:
    r = repo()
    r.upsert_sources([Source("s1", "raw", "https://a", True)])
    r.upsert_sources([Source("s1", "raw", "https://b", False)])
    row = r._connection.execute("SELECT url, enabled FROM sources").fetchone()
    assert row["url"] == "https://b" and row["enabled"] == 0


def test_prune_keeps_recent_history() -> None:
    r = repo()
    n = node()
    r.upsert_nodes([n])
    r.record_results([ValidationResult(n.fingerprint, ValidationStage.GEMINI, True)])
    assert r.prune_history(90) == 0        # today's row survives
    assert r.reliability(n.fingerprint) == (1, 1)


def test_error_histogram_groups_failure_reasons() -> None:
    r = repo()
    n = node()
    r.upsert_nodes([n])
    r.record_results([
        ValidationResult(n.fingerprint, ValidationStage.GEMINI, False, error="proxy failed"),
        ValidationResult(n.fingerprint, ValidationStage.GEMINI, False, error="proxy failed"),
        ValidationResult(n.fingerprint, ValidationStage.GEMINI, False, error="timeout"),
        ValidationResult(n.fingerprint, ValidationStage.GEMINI, True),
        ValidationResult(n.fingerprint, ValidationStage.CONNECTIVITY, False, error="timeout"),
    ])
    assert r.error_histogram("gemini") == [("proxy failed", 2), ("timeout", 1)]


def test_error_histogram_is_empty_when_nothing_failed() -> None:
    assert repo().error_histogram("gemini") == []
