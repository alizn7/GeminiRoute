"""SQLite repository.

The runner is ephemeral, so the .db file must be carried between runs (this
project keeps it on the gh-pages branch). Without that, reliability history
resets every hour and every node sits at the "unknown" score forever.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

from geminiroute.core.enums import NodeStatus, ProtocolType, ValidationStage
from geminiroute.core.models import Node, Score, Source, ValidationResult
from geminiroute.storage.base import NodeRepository

SCHEMA = """
CREATE TABLE IF NOT EXISTS nodes (
    fingerprint       TEXT PRIMARY KEY,
    protocol          TEXT NOT NULL,
    address           TEXT NOT NULL,
    port              INTEGER NOT NULL,
    transport         TEXT,
    security          TEXT,
    credential        TEXT,
    params_json       TEXT,
    raw               TEXT,
    remark            TEXT,
    status            TEXT NOT NULL,
    country           TEXT,
    city              TEXT,
    asn               TEXT,
    isp               TEXT,
    final_score       REAL,
    consecutive_fails INTEGER DEFAULT 0,
    first_seen_at     TEXT NOT NULL,
    last_checked_at   TEXT,
    next_retry_at     TEXT
);

CREATE TABLE IF NOT EXISTS sources (
    name              TEXT PRIMARY KEY,
    type              TEXT NOT NULL,
    url               TEXT NOT NULL,
    enabled           INTEGER DEFAULT 1,
    nodes_contributed INTEGER DEFAULT 0,
    nodes_valid       INTEGER DEFAULT 0,
    nodes_gemini_ok   INTEGER DEFAULT 0,
    last_collected_at TEXT
);

CREATE TABLE IF NOT EXISTS node_sources (
    node_fingerprint TEXT NOT NULL,
    source_name      TEXT NOT NULL,
    PRIMARY KEY (node_fingerprint, source_name)
);

CREATE TABLE IF NOT EXISTS validation_history (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    node_fingerprint TEXT NOT NULL,
    stage            TEXT NOT NULL,
    passed           INTEGER NOT NULL,
    latency_ms       REAL,
    error            TEXT,
    checked_at       TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_validation_history_node_time
    ON validation_history (node_fingerprint, checked_at);
"""


def _now() -> str:
    return datetime.now(UTC).isoformat()


class SqliteRepository(NodeRepository):
    def __init__(self, path: str | Path) -> None:
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(self.path)
        self._connection.row_factory = sqlite3.Row
        # WAL: reads must not block the long write batches at end of run.
        self._connection.execute("PRAGMA journal_mode=WAL")
        self._connection.executescript(SCHEMA)
        self._connection.commit()

    # ----------------------------------------------------------- nodes --

    def upsert_nodes(self, nodes: list[Node]) -> None:
        now = _now()
        with self._connection:
            for node in nodes:
                self._connection.execute(
                    """
                    INSERT INTO nodes (
                        fingerprint, protocol, address, port, transport, security,
                        credential, params_json, raw, remark, status, first_seen_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(fingerprint) DO UPDATE SET
                        remark = excluded.remark,
                        raw    = excluded.raw,
                        status = excluded.status
                    """,
                    (
                        node.fingerprint,
                        node.protocol.value,
                        node.address,
                        node.port,
                        node.transport,
                        node.security,
                        node.credential,
                        json.dumps(node.params),
                        node.raw,
                        node.remark,
                        node.status.value,
                        now,
                    ),
                )
                for source_name in node.source_names:
                    self._connection.execute(
                        "INSERT OR IGNORE INTO node_sources VALUES (?, ?)",
                        (node.fingerprint, source_name),
                    )

    def _row_to_node(self, row: sqlite3.Row) -> Node:
        return Node(
            protocol=ProtocolType(row["protocol"]),
            address=row["address"],
            port=row["port"],
            transport=row["transport"] or "",
            security=row["security"] or "",
            credential=row["credential"] or "",
            params=json.loads(row["params_json"] or "{}"),
            remark=row["remark"] or "",
            status=NodeStatus(row["status"]),
            fingerprint=row["fingerprint"],
            raw=row["raw"] or "",
        )

    def get_node(self, fingerprint: str) -> Node | None:
        row = self._connection.execute(
            "SELECT * FROM nodes WHERE fingerprint = ?", (fingerprint,)
        ).fetchone()
        return self._row_to_node(row) if row else None

    def list_nodes(self) -> list[Node]:
        rows = self._connection.execute("SELECT * FROM nodes").fetchall()
        return [self._row_to_node(r) for r in rows]

    def update_status(
        self,
        fingerprint: str,
        status: NodeStatus,
        consecutive_fails: int,
        next_retry_at: datetime | None,
    ) -> None:
        with self._connection:
            self._connection.execute(
                """
                UPDATE nodes
                   SET status = ?, consecutive_fails = ?, next_retry_at = ?,
                       last_checked_at = ?
                 WHERE fingerprint = ?
                """,
                (
                    status.value,
                    consecutive_fails,
                    next_retry_at.isoformat() if next_retry_at else None,
                    _now(),
                    fingerprint,
                ),
            )

    def get_consecutive_fails(self, fingerprint: str) -> int:
        row = self._connection.execute(
            "SELECT consecutive_fails FROM nodes WHERE fingerprint = ?", (fingerprint,)
        ).fetchone()
        return int(row["consecutive_fails"] or 0) if row else 0

    def set_geo(self, fingerprint: str, country: str | None, city: str | None,
                asn: str | None, isp: str | None) -> None:
        with self._connection:
            self._connection.execute(
                "UPDATE nodes SET country=?, city=?, asn=?, isp=? WHERE fingerprint=?",
                (country, city, asn, isp, fingerprint),
            )

    # --------------------------------------------------------- history --

    def record_results(self, results: list[ValidationResult]) -> None:
        with self._connection:
            self._connection.executemany(
                """
                INSERT INTO validation_history
                    (node_fingerprint, stage, passed, latency_ms, error, checked_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        r.node_fingerprint,
                        r.stage.value if isinstance(r.stage, ValidationStage) else str(r.stage),
                        1 if r.passed else 0,
                        r.latency.total_ms if r.latency else None,
                        r.error,
                        r.checked_at.isoformat(),
                    )
                    for r in results
                ],
            )

    def reliability(self, fingerprint: str, days: int = 30) -> tuple[int, int]:
        since = (datetime.now(UTC) - timedelta(days=days)).isoformat()
        row = self._connection.execute(
            """
            SELECT COALESCE(SUM(passed), 0) AS passed, COUNT(*) AS total
              FROM validation_history
             WHERE node_fingerprint = ? AND checked_at >= ? AND stage = ?
            """,
            (fingerprint, since, ValidationStage.GEMINI.value),
        ).fetchone()
        return int(row["passed"]), int(row["total"])

    def error_histogram(self, stage: str, limit: int = 20) -> list[tuple[str, int]]:
        """Most common failure reasons for a stage, most recent run first.

        A summary line says how many nodes failed; this says why, which is the
        difference between "the proxy stage is broken" and a fix.
        """
        rows = self._connection.execute(
            """
            SELECT COALESCE(error, "(none)") AS reason, COUNT(*) AS n
              FROM validation_history
             WHERE stage = ? AND passed = 0
          GROUP BY reason
          ORDER BY n DESC
             LIMIT ?
            """,
            (stage, limit),
        ).fetchall()
        return [(str(r["reason"]), int(r["n"])) for r in rows]

    def prune_history(self, older_than_days: int) -> int:
        cutoff = (datetime.now(UTC) - timedelta(days=older_than_days)).isoformat()
        with self._connection:
            cursor = self._connection.execute(
                "DELETE FROM validation_history WHERE checked_at < ?", (cutoff,)
            )
        return cursor.rowcount

    # ---------------------------------------------------------- scores --

    def save_scores(self, scores: list[Score]) -> None:
        with self._connection:
            self._connection.executemany(
                "UPDATE nodes SET final_score = ? WHERE fingerprint = ?",
                [(s.final_score, s.node_fingerprint) for s in scores],
            )

    # --------------------------------------------------------- sources --

    def upsert_sources(self, sources: list[Source]) -> None:
        with self._connection:
            self._connection.executemany(
                """
                INSERT INTO sources (name, type, url, enabled)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(name) DO UPDATE SET
                    type = excluded.type, url = excluded.url, enabled = excluded.enabled
                """,
                [(s.name, s.type, s.url, 1 if s.enabled else 0) for s in sources],
            )

    def record_source_stats(
        self, name: str, contributed: int, valid: int, gemini_ok: int
    ) -> None:
        with self._connection:
            self._connection.execute(
                """
                UPDATE sources
                   SET nodes_contributed = ?, nodes_valid = ?, nodes_gemini_ok = ?,
                       last_collected_at = ?
                 WHERE name = ?
                """,
                (contributed, valid, gemini_ok, _now(), name),
            )

    def close(self) -> None:
        self._connection.close()
