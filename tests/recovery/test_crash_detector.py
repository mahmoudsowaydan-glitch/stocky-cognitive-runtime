"""Tests for cognitive_runtime/recovery/crash_detector.py."""

import pytest

from cognitive_runtime.recovery.crash_detector import CrashDetector, CrashIndicator
from cognitive_runtime.contracts.execution_trace import ExecutionTrace


# ── Helpers ──


class MockState:
    def __init__(self, status="stopped", health="healthy"):
        self.status = status
        self.health_status = health


class MockQueueStats:
    def __init__(self, processed=10):
        self.processed = processed


class MockQueue:
    def __init__(self, processed=10):
        self.stats = MockQueueStats(processed)


class MockRuntime:
    def __init__(self, traces=None, state=None, queue=None):
        self._traces = traces or []
        self._state = state or MockState()
        self._queue = queue or MockQueue()


def make_trace(event_id, final_status="P4_ALLOW", exec_status="SUCCESS",
               preflight_valid=True):
    suffix = event_id[1:]
    try:
        seq = int(suffix)
    except ValueError:
        seq = 0
    return ExecutionTrace(
        event_id=event_id,
        session_id="s1",
        sequence_no=seq,
        correlation_id=f"c{suffix}",
        preflight_valid=preflight_valid,
        preflight_reason="preflight_passed",
        risk_score=0.1,
        p4_verdict="ALLOW" if final_status == "P4_ALLOW" else "BLOCK",
        p4_reason="ok",
        p4_risk_level="low",
        execution_status=exec_status,
        final_status=final_status,
    )


# ── CrashIndicator ──


def test_crash_indicator_required():
    ind = CrashIndicator(
        unclean_shutdown=False, corrupted_cycles=0,
        partial_executions=0, orphan_traces=0, gap_in_sequence=False,
    )
    assert ind.unclean_shutdown is False
    assert ind.corrupted_cycles == 0


def test_crash_indicator_optional_defaults():
    ind = CrashIndicator(
        unclean_shutdown=False, corrupted_cycles=0,
        partial_executions=0, orphan_traces=0, gap_in_sequence=False,
    )
    assert ind.last_trace_id is None
    assert ind.expected_trace_count == 0
    assert ind.actual_trace_count == 0
    assert ind.details == ""


def test_crash_indicator_all_fields():
    ind = CrashIndicator(
        unclean_shutdown=True, corrupted_cycles=2,
        partial_executions=1, orphan_traces=3, gap_in_sequence=True,
        last_trace_id="e5", expected_trace_count=6,
        actual_trace_count=4, details="sequence_gap; orphans=3",
    )
    assert ind.unclean_shutdown is True
    assert ind.corrupted_cycles == 2
    assert ind.last_trace_id == "e5"


# ── Clean shutdown ──


def test_stopped_status_no_crash():
    loop = MockRuntime(
        traces=[make_trace(f"e{i}") for i in range(5)],
        state=MockState(status="stopped"),
    )
    ind = CrashDetector().detect(loop)
    assert ind.unclean_shutdown is False
    assert ind.gap_in_sequence is False
    assert ind.orphan_traces == 0
    assert ind.partial_executions == 0
    assert ind.details == "clean"


def test_empty_traces_no_crash():
    loop = MockRuntime(traces=[], state=MockState(status="stopped"))
    ind = CrashDetector().detect(loop)
    assert ind.unclean_shutdown is False
    assert ind.details == "clean"


def test_single_trace_no_gap():
    loop = MockRuntime(
        traces=[make_trace("e0")],
        state=MockState(status="stopped"),
    )
    ind = CrashDetector().detect(loop)
    assert ind.gap_in_sequence is False


def test_all_traces_processed_clean():
    loop = MockRuntime(
        traces=[make_trace(f"e{i}") for i in range(5)],
        state=MockState(status="stopped"),
        queue=MockQueue(processed=5),
    )
    ind = CrashDetector().detect(loop)
    assert ind.unclean_shutdown is False


# ── Unclean shutdown ──


def test_status_running_detected():
    loop = MockRuntime(
        traces=[make_trace(f"e{i}") for i in range(3)],
        state=MockState(status="running"),
    )
    ind = CrashDetector().detect(loop)
    assert ind.unclean_shutdown is True
    assert "last_status=running" in ind.details


def test_status_unknown_detected():
    loop = MockRuntime(
        traces=[make_trace(f"e{i}") for i in range(3)],
        state=MockState(status="unknown"),
    )
    ind = CrashDetector().detect(loop)
    assert ind.unclean_shutdown is True


def test_critical_health_triggers_even_stopped():
    loop = MockRuntime(
        traces=[make_trace(f"e{i}") for i in range(3)],
        state=MockState(status="stopped", health="critical"),
    )
    ind = CrashDetector().detect(loop)
    assert ind.unclean_shutdown is True


def test_degraded_not_critical_does_not_trigger():
    loop = MockRuntime(
        traces=[make_trace(f"e{i}") for i in range(3)],
        state=MockState(status="stopped", health="degraded"),
    )
    ind = CrashDetector().detect(loop)
    assert ind.unclean_shutdown is False


# ── Sequence gaps ──


def test_gap_detected():
    traces = [make_trace("e0"), make_trace("e1"),
              make_trace("e2"), make_trace("e4")]
    loop = MockRuntime(traces=traces, state=MockState(status="stopped"))
    ind = CrashDetector().detect(loop)
    assert ind.gap_in_sequence is True


def test_no_gap():
    traces = [make_trace(f"e{i}") for i in range(5)]
    loop = MockRuntime(traces=traces, state=MockState(status="stopped"))
    ind = CrashDetector().detect(loop)
    assert ind.gap_in_sequence is False


def test_last_trace_id():
    traces = [make_trace("e0"), make_trace("e1"), make_trace("e2")]
    loop = MockRuntime(traces=traces, state=MockState(status="running"))
    ind = CrashDetector().detect(loop)
    assert ind.last_trace_id == "e2"


# ── Partial executions ──


def test_partial_execution_detected():
    traces = [
        make_trace("e0", final_status="P4_ALLOW"),
        make_trace("e1", final_status="UNKNOWN"),
    ]
    loop = MockRuntime(traces=traces, state=MockState(status="running"))
    ind = CrashDetector().detect(loop)
    assert ind.partial_executions == 1
    assert "partial=1" in ind.details


def test_no_partial_when_all_complete():
    traces = [
        make_trace("e0", final_status="P4_ALLOW"),
        make_trace("e1", final_status="P4_BLOCK"),
    ]
    loop = MockRuntime(traces=traces, state=MockState(status="stopped"))
    ind = CrashDetector().detect(loop)
    assert ind.partial_executions == 0


# ── Orphan traces ──


def test_orphans_detected():
    traces = [make_trace(f"e{i}") for i in range(10)]
    loop = MockRuntime(
        traces=traces, state=MockState(status="running"),
        queue=MockQueue(processed=7),
    )
    ind = CrashDetector().detect(loop)
    assert ind.orphan_traces == 3
    assert "orphans=3" in ind.details


def test_no_orphans():
    traces = [make_trace(f"e{i}") for i in range(5)]
    loop = MockRuntime(
        traces=traces, state=MockState(status="stopped"),
        queue=MockQueue(processed=5),
    )
    ind = CrashDetector().detect(loop)
    assert ind.orphan_traces == 0


# ── Corrupted cycles ──


def test_corrupted_unknown_status():
    traces = [
        make_trace("e0", final_status="P4_ALLOW"),
        make_trace("e1", final_status="UNKNOWN"),
    ]
    loop = MockRuntime(traces=traces, state=MockState(status="stopped"))
    ind = CrashDetector().detect(loop)
    assert ind.corrupted_cycles >= 1


def test_corrupted_mismatched_status():
    traces = [
        make_trace("e0", final_status="P4_ALLOW", exec_status="UNKNOWN"),
    ]
    loop = MockRuntime(traces=traces, state=MockState(status="stopped"))
    ind = CrashDetector().detect(loop)
    assert ind.corrupted_cycles >= 1


def test_unclean_with_corruption():
    traces = [
        make_trace("e0", final_status="P4_ALLOW"),
        make_trace("e1", final_status="UNKNOWN"),
    ]
    loop = MockRuntime(
        traces=traces, state=MockState(status="running"),
    )
    ind = CrashDetector().detect(loop)
    assert ind.unclean_shutdown is True
    assert ind.corrupted_cycles >= 1
    assert ind.details != ""


# ── last_check property ──


def test_last_check_none_before_detect():
    detector = CrashDetector()
    assert detector.last_check is None


def test_last_check_after_detect():
    detector = CrashDetector()
    loop = MockRuntime(state=MockState(status="running"))
    detector.detect(loop)
    assert detector.last_check is not None
    assert detector.last_check.unclean_shutdown is True


def test_last_check_updates():
    detector = CrashDetector()
    loop1 = MockRuntime(state=MockState(status="stopped"))
    detector.detect(loop1)
    assert detector.last_check.unclean_shutdown is False
    loop2 = MockRuntime(state=MockState(status="running"))
    detector.detect(loop2)
    assert detector.last_check.unclean_shutdown is True


# ── Edge cases ──


def test_no_state_attribute():
    class NoStateLoop:
        _traces = []
    ind = CrashDetector().detect(NoStateLoop())
    assert ind.unclean_shutdown is False


def test_empty_status_string():
    loop = MockRuntime(state=MockState(status=""))
    ind = CrashDetector().detect(loop)
    assert ind.unclean_shutdown is False


def test_no_traces_attribute():
    class NoTracesLoop:
        _state = MockState(status="stopped")
    ind = CrashDetector().detect(NoTracesLoop())
    assert ind.expected_trace_count == 0


def test_non_numeric_event_ids():
    traces = [make_trace("e_a"), make_trace("e_b"), make_trace("e_c")]
    loop = MockRuntime(traces=traces, state=MockState(status="stopped"))
    ind = CrashDetector().detect(loop)
    assert ind.gap_in_sequence is False
