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
from geminiroute.generation.branding import make_label, rebrand
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


def build_index_html(stats: dict[str, object]) -> str:
    """A landing page for the published tree.

    Also serves as the check that Pages is actually serving the branch: a
    root URL that 404s is ambiguous, one that renders is not.
    """
    funnel = stats.get("funnel", {})
    rows = "\n".join(
        f"      <tr><td>{name.replace('_', ' ')}</td><td>{value}</td></tr>"
        for name, value in (funnel.items() if isinstance(funnel, dict) else [])
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>GeminiRoute</title>
  <style>
    body {{ font-family: system-ui, sans-serif; max-width: 46rem; margin: 3rem auto;
           padding: 0 1rem; line-height: 1.6; color: #1a1a1a; }}
    code {{ background: #f4f4f4; padding: .15rem .35rem; border-radius: 3px; }}
    table {{ border-collapse: collapse; margin: 1rem 0; }}
    td {{ border-bottom: 1px solid #eee; padding: .35rem 1.5rem .35rem 0; }}
    td:last-child {{ text-align: right; font-variant-numeric: tabular-nums; }}
    .muted {{ color: #666; font-size: .9rem; }}
  </style>
</head>
<body>
  <h1>GeminiRoute</h1>
  <p class="muted">Generated {stats.get("generated_at", "")}</p>

  <h2>Subscriptions</h2>
  <ul>
    <li><a href="sub/gemini.txt">sub/gemini.txt</a> — verified nodes</li>
    <li><a href="sub/best.txt">sub/best.txt</a> — top 30 by score</li>
    <li><a href="sub/fast.txt">sub/fast.txt</a> — verified and under 500 ms</li>
    <li><a href="sub/all.txt">sub/all.txt</a> — everything tested</li>
  </ul>
  <p class="muted">Add one of these URLs to a client as a subscription link.
     Each has a <code>.plain.txt</code> twin that is not base64 encoded.</p>

  <h2>Using these</h2>
  <p>Nodes are verified against the Gemini <strong>API</strong>: each one is
     checked from inside its own tunnel for where it exits, and rejected if it
     comes out somewhere Gemini is not served.</p>
  <p class="muted">The Gemini <strong>web app</strong> has a second gate: it
     also looks at the country of the Google account you are signed into. A
     node can be perfectly good and still show
     <em>&ldquo;Gemini isn&rsquo;t currently supported in your country&rdquo;</em>
     because of the account, not the node. Open
     <code>gemini.google.com</code> in a private window, signed out, to rule
     that out.</p>

  <h2>API</h2>
  <ul>
    <li><a href="api/nodes.json">api/nodes.json</a></li>
    <li><a href="api/stats.json">api/stats.json</a></li>
  </ul>

  <h2>Last run</h2>
  <table>
{rows}
  </table>
</body>
</html>
"""


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
    }


def generate(
    output_dir: Path,
    items: list[ScoredNode],
    collected: int = 0,
    after_dedup: int = 0,
    after_pre: int = 0,
    after_connectivity: int = 0,
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

    write_subscription(sub_dir, "all", ranked)
    write_subscription(sub_dir, "gemini", gemini_ok)
    write_subscription(sub_dir, "best", gemini_ok[:BEST_COUNT])
    write_subscription(sub_dir, "fast", fast)

    by_country: dict[str, list[ScoredNode]] = {}
    for item in gemini_ok:
        by_country.setdefault(country_key(item.geo), []).append(item)
    for code, group in by_country.items():
        write_subscription(sub_dir / "country", code, group)

    _write(
        api_dir / "nodes.json",
        json.dumps(build_api_payload(ranked), ensure_ascii=False, indent=2),
    )
    stats = build_stats_payload(ranked, collected, after_dedup, after_pre, after_connectivity)
    _write(api_dir / "stats.json", json.dumps(stats, ensure_ascii=False, indent=2))
    _write(output_dir / "index.html", build_index_html(stats))
    log.info("generation_done", total=len(ranked), gemini_ok=len(gemini_ok))
