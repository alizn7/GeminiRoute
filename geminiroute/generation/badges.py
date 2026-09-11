"""Assets the README embeds so its numbers stay true without being edited.

A README with numbers typed into it is a document: the moment a run changes
them it is wrong, and nobody notices. These are regenerated every run and
served from the published branch, so the page reports the last run rather than
the last time someone remembered to update it.

  badge*.json — shields.io endpoint format, rendered by shields into a badge
  card.svg    — the funnel, drawn once per run, embedded as an image
"""

from __future__ import annotations

import html
import json
from typing import Any

CARD_WIDTH = 880
CARD_HEIGHT = 260

GROUND = "#0e1a24"
PANEL = "#15242f"
RULE = "#22384a"
INK = "#dce8f0"
MUTED = "#7793a8"
SIGNAL = "#e8a33d"
PASS = "#5bc08c"

FONT = (
    "ui-sans-serif, system-ui, -apple-system, 'Segoe UI', Roboto, "
    "'Helvetica Neue', Arial, sans-serif"
)

STAGES = [
    ("collected", "collected"),
    ("after_dedup", "unique"),
    ("after_pre_validation", "plausible"),
    ("after_connectivity", "reachable"),
    ("after_gemini", "verified"),
]


def _badge(label: str, message: str, colour: str) -> str:
    return json.dumps(
        {
            "schemaVersion": 1,
            "label": label,
            "message": message,
            "color": colour,
            "labelColor": "1f2d3a",
            "style": "flat-square",
        }
    )


def verified_badge(stats: dict[str, Any]) -> str:
    funnel = stats.get("funnel", {})
    count = funnel.get("after_gemini", 0) if isinstance(funnel, dict) else 0
    return _badge("verified routes", f"{count:,}", PASS.lstrip("#"))


def countries_badge(stats: dict[str, Any]) -> str:
    countries = stats.get("nodes_by_country", {})
    total = len(countries) if isinstance(countries, dict) else 0
    return _badge("exit countries", str(total), SIGNAL.lstrip("#"))


def success_badge(stats: dict[str, Any]) -> str:
    rate = stats.get("gemini_success_rate")
    text = f"{float(rate):.0%}" if isinstance(rate, (int, float)) else "unknown"
    return _badge("verified of tested", text, SIGNAL.lstrip("#"))


# One badge per published subscription, so the README can show how many routes
# are in each one right now instead of a number someone typed once.
SUBSCRIPTION_BADGES = {
    "best": ("best", PASS),
    "gemini": ("all verified", SIGNAL),
    "fast": ("fast", SIGNAL),
    "all": ("everything", MUTED),
}


def subscription_badges(file_counts: dict[str, int]) -> dict[str, str]:
    """`{filename: shields endpoint json}` for each subscription file."""
    return {
        name: _badge(label, f"{file_counts.get(name, 0):,} routes", colour.lstrip("#"))
        for name, (label, colour) in SUBSCRIPTION_BADGES.items()
    }


def stats_card(stats: dict[str, Any]) -> str:
    """The funnel as an SVG, for the README to embed.

    Text is drawn rather than laid out, so it needs no font file and renders
    the same wherever GitHub proxies it.
    """
    funnel = stats.get("funnel", {})
    funnel = funnel if isinstance(funnel, dict) else {}
    # Built with a loop rather than filtered in place: reassigning a name from a
    # comprehension over itself keeps the original, wider type, so the values
    # stay `int | None` no matter what the filter says.
    values: list[tuple[str, int]] = []
    for key, label in STAGES:
        value = funnel.get(key)
        if isinstance(value, int):
            values.append((label, value))
    top = max((v for _, v in values), default=0) or 1

    generated = html.escape(str(stats.get("generated_at", ""))[:16].replace("T", " "))
    verified = funnel.get("after_gemini", 0)
    collected = funnel.get("collected", 0)

    bar_left = 150
    bar_width = 560
    rows = []
    y = 92
    for label, count in values:
        width = max(round(count / top * bar_width), 2)
        colour = PASS if label == "verified" else RULE
        rows.append(
            f'<text x="130" y="{y + 13}" fill="{MUTED}" font-size="13" '
            f'text-anchor="end">{label}</text>'
            f'<rect x="{bar_left}" y="{y}" width="{bar_width}" height="20" rx="2" '
            f'fill="{PANEL}"/>'
            f'<rect x="{bar_left}" y="{y}" width="{width}" height="20" rx="2" '
            f'fill="{colour}"/>'
            f'<text x="{bar_left + bar_width + 14}" y="{y + 14}" '
            f'fill="{PASS if label == "verified" else INK}" font-size="13">'
            f"{count:,}</text>"
        )
        y += 28

    body = "".join(rows)
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{CARD_WIDTH}" \
height="{CARD_HEIGHT}" viewBox="0 0 {CARD_WIDTH} {CARD_HEIGHT}" \
role="img" aria-label="{verified} of {collected} routes verified in the last run">
<style>text {{ font-family: {FONT}; }}</style>
<rect width="{CARD_WIDTH}" height="{CARD_HEIGHT}" rx="6" fill="{GROUND}"/>
<text x="32" y="42" fill="{INK}" font-size="18" font-weight="600">\
What happened to the {collected:,} configs collected last run</text>
<text x="32" y="66" fill="{MUTED}" font-size="13">rebuilt hourly &#183; \
{generated} UTC</text>
{body}
</svg>
"""
