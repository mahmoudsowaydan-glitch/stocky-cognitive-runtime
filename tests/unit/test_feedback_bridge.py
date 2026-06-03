import pytest

from cognitive_runtime.contracts.causal_graph import (
    CausalGraph,
    CausalNode,
    CausalEdge,
    CausalGraphBuilder,
)
from cognitive_runtime.runtime.feedback_bridge import FeedbackBridge, FeedbackInsight, FeedbackReport


def test_feedback_insight_creation():
    insight = FeedbackInsight(
        insight_type="layer_dominance",
        description="execution dominates",
        severity="info",
        data={"layer": "execution", "percentage": 60},
    )
    assert insight.insight_type == "layer_dominance"
    assert insight.description == "execution dominates"
    assert insight.severity == "info"
    assert insight.data == {"layer": "execution", "percentage": 60}


def test_feedback_insight_default_data():
    insight = FeedbackInsight(
        insight_type="test", description="test", severity="info",
    )
    assert insight.data == {}


def test_feedback_report_defaults():
    r = FeedbackReport()
    assert r.insights == []
    assert r.failure_clusters == []
    assert r.dominant_layer_trends == {}


def test_analyze_empty_graph():
    bridge = FeedbackBridge()
    graph = CausalGraph({}, [])
    report = bridge.analyze(graph)
    assert report.insights == []
    assert report.failure_clusters == []
    assert report.dominant_layer_trends == {}


def test_dominance_insight_when_layer_exceeds_50_pct():
    n1 = CausalNode(
        node_id="n1", event_id="e1", correlation_id="c1",
        node_type="host_event", data={}, timestamp=0.0,
    )
    n2 = CausalNode(
        node_id="n2", event_id="e1", correlation_id="c1",
        node_type="host_event", data={}, timestamp=0.0,
    )
    n3 = CausalNode(
        node_id="n3", event_id="e1", correlation_id="c1",
        node_type="execution", data={}, timestamp=0.0,
    )
    graph = CausalGraph({"n1": n1, "n2": n2, "n3": n3}, [])
    bridge = FeedbackBridge()
    report = bridge.analyze(graph)
    assert "layer_dominance" in [i.insight_type for i in report.insights]
    assert report.dominant_layer_trends == {"host_event": 2, "execution": 1}


def test_no_dominance_when_no_layer_exceeds_50_pct():
    n1 = CausalNode(
        node_id="n1", event_id="e1", correlation_id="c1",
        node_type="host_event", data={}, timestamp=0.0,
    )
    n2 = CausalNode(
        node_id="n2", event_id="e1", correlation_id="c1",
        node_type="execution", data={}, timestamp=0.0,
    )
    graph = CausalGraph({"n1": n1, "n2": n2}, [])
    bridge = FeedbackBridge()
    report = bridge.analyze(graph)
    assert "layer_dominance" not in [i.insight_type for i in report.insights]


def test_failure_clusters_with_failure_points():
    n_fail = CausalNode(
        node_id="n1", event_id="e1", correlation_id="c1",
        node_type="outcome",
        data={"final_status": "failed", "reason": "execution_error"},
        timestamp=0.0,
    )
    n_block = CausalNode(
        node_id="n2", event_id="e2", correlation_id="c2",
        node_type="outcome",
        data={"final_status": "blocked", "reason": "policy"},
        timestamp=0.0,
    )
    n_ok = CausalNode(
        node_id="n3", event_id="e3", correlation_id="c3",
        node_type="outcome", data={"final_status": "success"},
        timestamp=0.0,
    )
    graph = CausalGraph({"n1": n_fail, "n2": n_block, "n3": n_ok}, [])
    bridge = FeedbackBridge()
    report = bridge.analyze(graph)
    assert len(report.failure_clusters) > 0
    assert "failure_cluster" in [i.insight_type for i in report.insights]


def test_no_failure_clusters_when_all_success():
    n = CausalNode(
        node_id="n1", event_id="e1", correlation_id="c1",
        node_type="outcome", data={"final_status": "success"},
        timestamp=0.0,
    )
    graph = CausalGraph({"n1": n}, [])
    bridge = FeedbackBridge()
    report = bridge.analyze(graph)
    assert report.failure_clusters == []


def test_sandbox_enforcement_insight():
    n_ok = CausalNode(
        node_id="n1", event_id="e1", correlation_id="c1",
        node_type="execution", data={"status": "SUCCESS"}, timestamp=0.0,
    )
    n_bad = CausalNode(
        node_id="n2", event_id="e2", correlation_id="c2",
        node_type="execution", data={"status": "FAILED"}, timestamp=0.0,
    )
    n_host = CausalNode(
        node_id="n3", event_id="e1", correlation_id="c1",
        node_type="host_event", data={}, timestamp=0.0,
    )
    graph = CausalGraph({"n1": n_ok, "n2": n_bad, "n3": n_host}, [])
    bridge = FeedbackBridge()
    report = bridge.analyze(graph)
    assert "sandbox_enforcement_active" in [i.insight_type for i in report.insights]


def test_no_sandbox_insight_when_all_success():
    n = CausalNode(
        node_id="n1", event_id="e1", correlation_id="c1",
        node_type="execution", data={"status": "SUCCESS"}, timestamp=0.0,
    )
    graph = CausalGraph({"n1": n}, [])
    bridge = FeedbackBridge()
    report = bridge.analyze(graph)
    assert "sandbox_enforcement_active" not in [i.insight_type for i in report.insights]


def test_preflight_blocking_insight():
    n_blocked = CausalNode(
        node_id="n1", event_id="e1", correlation_id="c1",
        node_type="blocked",
        data={"verdict": "BLOCKED", "reason": "invalid_payload"},
        timestamp=0.0,
    )
    graph = CausalGraph({"n1": n_blocked}, [])
    bridge = FeedbackBridge()
    report = bridge.analyze(graph)
    assert "preflight_blocking" in [i.insight_type for i in report.insights]


def test_no_preflight_blocking_insight():
    n_blocked = CausalNode(
        node_id="n1", event_id="e1", correlation_id="c1",
        node_type="blocked",
        data={"verdict": "BLOCK", "reason": "p4_blocked"},
        timestamp=0.0,
    )
    graph = CausalGraph({"n1": n_blocked}, [])
    bridge = FeedbackBridge()
    report = bridge.analyze(graph)
    assert "preflight_blocking" not in [i.insight_type for i in report.insights]


def test_bridge_history_accumulates():
    bridge = FeedbackBridge()
    bridge.analyze(CausalGraph({}, []))
    bridge.analyze(CausalGraph({}, []))
    assert len(bridge.history) == 2


def test_bridge_history_returns_copy():
    bridge = FeedbackBridge()
    bridge.analyze(CausalGraph({}, []))
    h = bridge.history
    h.clear()
    assert len(bridge.history) == 1
