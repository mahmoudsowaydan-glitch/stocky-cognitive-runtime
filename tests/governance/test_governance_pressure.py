import pytest

from cognitive_runtime.contracts.execution_trace import ExecutionTrace
from cognitive_runtime.governance.governance_pressure import GovernancePressure
from cognitive_runtime.governance.governance_report import PressureMetrics


def _make_trace(event_id="e1", p4_verdict="ALLOW", p4_rule_triggered=None):
    return ExecutionTrace(
        event_id=event_id, session_id="s1", sequence_no=1,
        correlation_id="c1",
        preflight_valid=True, preflight_reason="ok",
        risk_score=0.1,
        p4_verdict=p4_verdict, p4_reason="ok", p4_risk_level="low",
        p4_rule_triggered=p4_rule_triggered,
        execution_status="SUCCESS" if p4_verdict == "ALLOW" else "UNKNOWN",
        final_status=f"P4_{p4_verdict}",
    )


def test_pressure_empty_traces_produce_zero():
    p = GovernancePressure()
    result = p.analyze([])
    assert isinstance(result, PressureMetrics)
    assert result.rule_conflict_rate == 0.0
    assert result.p4_overload_rate == 0.0
    assert result.ambiguity_rate == 0.0
    assert result.escalation_rate == 0.0
    assert result.overall == 0.0


def test_pressure_all_allow_no_rule_triggered():
    p = GovernancePressure()
    result = p.analyze([_make_trace() for _ in range(10)])
    assert result.rule_conflict_rate == 0.0
    assert result.p4_overload_rate == 0.0
    assert result.overall == 0.0


def test_pressure_rule_conflict_rate_all_triggered():
    p = GovernancePressure()
    traces = [_make_trace(f"e{i}", p4_rule_triggered="rule_42") for i in range(5)]
    result = p.analyze(traces)
    assert result.rule_conflict_rate == 1.0


def test_pressure_rule_conflict_rate_some_triggered():
    p = GovernancePressure()
    traces = [_make_trace(f"e{i}", p4_rule_triggered="rule_42" if i < 3 else None) for i in range(10)]
    result = p.analyze(traces)
    assert result.rule_conflict_rate == pytest.approx(0.3)


def test_pressure_p4_overload_no_triggered():
    p = GovernancePressure()
    result = p.analyze([_make_trace() for _ in range(5)])
    assert result.p4_overload_rate == 0.0


def test_pressure_p4_overload_single_rule_repeated():
    p = GovernancePressure()
    traces = [_make_trace(f"e{i}", p4_rule_triggered="rule_42") for i in range(5)]
    result = p.analyze(traces)
    assert result.p4_overload_rate == min(1.0, (5 - 1) / 5)


def test_pressure_p4_overload_multiple_rules():
    p = GovernancePressure()
    traces = [
        _make_trace("e1", p4_rule_triggered="rule_a"),
        _make_trace("e2", p4_rule_triggered="rule_a"),
        _make_trace("e3", p4_rule_triggered="rule_a"),
        _make_trace("e4", p4_rule_triggered="rule_b"),
        _make_trace("e5", p4_rule_triggered="rule_b"),
    ]
    result = p.analyze(traces)
    assert result.p4_overload_rate == min(1.0, (3 - 1) / 5)


def test_pressure_ambiguity_rate_all_defer():
    p = GovernancePressure()
    traces = [_make_trace(f"e{i}", p4_verdict="DEFER") for i in range(4)]
    result = p.analyze(traces)
    assert result.ambiguity_rate == 1.0


def test_pressure_ambiguity_rate_all_review():
    p = GovernancePressure()
    traces = [_make_trace(f"e{i}", p4_verdict="REVIEW") for i in range(4)]
    result = p.analyze(traces)
    assert result.ambiguity_rate == 1.0


def test_pressure_ambiguity_rate_mixed():
    p = GovernancePressure()
    traces = [
        _make_trace("e1", p4_verdict="ALLOW"),
        _make_trace("e2", p4_verdict="DEFER"),
        _make_trace("e3", p4_verdict="ALLOW"),
        _make_trace("e4", p4_verdict="REVIEW"),
    ]
    result = p.analyze(traces)
    assert result.ambiguity_rate == 0.5


def test_pressure_escalation_rate_all_escalated():
    p = GovernancePressure()
    for verdict in ("BLOCK", "DEFER", "REVIEW"):
        traces = [_make_trace(f"e{i}", p4_verdict=verdict) for i in range(3)]
        result = p.analyze(traces)
        assert result.escalation_rate == 1.0


def test_pressure_escalation_rate_none():
    p = GovernancePressure()
    result = p.analyze([_make_trace() for _ in range(5)])
    assert result.escalation_rate == 0.0


def test_pressure_overall_weighted_and_capped():
    p = GovernancePressure()
    traces = [
        _make_trace("e1", p4_verdict="BLOCK", p4_rule_triggered="rule_x"),
        _make_trace("e2", p4_verdict="DEFER", p4_rule_triggered="rule_x"),
        _make_trace("e3", p4_verdict="ALLOW"),
    ]
    result = p.analyze(traces)
    expected = (
        0.30 * result.rule_conflict_rate
        + 0.30 * result.p4_overload_rate
        + 0.25 * result.ambiguity_rate
        + 0.15 * result.escalation_rate
    )
    assert result.overall == round(min(1.0, expected), 4)
    assert result.overall <= 1.0


def test_pressure_rounding_to_4_places():
    p = GovernancePressure()
    traces = [_make_trace(f"e{i}", p4_rule_triggered="rule_a") for i in range(3)]
    result = p.analyze(traces)
    for val in (result.rule_conflict_rate, result.p4_overload_rate, result.ambiguity_rate, result.escalation_rate, result.overall):
        s = str(val)
        if "." in s:
            assert len(s.split(".")[1]) <= 4


def test_pressure_p4_overload_single_element():
    p = GovernancePressure()
    traces = [_make_trace("e1", p4_rule_triggered="rule_x")]
    result = p.analyze(traces)
    assert result.p4_overload_rate == 0.0
