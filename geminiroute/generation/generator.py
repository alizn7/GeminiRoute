"""Subscription generation.

Each line is the node's ORIGINAL config string, not a re-serialisation:
re-encoding from parsed fields would silently drop any parameter we chose not
to model. Files are base64-encoded as a whole because that is what clients
expect; a plain variant is written alongside for debugging.
"""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from geminiroute.core.models import GeoInfo, Node, Score
from geminiroute.generation.badges import (
    countries_badge,
    stats_card,
    subscription_badges,
    success_badge,
    verified_badge,
)
from geminiroute.generation.branding import make_label, rebrand
from geminiroute.generation.dashboard import render as render_dashboard
from geminiroute.observability.logging import get_logger
from geminiroute.validation.geo import country_code as country_slug

log = get_logger(__name__)

BEST_COUNT = 30
FAST_LATENCY_MS = 500.0


@dataclass
class ScoredNode:
    """A node plus everything the generator needs to sort and label it."""

    node: Node
    score: Score
    gemini_passed: bool
    latency_ms: float | None = None
    geo: GeoInfo | None = None


def country_key(geo: GeoInfo | None) -> str:
    """Filesystem-safe key for the per-country files.

    Prefers the ISO code: the exit-location check reports a code rather than a
    name, and codes stay stable where display names do not.
    """
    if geo is None:
        return "unknown"
    if geo.country_code:
        return geo.country_code.lower()
    return country_slug(geo.country)


def _encode(lines: list[str]) -> str:
    return base64.b64encode("\n".join(lines).encode("utf-8")).decode("ascii")


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def branded_lines(nodes: list[ScoredNode]) -> list[str]:
    """Config lines with our own numbered label, in the order given.

    Numbered per file rather than globally, so every file reads 1..N.
    """
    lines: list[str] = []
    for index, item in enumerate(nodes, start=1):
        if not item.node.raw:
            continue
        code = item.geo.country_code if item.geo else None
        lines.append(rebrand(item.node.raw, item.node.protocol, make_label(index, code)))
    return lines


def write_subscription(directory: Path, name: str, nodes: list[ScoredNode]) -> None:
    """Write `<name>.txt` (base64) and `<name>.plain.txt` (human-readable)."""
    lines = branded_lines(nodes)
    _write(directory / f"{name}.txt", _encode(lines))
    _write(directory / f"{name}.plain.txt", "\n".join(lines) + ("\n" if lines else ""))
    log.info("subscription_written", name=name, nodes=len(lines))


def build_api_payload(items: list[ScoredNode]) -> dict[str, object]:
    """`api/nodes.json` — what the dashboard reads.

    Credentials are excluded: the dashboard does not need them, and a field
    named `credential` invites scraping.
    """
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "count": len(items),
        "nodes": [
            {
                "fingerprint": item.node.fingerprint,
                "protocol": item.node.protocol.value,
                "address": item.node.address,
                "port": item.node.port,
                "transport": item.node.transport,
                "security": item.node.security,
                "remark": item.node.remark,
                "sources": item.node.source_names,
                "status": item.node.status.value,
                "gemini_ok": item.gemini_passed,
                "latency_ms": item.latency_ms,
                "country": item.geo.country if item.geo else None,
                "city": item.geo.city if item.geo else None,
                "asn": item.geo.asn if item.geo else None,
                "score": item.score.final_score,
            }
            for item in items
        ],
    }


def build_stats_payload(
    items: list[ScoredNode],
    collected: int,
    after_dedup: int,
    after_pre: int,
    after_connectivity: int,
    sources: list[tuple[str, int, int, int]] | None = None,
) -> dict[str, object]:
    """`api/stats.json` — per-stage survivor counts.

    What makes a regression diagnosable: "0 published" is unactionable,
    "20,000 collected, 0 survived parsing" points at the parser.
    """
    gemini_ok = [i for i in items if i.gemini_passed]
    latencies = [i.latency_ms for i in items if i.latency_ms is not None]
    countries: dict[str, int] = {}
    for item in gemini_ok:
        key = country_key(item.geo)
        countries[key] = countries.get(key, 0) + 1

    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "funnel": {
            "collected": collected,
            "after_dedup": after_dedup,
            "after_pre_validation": after_pre,
            "after_connectivity": after_connectivity,
            "after_gemini": len(gemini_ok),
        },
        "gemini_success_rate": round(len(gemini_ok) / len(items), 4) if items else 0.0,
        "average_latency_ms": round(sum(latencies) / len(latencies), 2) if latencies else None,
        "nodes_by_country": dict(sorted(countries.items(), key=lambda kv: -kv[1])),
        # Published rather than left in the database: deciding whether a source
        # earns its place is the most common question about this pipeline, and
        # the database lives on a branch nobody wants to clone to answer it.
        "sources": [
            {
                "name": name,
                "contributed": contributed,
                "reachable": reachable,
                "gemini_ok": ok,
                "yield": round(ok / contributed, 4) if contributed else None,
            }
            for name, contributed, reachable, ok in sorted(
                sources or [], key=lambda row: -row[3]
            )
        ],
    }


def generate(
    output_dir: Path,
    items: list[ScoredNode],
    collected: int = 0,
    after_dedup: int = 0,
    after_pre: int = 0,
    after_connectivity: int = 0,
    sources: list[tuple[str, int, int, int]] | None = None,
) -> None:
    """Write the full published tree: sub/*.txt plus api/*.json."""
    sub_dir = output_dir / "sub"
    api_dir = output_dir / "api"

    ranked = sorted(items, key=lambda i: i.score.final_score, reverse=True)
    gemini_ok = [i for i in ranked if i.gemini_passed]
    fast = [
        i
        for i in gemini_ok
        if i.latency_ms is not None and i.latency_ms <= FAST_LATENCY_MS
    ]

    best = gemini_ok[:BEST_COUNT]
    write_subscription(sub_dir, "all", ranked)
    write_subscription(sub_dir, "gemini", gemini_ok)
    write_subscription(sub_dir, "best", best)
    write_subscription(sub_dir, "fast", fast)

    by_country: dict[str, list[ScoredNode]] = {}
    for item in gemini_ok:
        by_country.setdefault(country_key(item.geo), []).append(item)
    for code, group in by_country.items():
        write_subscription(sub_dir / "country", code, group)

    file_counts = {
        "all": len(ranked),
        "gemini": len(gemini_ok),
        "best": len(best),
        "fast": len(fast),
    }

    _write(
        api_dir / "nodes.json",
        json.dumps(build_api_payload(ranked), ensure_ascii=False, indent=2),
    )
    stats = build_stats_payload(
        ranked, collected, after_dedup, after_pre, after_connectivity, sources
    )
    _write(api_dir / "stats.json", json.dumps(stats, ensure_ascii=False, indent=2))
    _write(output_dir / "index.html", render_dashboard(stats, file_counts))

    # Embedded by the README so its numbers describe the last run rather than
    # the last time someone edited the file.
    _write(api_dir / "badge.json", verified_badge(stats))
    _write(api_dir / "badge-countries.json", countries_badge(stats))
    _write(api_dir / "badge-success.json", success_badge(stats))
    _write(output_dir / "card.svg", stats_card(stats))
    for name, payload in subscription_badges(file_counts).items():
        _write(api_dir / f"badge-sub-{name}.json", payload)
    log.info("generation_done", total=len(ranked), gemini_ok=len(gemini_ok))
