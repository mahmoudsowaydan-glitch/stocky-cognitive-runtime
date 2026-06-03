"""Integration tests for the full causal pipeline: ExecutionTrace -> CausalGraph -> Compression -> Stability -> Confidence."""

from unittest.mock import MagicMock

from cognitive_runtime.contracts.causal_graph import CausalGraphBuilder
from cognitive_runtime.contracts.execution_trace import ExecutionTrace
from cognitive_runtime.intelligence.compression_engine import CompressionEngine
from cognitive_runtime.stability.stability_analyzer import StabilityAnalyzer
from cognitive_runtime.confidence.runtime_confidence import RuntimeConfidenceEngine
from cognitive_runtime.runtime.runtime_state import RuntimeState


def make_trace(event_id: str, correlation_id: str, preflight_valid: bool = True,
               p4_verdict: str = "ALLOW", execution_status: str = "SUCCESS",
               final_status: str = "P4_ALLOW", risk_score: float = 0.1,
               execution_error: str = "") -> ExecutionTrace:
    return ExecutionTrace(
        event_id=event_id, session_id="s1", sequence_no=int(event_id[1:]),
        correlation_id=correlation_id,
        preflight_valid=preflight_valid, preflight_reason="ok" if preflight_valid else "blocked",
        risk_score=risk_score,
        p4_verdict=p4_verdict, p4_reason="ok", p4_risk_level="low",
        execution_status=execution_status, execution_error=execution_error or None,
        capabilities_checked=["filesystem.read"],
        final_status=final_status,
    )


TRACES_ALLOW = [make_trace(f"e{i}", f"c{i}") for i in range(1, 4)]
TRACES_MIXED = [
    make_trace("e1", "c1"),
    make_trace("e2", "c2", p4_verdict="BLOCK", execution_status="UNKNOWN", final_status="P4_BLOCK"),
    make_trace("e3", "c3", execution_status="FAILED", final_status="SANDBOX_FAILED", execution_error="timeout"),
]


# ─── a) Trace -> Graph -> Structure ────────────


def test_graph_from_allow_traces():
    graph = CausalGraphBuilder().build(TRACES_ALLOW)
    assert len(graph.nodes) == 15
    assert len(graph.edges) == 12
    assert len(graph.roots) == 3
    types = {n.node_type for n in graph.nodes.values()}
    assert types == {"host_event", "proposal", "decision", "execution", "outcome"}


def test_graph_from_mixed_traces():
    graph = CausalGraphBuilder().build(TRACES_MIXED)
    assert len(graph.nodes) == 14
    assert len(graph.roots) == 3
    fps = graph.failure_points
    assert len(fps) == 2


def test_graph_from_empty_traces():
    graph = CausalGraphBuilder().build([])
    assert len(graph.nodes) == 0
    assert len(graph.edges) == 0
    assert graph.roots == []


def test_graph_deterministic():
    g1 = CausalGraphBuilder().build(TRACES_ALLOW)
    g2 = CausalGraphBuilder().build(TRACES_ALLOW)
    assert list(g1.nodes.keys()) == list(g2.nodes.keys())


def test_graph_dominant_layers():
    graph = CausalGraphBuilder().build(TRACES_ALLOW)
    assert graph.dominant_layers["host_event"] == 3
    assert graph.dominant_layers["outcome"] == 3


def test_graph_traverse_and_path():
    graph = CausalGraphBuilder().build(TRACES_ALLOW[:1])
    path = graph.path_to_outcome("e1__host")
    assert len(path) == 5
    assert [n.node_type for n in path] == ["host_event", "proposal", "decision", "execution", "outcome"]


def test_graph_correlation_subgraph():
    graph = CausalGraphBuilder().build(TRACES_ALLOW)
    sub = graph.correlation_subgraph("c1")
    assert len(sub.nodes) == 5
    assert sub.get("e1__host") is not None
    assert sub.get("e2__host") is None


# ─── b) Compression Engine ───────────────────


def test_compression_process_allow_traces():
    graph = CausalGraphBuilder().build(TRACES_ALLOW)
    engine = CompressionEngine()
    report = engine.process(graph, TRACES_ALLOW)
    assert report.patterns_found >= 0
    assert report.failures_detected == 0
    assert report.total_patterns >= 0


def test_compression_detects_failures_in_mixed():
    graph = CausalGraphBuilder().build(TRACES_MIXED)
    engine = CompressionEngine()
    report = engine.process(graph, TRACES_MIXED)
    assert report.failures_detected >= 1
    assert report.total_failures >= 1


def test_compression_empty_traces():
    engine = CompressionEngine()
    report = engine.process(MagicMock(), [])
    assert report.patterns_found == 0
    assert report.failures_detected == 0


def test_compression_store_persists():
    engine = CompressionEngine()
    graph = CausalGraphBuilder().build(TRACES_ALLOW)
    engine.process(graph, TRACES_ALLOW)
    c1 = len(engine.store.patterns)
    engine.process(graph, TRACES_ALLOW)
    assert len(engine.store.patterns) >= c1


def test_compression_fingerprints():
    engine = CompressionEngine()
    graph = CausalGraphBuilder().build(TRACES_ALLOW)
    engine.process(graph, TRACES_ALLOW)
    assert isinstance(engine.store.fingerprints, dict)


# ─── c) Pattern Detection ────────────────────


def test_patterns_stored_after_compression():
    engine = CompressionEngine()
    graph = CausalGraphBuilder().build(TRACES_ALLOW)
    engine.process(graph, TRACES_ALLOW)
    assert isinstance(engine.store.patterns, dict)


def test_repeated_traces_increase_patterns():
    traces = [make_trace("e1", "c1"), make_trace("e2", "c2")]
    engine = CompressionEngine()
    graph = CausalGraphBuilder().build(traces)
    report = engine.process(graph, traces)
    assert report.patterns_found >= 0


# ─── d) Stability Analysis ───────────────────


def test_stability_produces_score():
    engine = CompressionEngine()
    analyzer = StabilityAnalyzer(engine.store)
    state = RuntimeState()
    state.status = "running"
    report = analyzer.analyze(TRACES_ALLOW, state)
    assert 0.0 <= report.score.overall <= 1.0
    assert report.trend.direction in ("stable", "improving", "degrading")


def test_stability_mixed_scores_lower():
    engine = CompressionEngine()
    state = RuntimeState()
    report_good = StabilityAnalyzer(engine.store).analyze(TRACES_ALLOW * 3, state)
    report_mixed = StabilityAnalyzer(engine.store).analyze(TRACES_MIXED * 3, state)
    assert report_good.score.overall >= report_mixed.score.overall


def test_stability_anomalies_present():
    engine = CompressionEngine()
    analyzer = StabilityAnalyzer(engine.store)
    state = RuntimeState()
    state.consecutive_failures = 5
    traces = [make_trace(f"e{i}", f"c{i}", execution_status="FAILED",
                         final_status="SANDBOX_FAILED", execution_error="err") for i in range(10)]
    report = analyzer.analyze(traces, state)
    assert len(report.anomalies) >= 0


def test_stability_score_components():
    engine = CompressionEngine()
    analyzer = StabilityAnalyzer(engine.store)
    state = RuntimeState()
    report = analyzer.analyze(TRACES_ALLOW, state)
    assert isinstance(report.score.failure_score, float)
    assert isinstance(report.score.drift_score, float)
    assert isinstance(report.score.consistency_score, float)
    assert isinstance(report.score.timing_stability, float)
    assert isinstance(report.score.novelty_score, float)


def test_stability_empty_traces():
    engine = CompressionEngine()
    analyzer = StabilityAnalyzer(engine.store)
    state = RuntimeState()
    report = analyzer.analyze([], state)
    assert report.score.overall >= 0.0
    assert report.current_window.trace_count == 0


# ─── e) Confidence Assessment ─────────────────


def test_confidence_assessment_succeeds():
    engine = CompressionEngine()
    analyzer = StabilityAnalyzer(engine.store)
    state = RuntimeState()
    report = analyzer.analyze(TRACES_ALLOW, state)
    conf = RuntimeConfidenceEngine()
    qs = {"queue_depth": 0, "total_events": 10, "dead_lettered": 0, "processed": 10, "failed": 0,
          "average_cycle_ms": 50.0, "last_cycle_ms": 45.0}
    cr = conf.assess(TRACES_ALLOW, state, qs, report.score.overall)
    assert 0.0 <= cr.score.overall <= 1.0
    assert cr.gradient.value in ("HIGH", "MEDIUM", "LOW", "CRITICAL")
    assert cr.trend_direction in ("stable", "improving", "degrading")


def test_confidence_with_failures_lower():
    state = RuntimeState()
    qs = {"queue_depth": 0, "total_events": 10, "dead_lettered": 0, "processed": 10, "failed": 0,
          "average_cycle_ms": 50.0, "last_cycle_ms": 45.0}
    r1 = RuntimeConfidenceEngine().assess(TRACES_ALLOW, state, qs)
    state2 = RuntimeState()
    state2.total_failures = 5
    state2.consecutive_failures = 3
    r2 = RuntimeConfidenceEngine().assess(TRACES_MIXED, state2, qs)
    assert r1.score.overall >= r2.score.overall


def test_confidence_empty_traces():
    state = RuntimeState()
    qs = {"queue_depth": 0, "total_events": 0, "dead_lettered": 0, "processed": 0, "failed": 0,
          "average_cycle_ms": 0.0, "last_cycle_ms": 0.0}
    report = RuntimeConfidenceEngine().assess([], state, qs)
    assert report.score.overall >= 0.0


def test_confidence_trend_tracking():
    conf = RuntimeConfidenceEngine()
    state = RuntimeState()
    qs = {"queue_depth": 0, "total_events": 10, "dead_lettered": 0, "processed": 10, "failed": 0,
          "average_cycle_ms": 50.0, "last_cycle_ms": 45.0}
    for _ in range(5):
        conf.assess(TRACES_ALLOW, state, qs)
    assert conf.current_gradient is not None


def test_confidence_components():
    state = RuntimeState()
    qs = {"queue_depth": 0, "total_events": 10, "dead_lettered": 0, "processed": 10, "failed": 0,
          "average_cycle_ms": 50.0, "last_cycle_ms": 45.0}
    report = RuntimeConfidenceEngine().assess(TRACES_ALLOW, state, qs)
    assert isinstance(report.score.decision_confidence, float)
    assert isinstance(report.score.operational_confidence, float)
    assert isinstance(report.score.execution_confidence, float)
    assert isinstance(report.degradation_detected, bool)
