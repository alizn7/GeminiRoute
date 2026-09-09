"""GeoIP via ip-api.com's batch endpoint.

Batched because the free tier allows 45 requests per minute but each request
carries up to 100 IPs. Geo data is decoration, not a filter: failures are
swallowed and the pipeline continues.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request

from geminiroute.core.models import GeoInfo
from geminiroute.observability.logging import get_logger

log = get_logger(__name__)

ENDPOINT = "http://ip-api.com/batch"
FIELDS = "status,country,city,as,isp,query"
BATCH_SIZE = 100
TIMEOUT = 15.0


def _chunks(items: list[str], size: int) -> list[list[str]]:
    return [items[i : i + size] for i in range(0, len(items), size)]


def lookup(ips: list[str]) -> dict[str, GeoInfo]:
    """Map IP -> GeoInfo. Missing or failed lookups are simply absent."""
    unique = sorted({ip for ip in ips if ip})
    resolved: dict[str, GeoInfo] = {}

    for chunk in _chunks(unique, BATCH_SIZE):
        body = json.dumps([{"query": ip, "fields": FIELDS} for ip in chunk]).encode()
        request = urllib.request.Request(
            ENDPOINT, data=body, headers={"Content-Type": "application/json"}
        )
        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT) as response:  # noqa: S310
                entries = json.loads(response.read())
        except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
            log.warning("geo_batch_failed", size=len(chunk), error=str(exc))
            continue

        if not isinstance(entries, list):
            continue
        for entry in entries:
            if not isinstance(entry, dict) or entry.get("status") != "success":
                continue
            ip = entry.get("query")
            if not ip:
                continue
            resolved[ip] = GeoInfo(
                country=entry.get("country"),
                city=entry.get("city"),
                asn=entry.get("as"),
                isp=entry.get("isp"),
            )

    log.info("geo_lookup_done", requested=len(unique), resolved=len(resolved))
    return resolved


def country_code(country: str | None) -> str:
    """A filesystem-safe slug for per-country subscription files."""
    if not country:
        return "unknown"
    return "".join(c for c in country.lower().replace(" ", "-") if c.isalnum() or c == "-")
