"""Tests for cognitive_runtime/recovery/recovery_report.py."""

import pytest

from cognitive_runtime.recovery.recovery_report import RecoveryReport
from cognitive_runtime.contracts.frozen.schema_version import FROZEN_SCHEMA_VERSION


# ── Defaults ──


def test_default_replay_valid():
    report = RecoveryReport(success=True, recovery_mode="clean_start")
    assert report.replay_valid is True


def test_default_corruption_false():
    report = RecoveryReport(success=True, recovery_mode="clean_start")
    assert report.corruption_detected is False


def test_default_cycles():
    report = RecoveryReport(success=True, recovery_mode="clean_start")
    assert report.total_cycles_requested == 0
    assert report.restored_cycles == 0
    assert report.skipped_cycles == 0


def test_default_replay_fields():
    report = RecoveryReport(success=True, recovery_mode="clean_start")
    assert report.replay_divergence_count == 0
    assert report.replay_divergences == []


def test_default_orphans():
    report = RecoveryReport(success=True, recovery_mode="clean_start")
    assert report.orphan_events_found == 0
    assert report.orphan_events_recovered == 0
    assert report.orphan_events == []


def test_default_checkpoints():
    report = RecoveryReport(success=True, recovery_mode="clean_start")
    assert report.checkpoint_restored is None
    assert report.checkpoint_count == 0
    assert report.latest_checkpoint_cycle == 0


def test_default_timing():
    report = RecoveryReport(success=True, recovery_mode="clean_start")
    assert report.recovery_started_at == 0.0
    assert report.recovery_completed_at == 0.0
    assert report.recovery_duration_ms == 0.0


def test_default_state():
    report = RecoveryReport(success=True, recovery_mode="clean_start")
    assert report.final_state_status == "stopped"
    assert report.final_health_status == "healthy"
    assert report.final_trace_count == 0


def test_default_schema():
    report = RecoveryReport(success=True, recovery_mode="clean_start")
    assert report.schema_version == str(FROZEN_SCHEMA_VERSION)
    assert report.contract_violations_during_recovery == 0


def test_default_corruption_details():
    report = RecoveryReport(success=True, recovery_mode="clean_start")
    assert report.corruption_details == []


# ── Field setting ──


def test_all_fields_set():
    report = RecoveryReport(
        success=True,
        recovery_mode="crash_recovery",
        total_cycles_requested=10,
        restored_cycles=8,
        skipped_cycles=2,
        replay_valid=True,
        replay_divergence_count=0,
        replay_divergences=[],
        corruption_detected=False,
        corruption_details=[],
        orphan_events_found=1,
        orphan_events_recovered=1,
        orphan_events=["e_orphan"],
        checkpoint_restored="cp_123",
        checkpoint_count=5,
        latest_checkpoint_cycle=9,
        recovery_started_at=1000.0,
        recovery_completed_at=1002.5,
        recovery_duration_ms=2500.0,
        final_state_status="running",
        final_health_status="degraded",
        final_trace_count=42,
        schema_version=str(FROZEN_SCHEMA_VERSION),
        contract_violations_during_recovery=0,
    )
    assert report.recovery_mode == "crash_recovery"
    assert report.restored_cycles == 8
    assert report.orphan_events == ["e_orphan"]
    assert report.checkpoint_restored == "cp_123"
    assert report.final_health_status == "degraded"


def test_set_replay_valid_false():
    report = RecoveryReport(success=False, recovery_mode="crash_recovery",
                            replay_valid=False)
    assert report.replay_valid is False


# ── Snapshot ──


def test_snapshot_keys():
    report = RecoveryReport(success=True, recovery_mode="clean_start")
    snap = report.snapshot()
    expected = {"success", "recovery_mode", "restored_cycles",
                 "replay_valid", "corruption_detected",
                 "orphan_events_found", "checkpoint_restored",
                 "recovery_duration_ms", "final_health_status",
                 "final_trace_count", "schema_version"}
    assert set(snap.keys()) == expected


def test_snapshot_values():
    report = RecoveryReport(
        success=True, recovery_mode="crash_recovery",
        restored_cycles=5, replay_valid=True,
        corruption_detected=False, orphan_events_found=2,
        checkpoint_restored="cp_99", recovery_duration_ms=123.456,
        final_health_status="healthy", final_trace_count=20,
        schema_version=str(FROZEN_SCHEMA_VERSION),
    )
    snap = report.snapshot()
    assert snap["success"] is True
    assert snap["recovery_mode"] == "crash_recovery"
    assert snap["restored_cycles"] == 5
    assert snap["checkpoint_restored"] == "cp_99"
    assert snap["final_trace_count"] == 20


def test_snapshot_duration_rounded():
    report = RecoveryReport(success=True, recovery_mode="clean_start",
                            recovery_duration_ms=123.45678)
    snap = report.snapshot()
    assert snap["recovery_duration_ms"] == 123.46


# ── Recovery modes ──


@pytest.mark.parametrize("mode", [
    "clean_start", "crash_recovery", "checkpoint_restore",
])
def test_valid_recovery_modes(mode):
    report = RecoveryReport(success=True, recovery_mode=mode)
    assert report.recovery_mode == mode
    assert report.snapshot()["recovery_mode"] == mode
