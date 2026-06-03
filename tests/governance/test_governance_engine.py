import pytest

from cognitive_runtime.contracts.execution_trace import ExecutionTrace
from cognitive_runtime.contracts.causal_graph import CausalGraph
from cognitive_runtime.intelligence.intelligence_store import IntelligenceStore
from cognitive_runtime.runtime.runtime_state import RuntimeState
from cognitive_runtime.runtime.coherence_monitor import CoherenceMonitor
from cognitive_runtime.stability.stability_analyzer import StabilityAnalyzer
from cognitive_runtime.confidence.runtime_confidence import RuntimeConfidenceEngine
from cognitive_runtime.governance.governance_engine import GovernanceEngine
from cognitive_runtime.governance.governance_report import GovernanceReport, DecaySignal


@pytest.fixture
def sample_traces():
    return [
        ExecutionTrace(
            event_id=f"e{i}", session_id="s1", sequence_no=i,
            correlation_id=f"c{i}",
            preflight_valid=True, preflight_reason="ok",
            risk_score=0.1,
            p4_verdict="ALLOW", p4_reason="ok", p4_risk_level="low",
            execution_status="SUCCESS",
            final_status="P4_ALLOW",
        ) for i in range(10)
    ]


@pytest.fixture
def bad_traces():
    return [
        ExecutionTrace(
            event_id=f"e{i}", session_id="s1", sequence_no=i,
            correlation_id=f"c{i}",
            preflight_valid=False, preflight_reason="failed",
            risk_score=0.9,
            p4_verdict="BLOCK", p4_reason="violation", p4_risk_level="high",
            p4_rule_triggered="rule_42",
            execution_status="FAILED",
            execution_error="crash",
            final_status="SANDBOX_FAILED",
        ) for i in range(10)
    ]


@pytest.fixture
def minimal_graph():
    return CausalGraph({}, [])


@pytest.fixture
def runtime_state():
    return RuntimeState(status="running", started_at=100.0)


@pytest.fixture
def intelligence_store():
    return IntelligenceStore()


@pytest.fixture
def coherence_monitor():
    mon = CoherenceMonitor()
    for _ in range(5):
        mon.check_trace(ExecutionTrace(
            event_id="e1", session_id="s1", sequence_no=1,
            correlation_id="c1",
            preflight_valid=True, preflight_reason="ok",
            risk_score=0.1,
            p4_verdict="ALLOW", p4_reason="ok", p4_risk_level="low",
            execution_status="SUCCESS",
            final_status="P4_ALLOW",
        ))
    return mon


@pytest.fixture
def stability_analyzer(intelligence_store, runtime_state):
    analyzer = StabilityAnalyzer(intelligence_store)
    trace = ExecutionTrace(
        event_id="e1", session_id="s1", sequence_no=1,
        correlation_id="c1",
        preflight_valid=True, preflight_reason="ok",
        risk_score=0.1,
        p4_verdict="ALLOW", p4_reason="ok", p4_risk_level="low",
        execution_status="SUCCESS",
        final_status="P4_ALLOW",
    )
    for _ in range(5):
        analyzer.analyze([trace], runtime_state)
    return analyzer


@pytest.fixture
def confidence_engine():
    return RuntimeConfidenceEngine()


def test_assess_returns_governance_report(sample_traces, minimal_graph, runtime_state,
                                          intelligence_store, coherence_monitor,
                                          stability_analyzer):
    engine = GovernanceEngine()
    report = engine.assess(sample_traces, runtime_state, minimal_graph,
                           intelligence_store, coherence_monitor, stability_analyzer)
    assert isinstance(report, GovernanceReport)


def test_assess_populates_all_fields(sample_traces, minimal_graph, runtime_state,
                                     intelligence_store, coherence_monitor,
                                     stability_analyzer):
    engine = GovernanceEngine()
    report = engine.assess(sample_traces, runtime_state, minimal_graph,
                           intelligence_store, coherence_monitor, stability_analyzer)
    assert report.entropy is not None
    assert report.drift is not None
    assert report.pressure is not None
    assert report.decay_signals is not None
    assert isinstance(report.governance_status, str)
    assert isinstance(report.score, float)
    assert isinstance(report.trend_direction, str)
    assert isinstance(report.trend_delta, float)


def test_assess_score_within_bounds(sample_traces, minimal_graph, runtime_state,
                                    intelligence_store, coherence_monitor,
                                    stability_analyzer):
    engine = GovernanceEngine()
    report = engine.assess(sample_traces, runtime_state, minimal_graph,
                           intelligence_store, coherence_monitor, stability_analyzer)
    assert 0.0 <= report.score <= 1.0


def test_assess_decay_signals_list(sample_traces, minimal_graph, runtime_state,
                                   intelligence_store, coherence_monitor,
                                   stability_analyzer):
    engine = GovernanceEngine()
    report = engine.assess(sample_traces, runtime_state, minimal_graph,
                           intelligence_store, coherence_monitor, stability_analyzer)
    assert isinstance(report.decay_signals, list)


def test_assess_entropy_metrics_initialized(sample_traces, minimal_graph, runtime_state,
                                            intelligence_store, coherence_monitor,
                                            stability_analyzer):
    engine = GovernanceEngine()
    report = engine.assess(sample_traces, runtime_state, minimal_graph,
                           intelligence_store, coherence_monitor, stability_analyzer)
    e = report.entropy
    assert hasattr(e, 'causal_density')
    assert hasattr(e, 'pattern_explosion')
    assert hasattr(e, 'trace_inflation')
    assert hasattr(e, 'graph_branching')
    assert hasattr(e, 'overall')


def test_assess_drift_metrics_initialized(sample_traces, minimal_graph, runtime_state,
                                          intelligence_store, coherence_monitor,
                                          stability_analyzer):
    engine = GovernanceEngine()
    report = engine.assess(sample_traces, runtime_state, minimal_graph,
                           intelligence_store, coherence_monitor, stability_analyzer)
    d = report.drift
    assert hasattr(d, 'preflight_overreach')
    assert hasattr(d, 'p4_avoidance')
    assert hasattr(d, 'risk_influence')
    assert hasattr(d, 'coherence_drift_rate')
    assert hasattr(d, 'overall')


def test_assess_pressure_metrics_initialized(sample_traces, minimal_graph, runtime_state,
                                             intelligence_store, coherence_monitor,
                                             stability_analyzer):
    engine = GovernanceEngine()
    report = engine.assess(sample_traces, runtime_state, minimal_graph,
                           intelligence_store, coherence_monitor, stability_analyzer)
    p = report.pressure
    assert hasattr(p, 'rule_conflict_rate')
    assert hasattr(p, 'p4_overload_rate')
    assert hasattr(p, 'ambiguity_rate')
    assert hasattr(p, 'escalation_rate')
    assert hasattr(p, 'overall')


def test_assess_status_nominal_for_clean_traces(sample_traces, minimal_graph, runtime_state,
                                                intelligence_store, coherence_monitor,
                                                stability_analyzer):
    engine = GovernanceEngine()
    report = engine.assess(sample_traces, runtime_state, minimal_graph,
                           intelligence_store, coherence_monitor, stability_analyzer)
    assert report.governance_status in ("NOMINAL", "MONITORING")


def test_assess_status_critical_with_bad_traces(bad_traces, minimal_graph, runtime_state,
                                                intelligence_store, coherence_monitor,
                                                stability_analyzer):
    engine = GovernanceEngine()
    report = engine.assess(bad_traces, runtime_state, minimal_graph,
                           intelligence_store, coherence_monitor, stability_analyzer)
    assert report.governance_status == "CRITICAL"


def test_assess_trend_stable_on_first_call(sample_traces, minimal_graph, runtime_state,
                                           intelligence_store, coherence_monitor,
                                           stability_analyzer):
    engine = GovernanceEngine()
    report = engine.assess(sample_traces, runtime_state, minimal_graph,
                           intelligence_store, coherence_monitor, stability_analyzer)
    assert report.trend_direction == "stable"
    assert report.trend_delta == 0.0


def test_assess_trend_detected_after_multiple(sample_traces, bad_traces, minimal_graph,
                                               runtime_state, intelligence_store,
                                               coherence_monitor, stability_analyzer):
    engine = GovernanceEngine()
    engine.assess(sample_traces, runtime_state, minimal_graph,
                  intelligence_store, coherence_monitor, stability_analyzer)
    report2 = engine.assess(bad_traces, runtime_state, minimal_graph,
                            intelligence_store, coherence_monitor, stability_analyzer)
    assert report2.trend_direction in ("worsening", "stable", "improving")


def test_assess_with_confidence_engine(sample_traces, minimal_graph, runtime_state,
                                       intelligence_store, coherence_monitor,
                                       stability_analyzer, confidence_engine):
    engine = GovernanceEngine()
    report = engine.assess(sample_traces, runtime_state, minimal_graph,
                           intelligence_store, coherence_monitor,
                           stability_analyzer, confidence=confidence_engine)
    assert isinstance(report, GovernanceReport)


def test_classify_status_thresholds():
    engine = GovernanceEngine()
    assert engine._classify_status(0.8, 0, 0, []) == "CRITICAL"
    assert engine._classify_status(0, 0.8, 0, []) == "CRITICAL"
    assert engine._classify_status(0, 0, 0.8, []) == "CRITICAL"
    assert engine._classify_status(0.6, 0, 0, []) == "ELEVATED"
    assert engine._classify_status(0, 0.6, 0, []) == "ELEVATED"
    assert engine._classify_status(0.4, 0, 0, []) == "MONITORING"
    assert engine._classify_status(0.2, 0, 0, []) == "NOMINAL"


def test_classify_status_with_decay():
    engine = GovernanceEngine()
    decay = [DecaySignal("test", 0.9, "bad")]
    assert engine._classify_status(0, 0, 0, decay) == "CRITICAL"
    decay = [DecaySignal("test", 0.4, "medium")]
    assert engine._classify_status(0, 0, 0, decay) == "MONITORING"


def test_score_history_limited_to_20(sample_traces, minimal_graph, runtime_state,
                                     intelligence_store, coherence_monitor,
                                     stability_analyzer):
    engine = GovernanceEngine()
    for _ in range(25):
        engine.assess(sample_traces, runtime_state, minimal_graph,
                      intelligence_store, coherence_monitor, stability_analyzer)
    assert len(engine._score_history) == 20


def test_entropy_zero_for_empty_traces(runtime_state, intelligence_store,
                                       coherence_monitor, stability_analyzer):
    engine = GovernanceEngine()
    graph = CausalGraph({}, [])
    report = engine.assess([], runtime_state, graph, intelligence_store,
                           coherence_monitor, stability_analyzer)
    assert report.score == 0.0


def test_multiple_assess_accumulates_history(sample_traces, minimal_graph,
                                             runtime_state, intelligence_store,
                                             coherence_monitor, stability_analyzer):
    engine = GovernanceEngine()
    for _ in range(3):
        engine.assess(sample_traces, runtime_state, minimal_graph,
                      intelligence_store, coherence_monitor, stability_analyzer)
    assert len(engine._score_history) == 3
