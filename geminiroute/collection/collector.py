"""Fetching raw config text from sources.

Built on urllib rather than httpx: a few dozen requests per run, and staying
dependency-free means it can be tested against a local server.

    raw     — one URL whose body is a config list (plain or base64)
    github  — a GitHub contents-API directory; every file inside is fetched
"""

from __future__ import annotations

import base64
import binascii
import json
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from dataclasses import dataclass

from geminiroute.core.models import Source
from geminiroute.observability.logging import get_logger

log = get_logger(__name__)

USER_AGENT = "GeminiRoute/0.1 (+https://github.com/)"
DEFAULT_TIMEOUT = 20.0
MAX_BODY_BYTES = 8 * 1024 * 1024


@dataclass(frozen=True)
class CollectionResult:
    """What one source produced during one run."""

    source: Source
    lines: list[str]
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None


def fetch_text(url: str, timeout: float = DEFAULT_TIMEOUT) -> str:
    """GET a URL and return its body as text. Raises on failure."""
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
        # urlopen is typed as Any in typeshed; pin the type here so the
        # decoded return value is a real str rather than Any.
        body: bytes = response.read(MAX_BODY_BYTES)
    return body.decode("utf-8", errors="replace")


def maybe_decode_base64(body: str) -> str:
    """Decode a base64 subscription body, if that is what it is.

    The result is only accepted when it looks like configs: a plain-text list
    can also be base64-decodable, into noise.
    """
    candidate = "".join(body.split())
    if not candidate:
        return body
    try:
        decoded = base64.b64decode(candidate + "=" * (-len(candidate) % 4)).decode("utf-8")
    except (binascii.Error, UnicodeDecodeError, ValueError):
        return body
    return decoded if "://" in decoded else body


def split_lines(body: str) -> list[str]:
    return [line.strip() for line in body.splitlines() if line.strip()]


class Collector(ABC):
    """One implementation per source type."""

    type: str

    @abstractmethod
    def collect(self, source: Source) -> list[str]:
        """Return raw config lines. May raise; the runner turns that into an error."""


class RawCollector(Collector):
    """A single URL whose body is a list of configs, plain or base64."""

    type = "raw"

    def collect(self, source: Source) -> list[str]:
        return split_lines(maybe_decode_base64(fetch_text(source.url)))


class GithubCollector(Collector):
    """A GitHub repo directory; every file in it is fetched and concatenated.

    `source.url` is a GitHub contents-API URL, e.g.
    https://api.github.com/repos/<owner>/<repo>/contents/<path>
    """

    type = "github"

    def collect(self, source: Source) -> list[str]:
        listing = json.loads(fetch_text(source.url))
        if not isinstance(listing, list):
            raise ValueError("expected a directory listing")

        lines: list[str] = []
        for entry in listing:
            if entry.get("type") != "file":
                continue
            download_url = entry.get("download_url")
            if not download_url:
                continue
            try:
                lines.extend(split_lines(maybe_decode_base64(fetch_text(download_url))))
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                # One bad file must not lose the whole directory.
                log.warning("github_file_failed", url=download_url, error=str(exc))
        return lines


_COLLECTORS: tuple[Collector, ...] = (RawCollector(), GithubCollector())
_BY_TYPE: dict[str, Collector] = {c.type: c for c in _COLLECTORS}


def get_collector(source_type: str) -> Collector | None:
    return _BY_TYPE.get(source_type.strip().lower())


def collect_source(source: Source) -> CollectionResult:
    """Collect one source, converting any failure into a result, never a raise."""
    collector = get_collector(source.type)
    if collector is None:
        return CollectionResult(source, [], error=f"unknown source type: {source.type}")
    try:
        lines = collector.collect(source)
    except (urllib.error.URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError) as exc:
        log.warning("source_failed", source=source.name, error=str(exc))
        return CollectionResult(source, [], error=str(exc))
    log.info("source_collected", source=source.name, lines=len(lines))
    return CollectionResult(source, lines)


def collect_all(sources: list[Source]) -> list[CollectionResult]:
    """Collect every enabled source. A dead source degrades the run."""
    return [collect_source(s) for s in sources if s.enabled]
