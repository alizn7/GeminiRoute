"""Screening a candidate source.

Four sources have been added and removed on the strength of a full hourly run
each. The verdict logic here is what that experience produced, so it is tested
against the numbers those runs actually returned.
"""

from geminiroute.orchestration.trial import Trial, verdict_text


def trial(**kwargs: object) -> Trial:
    defaults: dict[str, object] = {"url": "https://example.net/sub"}
    defaults.update(kwargs)
    return Trial(**defaults)  # type: ignore[arg-type]


def test_conversion_is_verified_over_reachable() -> None:
    """Not over collected: a list can be huge and reachable and still useless,
    which is exactly the failure this is built to catch."""
    assert trial(reachable=100, verified=28).conversion == 0.28


def test_conversion_is_unknown_without_reachable_nodes() -> None:
    assert trial(reachable=0, verified=0).conversion is None


def test_novelty_measures_what_the_current_sources_miss() -> None:
    assert trial(unique=1000, already_covered=250).novelty == 0.75


def test_novelty_is_unknown_for_an_empty_source() -> None:
    assert trial(unique=0).novelty is None


def test_the_sources_that_were_kept_read_as_comparable() -> None:
    # barry-far-vless: 479 reachable, 245 verified.
    verdict = verdict_text(trial(reachable=479, verified=245, unique=1823))
    assert "Comparable" in verdict


def test_the_sources_that_were_dropped_read_as_useless() -> None:
    # coldwater Sub7 and Sub10: 428 reachable between them, none verified.
    verdict = verdict_text(trial(reachable=428, verified=0, unique=1200))
    assert "useless" in verdict


def test_a_barely_converting_source_is_still_rejected() -> None:
    # morpheusadam best.txt: 1102 reachable, 7 verified.
    assert "useless" in verdict_text(trial(reachable=1102, verified=7, unique=1922))


def test_a_good_but_redundant_source_is_called_out() -> None:
    """A list that only repeats what is configured adds run time and nothing."""
    verdict = verdict_text(trial(reachable=100, verified=40, unique=500,
                                 already_covered=480))
    assert "already covered" in verdict


def test_nothing_reachable_is_reported_plainly() -> None:
    assert "Not worth adding" in verdict_text(trial(reachable=0))


def test_a_collection_failure_is_reported_as_such() -> None:
    verdict = verdict_text(trial(error="HTTP Error 404: Not Found"))
    assert "Could not evaluate" in verdict
    assert "404" in verdict
