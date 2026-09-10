"""Backoff filtering and source attribution — the two things that were
implemented but never wired into the pipeline."""

from datetime import UTC, datetime, timedelta

from geminiroute.core.enums import NodeStatus, ProtocolType, ValidationStage
from geminiroute.core.models import Node, Score, ValidationResult
from geminiroute.generation.generator import ScoredNode
from geminiroute.orchestration.runner import RunStats, _apply_backoff, _record_source_stats
from geminiroute.storage.sqlite_repo import SqliteRepository


def node(address: str, sources: list[str] | None = None) -> Node:
    return Node(
        protocol=ProtocolType.VLESS, address=address, port=443, credential="uuid",
        raw=f"vless://uuid@{address}:443", source_names=list(sources or ["s1"]),
    )


def scored_node(n: Node, passed: bool) -> ScoredNode:
    return ScoredNode(node=n, score=Score(n.fingerprint, 0, 0, 0, 0, 0.5), gemini_passed=passed)


def test_new_nodes_are_always_due() -> None:
    repo = SqliteRepository(":memory:")
    stats = RunStats()
    nodes = [node("a.example.net"), node("b.example.net")]
    assert len(_apply_backoff(repo, nodes, stats)) == 2
    assert stats.skipped_in_backoff == 0


def test_node_inside_its_backoff_window_is_skipped() -> None:
    repo = SqliteRepository(":memory:")
    n = node("a.example.net")
    repo.upsert_nodes([n])
    repo.update_status(n.fingerprint, NodeStatus.DEGRADED, 1,
                       datetime.now(UTC) + timedelta(minutes=30))

    stats = RunStats()
    assert _apply_backoff(repo, [n], stats) == []
    assert stats.skipped_in_backoff == 1


def test_node_past_its_backoff_window_is_tested_again() -> None:
    repo = SqliteRepository(":memory:")
    n = node("a.example.net")
    repo.upsert_nodes([n])
    repo.update_status(n.fingerprint, NodeStatus.DEGRADED, 1,
                       datetime.now(UTC) - timedelta(minutes=1))
    assert len(_apply_backoff(repo, [n], RunStats())) == 1


def test_dead_node_leaving_backoff_is_revived_to_recheck() -> None:
    """DEAD is not a grave: once the wait elapses the node re-enters the pool."""
    repo = SqliteRepository(":memory:")
    n = node("a.example.net")
    repo.upsert_nodes([n])
    repo.update_status(n.fingerprint, NodeStatus.DEAD, 3,
                       datetime.now(UTC) - timedelta(hours=1))
    due = _apply_backoff(repo, [n], RunStats())
    assert due[0].status is NodeStatus.RECHECK


def test_source_stats_attribute_each_stage() -> None:
    repo = SqliteRepository(":memory:")
    good = node("good.example.net", ["rich-source"])
    weak = node("weak.example.net", ["rich-source"])
    dud = node("dud.example.net", ["dud-source"])
    repo.upsert_sources([])
    repo.upsert_nodes([good, weak, dud])

    _record_source_stats(repo, [good, weak, dud], [good, weak],
                         [scored_node(good, True), scored_node(weak, False)])

    rows = {r["name"]: r for r in repo._connection.execute(
        "SELECT name, nodes_contributed, nodes_valid, nodes_gemini_ok FROM sources")}
    assert rows["rich-source"]["nodes_contributed"] == 2
    assert rows["rich-source"]["nodes_valid"] == 2
    assert rows["rich-source"]["nodes_gemini_ok"] == 1
    assert rows["dud-source"]["nodes_gemini_ok"] == 0


def test_a_node_from_two_sources_counts_for_both() -> None:
    repo = SqliteRepository(":memory:")
    shared = node("shared.example.net", ["s1", "s2"])
    repo.upsert_nodes([shared])
    _record_source_stats(repo, [shared], [shared], [scored_node(shared, True)])
    rows = {r["name"]: r["nodes_gemini_ok"] for r in repo._connection.execute(
        "SELECT name, nodes_gemini_ok FROM sources")}
    assert rows == {"s1": 1, "s2": 1}


def test_proven_nodes_outrank_faster_untested_ones() -> None:
    """Latency alone over-selects CDN-fronted configs, whose handshake succeeds
    regardless of whether the node behind them is alive."""
    repo = SqliteRepository(":memory:")
    proven, fast = node("proven.example.net"), node("fast.example.net")
    repo.upsert_nodes([proven, fast])
    repo.record_results([
        ValidationResult(proven.fingerprint, ValidationStage.GEMINI, True)
    ])
    assert repo.successful_fingerprints() == {proven.fingerprint}
