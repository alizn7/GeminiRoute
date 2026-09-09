"""Storage interface. The pipeline talks to this, never to sqlite3 directly.

`reliability` returns (passed, total) counts rather than a stored average, so
the window can change without a migration or a backfill.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from geminiroute.core.models import Node, Score, Source, ValidationResult


class NodeRepository(ABC):
    @abstractmethod
    def upsert_nodes(self, nodes: list[Node]) -> None:
        """Insert new nodes; update the mutable fields of existing ones."""

    @abstractmethod
    def get_node(self, fingerprint: str) -> Node | None: ...

    @abstractmethod
    def list_nodes(self) -> list[Node]: ...

    @abstractmethod
    def record_results(self, results: list[ValidationResult]) -> None:
        """Append to validation history. Append-only by design."""

    @abstractmethod
    def reliability(self, fingerprint: str, days: int = 30) -> tuple[int, int]:
        """(passed_checks, total_checks) over the window, computed on read."""

    @abstractmethod
    def save_scores(self, scores: list[Score]) -> None: ...

    @abstractmethod
    def upsert_sources(self, sources: list[Source]) -> None: ...

    @abstractmethod
    def prune_history(self, older_than_days: int) -> int:
        """Delete old history rows, returning how many were removed."""

    @abstractmethod
    def close(self) -> None: ...
