"""The alert log, and the retention policy that keeps it honest."""

import logging
import os
import sqlite3
import threading
import time
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS alerts (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    at            REAL    NOT NULL,
    camera_id     TEXT    NOT NULL,
    event_type    TEXT    NOT NULL,
    severity      TEXT    NOT NULL,
    detail        TEXT    NOT NULL DEFAULT '',
    confidence    REAL    NOT NULL DEFAULT 0,
    snapshot      TEXT,
    acknowledged  INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_alerts_at ON alerts (at DESC);
CREATE INDEX IF NOT EXISTS idx_alerts_camera ON alerts (camera_id, at DESC);
"""


@dataclass(frozen=True)
class AlertRecord:
    id: int
    at: float
    camera_id: str
    event_type: str
    severity: str
    detail: str
    confidence: float
    snapshot: str
    acknowledged: bool

    @classmethod
    def from_row(cls, row):
        return cls(
            id=row["id"],
            at=row["at"],
            camera_id=row["camera_id"],
            event_type=row["event_type"],
            severity=row["severity"],
            detail=row["detail"],
            confidence=row["confidence"],
            snapshot=row["snapshot"] or "",
            acknowledged=bool(row["acknowledged"]),
        )

    @property
    def timestamp(self):
        return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(self.at))


class EventStore:
    def __init__(self, config, root=None):
        root = Path(root) if root else Path.cwd()
        self.db_path = root / config.db_path
        self.snapshot_dir = root / config.snapshot_dir
        self.save_snapshots = config.save_snapshots
        self.retention_days = config.retention_days
        self._write_lock = threading.Lock()

        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        if self.save_snapshots:
            self.snapshot_dir.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as conn, conn:
            conn.executescript(SCHEMA)

    def _connect(self):
        """Always wrap in closing(): sqlite3's context manager commits but does
        not close, which leaks handles and locks the file on Windows."""
        conn = sqlite3.connect(str(self.db_path), timeout=10)
        conn.row_factory = sqlite3.Row
        return conn

    def record(self, camera_id, event_type, severity, detail, confidence, at=None,
               snapshot_bytes=None):
        at = time.time() if at is None else at
        snapshot_name = ""

        if snapshot_bytes and self.save_snapshots:
            snapshot_name = "{}_{}_{}.jpg".format(
                camera_id, event_type, time.strftime("%Y%m%d-%H%M%S", time.localtime(at))
            )
            try:
                (self.snapshot_dir / snapshot_name).write_bytes(snapshot_bytes)
            except OSError:
                log.exception("could not write snapshot %s", snapshot_name)
                snapshot_name = ""

        with self._write_lock, closing(self._connect()) as conn, conn:
            cursor = conn.execute(
                "INSERT INTO alerts (at, camera_id, event_type, severity, detail,"
                " confidence, snapshot) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (at, camera_id, event_type, severity, detail, confidence, snapshot_name),
            )
            return cursor.lastrowid

    def acknowledge(self, alert_id):
        with self._write_lock, closing(self._connect()) as conn, conn:
            conn.execute("UPDATE alerts SET acknowledged = 1 WHERE id = ?", (alert_id,))

    def recent(self, limit=50, camera_id=None, severity=None):
        query = "SELECT * FROM alerts"
        clauses, params = [], []
        if camera_id:
            clauses.append("camera_id = ?")
            params.append(camera_id)
        if severity:
            clauses.append("severity = ?")
            params.append(severity)
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY at DESC LIMIT ?"
        params.append(int(limit))

        with closing(self._connect()) as conn:
            return [AlertRecord.from_row(r) for r in conn.execute(query, params)]

    def counts_by_severity(self):
        with closing(self._connect()) as conn:
            rows = conn.execute(
                "SELECT severity, COUNT(*) AS n FROM alerts GROUP BY severity"
            )
            return {r["severity"]: r["n"] for r in rows}

    def counts_by_event(self):
        with closing(self._connect()) as conn:
            rows = conn.execute(
                "SELECT event_type, COUNT(*) AS n FROM alerts"
                " GROUP BY event_type ORDER BY n DESC"
            )
            return {r["event_type"]: r["n"] for r in rows}

    def unacknowledged_count(self):
        with closing(self._connect()) as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS n FROM alerts WHERE acknowledged = 0"
            ).fetchone()
            return row["n"]

    def purge_expired(self, now=None):
        """Drop alerts past the retention window. Files go before rows, so an
        interrupted purge leaves an orphaned row rather than an orphaned image."""
        if self.retention_days <= 0:
            return 0
        now = time.time() if now is None else now
        cutoff = now - self.retention_days * 86400

        with self._write_lock, closing(self._connect()) as conn, conn:
            rows = conn.execute(
                "SELECT id, snapshot FROM alerts WHERE at < ?", (cutoff,)
            ).fetchall()
            for row in rows:
                if row["snapshot"]:
                    try:
                        os.remove(self.snapshot_dir / row["snapshot"])
                    except FileNotFoundError:
                        pass
                    except OSError:
                        log.exception("could not delete snapshot %s", row["snapshot"])
            conn.execute("DELETE FROM alerts WHERE at < ?", (cutoff,))
            return len(rows)
