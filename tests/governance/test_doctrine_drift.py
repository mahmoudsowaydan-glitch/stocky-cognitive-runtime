import pytest

from cognitive_runtime.contracts.execution_trace import ExecutionTrace
from cognitive_runtime.runtime.coherence_monitor import CoherenceReport
from cognitive_runtime.governance.doctrine_drift import DoctrineDrift
from cognitive_runtime.governance.governance_report import DriftMetrics


def _make_trace(event_id="e1", preflight_valid=True, p4_verdict="ALLOW", risk_score=0.1):
    return ExecutionTrace(
        event_id=event_id, session_id="s1", sequence_no=1,
        correlation_id="c1",
        preflight_valid=preflight_valid, preflight_reason="ok",
        risk_score=risk_score,
        p4_verdict=p4_verdict, p4_reason="ok", p4_risk_level="low",
        execution_status="SUCCESS",
        final_status=f"P4_{p4_verdict}" if p4_verdict in ("ALLOW", "BLOCK") else "UNKNOWN",
    )


def test_drift_empty_traces_produce_baseline_drift():
    drift = DoctrineDrift()
    result = drift.analyze([], [])
    assert isinstance(result, DriftMetrics)
    assert result.preflight_overreach == 0.0
    assert result.p4_avoidance == 0.0
    assert result.risk_influence == 0.0
    assert result.coherence_drift_rate == 0.0
    assert result.overall == 0.0


def test_drift_all_allow_traces_low_drift():
    drift = DoctrineDrift()
    result = drift.analyze([_make_trace() for _ in range(10)], [])
    assert result.overall == 0.0


def test_drift_preflight_overreach_with_blocked_traces():
    drift = DoctrineDrift()
    traces = [_make_trace(event_id=f"e{i}", preflight_valid=False) for i in range(5)]
    result = drift.analyze(traces, [])
    assert result.preflight_overreach == 1.0
    assert result.overall > 0


def test_drift_preflight_overreach_mixed():
    drift = DoctrineDrift()
    traces = [_make_trace(event_id=f"e{i}", preflight_valid=(i > 2)) for i in range(10)]
    result = drift.analyze(traces, [])
    assert result.preflight_overreach == pytest.approx(0.3)


def test_drift_p4_avoidance_with_non_allow():
    drift = DoctrineDrift()
    traces = [_make_trace(event_id=f"e{i}", p4_verdict="BLOCK") for i in range(5)]
    result = drift.analyze(traces, [])
    assert result.p4_avoidance == 1.0


def test_drift_p4_avoidance_mixed():
    drift = DoctrineDrift()
    traces = [
        _make_trace(event_id=f"e{i}", p4_verdict="ALLOW" if i < 6 else "BLOCK")
        for i in range(8)
    ]
    result = drift.analyze(traces, [])
    assert result.p4_avoidance == pytest.approx(0.25)


def test_drift_risk_influence_no_blocked():
    drift = DoctrineDrift()
    result = drift.analyze([_make_trace() for _ in range(5)], [])
    assert result.risk_influence == 0.0


def test_drift_risk_influence_with_high_risk_blocked():
    drift = DoctrineDrift()
    traces = [
        _make_trace("e1", p4_verdict="BLOCK", risk_score=0.8),
        _make_trace("e2", p4_verdict="BLOCK", risk_score=0.3),
        _make_trace("e3", p4_verdict="BLOCK", risk_score=0.9),
    ]
    result = drift.analyze(traces, [])
    assert result.risk_influence == round(2 / 3, 4)


def test_drift_risk_influence_with_defer():
    drift = DoctrineDrift()
    traces = [
        _make_trace("e1", p4_verdict="DEFER", risk_score=0.9),
        _make_trace("e2", p4_verdict="ALLOW", risk_score=0.1),
    ]
    result = drift.analyze(traces, [])
    assert result.risk_influence == 1.0


def test_drift_coherence_drift_few_reports():
    drift = DoctrineDrift()
    reports = [CoherenceReport(drift_detected=False, drift_count=1) for _ in range(3)]
    result = drift.analyze([_make_trace()], reports)
    assert result.coherence_drift_rate == 0.0


def test_drift_coherence_drift_exactly_5():
    drift = DoctrineDrift()
    reports = [CoherenceReport(drift_detected=True, drift_count=c) for c in (0, 1, 2, 3, 4)]
    result = drift.analyze([_make_trace()], reports)
    total_drift = 0 + 1 + 2 + 3 + 4
    assert result.coherence_drift_rate == min(1.0, total_drift / 5)


def test_drift_coherence_drift_uses_last_5():
    drift = DoctrineDrift()
    reports = [CoherenceReport(drift_detected=True, drift_count=c) for c in range(10)]
    result = drift.analyze([_make_trace()], reports)
    recent = reports[-5:]
    total_drift = sum(r.drift_count for r in recent)
    assert result.coherence_drift_rate == min(1.0, total_drift / 5)


def test_drift_overall_weighted_sum():
    drift = DoctrineDrift()
    traces = [
        _make_trace("e1", preflight_valid=False),
        _make_trace("e2", p4_verdict="BLOCK", risk_score=0.9),
        _make_trace("e3", p4_verdict="BLOCK", risk_score=0.8),
    ]
    result = drift.analyze(traces, [])
    expected = (
        0.30 * result.preflight_overreach
        + 0.30 * result.p4_avoidance
        + 0.20 * result.risk_influence
        + 0.20 * result.coherence_drift_rate
    )
    assert result.overall == round(expected, 4)


def test_drift_overall_capped_and_rounded():
    drift = DoctrineDrift()
    traces = [_make_trace(f"e{i}", preflight_valid=False, p4_verdict="BLOCK") for i in range(5)]
    result = drift.analyze(traces, [])
    assert result.overall <= 1.0
    s = str(result.overall)
    if "." in s:
        assert len(s.split(".")[1]) <= 4


def test_drift_rounding_precision():
    drift = DoctrineDrift()
    traces = [_make_trace(f"e{i}", preflight_valid=(i != 0)) for i in range(3)]
    result = drift.analyze(traces, [])
    for val in (result.preflight_overreach, result.p4_avoidance, result.risk_influence, result.coherence_drift_rate, result.overall):
        s = str(val)
        if "." in s:
            assert len(s.split(".")[1]) <= 4
