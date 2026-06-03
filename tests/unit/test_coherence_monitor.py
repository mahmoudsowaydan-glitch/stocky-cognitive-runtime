import pytest

from cognitive_runtime.contracts.execution_trace import ExecutionTrace
from cognitive_runtime.contracts.causal_graph import CausalGraph, CausalNode, CausalEdge
from cognitive_runtime.runtime.coherence_monitor import CoherenceMonitor, CoherenceReport


def test_coherence_report_defaults():
    r = CoherenceReport()
    assert r.drift_detected is False
    assert r.drift_count == 0
    assert r.warnings == []
    assert r.inconsistencies == []


def test_check_trace_normal():
    monitor = CoherenceMonitor()
    trace = ExecutionTrace(
        event_id="e1", session_id="s1",
        preflight_valid=True,
        risk_score=0.1,
        p4_verdict="ALLOW",
        execution_status="SUCCESS",
    )
    report = monitor.check_trace(trace)
    assert report.drift_detected is False
    assert report.drift_count == 0
    assert report.warnings == []


def test_rule1_preflight_valid_p4_blocked():
    monitor = CoherenceMonitor()
    trace = ExecutionTrace(
        event_id="e1", session_id="s1",
        preflight_valid=True,
        p4_verdict="BLOCK",
    )
    report = monitor.check_trace(trace)
    assert report.drift_count == 1
    assert report.drift_detected is True
    assert any("preflight_passed_but_p4_blocked" in w for w in report.warnings)
    assert len(report.inconsistencies) == 1
    assert report.inconsistencies[0]["type"] == "preflight_p4_mismatch"


def test_rule1_preflight_valid_p4_deferred():
    monitor = CoherenceMonitor()
    trace = ExecutionTrace(
        event_id="e1", session_id="s1",
        preflight_valid=True,
        p4_verdict="DEFER",
    )
    report = monitor.check_trace(trace)
    assert report.drift_count == 1


def test_rule1_preflight_valid_p4_allow_no_drift():
    monitor = CoherenceMonitor()
    trace = ExecutionTrace(event_id="e1", preflight_valid=True, p4_verdict="ALLOW")
    assert monitor.check_trace(trace).drift_count == 0


def test_rule2_p4_allow_sandbox_failed():
    monitor = CoherenceMonitor()
    trace = ExecutionTrace(
        event_id="e1", session_id="s1",
        preflight_valid=True,
        p4_verdict="ALLOW",
        execution_status="FAILED",
        execution_error="crash",
    )
    report = monitor.check_trace(trace)
    assert report.drift_count == 1
    assert report.drift_detected is True
    assert any("p4_allowed_but_sandbox_failed" in w for w in report.warnings)
    assert report.inconsistencies[0]["type"] == "p4_sandbox_mismatch"
    assert report.inconsistencies[0]["error"] == "crash"


def test_rule2_p4_block_sandbox_failed_no_drift():
    monitor = CoherenceMonitor()
    trace = ExecutionTrace(event_id="e1", p4_verdict="BLOCK", execution_status="FAILED")
    assert monitor.check_trace(trace).drift_count == 0


def test_rule3_high_risk_p4_allow_warning():
    monitor = CoherenceMonitor()
    trace = ExecutionTrace(
        event_id="e1", session_id="s1",
        risk_score=0.85,
        p4_verdict="ALLOW",
    )
    report = monitor.check_trace(trace)
    assert any("high_risk_allowed_by_p4" in w for w in report.warnings)
    assert report.drift_count == 0


def test_rule3_risk_0_8_no_warning():
    monitor = CoherenceMonitor()
    trace = ExecutionTrace(event_id="e1", risk_score=0.8, p4_verdict="ALLOW")
    assert monitor.check_trace(trace).drift_count == 0


def test_rule3_high_risk_p4_block_no_warning():
    monitor = CoherenceMonitor()
    trace = ExecutionTrace(event_id="e1", risk_score=0.9, p4_verdict="BLOCK")
    report = monitor.check_trace(trace)
    assert not any("high_risk_allowed_by_p4" in w for w in report.warnings)


def test_rule4_extreme_risk_not_blocked():
    monitor = CoherenceMonitor()
    trace = ExecutionTrace(
        event_id="e1", session_id="s1",
        preflight_valid=True,
        risk_score=0.95,
        p4_verdict="ALLOW",
    )
    report = monitor.check_trace(trace)
    assert report.drift_count == 1
    assert report.drift_detected is True
    assert any("extreme_risk_not_blocked" in w for w in report.warnings)


def test_rule4_risk_0_9_no_drift():
    monitor = CoherenceMonitor()
    trace = ExecutionTrace(
        event_id="e1",
        preflight_valid=True,
        risk_score=0.9,
        p4_verdict="ALLOW",
    )
    assert monitor.check_trace(trace).drift_count == 0


def test_rule4_extreme_risk_no_preflight_no_drift():
    monitor = CoherenceMonitor()
    trace = ExecutionTrace(
        event_id="e1",
        preflight_valid=False,
        risk_score=0.95,
        p4_verdict="ALLOW",
    )
    assert monitor.check_trace(trace).drift_count == 0


def test_check_causal_graph_no_failures():
    monitor = CoherenceMonitor()
    n = CausalNode(
        node_id="n1", event_id="e1", correlation_id="c1",
        node_type="outcome", data={"final_status": "success"}, timestamp=0.0,
    )
    graph = CausalGraph({"n1": n}, [])
    report = monitor.check_causal_graph(graph)
    assert report.drift_detected is False


def test_check_causal_graph_with_failures_and_decision_dominant():
    monitor = CoherenceMonitor()
    n_fail = CausalNode(
        node_id="n1", event_id="e1", correlation_id="c1",
        node_type="outcome", data={"final_status": "failed"}, timestamp=0.0,
    )
    n_ok = CausalNode(
        node_id="n2", event_id="e2", correlation_id="c2",
        node_type="decision", data={}, timestamp=0.0,
    )
    graph = CausalGraph({"n1": n_fail, "n2": n_ok}, [])
    report = monitor.check_causal_graph(graph)
    assert any("failure_under_p4_dominant" in w for w in report.warnings)


def test_report_property():
    monitor = CoherenceMonitor()
    trace = ExecutionTrace(event_id="e1", preflight_valid=True, p4_verdict="BLOCK")
    report = monitor.check_trace(trace)
    assert monitor.report is report


def test_history_property():
    monitor = CoherenceMonitor()
    t1 = ExecutionTrace(event_id="e1", preflight_valid=True, p4_verdict="BLOCK")
    t2 = ExecutionTrace(event_id="e2", p4_verdict="ALLOW", execution_status="FAILED")
    r1 = monitor.check_trace(t1)
    r2 = monitor.check_trace(t2)
    assert len(monitor.history) == 2
    assert monitor.history[0] is r1
    assert monitor.history[1] is r2


def test_history_returns_copy():
    monitor = CoherenceMonitor()
    trace = ExecutionTrace(event_id="e1", preflight_valid=True, p4_verdict="BLOCK")
    monitor.check_trace(trace)
    h = monitor.history
    h.clear()
    assert len(monitor.history) == 1


def test_reset():
    monitor = CoherenceMonitor()
    trace = ExecutionTrace(event_id="e1", preflight_valid=True, p4_verdict="BLOCK")
    monitor.check_trace(trace)
    assert monitor.report.drift_detected is True
    monitor.reset()
    assert monitor.report.drift_detected is False
    assert monitor.report.drift_count == 0
    assert monitor.history == []
