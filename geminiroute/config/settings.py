"""Configuration.

    sources.toml — content, edited in PRs and reviewed like code
    environment  — secrets and per-run knobs, injected by the workflow

GEMINI_API_KEY is optional: without it the pipeline still validates
reachability, which keeps the repo forkable by anyone.
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from geminiroute.core.models import Source

DEFAULT_SOURCES_FILE = "sources.toml"


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, "") or default)
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, "") or default)
    except ValueError:
        return default


@dataclass
class Settings:
    output_dir: Path = Path("dist")
    database_path: Path = Path("data/geminiroute.db")

    connectivity_concurrency: int = 100
    connectivity_timeout: float = 8.0
    dns_concurrency: int = 64
    dns_timeout: float = 3.0
    # Cap on nodes entering validation at all. 0 means no cap; useful for
    # quick local runs against a full source list.
    max_nodes: int = 0
    max_latency_ms: float = 3000.0

    # Measured against a real source list: ~8.8s of work per node, ~5% pass.
    # pool 20 / timeout 12 puts 1200 candidates at roughly 9 minutes, which
    # leaves real headroom under the workflow's 50-minute job limit.
    gemini_pool_size: int = 20
    gemini_timeout: float = 12.0
    gemini_api_key: str | None = None
    # API calls per run. Free-tier quota is a few hundred a day and this runs
    # hourly, so the key confirms winners rather than testing everything.
    gemini_api_confirm_limit: int = 10
    xray_path: str | None = None

    # Cap on how many survivors reach the expensive stage, so an unexpected
    # influx of sources cannot push the run past the job time limit.
    max_gemini_candidates: int = 1600

    history_retention_days: int = 90
    log_level: str = "INFO"

    sources: list[Source] = field(default_factory=list)

    @classmethod
    def from_env(cls, sources_file: str | Path = DEFAULT_SOURCES_FILE) -> Settings:
        return cls(
            output_dir=Path(os.environ.get("GR_OUTPUT_DIR", "dist")),
            database_path=Path(os.environ.get("GR_DATABASE_PATH", "data/geminiroute.db")),
            connectivity_concurrency=_env_int("GR_CONNECTIVITY_CONCURRENCY", 100),
            connectivity_timeout=_env_float("GR_CONNECTIVITY_TIMEOUT", 8.0),
            dns_concurrency=_env_int("GR_DNS_CONCURRENCY", 64),
            dns_timeout=_env_float("GR_DNS_TIMEOUT", 3.0),
            max_nodes=_env_int("GR_MAX_NODES", 0),
            max_latency_ms=_env_float("GR_MAX_LATENCY_MS", 3000.0),
            gemini_pool_size=_env_int("GR_GEMINI_POOL_SIZE", 20),
            gemini_timeout=_env_float("GR_GEMINI_TIMEOUT", 12.0),
            gemini_api_key=os.environ.get("GEMINI_API_KEY") or None,
            gemini_api_confirm_limit=_env_int("GR_GEMINI_API_CONFIRM_LIMIT", 10),
            xray_path=os.environ.get("XRAY_PATH") or None,
            max_gemini_candidates=_env_int("GR_MAX_GEMINI_CANDIDATES", 1600),
            history_retention_days=_env_int("GR_HISTORY_RETENTION_DAYS", 90),
            log_level=os.environ.get("GR_LOG_LEVEL", "INFO"),
            sources=load_sources(sources_file),
        )


def load_sources(path: str | Path) -> list[Source]:
    """Read sources.toml. A missing file yields no sources, not an error."""
    file_path = Path(path)
    if not file_path.exists():
        return []

    with file_path.open("rb") as handle:
        data = tomllib.load(handle)

    sources: list[Source] = []
    for entry in data.get("source", []):
        if not isinstance(entry, dict):
            continue
        name = str(entry.get("name", "")).strip()
        url = str(entry.get("url", "")).strip()
        if not name or not url:
            continue
        sources.append(
            Source(
                name=name,
                type=str(entry.get("type", "raw")).strip().lower(),
                url=url,
                enabled=bool(entry.get("enabled", True)),
            )
        )
    return sources
