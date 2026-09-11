"""The published status page.

Checked structurally rather than visually: the page is served to people on
censored networks, so what matters is that it needs nothing external, escapes
what it renders, and degrades to something readable when a run produced little.
"""

import re

from geminiroute.generation.dashboard import render

STATS = {
    "generated_at": "2026-09-11T05:45:36Z",
    "funnel": {
        "collected": 7127, "after_dedup": 3884, "after_pre_validation": 3225,
        "after_connectivity": 1516, "after_gemini": 383,
    },
    "gemini_success_rate": 0.3192,
    "average_latency_ms": 209.87,
    "nodes_by_country": {"us": 84, "nl": 63, "de": 60, "fr": 31},
    "sources": [
        {"name": "good", "contributed": 2100, "reachable": 900,
         "gemini_ok": 250, "yield": 0.119},
        {"name": "weak", "contributed": 600, "reachable": 120,
         "gemini_ok": 2, "yield": 0.0033},
    ],
}


def test_page_makes_no_external_requests() -> None:
    """Readers are on networks where a font CDN may simply not resolve, and a
    status page that half-loads is worse than a plain one."""
    assert re.findall(r'(?:src|href)="https?://', render(STATS)) == []


def test_funnel_bars_descend_with_the_counts() -> None:
    widths = [float(w) for w in re.findall(r'class="fill" style="width:([\d.]+)%', render(STATS))]
    assert widths == sorted(widths, reverse=True)
    assert widths[0] == 100.0


def test_every_funnel_stage_is_shown() -> None:
    html = render(STATS)
    for label in ("collected", "unique", "plausible", "reachable", "verified"):
        assert f"<span>{label}</span>" in html


def test_counts_are_rendered_with_separators() -> None:
    assert "7,127" in render(STATS)


def test_subscription_files_carry_their_counts() -> None:
    html = render(STATS, {"best": 30, "gemini": 383, "fast": 51, "all": 1600})
    assert "383 routes" in html
    assert 'data-file="sub/best.txt"' in html


def test_country_codes_become_flags() -> None:
    assert "🇺🇸" in render(STATS)
    assert "🇳🇱" in render(STATS)


def test_source_yield_is_shown_as_a_percentage() -> None:
    html = render(STATS)
    assert "11.9%" in html
    assert "0.3%" in html


def test_account_gate_is_explained() -> None:
    """Every reader hits this: a working route still refused because of the
    country on their Google account."""
    html = render(STATS)
    assert "private window" in html
    assert "web app" in html


def test_empty_run_still_renders() -> None:
    html = render({"generated_at": "x", "funnel": {}, "nodes_by_country": {}, "sources": []})
    assert "<title>GeminiRoute</title>" in html
    assert "No verified routes" in html


def test_missing_keys_do_not_crash() -> None:
    assert "<title>GeminiRoute</title>" in render({})


def test_wrong_types_are_tolerated() -> None:
    """stats.json is written by this project, but the renderer should not be
    the thing that breaks if a field is ever malformed."""
    html = render({"funnel": "nonsense", "nodes_by_country": None, "sources": "nope"})
    assert "<title>GeminiRoute</title>" in html


def test_country_codes_are_escaped() -> None:
    html = render({**STATS, "nodes_by_country": {"<script>": 3}})
    assert "<script>alert" not in html
    assert "&lt;script&gt;" in html


def test_source_names_are_escaped() -> None:
    html = render({**STATS, "sources": [
        {"name": "<img src=x>", "contributed": 1, "reachable": 1,
         "gemini_ok": 1, "yield": 1.0}]})
    assert "<img src=x>" not in html
    assert "&lt;img" in html


def test_tags_are_balanced() -> None:
    html = render(STATS)
    for tag in ("html", "body", "main", "section", "table"):
        assert html.count(f"<{tag}") == html.count(f"</{tag}>")


def test_accessibility_floor() -> None:
    html = render(STATS)
    assert 'name="viewport"' in html
    assert "prefers-reduced-motion" in html
    assert "focus-visible" in html
