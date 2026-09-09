"""Deduplication by fingerprint.

First occurrence wins for every field except `source_names`, which accumulates
so source quality can be measured later.
"""

from __future__ import annotations

from dataclasses import replace

from geminiroute.core.models import Node


def deduplicate(nodes: list[Node]) -> list[Node]:
    """Collapse nodes sharing a fingerprint, merging their source lists.

    Input order is preserved, which keeps runs comparable to each other.
    """
    merged: dict[str, Node] = {}

    for node in nodes:
        existing = merged.get(node.fingerprint)
        if existing is None:
            merged[node.fingerprint] = replace(node, source_names=list(node.source_names))
            continue

        for source_name in node.source_names:
            if source_name not in existing.source_names:
                existing.source_names.append(source_name)

        # Take a remark from a later duplicate only if the first copy had none.
        if not existing.remark and node.remark:
            merged[node.fingerprint] = replace(
                existing, remark=node.remark, source_names=existing.source_names
            )

    return list(merged.values())


def duplicate_count(nodes: list[Node]) -> int:
    """How many lines were redundant. Measures source overlap."""
    return len(nodes) - len({n.fingerprint for n in nodes})
