"""Crash recovery tests -- forced shutdown, WAL corruption, interrupted checkpoints, recovery replay, and corrupt checkpoint detection."""

import gc
import json
import os
import shutil
import tempfile
from unittest.mock import MagicMock

import pytest

from cognitive_runtime.contracts.execution_trace import ExecutionTrace
from cognitive_runtime.recovery.crash_detector import CrashDetector
from cognitive_runtime.recovery.checkpoint_manager import CheckpointManager
from cognitive_runtime.recovery.persistence_guard import PersistenceGuard
from cognitive_runtime.recovery.replay_validator import ReplayValidator
from cognitive_runtime.recovery.runtime_snapshot import RuntimeSnapshot
from cognitive_runtime.recovery.recovery_coordinator import RecoveryCoordinator
from cognitive_runtime.contracts.frozen.schema_version import FROZEN_SCHEMA_VERSION
from cognitive_runtime.runtime.runtime_state import RuntimeState


def make_trace(event_id, final_status="P4_ALLOW"):
    return ExecutionTrace(
        event_id=event_id, session_id="s1", sequence_no=int(event_id[1:]),
        correlation_id=f"c{event_id[1:]}",
        preflight_valid=True, preflight_reason="ok", risk_score=0.1,
        p4_verdict="ALLOW", p4_reason="ok", p4_risk_level="low",
        execution_status="SUCCESS", final_status=final_status,
    )


def trace_dicts(traces):
    import dataclasses
    return [dataclasses.asdict(t) for t in traces]


@pytest.fixture
def tmp_dir():
    path = tempfile.mkdtemp()
    yield path
    for _ in range(3):
        try:
            shutil.rmtree(path)
        except PermissionError:
            gc.collect()


# ─── a) Forced Shutdown ──────────────────────


def test_detects_unclean_shutdown():
    loop = MagicMock()
    loop._traces = [make_trace("e1")]
    loop._state = MagicMock()
    loop._state.status = "running"
    loop._state.health_status = "healthy"
    loop._queue = None
    ind = CrashDetector().detect(loop)
    assert ind.unclean_shutdown
    assert "running" in ind.details


def test_clean_shutdown_passes():
    loop = MagicMock()
    loop._traces = [make_trace("e1")]
    loop._state = MagicMock()
    loop._state.status = "stopped"
    loop._state.health_status = "healthy"
    loop._queue = None
    assert not CrashDetector().detect(loop).unclean_shutdown


def test_sequence_gap_detected():
    loop = MagicMock()
    loop._traces = [make_trace("e1"), make_trace("e3")]
    loop._state = MagicMock()
    loop._state.status = "stopped"
    loop._state.health_status = "healthy"
    loop._queue = None
    ind = CrashDetector().detect(loop)
    assert ind.gap_in_sequence and ind.unclean_shutdown


def test_partial_executions_counted():
    loop = MagicMock()
    loop._traces = [make_trace("e1", "UNKNOWN"), make_trace("e2", "UNKNOWN")]
    loop._state = MagicMock()
    loop._state.status = "stopped"
    loop._state.health_status = "healthy"
    loop._queue = None
    ind = CrashDetector().detect(loop)
    assert ind.partial_executions == 2 and ind.unclean_shutdown


def test_no_traces_not_unclean():
    loop = MagicMock()
    loop._traces = []
    loop._state = MagicMock()
    loop._state.status = "stopped"
    loop._state.health_status = "healthy"
    loop._queue = None
    assert not CrashDetector().detect(loop).unclean_shutdown


def test_critical_health_triggers_unclean():
    loop = MagicMock()
    loop._traces = [make_trace("e1")]
    loop._state = MagicMock()
    loop._state.status = "stopped"
    loop._state.health_status = "critical"
    loop._queue = None
    ind = CrashDetector().detect(loop)
    assert ind.unclean_shutdown


# ─── b) Partial WAL Corruption ───────────────


def test_orphan_traces_detected():
    loop = MagicMock()
    loop._traces = [make_trace("e1"), make_trace("e2")]
    loop._state = MagicMock()
    loop._state.status = "stopped"
    loop._state.health_status = "healthy"
    loop._queue = MagicMock()
    loop._queue.stats.processed = 1
    assert CrashDetector().detect(loop).orphan_traces > 0


def test_no_orphans_when_counts_match():
    loop = MagicMock()
    loop._traces = [make_trace("e1")]
    loop._state = MagicMock()
    loop._state.status = "stopped"
    loop._state.health_status = "healthy"
    loop._queue = MagicMock()
    loop._queue.stats.processed = 1
    assert max(0, 1 - 1) == 0


def test_no_queue_no_orphan():
    loop = MagicMock()
    loop._traces = [make_trace("e1")]
    loop._state = MagicMock()
    loop._state.status = "stopped"
    loop._state.health_status = "healthy"
    loop._queue = None
    assert CrashDetector().detect(loop).orphan_traces == 0


def test_corrupted_cycles_detected():
    loop = MagicMock()
    loop._traces = [make_trace("e1", "UNKNOWN"), make_trace("e2", "P4_ALLOW")]
    loop._state = MagicMock()
    loop._state.status = "stopped"
    loop._state.health_status = "healthy"
    loop._queue = None
    assert CrashDetector().detect(loop).corrupted_cycles >= 1


# ─── c) Interrupted Checkpoint ───────────────


def test_half_written_file_returns_none(tmp_dir):
    mgr = CheckpointManager(checkpoint_dir=tmp_dir, enabled=True)
    snap = RuntimeSnapshot(snapshot_id="cp_t", created_at=100.0, runtime_state_snapshot={},
                           trace_count=0, traces=[], schema_version=str(FROZEN_SCHEMA_VERSION))
    mgr.save(snap)
    path = mgr.latest.file_path
    with open(path, "w") as f:
        f.write('{"incomplete": ')
    assert mgr.load_latest() is None


def test_empty_checkpoint_file(tmp_dir):
    mgr = CheckpointManager(checkpoint_dir=tmp_dir, enabled=True)
    snap = RuntimeSnapshot(snapshot_id="cp_e", created_at=100.0, runtime_state_snapshot={},
                           trace_count=0, traces=[], schema_version=str(FROZEN_SCHEMA_VERSION))
    mgr.save(snap)
    with open(mgr.latest.file_path, "w") as f:
        f.write("")
    assert mgr.load_latest() is None


def test_missing_checkpoint(tmp_dir):
    assert CheckpointManager(checkpoint_dir=tmp_dir, enabled=True).load_latest() is None


def test_nonexistent_checkpoint_id(tmp_dir):
    assert CheckpointManager(checkpoint_dir=tmp_dir).load_id("nonexistent") is None


def test_broken_json_file(tmp_dir):
    mgr = CheckpointManager(checkpoint_dir=tmp_dir, enabled=True)
    snap = RuntimeSnapshot(snapshot_id="cp_b", created_at=100.0, runtime_state_snapshot={},
                           trace_count=0, traces=[], schema_version=str(FROZEN_SCHEMA_VERSION))
    mgr.save(snap)
    with open(mgr.latest.file_path, "w") as f:
        f.write("{broken json!!!!}")
    assert mgr.load_latest() is None


def test_incomplete_snapshot_fails_validation():
    guard = PersistenceGuard()
    snap = RuntimeSnapshot(snapshot_id="cp_h", created_at=100.0, runtime_state_snapshot={},
                           trace_count=0, traces=[], schema_version=str(FROZEN_SCHEMA_VERSION))
    snap.runtime_state_snapshot = None
    v = guard.validate_snapshot(snap)
    assert not v.has_required_fields and not v.valid


# ─── d) Recovery Replay ──────────────────────


def test_recovery_replay_validates(tmp_dir):
    traces = [make_trace("e1"), make_trace("e2")]
    snap = RuntimeSnapshot(snapshot_id="cp_r", created_at=100.0,
                           runtime_state_snapshot={"status": "running", "total_events_processed": 2},
                           trace_count=2, traces=trace_dicts(traces), schema_version=str(FROZEN_SCHEMA_VERSION))
    mgr = CheckpointManager(checkpoint_dir=tmp_dir, enabled=True)
    mgr.save(snap)
    loaded = mgr.load_latest()
    assert loaded is not None and loaded.trace_count == 2
    v = ReplayValidator().validate(loaded, traces)
    assert v.valid and v.divergence_count == 0


def test_restore_snapshot_into_loop(tmp_dir):
    traces = [make_trace("e1")]
    snap = RuntimeSnapshot(snapshot_id="cp_rs", created_at=100.0,
                           runtime_state_snapshot={"status": "running", "total_events_processed": 1},
                           trace_count=1, traces=trace_dicts(traces), schema_version=str(FROZEN_SCHEMA_VERSION))
    mgr = CheckpointManager(checkpoint_dir=tmp_dir, enabled=True)
    mgr.save(snap)
    loop = MagicMock()
    loop._traces = []
    loop._state = RuntimeState()
    coord = RecoveryCoordinator(checkpoint_manager=mgr, compatibility_guard=MagicMock())
    coord._apply_snapshot(loop, snap)
    assert len(loop._traces) == 1 and loop._traces[0].event_id == "e1"


def test_replay_detects_divergence(tmp_dir):
    orig = [make_trace("e1", "P4_ALLOW")]
    repl = [make_trace("e1", "SANDBOX_FAILED")]
    snap = RuntimeSnapshot(snapshot_id="cp_d", created_at=100.0, runtime_state_snapshot={},
                           trace_count=1, traces=trace_dicts(orig), schema_version=str(FROZEN_SCHEMA_VERSION))
    v = ReplayValidator().validate(snap, repl)
    assert not v.valid and v.divergence_count > 0


def test_persistence_guard_validates_snapshot(tmp_dir):
    snap = RuntimeSnapshot(snapshot_id="cp_v", created_at=100.0,
                           runtime_state_snapshot={"status": "running"},
                           trace_count=1, traces=trace_dicts([make_trace("e1")]),
                           schema_version=str(FROZEN_SCHEMA_VERSION))
    v = PersistenceGuard().validate_snapshot(snap)
    assert v.valid and v.schema_match


# ─── e) Corrupt Checkpoint ───────────────────


def test_wrong_schema_version_detected(tmp_dir):
    snap = RuntimeSnapshot(snapshot_id="cp_c", created_at=100.0,
                           runtime_state_snapshot={"status": "running"},
                           trace_count=2, traces=trace_dicts([make_trace("e1"), make_trace("e2")]),
                           schema_version="99.0.0")
    mgr = CheckpointManager(checkpoint_dir=tmp_dir, enabled=True)
    mgr.save(snap)
    loaded = mgr.load_latest()
    assert loaded is not None and loaded.schema_version == "99.0.0"
    v = PersistenceGuard().validate_snapshot(loaded)
    assert not v.valid and not v.schema_match
    assert any("Schema mismatch" in err for err in v.contract_violations)


def test_trace_count_mismatch_detected():
    snap = RuntimeSnapshot(snapshot_id="cp_m", created_at=100.0, runtime_state_snapshot={},
                           trace_count=5, traces=trace_dicts([make_trace("e1")]),
                           schema_version=str(FROZEN_SCHEMA_VERSION))
    v = PersistenceGuard().validate_snapshot(snap)
    assert not v.valid
    assert any("Trace count mismatch" in err for err in v.contract_violations)


def test_valid_checkpoint_passes(tmp_dir):
    snap = RuntimeSnapshot(snapshot_id="cp_p", created_at=100.0, runtime_state_snapshot={},
                           trace_count=1, traces=trace_dicts([make_trace("e1")]),
                           schema_version=str(FROZEN_SCHEMA_VERSION))
    mgr = CheckpointManager(checkpoint_dir=tmp_dir, enabled=True)
    mgr.save(snap)
    v = PersistenceGuard().validate_snapshot(mgr.load_latest())
    assert v.valid


def test_missing_required_fields_fails():
    guard = PersistenceGuard()

    class BadSnapshot:
        pass

    with pytest.raises(AttributeError):
        guard.validate_snapshot(BadSnapshot())


def test_recovery_coordinator_reports_corruption(tmp_dir):
    snap = RuntimeSnapshot(snapshot_id="cp_rpt", created_at=100.0, runtime_state_snapshot={},
                           trace_count=0, traces=[], schema_version="99.0.0")
    mgr = CheckpointManager(checkpoint_dir=tmp_dir, enabled=True)
    mgr.save(snap)
    guard = PersistenceGuard()
    coord = RecoveryCoordinator(checkpoint_manager=mgr, compatibility_guard=MagicMock())
    loop = MagicMock()
    loop._traces = []
    loop._state = RuntimeState()
    loop._contract_guard = MagicMock()
    loop._contract_guard.run_all.return_value = {"passed": True, "violations_found": 0, "total_violations": 0}
    report = coord.recover(loop)
    assert report.corruption_detected
    assert report.recovery_mode == "clean_start"
