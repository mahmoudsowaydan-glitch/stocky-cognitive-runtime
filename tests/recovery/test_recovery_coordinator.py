"""Tests for cognitive_runtime/recovery/recovery_coordinator.py."""

import pytest

from cognitive_runtime.recovery import (
    RecoveryCoordinator, CheckpointManager,
)
from cognitive_runtime.recovery.recovery_report import RecoveryReport
from cognitive_runtime.recovery.runtime_snapshot import RuntimeSnapshot
from cognitive_runtime.contracts.execution_trace import ExecutionTrace
from cognitive_runtime.contracts.frozen.schema_version import FROZEN_SCHEMA_VERSION


# ── Mocks ──


class MockState:
    def __init__(self, status="stopped", health="healthy", tep=0):
        self.status = status
        self.health_status = health
        self.total_events_processed = tep

    def snapshot(self):
        return {
            "status": self.status,
            "health_status": self.health_status,
            "total_events_processed": self.total_events_processed,
        }


class MockQueueStats:
    def __init__(self, depth=0, processed=0):
        self.queue_depth = depth
        self.processed = processed


class MockQueue:
    def __init__(self, depth=0, processed=0):
        self.stats = MockQueueStats(depth, processed)


class MockGuard:
    def __init__(self, gradient="HIGH"):
        self._current_gradient = gradient


class MockConfidence:
    def __init__(self, history=None, gradient="HIGH"):
        self._score_history = history or []
        self._guard = MockGuard(gradient)


class MockGovernance:
    def __init__(self, history=None):
        self._score_history = history or []


class MockStability:
    def __init__(self, history=None):
        self._score_history = history or []


class MockContractGuard:
    def __init__(self, passed=True, violations=None):
        self._violations = violations or []

    def run_all(self, loop):
        return {"passed": len(self._violations) == 0}

    @property
    def violations(self):
        return self._violations


class MockRuntimeLoop:
    def __init__(self, status="stopped", health="healthy",
                 traces=None, tep=0, queue_depth=0, queue_processed=0,
                 gov_history=None, conf_history=None, conf_gradient="HIGH",
                 stab_history=None, contract_violations=None):
        self._traces = traces or []
        self._state = MockState(status=status, health=health, tep=tep)
        self._queue = MockQueue(depth=queue_depth, processed=queue_processed)
        self._governance = MockGovernance(gov_history)
        self._confidence = MockConfidence(conf_history, conf_gradient)
        self._stability = MockStability(stab_history)
        self._contract_guard = MockContractGuard(
            passed=len(contract_violations or []) == 0,
            violations=contract_violations or [],
        )
        self.state = self._state


# ── Helpers ──


def make_trace(event_id, final_status="P4_ALLOW"):
    suffix = event_id[1:]
    try:
        seq = int(suffix)
    except ValueError:
        seq = 0
    return ExecutionTrace(
        event_id=event_id, session_id="s1",
        sequence_no=seq,
        correlation_id=f"c{suffix}",
        preflight_valid=True, preflight_reason="preflight_passed",
        risk_score=0.1,
        p4_verdict="ALLOW" if final_status == "P4_ALLOW" else "BLOCK",
        p4_reason="ok", p4_risk_level="low",
        execution_status="SUCCESS", final_status=final_status,
    )


def make_trace_dict(event_id, final_status="P4_ALLOW"):
    suffix = event_id[1:]
    try:
        seq = int(suffix)
    except ValueError:
        seq = 0
    return {
        "event_id": event_id, "session_id": "s1",
        "sequence_no": seq,
        "final_status": final_status,
        "preflight_valid": True, "preflight_reason": "preflight_passed",
        "p4_verdict": "ALLOW", "p4_reason": "ok", "p4_risk_level": "low",
        "execution_status": "SUCCESS",
        "preflight_time": 0.0, "p4_time": 0.0,
        "execution_time": 0.0, "total_time": 0.0,
        "correlation_id": f"c{event_id[1:]}", "risk_score": 0.1,
        "preflight_rules_triggered": [], "p4_rule_triggered": None,
        "execution_error": None, "capabilities_checked": [],
        "resource_usage": {},
    }


# ── Clean start ──


def test_clean_start_success(tmp_dir):
    cm = CheckpointManager(checkpoint_dir=tmp_dir)
    traces = [make_trace(f"e{i}") for i in range(3)]
    loop = MockRuntimeLoop(status="stopped", traces=traces)
    report = RecoveryCoordinator(checkpoint_manager=cm).recover(loop)
    assert report.success is True
    assert report.recovery_mode == "clean_start"
    assert report.replay_valid is True
    assert report.checkpoint_restored is None
    assert report.restored_cycles == 0
    assert report.corruption_detected is False


def test_clean_start_no_checkpoints(tmp_dir):
    cm = CheckpointManager(checkpoint_dir=tmp_dir)
    loop = MockRuntimeLoop(status="stopped")
    report = RecoveryCoordinator(checkpoint_manager=cm).recover(loop)
    assert report.checkpoint_count == 0
    assert report.checkpoint_restored is None


def test_clean_start_replay_valid(tmp_dir):
    cm = CheckpointManager(checkpoint_dir=tmp_dir)
    traces = [make_trace(f"e{i}") for i in range(2)]
    loop = MockRuntimeLoop(status="stopped", traces=traces)
    report = RecoveryCoordinator(checkpoint_manager=cm).recover(loop)
    assert report.replay_valid is True
    assert report.replay_divergence_count == 0


def test_clean_start_final_trace_count(tmp_dir):
    cm = CheckpointManager(checkpoint_dir=tmp_dir)
    traces = [make_trace(f"e{i}") for i in range(5)]
    loop = MockRuntimeLoop(status="stopped", traces=traces)
    report = RecoveryCoordinator(checkpoint_manager=cm).recover(loop)
    assert report.final_trace_count == 5


def test_clean_start_last_report(tmp_dir):
    cm = CheckpointManager(checkpoint_dir=tmp_dir)
    loop = MockRuntimeLoop(status="stopped")
    coord = RecoveryCoordinator(checkpoint_manager=cm)
    assert coord.last_report is None
    coord.recover(loop)
    assert coord.last_report is not None
    assert isinstance(coord.last_report, RecoveryReport)


# ── Crash recovery ──


def test_crash_recovery_restores_checkpoint(tmp_dir):
    cm = CheckpointManager(checkpoint_dir=tmp_dir)
    snap = RuntimeSnapshot(
        snapshot_id="cp_crash", created_at=1000.0,
        runtime_state_snapshot={"status": "stopped"},
        trace_count=2,
        traces=[make_trace_dict("e0"), make_trace_dict("e1")],
    )
    cm.save(snap)
    loop = MockRuntimeLoop(
        status="running",
        traces=[make_trace("e0"), make_trace("e1"), make_trace("e2")],
        tep=3,
    )
    report = RecoveryCoordinator(checkpoint_manager=cm).recover(loop)
    assert report.recovery_mode == "crash_recovery"
    assert report.checkpoint_restored == "cp_crash"
    assert report.checkpoint_count == 1
    assert report.restored_cycles > 0


def test_crash_recovery_restored_cycles(tmp_dir):
    cm = CheckpointManager(checkpoint_dir=tmp_dir)
    snap = RuntimeSnapshot(
        snapshot_id="cp_cycles", created_at=1000.0,
        runtime_state_snapshot={"status": "stopped"},
        trace_count=3,
        traces=[make_trace_dict(f"e{i}") for i in range(3)],
    )
    cm.save(snap)
    loop = MockRuntimeLoop(
        status="running",
        traces=[make_trace(f"e{i}") for i in range(5)],
    )
    report = RecoveryCoordinator(checkpoint_manager=cm).recover(loop)
    assert report.restored_cycles == 3


def test_crash_recovery_corruption_from_bad_schema(tmp_dir):
    cm = CheckpointManager(checkpoint_dir=tmp_dir)
    snap = RuntimeSnapshot(
        snapshot_id="cp_bad_schema", created_at=1000.0,
        runtime_state_snapshot={"status": "stopped"},
        trace_count=1, traces=[make_trace_dict("e0")],
        schema_version="2.0.0",
    )
    cm.save(snap)
    loop = MockRuntimeLoop(status="running", traces=[make_trace("e0")])
    report = RecoveryCoordinator(checkpoint_manager=cm).recover(loop)
    assert report.corruption_detected is True


def test_crash_recovery_replay_valid(tmp_dir):
    cm = CheckpointManager(checkpoint_dir=tmp_dir)
    snap = RuntimeSnapshot(
        snapshot_id="cp_replay", created_at=1000.0,
        runtime_state_snapshot={"status": "stopped"},
        trace_count=2,
        traces=[make_trace_dict("e0"), make_trace_dict("e1")],
    )
    cm.save(snap)
    traces = [make_trace("e0"), make_trace("e1")]
    loop = MockRuntimeLoop(status="running", traces=traces)
    report = RecoveryCoordinator(checkpoint_manager=cm).recover(loop)
    assert report.replay_valid is True


# ── Empty loop ──


def test_empty_traces_clean_start(tmp_dir):
    cm = CheckpointManager(checkpoint_dir=tmp_dir)
    loop = MockRuntimeLoop(status="stopped", traces=[])
    report = RecoveryCoordinator(checkpoint_manager=cm).recover(loop)
    assert report.success is True
    assert report.recovery_mode == "clean_start"
    assert report.final_trace_count == 0


def test_empty_traces_no_crash(tmp_dir):
    cm = CheckpointManager(checkpoint_dir=tmp_dir)
    loop = MockRuntimeLoop(status="stopped", traces=[])
    report = RecoveryCoordinator(checkpoint_manager=cm).recover(loop)
    assert report.corruption_detected is False


def test_empty_traces_replay_valid(tmp_dir):
    cm = CheckpointManager(checkpoint_dir=tmp_dir)
    loop = MockRuntimeLoop(status="stopped", traces=[])
    report = RecoveryCoordinator(checkpoint_manager=cm).recover(loop)
    assert report.replay_valid is True


# ── Recovery in progress guard ──


def test_recovery_in_progress_flag_cleared(tmp_dir):
    cm = CheckpointManager(checkpoint_dir=tmp_dir)
    loop = MockRuntimeLoop(status="stopped")
    coord = RecoveryCoordinator(checkpoint_manager=cm)
    assert coord.recovery_in_progress is False
    coord.recover(loop)
    assert coord.recovery_in_progress is False


# ── Corrupted state ──


def test_corruption_from_crash(tmp_dir):
    cm = CheckpointManager(checkpoint_dir=tmp_dir)
    loop = MockRuntimeLoop(status="running")
    report = RecoveryCoordinator(checkpoint_manager=cm).recover(loop)
    assert report.corruption_detected is True
    assert report.corruption_details != []


def test_corruption_with_unknown_status(tmp_dir):
    cm = CheckpointManager(checkpoint_dir=tmp_dir)
    loop = MockRuntimeLoop(status="unknown")
    report = RecoveryCoordinator(checkpoint_manager=cm).recover(loop)
    assert report.corruption_detected is True


def test_corruption_from_contract_violations(tmp_dir):
    cm = CheckpointManager(checkpoint_dir=tmp_dir)
    violations = [{"component": "trace", "message": "field_missing"}]
    loop = MockRuntimeLoop(
        status="stopped", traces=[make_trace("e0")],
        contract_violations=violations,
    )
    report = RecoveryCoordinator(checkpoint_manager=cm).recover(loop)
    assert report.corruption_detected is True
    assert any("post-recovery" in d for d in report.corruption_details)


def test_orphan_events_from_crash(tmp_dir):
    cm = CheckpointManager(checkpoint_dir=tmp_dir)
    traces = [make_trace(f"e{i}") for i in range(5)]
    loop = MockRuntimeLoop(
        status="running", traces=traces, queue_processed=3,
    )
    report = RecoveryCoordinator(checkpoint_manager=cm).recover(loop)
    assert report.orphan_events_found > 0


# ── HAL observer ──


def test_hal_observer_called(tmp_dir):
    cm = CheckpointManager(checkpoint_dir=tmp_dir)
    loop = MockRuntimeLoop(status="stopped")
    calls = []
    coord = RecoveryCoordinator(checkpoint_manager=cm, hal_observer=calls.append)
    coord.recover(loop)
    assert len(calls) >= 1
    assert calls[-1]["type"] == "recovery.report"


def test_hal_observer_snapshot_data(tmp_dir):
    cm = CheckpointManager(checkpoint_dir=tmp_dir)
    loop = MockRuntimeLoop(status="stopped")
    calls = []
    coord = RecoveryCoordinator(checkpoint_manager=cm, hal_observer=calls.append)
    coord.recover(loop)
    snap = calls[-1]["data"]
    assert "recovery_mode" in snap
    assert "success" in snap


def test_hal_observer_no_observer(tmp_dir):
    cm = CheckpointManager(checkpoint_dir=tmp_dir)
    loop = MockRuntimeLoop(status="stopped")
    report = RecoveryCoordinator(checkpoint_manager=cm).recover(loop)
    assert report.success is True


# ── Schema and state ──


def test_report_schema_version(tmp_dir):
    cm = CheckpointManager(checkpoint_dir=tmp_dir)
    loop = MockRuntimeLoop(status="stopped")
    report = RecoveryCoordinator(checkpoint_manager=cm).recover(loop)
    assert report.schema_version == str(FROZEN_SCHEMA_VERSION)


def test_final_state_values(tmp_dir):
    cm = CheckpointManager(checkpoint_dir=tmp_dir)
    loop = MockRuntimeLoop(status="running", health="degraded")
    report = RecoveryCoordinator(checkpoint_manager=cm).recover(loop)
    assert report.final_state_status == "running"
    assert report.final_health_status == "degraded"


# ── Error handling ──


def test_recover_handles_exception(tmp_dir):
    cm = CheckpointManager(checkpoint_dir=tmp_dir)
    loop = object()
    report = RecoveryCoordinator(checkpoint_manager=cm).recover(loop)
    assert report.final_trace_count == 0
    assert report.recovery_mode == "clean_start"


# ── _apply_snapshot ──


def test_apply_snapshot_restores_traces(tmp_dir):
    cm = CheckpointManager(checkpoint_dir=tmp_dir)
    snap = RuntimeSnapshot(
        snapshot_id="cp_apply", created_at=1000.0,
        runtime_state_snapshot={"status": "running"},
        trace_count=2,
        traces=[make_trace_dict("e0"), make_trace_dict("e1")],
    )
    cm.save(snap)
    loop = MockRuntimeLoop(
        status="running", traces=[make_trace("e0"), make_trace("e1")], tep=5,
    )
    RecoveryCoordinator(checkpoint_manager=cm).recover(loop)
    assert len(loop._traces) == 2


def test_apply_snapshot_restores_state(tmp_dir):
    cm = CheckpointManager(checkpoint_dir=tmp_dir)
    snap = RuntimeSnapshot(
        snapshot_id="cp_state", created_at=1000.0,
        runtime_state_snapshot={"status": "running", "health_status": "degraded"},
        trace_count=0, traces=[],
    )
    cm.save(snap)
    loop = MockRuntimeLoop(status="stopped", health="healthy")
    RecoveryCoordinator(checkpoint_manager=cm).recover(loop)
    assert loop._state.status in ("running", "stopped")


def test_apply_snapshot_restores_governance(tmp_dir):
    cm = CheckpointManager(checkpoint_dir=tmp_dir)
    snap = RuntimeSnapshot(
        snapshot_id="cp_subsys", created_at=1000.0,
        runtime_state_snapshot={"status": "stopped"},
        trace_count=0, traces=[],
        governance_score_history=[0.8, 0.9],
        confidence_score_history=[0.7, 0.85],
        confidence_gradient="LOW",
        stability_score_history=[0.6, 0.65],
    )
    cm.save(snap)
    loop = MockRuntimeLoop(
        status="stopped",
        gov_history=[0.5], conf_history=[0.5],
        conf_gradient="HIGH", stab_history=[0.5],
    )
    RecoveryCoordinator(checkpoint_manager=cm).recover(loop)
    assert loop._governance._score_history == [0.8, 0.9]
    assert loop._confidence._score_history == [0.7, 0.85]
    assert loop._stability._score_history == [0.6, 0.65]
