import gc
import os
import shutil
import tempfile
import time

import pytest

from cognitive_runtime.substrate.event_queue import EventQueue, QueueStats
from cognitive_runtime.contracts.execution_contract import (
    Capability,
    HostEvent,
    ExecutionProposal,
    ExecutionResult,
    PolicyDecision,
)


@pytest.fixture
def tmp_db():
    d = tempfile.mkdtemp()
    yield os.path.join(d, "test.db")
    for _ in range(3):
        try:
            shutil.rmtree(d)
        except (PermissionError, FileNotFoundError):
            gc.collect()


@pytest.fixture
def event_queue(tmp_db):
    q = EventQueue(db_path=tmp_db)
    q.open()
    yield q
    q.close()


def _make_host_event(event_id="e1", session_id="s1", source="test"):
    return HostEvent(
        event_id=event_id,
        session_id=session_id,
        timestamp=time.time(),
        source=source,
        payload={"key": event_id},
    )


def _make_result(event_id="e1", status="SUCCESS"):
    return ExecutionResult(
        execution_id=f"ex-{event_id}",
        proposal_id=f"p-{event_id}",
        session_id="s1",
        status=status,
        output={"data": "ok"} if status == "SUCCESS" else None,
        error=None if status == "SUCCESS" else "err",
        started_at=time.time(),
        finished_at=time.time() + 1,
    )


def _make_proposal(event_id="e1"):
    return ExecutionProposal(
        proposal_id=f"p-{event_id}",
        session_id="s1",
        event_id=event_id,
        action="test",
        target="/tmp/test",
        params={},
        required_capabilities=[Capability.FILESYSTEM_READ],
        confidence=0.8,
        risk_score=0.1,
        metadata={},
    )


class TestQueueStats:
    def test_defaults(self):
        s = QueueStats()
        assert s.total_events == 0
        assert s.processed == 0
        assert s.failed == 0
        assert s.dead_lettered == 0
        assert s.queue_depth == 0
        assert s.last_event_id == ""
        assert s.last_event_at is None


class TestEventQueue:
    def test_open_creates_schema(self, tmp_db):
        q = EventQueue(db_path=tmp_db)
        q.open()
        tables = q._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        names = [r["name"] for r in tables]
        assert "events" in names
        assert "dead_letter" in names
        assert "decisions" in names
        assert "results" in names
        q.close()

    def test_close_sets_closed(self, tmp_db):
        q = EventQueue(db_path=tmp_db)
        q.open()
        assert q._closed is False
        q.close()
        assert q._closed is True

    def test_push_stores_event(self, tmp_db):
        q = EventQueue(db_path=tmp_db)
        q.open()
        ev = _make_host_event("e1")
        q.push(ev)
        row = q._conn.execute(
            "SELECT * FROM events WHERE event_id = ?", ("e1",)
        ).fetchone()
        assert row is not None
        assert row["event_id"] == "e1"
        assert row["session_id"] == "s1"
        assert row["event_type"] == "test"
        assert row["status"] == "pending"
        q.close()

    def test_push_increments_total_events(self, tmp_db):
        q = EventQueue(db_path=tmp_db)
        q.open()
        q.push(_make_host_event("e1"))
        assert q._stats.total_events == 1
        q.push(_make_host_event("e2"))
        assert q._stats.total_events == 2
        q.close()

    def test_push_sets_last_event_id(self, tmp_db):
        q = EventQueue(db_path=tmp_db)
        q.open()
        q.push(_make_host_event("e1"))
        assert q._stats.last_event_id == "e1"
        q.push(_make_host_event("e2"))
        assert q._stats.last_event_id == "e2"
        q.close()

    def test_pop_returns_events_in_fifo_order(self, tmp_db):
        q = EventQueue(db_path=tmp_db)
        q.open()
        q.push(_make_host_event("e1"))
        q.push(_make_host_event("e2"))
        q.push(_make_host_event("e3"))

        popped1 = q.pop()
        assert popped1 is not None
        assert popped1.event_id == "e1"

        popped2 = q.pop()
        assert popped2 is not None
        assert popped2.event_id == "e2"

        popped3 = q.pop()
        assert popped3 is not None
        assert popped3.event_id == "e3"
        q.close()

    def test_pop_marks_as_processing(self, tmp_db):
        q = EventQueue(db_path=tmp_db)
        q.open()
        q.push(_make_host_event("e1"))
        q.pop()
        row = q._conn.execute(
            "SELECT status FROM events WHERE event_id = ?", ("e1",)
        ).fetchone()
        assert row["status"] == "processing"
        q.close()

    def test_pop_returns_none_when_empty(self, tmp_db):
        q = EventQueue(db_path=tmp_db)
        q.open()
        assert q.pop() is None
        q.close()

    def test_ack_marks_completed(self, tmp_db):
        q = EventQueue(db_path=tmp_db)
        q.open()
        q.push(_make_host_event("e1"))
        q.pop()
        q.ack("e1", _make_result("e1"))
        row = q._conn.execute(
            "SELECT status FROM events WHERE event_id = ?", ("e1",)
        ).fetchone()
        assert row["status"] == "completed"
        q.close()

    def test_ack_updates_stats(self, tmp_db):
        q = EventQueue(db_path=tmp_db)
        q.open()
        q.push(_make_host_event("e1"))
        q.pop()
        assert q._stats.processed == 0
        q.ack("e1", _make_result("e1"))
        assert q._stats.processed == 1
        q.close()

    def test_nack_max_retries_moves_to_dead_letter(self, tmp_db):
        q = EventQueue(db_path=tmp_db, max_retries=2)
        q.open()
        q.push(_make_host_event("e1"))
        prop = _make_proposal("e1")

        q.pop()
        q.nack("e1", "error1", prop)
        assert q._stats.failed == 1

        q.pop()
        q.nack("e1", "error2", prop)
        assert q._stats.dead_lettered == 1

        dle = q.dead_letter_events()
        assert len(dle) == 1
        assert dle[0].event_id == "e1"
        assert dle[0].failure_reason == "error2"
        q.close()

    def test_nack_fewer_retries_resets_to_pending(self, tmp_db):
        q = EventQueue(db_path=tmp_db, max_retries=3)
        q.open()
        q.push(_make_host_event("e1"))
        prop = _make_proposal("e1")

        q.pop()
        q.nack("e1", "transient", prop)

        row = q._conn.execute(
            "SELECT status, retry_count FROM events WHERE event_id = ?", ("e1",)
        ).fetchone()
        assert row["status"] == "pending"
        assert row["retry_count"] == 1

        q.pop()
        q.close()

    def test_dead_letter_events_returns_list(self, tmp_db):
        q = EventQueue(db_path=tmp_db, max_retries=1)
        q.open()
        q.push(_make_host_event("e1"))
        prop = _make_proposal("e1")
        q.pop()
        q.nack("e1", "fatal", prop)

        dle = q.dead_letter_events()
        assert len(dle) == 1
        assert isinstance(dle[0].original_event, dict)
        q.close()

    def test_dead_letter_events_empty(self, tmp_db):
        q = EventQueue(db_path=tmp_db)
        q.open()
        assert q.dead_letter_events() == []
        q.close()

    def test_replay_dead_letter_requeues_and_removes(self, tmp_db):
        q = EventQueue(db_path=tmp_db, max_retries=1)
        q.open()
        q.push(_make_host_event("e1"))
        prop = _make_proposal("e1")
        q.pop()
        q.nack("e1", "fatal", prop)

        ev = q.replay_dead_letter("e1")
        assert ev is not None
        assert ev.event_id != "e1"
        assert ev.source == "replay"

        assert q.dead_letter_events() == []
        assert q.queue_depth == 1
        q.close()

    def test_replay_dead_letter_returns_none_for_missing(self, tmp_db):
        q = EventQueue(db_path=tmp_db)
        q.open()
        assert q.replay_dead_letter("nonexistent") is None
        q.close()

    def test_record_decision_stores_in_decisions_table(self, tmp_db):
        q = EventQueue(db_path=tmp_db)
        q.open()
        dec = PolicyDecision(
            decision_id="d1",
            proposal_id="p1",
            session_id="s1",
            verdict="ALLOW",
            reason="ok",
            risk_level="low",
            rule_triggered=None,
            confidence=0.9,
        )
        q.record_decision(dec)
        row = q._conn.execute(
            "SELECT * FROM decisions WHERE decision_id = ?", ("d1",)
        ).fetchone()
        assert row is not None
        assert row["verdict"] == "ALLOW"
        q.close()

    def test_get_by_session_returns_events(self, tmp_db):
        q = EventQueue(db_path=tmp_db)
        q.open()
        q.push(_make_host_event("e1", session_id="s1"))
        q.push(_make_host_event("e2", session_id="s1"))
        q.push(_make_host_event("e3", session_id="s2"))

        events = q.get_by_session("s1")
        assert len(events) == 2
        assert events[0].event_id == "e1"
        assert events[1].event_id == "e2"
        q.close()

    def test_get_by_session_empty(self, tmp_db):
        q = EventQueue(db_path=tmp_db)
        q.open()
        assert q.get_by_session("nonexistent") == []
        q.close()

    def test_get_by_range_returns_events(self, tmp_db):
        q = EventQueue(db_path=tmp_db)
        q.open()
        q.push(_make_host_event("e1"))
        q.push(_make_host_event("e2"))
        q.push(_make_host_event("e3"))

        events = q.get_by_range(1, 2)
        assert len(events) == 2
        assert events[0].event_id == "e1"
        assert events[1].event_id == "e2"
        q.close()

    def test_get_by_range_empty(self, tmp_db):
        q = EventQueue(db_path=tmp_db)
        q.open()
        assert q.get_by_range(99, 101) == []
        q.close()

    def test_replay_delegates_to_get_by_session(self, tmp_db):
        q = EventQueue(db_path=tmp_db)
        q.open()
        q.push(_make_host_event("e1", session_id="s1"))
        q.push(_make_host_event("e2", session_id="s1"))

        r = q.replay("s1")
        assert len(r) == 2
        assert r[0].event_id == "e1"
        assert r[1].event_id == "e2"
        q.close()

    def test_count_by_status(self, tmp_db):
        q = EventQueue(db_path=tmp_db)
        q.open()
        q.push(_make_host_event("e1"))
        q.push(_make_host_event("e2"))
        q.pop()
        q.ack("e1", _make_result("e1"))
        q.push(_make_host_event("e3"))

        counts = q.count_by_status()
        assert counts.get("completed") == 1
        # e2 was never popped so it's still pending; e3 was just pushed
        assert counts.get("pending") == 2
        q.close()

    def test_stats_property(self, tmp_db):
        q = EventQueue(db_path=tmp_db)
        q.open()
        q.push(_make_host_event("e1"))
        q.pop()
        q.ack("e1", _make_result("e1"))

        s = q.stats
        assert isinstance(s, QueueStats)
        assert s.total_events == 1
        q.close()

    def test_queue_depth_property(self, tmp_db):
        q = EventQueue(db_path=tmp_db)
        q.open()
        assert q.queue_depth == 0
        q.push(_make_host_event("e1"))
        assert q.queue_depth == 1
        q.push(_make_host_event("e2"))
        assert q.queue_depth == 2
        q.pop()
        assert q.queue_depth == 1
        q.close()

    def test_multiple_pushes_preserve_order(self, tmp_db):
        q = EventQueue(db_path=tmp_db)
        q.open()
        q.push(_make_host_event("e1"))
        q.push(_make_host_event("e2"))
        q.push(_make_host_event("e3"))

        rows = q._conn.execute(
            "SELECT event_id FROM events ORDER BY sequence_no ASC"
        ).fetchall()
        assert [r["event_id"] for r in rows] == ["e1", "e2", "e3"]
        q.close()

    def test_queue_depth_when_closed(self, tmp_db):
        q = EventQueue(db_path=tmp_db)
        assert q.queue_depth == 0

    def test_push_then_pop_then_push_again(self, tmp_db):
        q = EventQueue(db_path=tmp_db)
        q.open()
        q.push(_make_host_event("e1"))
        q.pop()
        q.push(_make_host_event("e2"))
        popped = q.pop()
        assert popped is not None
        assert popped.event_id == "e2"
        q.close()

    def test_nack_nonexistent_event(self, tmp_db):
        q = EventQueue(db_path=tmp_db)
        q.open()
        q.nack("nonexistent", "error")
        q.close()

    def test_ack_with_failed_result_updates_status(self, tmp_db):
        q = EventQueue(db_path=tmp_db)
        q.open()
        q.push(_make_host_event("e1"))
        q.pop()
        q.ack("e1", _make_result("e1", status="FAILED"))
        row = q._conn.execute(
            "SELECT status, result FROM events WHERE event_id = ?", ("e1",)
        ).fetchone()
        assert row["status"] == "completed"
        import json
        assert json.loads(row["result"])["status"] == "FAILED"
        q.close()
