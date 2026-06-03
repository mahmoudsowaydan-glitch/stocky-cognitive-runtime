import json
import sqlite3
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from ..contracts.execution_contract import (
    Capability,
    DeadLetterEvent,
    ExecutionProposal,
    ExecutionResult,
    HostEvent,
    PolicyDecision,
)


@dataclass
class QueueStats:
    total_events: int = 0
    processed: int = 0
    failed: int = 0
    dead_lettered: int = 0
    queue_depth: int = 0
    last_event_id: str = ""
    last_event_at: Optional[float] = None


class EventQueue:
    MAX_DEAD_LETTER = 1000

    def __init__(self, db_path: str = "stocky_queue.db", max_retries: int = 3):
        self._db_path = db_path
        self._max_retries = max_retries
        self._conn: Optional[sqlite3.Connection] = None
        self._stats = QueueStats()
        self._closed = False

    # ──────────────────────────────────────────────
    #  Lifecycle
    # ──────────────────────────────────────────────

    def open(self) -> None:
        self._conn = sqlite3.connect(self._db_path)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._create_schema()
        self._refresh_stats()

    def close(self) -> None:
        if self._conn:
            try:
                self._conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                self._conn.execute("PRAGMA journal_mode=DELETE")
                self._conn.commit()
            except Exception:
                pass
            self._conn.close()
            self._conn = None
            self._closed = True

    # ──────────────────────────────────────────────
    #  Schema
    # ──────────────────────────────────────────────

    def _create_schema(self) -> None:
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS events (
                event_id      TEXT PRIMARY KEY,
                session_id    TEXT NOT NULL,
                event_type    TEXT NOT NULL,
                payload       TEXT NOT NULL,
                status        TEXT NOT NULL DEFAULT 'pending',
                retry_count   INTEGER NOT NULL DEFAULT 0,
                created_at    REAL NOT NULL,
                started_at    REAL,
                finished_at   REAL,
                result        TEXT,
                error         TEXT,
                sequence_no   INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS dead_letter (
                event_id      TEXT PRIMARY KEY,
                original_event TEXT NOT NULL,
                failure_reason TEXT NOT NULL,
                retry_count   INTEGER NOT NULL,
                created_at    REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS decisions (
                decision_id   TEXT PRIMARY KEY,
                proposal_id   TEXT NOT NULL,
                session_id    TEXT NOT NULL,
                verdict       TEXT NOT NULL,
                reason        TEXT,
                risk_level    TEXT,
                rule_triggered TEXT,
                confidence    REAL,
                created_at    REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS results (
                execution_id  TEXT PRIMARY KEY,
                proposal_id   TEXT NOT NULL,
                session_id    TEXT NOT NULL,
                status        TEXT NOT NULL,
                output        TEXT,
                error         TEXT,
                started_at    REAL NOT NULL,
                finished_at   REAL NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_events_status ON events(status);
            CREATE INDEX IF NOT EXISTS idx_events_session ON events(session_id);
            CREATE INDEX IF NOT EXISTS idx_events_sequence ON events(sequence_no);
        """)
        self._conn.commit()

    # ──────────────────────────────────────────────
    #  Event Lifecycle
    # ──────────────────────────────────────────────

    def push(self, event: HostEvent) -> HostEvent:
        now = time.time()
        seq = self._next_sequence()
        self._conn.execute(
            """INSERT INTO events
               (event_id, session_id, event_type, payload, status, retry_count, created_at, sequence_no)
               VALUES (?, ?, ?, ?, 'pending', 0, ?, ?)""",
            (event.event_id, event.session_id, event.source,
             json.dumps(event.payload), now, seq),
        )
        self._conn.commit()
        self._stats.total_events += 1
        self._stats.last_event_id = event.event_id
        self._stats.last_event_at = now
        return event

    def pop(self) -> Optional[HostEvent]:
        row = self._conn.execute(
            """SELECT * FROM events
               WHERE status = 'pending'
               ORDER BY sequence_no ASC
               LIMIT 1"""
        ).fetchone()
        if row is None:
            return None

        event_id = row["event_id"]
        self._conn.execute(
            "UPDATE events SET status = 'processing', started_at = ? WHERE event_id = ?",
            (time.time(), event_id),
        )
        self._conn.commit()

        return HostEvent(
            event_id=row["event_id"],
            session_id=row["session_id"],
            timestamp=row["created_at"],
            source=row["event_type"],
            payload=json.loads(row["payload"]),
        )

    def ack(self, event_id: str, result: ExecutionResult) -> None:
        self._conn.execute(
            """UPDATE events
               SET status = ?, finished_at = ?, result = ?
               WHERE event_id = ?""",
            ("completed", time.time(), json.dumps({
                "status": result.status,
                "output": result.output,
                "error": result.error,
            }), event_id),
        )
        self._insert_result(result)
        self._conn.commit()
        self._stats.processed += 1

    def nack(self, event_id: str, error: str, proposal: Optional[ExecutionProposal] = None) -> None:
        row = self._conn.execute(
            "SELECT retry_count, payload FROM events WHERE event_id = ?",
            (event_id,),
        ).fetchone()

        if row is None:
            return

        retries = row["retry_count"] + 1

        if retries >= self._max_retries:
            self._move_to_dlq(event_id, row["payload"], error, retries)
            self._conn.execute(
                "UPDATE events SET status = 'dead', error = ?, retry_count = ? WHERE event_id = ?",
                (error, retries, event_id),
            )
            self._stats.dead_lettered += 1
        else:
            self._conn.execute(
                "UPDATE events SET status = 'pending', retry_count = ? WHERE event_id = ?",
                (retries, event_id),
            )
            self._stats.failed += 1
        self._conn.commit()

    # ──────────────────────────────────────────────
    #  DLQ
    # ──────────────────────────────────────────────

    def _move_to_dlq(self, event_id: str, payload: str, reason: str, count: int) -> None:
        self._conn.execute(
            """INSERT OR IGNORE INTO dead_letter
               (event_id, original_event, failure_reason, retry_count, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (event_id, payload, reason, count, time.time()),
        )
        self._prune_dead_letter()

    def _prune_dead_letter(self) -> None:
        count = self._conn.execute("SELECT COUNT(*) as cnt FROM dead_letter").fetchone()["cnt"]
        if count > self.MAX_DEAD_LETTER:
            excess = count - self.MAX_DEAD_LETTER
            self._conn.execute(
                """DELETE FROM dead_letter WHERE rowid IN (
                    SELECT rowid FROM dead_letter ORDER BY created_at ASC LIMIT ?
                )""",
                (excess,),
            )
            self._conn.commit()

    def dead_letter_events(self) -> list[DeadLetterEvent]:
        rows = self._conn.execute(
            "SELECT * FROM dead_letter ORDER BY created_at DESC"
        ).fetchall()
        return [
            DeadLetterEvent(
                event_id=r["event_id"],
                original_event=json.loads(r["original_event"]),
                failure_reason=r["failure_reason"],
                retry_count=r["retry_count"],
            )
            for r in rows
        ]

    def replay_dead_letter(self, event_id: str) -> Optional[HostEvent]:
        row = self._conn.execute(
            "SELECT * FROM dead_letter WHERE event_id = ?",
            (event_id,),
        ).fetchone()
        if row is None:
            return None

        payload = json.loads(row["original_event"]) if isinstance(row["original_event"], str) else row["original_event"]
        ev = HostEvent(
            event_id=str(uuid.uuid4()),
            session_id=payload.get("session_id", ""),
            timestamp=time.time(),
            source="replay",
            payload=payload,
        )
        self.push(ev)
        self._conn.execute("DELETE FROM dead_letter WHERE event_id = ?", (event_id,))
        self._conn.commit()
        return ev

    # ──────────────────────────────────────────────
    #  Replay
    # ──────────────────────────────────────────────

    def get_by_session(self, session_id: str) -> list[HostEvent]:
        rows = self._conn.execute(
            "SELECT * FROM events WHERE session_id = ? ORDER BY sequence_no ASC",
            (session_id,),
        ).fetchall()
        return [
            HostEvent(event_id=r["event_id"], session_id=r["session_id"],
                      timestamp=r["created_at"], source=r["event_type"],
                      payload=json.loads(r["payload"]))
            for r in rows
        ]

    def get_by_range(self, start_seq: int, end_seq: int) -> list[HostEvent]:
        rows = self._conn.execute(
            "SELECT * FROM events WHERE sequence_no BETWEEN ? AND ? ORDER BY sequence_no ASC",
            (start_seq, end_seq),
        ).fetchall()
        return [
            HostEvent(event_id=r["event_id"], session_id=r["session_id"],
                      timestamp=r["created_at"], source=r["event_type"],
                      payload=json.loads(r["payload"]))
            for r in rows
        ]

    def replay(self, session_id: str) -> list[HostEvent]:
        return self.get_by_session(session_id)

    def count_by_status(self) -> dict[str, int]:
        rows = self._conn.execute(
            "SELECT status, COUNT(*) as cnt FROM events GROUP BY status"
        ).fetchall()
        return {r["status"]: r["cnt"] for r in rows}

    # ──────────────────────────────────────────────
    #  Decisions
    # ──────────────────────────────────────────────

    def record_decision(self, decision: PolicyDecision) -> None:
        self._conn.execute(
            """INSERT INTO decisions
               (decision_id, proposal_id, session_id, verdict, reason, risk_level, rule_triggered, confidence, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (decision.decision_id, decision.proposal_id, decision.session_id,
             decision.verdict, decision.reason, decision.risk_level,
             decision.rule_triggered, decision.confidence, time.time()),
        )
        self._conn.commit()

    # ──────────────────────────────────────────────
    #  Internal
    # ──────────────────────────────────────────────

    def _insert_result(self, result: ExecutionResult) -> None:
        self._conn.execute(
            """INSERT OR IGNORE INTO results
               (execution_id, proposal_id, session_id, status, output, error, started_at, finished_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (result.execution_id, result.proposal_id, result.session_id,
             result.status, json.dumps(result.output) if result.output else None,
             result.error, result.started_at, result.finished_at),
        )

    def _next_sequence(self) -> int:
        row = self._conn.execute("SELECT COALESCE(MAX(sequence_no), 0) + 1 AS seq FROM events").fetchone()
        return row["seq"]

    def _refresh_stats(self) -> None:
        counts = self.count_by_status()
        self._stats.processed = counts.get("completed", 0)
        self._stats.failed = counts.get("pending", 0)  # pending = not yet processed
        self._stats.queue_depth = counts.get("pending", 0)
        dlq_count = self._conn.execute("SELECT COUNT(*) as cnt FROM dead_letter").fetchone()["cnt"]
        self._stats.dead_lettered = dlq_count

    @property
    def stats(self) -> QueueStats:
        return self._stats

    @property
    def queue_depth(self) -> int:
        if not self._conn:
            return 0
        row = self._conn.execute("SELECT COUNT(*) as cnt FROM events WHERE status = 'pending'").fetchone()
        return row["cnt"] if row else 0
