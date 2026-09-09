from geminiroute.core.models import LatencyResult
from geminiroute.scoring.scorer import (
    ScoreInputs,
    connection_score,
    latency_score,
    reliability_score,
    score_node,
)


def latency(total: float, connect: float = 100.0, tls: float | None = None) -> LatencyResult:
    return LatencyResult(dns_ms=5.0, connect_ms=connect, tls_ms=tls, total_ms=total)


def test_latency_score_saturates_at_both_ends() -> None:
    assert latency_score(latency(50)) == 1.0
    assert latency_score(latency(5000)) == 0.0


def test_latency_score_is_monotonic() -> None:
    assert latency_score(latency(200)) > latency_score(latency(800))


def test_missing_latency_scores_zero_not_an_error() -> None:
    assert latency_score(None) == 0.0


def test_unknown_reliability_sits_mid_pack() -> None:
    """New nodes are unknown, not bad. Either extreme would be a claim the
    data does not support."""
    assert reliability_score(0, 0) == 0.5


def test_reliability_is_a_pass_ratio() -> None:
    assert reliability_score(9, 10) == 0.9
    assert reliability_score(0, 10) == 0.0


def test_connection_score_penalises_a_slow_tls_handshake() -> None:
    fast = connection_score(latency(300, connect=50, tls=50))
    slow = connection_score(latency(300, connect=50, tls=1400))
    assert fast > slow


def test_weights_sum_to_one_for_a_perfect_node() -> None:
    perfect = score_node(
        ScoreInputs("fp", latency(50, connect=0, tls=0), gemini_passed=True,
                    passed_checks=10, total_checks=10)
    )
    assert perfect.final_score == 1.0


def test_worst_possible_node_scores_zero() -> None:
    worst = score_node(
        ScoreInputs("fp", None, gemini_passed=False, passed_checks=0, total_checks=10)
    )
    assert worst.final_score == 0.0


def test_failing_gemini_costs_exactly_its_weight() -> None:
    common = dict(passed_checks=10, total_checks=10)
    with_gemini = score_node(ScoreInputs("fp", latency(50, 0, 0), True, **common))
    without = score_node(ScoreInputs("fp", latency(50, 0, 0), False, **common))
    assert round(with_gemini.final_score - without.final_score, 4) == 0.30


def test_a_fast_verified_node_outranks_a_slow_one() -> None:
    fast = score_node(ScoreInputs("a", latency(120, 40, 40), True))
    slow = score_node(ScoreInputs("b", latency(2500, 900, 1200), True))
    assert fast.final_score > slow.final_score
