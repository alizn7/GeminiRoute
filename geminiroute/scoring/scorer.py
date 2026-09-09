"""Scoring: latency 30%, gemini 30%, reliability 25%, connection 15%.

Each sub-score is normalised to 0..1 first, so changing a weight cannot change
the scale of the result. Pure arithmetic — no I/O, no clock.
"""

from __future__ import annotations

from dataclasses import dataclass

from geminiroute.core.models import LatencyResult, Score

WEIGHT_LATENCY = 0.30
WEIGHT_GEMINI = 0.30
WEIGHT_RELIABILITY = 0.25
WEIGHT_CONNECTION = 0.15

# Fixed thresholds, not the observed range: normalising over the range would
# make scores incomparable between runs, since the range changes hourly.
LATENCY_EXCELLENT_MS = 150.0
LATENCY_USELESS_MS = 3000.0


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def latency_score(latency: LatencyResult | None) -> float:
    if latency is None or latency.total_ms is None:
        return 0.0
    total = latency.total_ms
    if total <= LATENCY_EXCELLENT_MS:
        return 1.0
    if total >= LATENCY_USELESS_MS:
        return 0.0
    span = LATENCY_USELESS_MS - LATENCY_EXCELLENT_MS
    return _clamp(1.0 - (total - LATENCY_EXCELLENT_MS) / span)


def gemini_score(passed: bool) -> float:
    """Binary by design: a node either reaches the API or it does not."""
    return 1.0 if passed else 0.0


def reliability_score(passed_checks: int, total_checks: int) -> float:
    """Share of historical checks this node passed.

    No history scores 0.5: unknown, not good or bad. New nodes start mid-pack
    and earn their position over the next few runs.
    """
    if total_checks <= 0:
        return 0.5
    return _clamp(passed_checks / total_checks)


def connection_score(latency: LatencyResult | None) -> float:
    """Handshake quality, separate from total latency.

    Acceptable total latency with a slow TLS handshake usually means an
    overloaded server that will degrade under real use.
    """
    if latency is None:
        return 0.0
    connect = latency.connect_ms
    if connect is None:
        return 0.0

    score = _clamp(1.0 - connect / 1000.0)
    if latency.tls_ms is not None:
        score = (score + _clamp(1.0 - latency.tls_ms / 1500.0)) / 2
    return score


@dataclass(frozen=True)
class ScoreInputs:
    node_fingerprint: str
    latency: LatencyResult | None
    gemini_passed: bool
    passed_checks: int = 0
    total_checks: int = 0


def score_node(inputs: ScoreInputs) -> Score:
    latency = latency_score(inputs.latency)
    gemini = gemini_score(inputs.gemini_passed)
    reliability = reliability_score(inputs.passed_checks, inputs.total_checks)
    connection = connection_score(inputs.latency)

    final = (
        latency * WEIGHT_LATENCY
        + gemini * WEIGHT_GEMINI
        + reliability * WEIGHT_RELIABILITY
        + connection * WEIGHT_CONNECTION
    )

    return Score(
        node_fingerprint=inputs.node_fingerprint,
        latency_score=round(latency, 4),
        gemini_score=round(gemini, 4),
        reliability_score=round(reliability, 4),
        connection_score=round(connection, 4),
        final_score=round(final, 4),
    )


def score_all(inputs: list[ScoreInputs]) -> list[Score]:
    return [score_node(i) for i in inputs]
