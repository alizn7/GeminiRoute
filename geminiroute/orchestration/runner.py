"""Pipeline wiring — the only place that knows the order of the stages.

    collect -> parse -> normalize -> dedup -> pre -> connectivity
            -> [cap] -> geo -> gemini -> score -> generate

Cheap filters run first so the expensive stage sees hundreds of nodes instead
of tens of thousands. The cap exists because a sudden influx of sources could
otherwise push the Gemini stage past the job time limit.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone

from geminiroute.collection.collector import collect_all
from geminiroute.config.settings import Settings
from geminiroute.core.enums import NodeStatus, ValidationStage
from geminiroute.core.models import GeoInfo, LatencyResult, Node, ValidationResult
from geminiroute.dedup.deduplicator import deduplicate, duplicate_count
from geminiroute.generation.generator import ScoredNode, generate
from geminiroute.normalization.normalizer import normalize_all
from geminiroute.observability.logging import get_logger
from geminiroute.parsing.registry import parse_lines
from geminiroute.reliability.lifecycle import next_status
from geminiroute.retry.policy import decide
from geminiroute.scoring.scorer import ScoreInputs, score_node
from geminiroute.storage.sqlite_repo import SqliteRepository
from geminiroute.validation import connectivity, geo, pre
from geminiroute.validation.gemini import GeminiValidator, find_xray_binary

log = get_logger(__name__)


@dataclass
class RunStats:
    """The funnel, recorded stage by stage."""

    collected: int = 0
    parsed: int = 0
    after_dedup: int = 0
    after_pre: int = 0
    after_connectivity: int = 0
    gemini_tested: int = 0
    gemini_passed: int = 0
    errors: list[str] = field(default_factory=list)


def collect_and_parse(settings: Settings) -> tuple[list[Node], RunStats]:
    """Collect, parse, normalize, dedup. No network validation yet."""
    stats = RunStats()
    nodes: list[Node] = []

    for result in collect_all(settings.sources):
        stats.collected += len(result.lines)
        if not result.ok and result.error:
            stats.errors.append(f"{result.source.name}: {result.error}")
            continue
        parsed = parse_lines(result.lines)
        for node in parsed:
            node.source_names.append(result.source.name)
        nodes.extend(parsed)

    stats.parsed = len(nodes)
    normalized = normalize_all(nodes)
    deduped = deduplicate(normalized)
    stats.after_dedup = len(deduped)

    log.info(
        "collection_done",
        collected=stats.collected,
        parsed=stats.parsed,
        duplicates=duplicate_count(normalized),
        unique=stats.after_dedup,
    )
    return deduped, stats


async def run_pipeline(settings: Settings) -> RunStats:
    """Execute a full run and write the published output tree."""
    repository = SqliteRepository(settings.database_path)
    try:
        repository.upsert_sources(settings.sources)

        nodes, stats = collect_and_parse(settings)
        repository.upsert_nodes(nodes)

        # --- stage: pre-validation (free) -----------------------------
        survivors, pre_results = pre.filter_nodes(nodes)
        repository.record_results(pre_results)
        stats.after_pre = len(survivors)

        # --- stage: connectivity + latency (cheap) --------------------
        connectivity_results = await connectivity.probe_all(
            survivors,
            concurrency=settings.connectivity_concurrency,
            timeout=settings.connectivity_timeout,
        )
        repository.record_results(connectivity_results)
        latency_by_fingerprint = {
            r.node_fingerprint: r.latency for r in connectivity_results if r.passed
        }
        reachable = connectivity.filter_by_connectivity(
            survivors, connectivity_results, max_latency_ms=settings.max_latency_ms
        )
        stats.after_connectivity = len(reachable)

        # --- cap: keep the fastest N for the expensive stage ----------
        def total_latency(node: Node) -> float:
            latency = latency_by_fingerprint.get(node.fingerprint)
            return latency.total_ms if latency and latency.total_ms is not None else 1e9

        candidates = sorted(reachable, key=total_latency)[: settings.max_gemini_candidates]

        # --- geo (decorative, never a filter) -------------------------
        geo_by_fingerprint = await _lookup_geo(candidates)
        for node in candidates:
            info = geo_by_fingerprint.get(node.fingerprint)
            if info is not None:
                repository.set_geo(node.fingerprint, info.country, info.city, info.asn, info.isp)

        # --- stage: gemini validation (expensive) ---------------------
        gemini_results = await _validate_gemini(settings, candidates, stats)
        repository.record_results(gemini_results)
        gemini_by_fingerprint = {r.node_fingerprint: r for r in gemini_results}

        # --- lifecycle + retry scheduling -----------------------------
        scored: list[ScoredNode] = []
        for node in candidates:
            result = gemini_by_fingerprint.get(node.fingerprint)
            passed = bool(result and result.passed)
            fails = 0 if passed else repository.get_consecutive_fails(node.fingerprint) + 1
            status = next_status(node.status, passed, fails)
            retry = decide(fails)
            repository.update_status(node.fingerprint, status, fails, retry.next_retry_at)

            passed_checks, total_checks = repository.reliability(node.fingerprint)
            latency = latency_by_fingerprint.get(node.fingerprint)
            score = score_node(
                ScoreInputs(
                    node_fingerprint=node.fingerprint,
                    latency=latency,
                    gemini_passed=passed,
                    passed_checks=passed_checks,
                    total_checks=total_checks,
                )
            )
            node.status = status
            scored.append(
                ScoredNode(
                    node=node,
                    score=score,
                    gemini_passed=passed,
                    latency_ms=latency.total_ms if latency else None,
                    geo=geo_by_fingerprint.get(node.fingerprint),
                )
            )

        repository.save_scores([item.score for item in scored])
        stats.gemini_passed = sum(1 for item in scored if item.gemini_passed)

        # --- stage: generate ------------------------------------------
        generate(
            settings.output_dir,
            scored,
            collected=stats.collected,
            after_dedup=stats.after_dedup,
            after_pre=stats.after_pre,
            after_connectivity=stats.after_connectivity,
        )

        removed = repository.prune_history(settings.history_retention_days)
        log.info(
            "run_complete",
            collected=stats.collected,
            unique=stats.after_dedup,
            reachable=stats.after_connectivity,
            gemini_passed=stats.gemini_passed,
            history_rows_pruned=removed,
        )
        return stats
    finally:
        repository.close()


async def _lookup_geo(nodes: list[Node]) -> dict[str, GeoInfo]:
    """Resolve geo for the candidate set, keyed by fingerprint."""
    if not nodes:
        return {}
    ip_by_fingerprint: dict[str, str] = {}
    for node in nodes:
        ip, _ = await connectivity.resolve(node.address, timeout=3.0)
        if ip:
            ip_by_fingerprint[node.fingerprint] = ip

    geo_by_ip = await asyncio.to_thread(geo.lookup, list(ip_by_fingerprint.values()))
    return {
        fingerprint: geo_by_ip[ip]
        for fingerprint, ip in ip_by_fingerprint.items()
        if ip in geo_by_ip
    }


async def _validate_gemini(
    settings: Settings, nodes: list[Node], stats: RunStats
) -> list[ValidationResult]:
    """Run the Gemini stage, degrading gracefully when xray is unavailable."""
    stats.gemini_tested = len(nodes)
    if not nodes:
        return []

    xray_path = find_xray_binary(settings.xray_path)
    if xray_path is None:
        # A degraded run, not a silent skip: publishing unverified nodes as
        # verified would be worse than publishing nothing.
        message = "xray binary not found; gemini stage skipped"
        log.error("gemini_stage_unavailable", reason=message)
        stats.errors.append(message)
        return [
            ValidationResult(
                node_fingerprint=node.fingerprint,
                stage=ValidationStage.GEMINI,
                passed=False,
                error="proxy core unavailable",
                checked_at=datetime.now(timezone.utc),
            )
            for node in nodes
        ]

    validator = GeminiValidator(
        xray_path=xray_path,
        api_key=settings.gemini_api_key,
        pool_size=settings.gemini_pool_size,
        timeout=settings.gemini_timeout,
    )
    return await validator.validate_all(nodes)


def build_scored_node(node: Node, latency: LatencyResult | None, passed: bool) -> ScoredNode:
    """Small helper used by tests to build a ScoredNode without a full run."""
    score = score_node(
        ScoreInputs(node_fingerprint=node.fingerprint, latency=latency, gemini_passed=passed)
    )
    node.status = NodeStatus.HEALTHY if passed else NodeStatus.DEGRADED
    return ScoredNode(
        node=node,
        score=score,
        gemini_passed=passed,
        latency_ms=latency.total_ms if latency else None,
    )
