"""Screening a candidate source without waiting for an hourly run.

Source quality is now what limits this pipeline, not capacity: a run has spare
room in the candidate cap, so the question is never "can we test more?" but
"is this list worth testing?". Four candidates have been added and removed on
the strength of a full run each, which is an expensive way to learn that a
list of two thousand configs verifies none of them.

This answers the same question against a sample, in about two minutes, before
anything reaches sources.toml.

The number to read is `verified / reachable`. Established sources sit between
17% and 66%; every list dropped so far sat under 3% while having *better* TCP
reachability than the ones kept.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from geminiroute.collection.collector import collect_source
from geminiroute.config.settings import Settings
from geminiroute.core.models import Node, Source
from geminiroute.dedup.deduplicator import deduplicate
from geminiroute.normalization.normalizer import normalize_all
from geminiroute.observability.logging import get_logger
from geminiroute.parsing.registry import parse_lines
from geminiroute.validation import connectivity, pre
from geminiroute.validation.gemini import GeminiValidator, find_xray_binary

log = get_logger(__name__)

DEFAULT_SAMPLE = 150


@dataclass
class Trial:
    """What a candidate source produced against a sample."""

    url: str
    collected: int = 0
    parsed: int = 0
    unique: int = 0
    already_covered: int = 0
    sampled: int = 0
    reachable: int = 0
    verified: int = 0
    error: str | None = None
    countries: dict[str, int] = field(default_factory=dict)

    @property
    def conversion(self) -> float | None:
        """Verified as a share of reachable — the number that separates a good
        list from a wall of CDN edges."""
        return self.verified / self.reachable if self.reachable else None

    @property
    def novelty(self) -> float | None:
        """Share of its unique nodes that the current sources do not already
        carry. A list that only repeats what is configured adds run time and
        nothing else."""
        if not self.unique:
            return None
        return 1 - self.already_covered / self.unique


def _collect(source: Source) -> list[Node]:
    result = collect_source(source)
    if not result.ok:
        return []
    nodes = parse_lines(result.lines)
    for node in nodes:
        node.source_names.append(source.name)
    return deduplicate(normalize_all(nodes))


async def evaluate_source(
    url: str,
    settings: Settings,
    source_type: str = "raw",
    sample: int = DEFAULT_SAMPLE,
    rng: random.Random | None = None,
) -> Trial:
    """Collect a candidate, sample it, and run the sample through the funnel."""
    rng = rng or random.Random()
    trial = Trial(url=url)

    candidate = Source(name="candidate", type=source_type, url=url, enabled=True)
    result = collect_source(candidate)
    if not result.ok:
        trial.error = result.error
        return trial

    trial.collected = len(result.lines)
    parsed = parse_lines(result.lines)
    trial.parsed = len(parsed)
    nodes = deduplicate(normalize_all(parsed))
    trial.unique = len(nodes)
    if not nodes:
        trial.error = "nothing parsed"
        return trial

    # How much of this is already covered by what is configured?
    existing: set[str] = set()
    for source in settings.sources:
        if source.enabled:
            existing.update(n.fingerprint for n in _collect(source))
    trial.already_covered = sum(1 for n in nodes if n.fingerprint in existing)

    survivors, _ = pre.filter_nodes(nodes)
    rng.shuffle(survivors)
    chosen = survivors[:sample]
    trial.sampled = len(chosen)
    if not chosen:
        trial.error = "nothing survived plausibility checks"
        return trial

    results = await connectivity.probe_all(
        chosen,
        concurrency=settings.connectivity_concurrency,
        timeout=settings.connectivity_timeout,
    )
    reachable = connectivity.filter_by_connectivity(
        chosen, results, max_latency_ms=settings.max_latency_ms
    )
    trial.reachable = len(reachable)
    if not reachable:
        return trial

    xray_path = find_xray_binary(settings.xray_path)
    if xray_path is None:
        trial.error = "xray not found; the verification half was skipped"
        return trial

    validator = GeminiValidator(
        xray_path=xray_path,
        api_key=settings.gemini_api_key,
        pool_size=settings.gemini_pool_size,
        timeout=settings.gemini_timeout,
        api_confirm_limit=0,  # screening should not spend the run's API quota
    )
    verdicts = await validator.validate_all(reachable)
    trial.verified = sum(1 for v in verdicts if v.passed)
    for verdict in verdicts:
        if verdict.passed and verdict.geo and verdict.geo.country_code:
            code = verdict.geo.country_code.lower()
            trial.countries[code] = trial.countries.get(code, 0) + 1

    return trial


def verdict_text(trial: Trial) -> str:
    """A recommendation, phrased as the evidence rather than a rule."""
    if trial.error and not trial.reachable:
        return f"Could not evaluate: {trial.error}"
    conversion = trial.conversion
    if conversion is None:
        return "Nothing reachable in the sample. Not worth adding."
    if conversion < 0.03:
        return (
            f"{conversion:.1%} of reachable nodes verified. Every list dropped so "
            "far looked like this — reachable, and useless."
        )
    novelty = trial.novelty
    if novelty is not None and novelty < 0.1:
        return (
            f"{conversion:.1%} conversion, but {1 - novelty:.0%} of it is already "
            "covered by the configured sources. Little to gain."
        )
    return f"{conversion:.1%} of reachable nodes verified. Comparable to the sources kept."
