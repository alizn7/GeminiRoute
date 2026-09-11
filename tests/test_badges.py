"""Live README assets.

A README with numbers typed into it goes stale silently. These are regenerated
every run, so what matters is that they stay valid when a run produces
something unusual — nothing verified, a missing field, a malformed payload.
"""

import json
import xml.etree.ElementTree as ET

from geminiroute.generation.badges import (
    countries_badge,
    stats_card,
    success_badge,
    verified_badge,
)

STATS = {
    "generated_at": "2026-09-11T05:45:36.714102+00:00",
    "funnel": {
        "collected": 7127, "after_dedup": 3884, "after_pre_validation": 3225,
        "after_connectivity": 1516, "after_gemini": 383,
    },
    "gemini_success_rate": 0.3192,
    "nodes_by_country": {"us": 84, "nl": 63, "de": 60},
}


def test_badges_follow_the_shields_endpoint_schema() -> None:
    for payload in (verified_badge(STATS), countries_badge(STATS), success_badge(STATS)):
        badge = json.loads(payload)
        assert badge["schemaVersion"] == 1
        assert badge["label"] and badge["message"]


def test_verified_badge_reports_the_last_stage() -> None:
    assert json.loads(verified_badge(STATS))["message"] == "383"


def test_countries_badge_counts_distinct_exits() -> None:
    assert json.loads(countries_badge(STATS))["message"] == "3"


def test_success_badge_is_a_percentage() -> None:
    assert json.loads(success_badge(STATS))["message"] == "32%"


def test_badges_survive_an_empty_run() -> None:
    empty = {"funnel": {}, "nodes_by_country": {}}
    assert json.loads(verified_badge(empty))["message"] == "0"
    assert json.loads(countries_badge(empty))["message"] == "0"
    assert json.loads(success_badge(empty))["message"] == "unknown"


def test_badges_survive_missing_keys() -> None:
    assert json.loads(verified_badge({}))["message"] == "0"
    assert json.loads(success_badge({}))["message"] == "unknown"


def test_card_is_valid_svg() -> None:
    ET.fromstring(stats_card(STATS))


def test_card_bars_descend_with_the_counts() -> None:
    root = ET.fromstring(stats_card(STATS))
    ns = "{http://www.w3.org/2000/svg}"
    # Odd-indexed rects are the fills drawn over each track.
    fills = [float(r.get("width")) for r in root.iter(f"{ns}rect")][3::2]
    assert fills == sorted(fills, reverse=True)


def test_card_labels_every_stage() -> None:
    card = stats_card(STATS)
    for label in ("collected", "unique", "plausible", "reachable", "verified"):
        assert f">{label}</text>" in card


def test_card_carries_an_accessible_label() -> None:
    root = ET.fromstring(stats_card(STATS))
    assert "383" in (root.get("aria-label") or "")


def test_card_survives_an_empty_run() -> None:
    ET.fromstring(stats_card({"funnel": {}}))


def test_card_needs_no_font_file() -> None:
    """GitHub proxies this image; anything it cannot fetch will not render."""
    assert "@font-face" not in stats_card(STATS)
    assert "http" not in stats_card(STATS).replace("http://www.w3.org/2000/svg", "")
