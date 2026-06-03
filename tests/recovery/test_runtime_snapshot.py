"""Tests for cognitive_runtime/recovery/runtime_snapshot.py."""

import json
import time
from dataclasses import asdict

import pytest

from cognitive_runtime.recovery.runtime_snapshot import RuntimeSnapshot
from cognitive_runtime.contracts.execution_trace import ExecutionTrace
from cognitive_runtime.contracts.frozen.schema_version import FROZEN_SCHEMA_VERSION
from cognitive_runtime.contracts.frozen.schema_version import FROZEN_SCHEMA_VERSION, fingerprint


# ── Mock helpers ──


class MockState:
    def __init__(self, status="stopped", health="healthy", tep=10):
        self.status = status
        self.health_status = health
        self.total_events_processed = tep

    def snapshot(self):
        return {
            "status": self.status,
            "health_status": self.health_status,
            "total_events_processed": self.total_events_processed,
        }


class MockGuard:
    def __init__(self, gradient="HIGH"):
        self._current_gradient = gradient


class MockConfidence:
    def __init__(self, history=None, gradient="HIGH"):
        self._score_history = history or [0.9, 0.85, 0.95]
        self._guard = MockGuard(gradient)


class MockGovernance:
    def __init__(self, history=None):
        self._score_history = history or [0.8, 0.75, 0.9]


class MockStability:
    def __init__(self, history=None):
        self._score_history = history or [0.7, 0.72, 0.68]


class MockQueueStats:
    def __init__(self, depth=5):
        self.queue_depth = depth


class MockQueue:
    def __init__(self, depth=5):
        self.stats = MockQueueStats(depth)


class MockRuntimeLoop:
    def __init__(self, traces=None, state=None, governance=None,
                 confidence=None, stability=None, queue=None):
        self._traces = traces or []
        self._state = state or MockState()
        self._governance = governance or MockGovernance()
        self._confidence = confidence or MockConfidence()
        self._stability = stability or MockStability()
        self._queue = queue or MockQueue()
        self.state = self._state


def make_traces(n):
    return [
        ExecutionTrace(
            event_id=f"e{i}", session_id="s1", sequence_no=i,
            correlation_id=f"c{i}",
            preflight_valid=True, preflight_reason="preflight_passed",
            risk_score=0.1,
            p4_verdict="ALLOW", p4_reason="ok", p4_risk_level="low",
            execution_status="SUCCESS",
            final_status="P4_ALLOW",
        )
        for i in range(n)
    ]


# ── Dataclass defaults ──


def test_minimal_construction():
    snap = RuntimeSnapshot(
        snapshot_id="cp_1",
        created_at=1000.0,
        runtime_state_snapshot={},
        trace_count=0,
        traces=[],
    )
    assert snap.snapshot_id == "cp_1"
    assert snap.created_at == 1000.0
    assert snap.trace_count == 0


def test_default_sub_system_state():
    snap = RuntimeSnapshot(
        snapshot_id="cp_1", created_at=1.0,
        runtime_state_snapshot={}, trace_count=0, traces=[],
    )
    assert snap.governance_score_history == []
    assert snap.confidence_score_history == []
    assert snap.confidence_gradient == "HIGH"
    assert snap.stability_score_history == []


def test_default_queue_stats():
    snap = RuntimeSnapshot(
        snapshot_id="cp_1", created_at=1.0,
        runtime_state_snapshot={}, trace_count=0, traces=[],
    )
    assert snap.queue_depth == 0
    assert snap.total_events_processed == 0


def test_default_schema():
    snap = RuntimeSnapshot(
        snapshot_id="cp_1", created_at=1.0,
        runtime_state_snapshot={}, trace_count=0, traces=[],
    )
    assert snap.schema_version == str(FROZEN_SCHEMA_VERSION)
    assert snap.schema_fingerprint == ""


def test_default_metadata():
    snap = RuntimeSnapshot(
        snapshot_id="cp_1", created_at=1.0,
        runtime_state_snapshot={}, trace_count=0, traces=[],
    )
    assert snap.cycle_count == 0
    assert snap.recovery_mode_enabled is False


def test_all_fields_provided():
    snap = RuntimeSnapshot(
        snapshot_id="cp_x", created_at=500.0,
        runtime_state_snapshot={"status": "running"},
        trace_count=2,
        traces=[{"event_id": "e1", "final_status": "P4_ALLOW"}],
        governance_score_history=[0.8, 0.9],
        confidence_score_history=[0.7, 0.85],
        confidence_gradient="LOW",
        stability_score_history=[0.6, 0.65],
        queue_depth=3, total_events_processed=10,
        schema_version=str(FROZEN_SCHEMA_VERSION), schema_fingerprint="abc123",
        cycle_count=5, recovery_mode_enabled=True,
    )
    assert snap.governance_score_history == [0.8, 0.9]
    assert snap.confidence_gradient == "LOW"
    assert snap.queue_depth == 3
    assert snap.recovery_mode_enabled is True


# ── capture() ──


def test_capture_basic(sample_traces_10):
    traces = sample_traces_10
    state = MockState(status="running", tep=10)
    gov = MockGovernance([0.8, 0.9])
    conf = MockConfidence([0.7, 0.85], "LOW")
    stab = MockStability([0.6, 0.65])
    queue = MockQueue(depth=3)

    loop = MockRuntimeLoop(
        traces=traces, state=state,
        governance=gov, confidence=conf,
        stability=stab, queue=queue,
    )
    snap = RuntimeSnapshot.capture(loop)

    assert snap.trace_count == 10
    assert len(snap.traces) == 10
    assert snap.traces[0]["event_id"] == "e0"
    assert snap.traces[-1]["event_id"] == "e9"
    assert snap.runtime_state_snapshot["status"] == "running"
    assert snap.governance_score_history == [0.8, 0.9]
    assert snap.confidence_score_history == [0.7, 0.85]
    assert snap.confidence_gradient == "LOW"
    assert snap.stability_score_history == [0.6, 0.65]
    assert snap.queue_depth == 3
    assert snap.total_events_processed == 10


def test_capture_empty_loop():
    loop = MockRuntimeLoop(traces=[])
    snap = RuntimeSnapshot.capture(loop)
    assert snap.trace_count == 0
    assert snap.traces == []


def test_capture_missing_attributes_graceful():
    loop = object()
    snap = RuntimeSnapshot.capture(loop)
    assert snap.trace_count == 0
    assert snap.traces == []
    assert snap.runtime_state_snapshot == {}
    assert snap.governance_score_history == []


def test_capture_partial_attributes():
    class PartialLoop:
        pass
    loop = PartialLoop()
    loop._traces = make_traces(2)
    snap = RuntimeSnapshot.capture(loop)
    assert snap.trace_count == 2
    assert snap.runtime_state_snapshot == {}


def test_capture_snapshot_id():
    loop = MockRuntimeLoop()
    snap = RuntimeSnapshot.capture(loop, snapshot_id="my_cp")
    assert snap.snapshot_id == "my_cp"


def test_capture_auto_snapshot_id():
    loop = MockRuntimeLoop()
    before = time.time()
    snap = RuntimeSnapshot.capture(loop)
    after = time.time()
    assert snap.snapshot_id.startswith("cp_")
    cp_time = float(snap.snapshot_id[3:])
    assert before <= cp_time <= after


def test_capture_default_gradient():
    loop = MockRuntimeLoop()
    snap = RuntimeSnapshot.capture(loop)
    assert snap.confidence_gradient == "HIGH"


def test_capture_schema_fields():
    loop = MockRuntimeLoop()
    snap = RuntimeSnapshot.capture(loop)
    assert snap.schema_version == str(FROZEN_SCHEMA_VERSION)
    assert snap.schema_fingerprint == fingerprint("RuntimeSnapshot")


def test_capture_cycle_count_equals_trace_count():
    loop = MockRuntimeLoop(traces=make_traces(5))
    snap = RuntimeSnapshot.capture(loop)
    assert snap.cycle_count == 5


# ── to_dict() ──


def test_to_dict_keys():
    snap = RuntimeSnapshot(
        snapshot_id="cp_1", created_at=1.0,
        runtime_state_snapshot={}, trace_count=0, traces=[],
    )
    d = snap.to_dict()
    assert isinstance(d, dict)
    assert "snapshot_id" in d
    assert "traces" in d
    assert "created_at" in d


def test_to_dict_values():
    traces = [{"event_id": "e1", "final_status": "P4_ALLOW"}]
    snap = RuntimeSnapshot(
        snapshot_id="cp_1", created_at=100.0,
        runtime_state_snapshot={"status": "stopped"},
        trace_count=1, traces=traces,
    )
    d = snap.to_dict()
    assert d["snapshot_id"] == "cp_1"
    assert d["trace_count"] == 1
    assert d["traces"] == traces


# ── JSON round-trip ──


def test_to_json_round_trip():
    traces = [{"event_id": "e1", "final_status": "P4_ALLOW"}]
    snap = RuntimeSnapshot(
        snapshot_id="cp_x", created_at=200.0,
        runtime_state_snapshot={"status": "running"},
        trace_count=1, traces=traces,
    )
    raw = snap.to_json()
    parsed = json.loads(raw)
    assert parsed["snapshot_id"] == "cp_x"
    assert parsed["trace_count"] == 1


def test_from_json():
    data = {
        "snapshot_id": "cp_42", "created_at": 300.0,
        "runtime_state_snapshot": {"status": "stopped"},
        "trace_count": 0, "traces": [],
    }
    snap = RuntimeSnapshot.from_json(json.dumps(data))
    assert snap.snapshot_id == "cp_42"
    assert snap.created_at == 300.0


def test_from_json_with_optional_fields():
    data = {
        "snapshot_id": "cp_99", "created_at": 400.0,
        "runtime_state_snapshot": {},
        "trace_count": 2,
        "traces": [{"event_id": "e1"}, {"event_id": "e2"}],
        "governance_score_history": [0.9, 0.8],
        "queue_depth": 7,
    }
    snap = RuntimeSnapshot.from_json(json.dumps(data))
    assert snap.governance_score_history == [0.9, 0.8]
    assert snap.queue_depth == 7


def test_from_json_missing_fields_get_defaults():
    data = {
        "snapshot_id": "cp_1", "created_at": 1.0,
        "runtime_state_snapshot": {}, "trace_count": 0, "traces": [],
    }
    snap = RuntimeSnapshot.from_json(json.dumps(data))
    assert snap.confidence_gradient == "HIGH"
    assert snap.recovery_mode_enabled is False


def test_from_dict():
    data = {
        "snapshot_id": "cp_1", "created_at": 1.0,
        "runtime_state_snapshot": {}, "trace_count": 0, "traces": [],
    }
    snap = RuntimeSnapshot.from_dict(data)
    assert snap.snapshot_id == "cp_1"


# ── Trace handling ──


def test_capture_trace_fields(sample_trace_allow):
    traces = [sample_trace_allow]
    loop = MockRuntimeLoop(traces=traces)
    snap = RuntimeSnapshot.capture(loop)
    assert len(snap.traces) == 1
    d = snap.traces[0]
    assert d["event_id"] == "e1"
    assert d["final_status"] == "P4_ALLOW"


def test_capture_handles_bad_trace_objects():
    class BadTrace:
        event_id = "bad"
    loop = MockRuntimeLoop(traces=[BadTrace()])
    snap = RuntimeSnapshot.capture(loop)
    assert len(snap.traces) == 1
    assert snap.traces[0]["event_id"] == "bad"
