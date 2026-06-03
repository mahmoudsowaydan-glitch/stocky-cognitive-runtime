"""Diagnostic: Queue starvation — tests crash detector under event delivery gaps."""

from unittest.mock import MagicMock

from cognitive_runtime.recovery.crash_detector import CrashDetector
from cognitive_runtime.contracts.execution_trace import ExecutionTrace


def make_trace(eid: str, status: str = "P4_ALLOW") -> ExecutionTrace:
    return ExecutionTrace(
        event_id=eid, session_id="s1", sequence_no=int(eid[1:]),
        correlation_id=f"c{eid[1:]}",
        preflight_valid=True, preflight_reason="ok",
        risk_score=0.1,
        p4_verdict="ALLOW", p4_reason="ok", p4_risk_level="low",
        execution_status="SUCCESS",
        final_status=status,
    )


def test_starvation_detected_as_orphan_traces():
    detector = CrashDetector()
    state = MagicMock()
    state.status = "stopped"
    state.health_status = "healthy"
    queue = MagicMock()
    queue.stats.processed = 2
    traces = [make_trace("e0"), make_trace("e1"), make_trace("e2"), make_trace("e3")]
    loop = MagicMock()
    loop._traces = traces
    loop._state = state
    loop._queue = queue
    result = detector.detect(loop)
    assert result.orphan_traces > 0


def test_no_starvation_with_matched_counts():
    detector = CrashDetector()
    state = MagicMock()
    state.status = "stopped"
    state.health_status = "healthy"
    queue = MagicMock()
    queue.stats.processed = 3
    traces = [make_trace("e0"), make_trace("e1"), make_trace("e2")]
    loop = MagicMock()
    loop._traces = traces
    loop._state = state
    loop._queue = queue
    result = detector.detect(loop)
    assert result.orphan_traces == 0


def test_starvation_does_not_false_positive_on_empty():
    detector = CrashDetector()
    state = MagicMock()
    state.status = "stopped"
    state.health_status = "healthy"
    queue = MagicMock()
    queue.stats.processed = 0
    loop = MagicMock()
    loop._traces = []
    loop._state = state
    loop._queue = queue
    result = detector.detect(loop)
    assert not result.unclean_shutdown


def test_starvation_with_backpressure_survives():
    detector = CrashDetector()
    state = MagicMock()
    state.status = "running"
    state.health_status = "degraded"
    queue = MagicMock()
    queue.stats.processed = 10
    traces = [make_trace(f"e{i}") for i in range(15)]
    loop = MagicMock()
    loop._traces = traces
    loop._state = state
    loop._queue = queue
    result = detector.detect(loop)
    assert result.orphan_traces == 5
