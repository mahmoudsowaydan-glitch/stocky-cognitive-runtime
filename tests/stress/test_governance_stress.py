import pytest

from cognitive_runtime.contracts.execution_trace import ExecutionTrace
from cognitive_runtime.contracts.causal_graph import CausalGraphBuilder
from cognitive_runtime.governance.governance_engine import GovernanceEngine
from cognitive_runtime.intelligence.intelligence_store import IntelligenceStore
from cognitive_runtime.runtime.runtime_state import RuntimeState
from cognitive_runtime.runtime.coherence_monitor import CoherenceMonitor
from cognitive_runtime.stability.stability_analyzer import StabilityAnalyzer


pytestmark = pytest.mark.stress


def _trace(event_id: str, risk: float = 0.1, verdict: str = "ALLOW",
           status: str = "SUCCESS", final: str = "P4_ALLOW",
           preflight: bool = True, rule: str = None) -> ExecutionTrace:
    return ExecutionTrace(
        event_id=event_id,
        session_id="gov-stress",
        sequence_no=1,
        correlation_id=f"cr-{event_id}",
        preflight_valid=preflight,
        preflight_reason="preflight_passed",
        risk_score=risk,
        p4_verdict=verdict,
        p4_reason="ok",
        p4_risk_level="low" if risk < 0.5 else "high",
        p4_rule_triggered=rule,
        execution_status=status,
        final_status=final,
        total_time=10.0,
    )


# ── (a) Doctrine drift accumulation ──

def test_drift_increases_with_rising_risk_scores():
    engine = GovernanceEngine()
    store = IntelligenceStore()
    coherence = CoherenceMonitor()
    stab = StabilityAnalyzer(store, window_size=200, history_size=20)
    state = RuntimeState()
    state.started_at = 1000.0
    state.status = "running"
    traces = []
    builder = CausalGraphBuilder()

    for i in range(100):
        risk = 0.05 + i * 0.0095
        trace = _trace(
            event_id=f"drift-e{i:03d}",
            risk=risk,
            verdict="BLOCK" if risk > 0.5 else "ALLOW",
            final="P4_BLOCK" if risk > 0.5 else "P4_ALLOW",
            status="UNKNOWN" if risk > 0.5 else "SUCCESS",
        )
        traces.append(trace)
        state.record_cycle(duration_ms=10.0, success=(risk <= 0.5), queue_depth=0)
        coherence.check_trace(trace)

    graph = builder.build(traces)
    stab.analyze(traces, state, graph)
    report = engine.assess(traces, state, graph, store, coherence, stab)

    assert report.drift.overall > 0.3
    assert 0.0 <= report.drift.overall <= 1.0


# ── (b) Entropy pressure ──

def test_entropy_score_changes_with_varied_patterns():
    engine = GovernanceEngine()
    store = IntelligenceStore()
    coherence = CoherenceMonitor()
    stab = StabilityAnalyzer(store, window_size=200, history_size=20)
    state = RuntimeState()
    state.started_at = 1000.0
    state.status = "running"
    traces = []
    builder = CausalGraphBuilder()

    for i in range(100):
        risk = 0.1 + (i % 20) * 0.04
        trace = _trace(
            event_id=f"ent-e{i:03d}",
            risk=risk,
            verdict="BLOCK" if i % 7 == 0 else "ALLOW",
            final="P4_BLOCK" if i % 7 == 0 else "P4_ALLOW",
            status="FAILED" if i % 13 == 0 else "SUCCESS",
        )
        traces.append(trace)
        state.record_cycle(duration_ms=10.0, success=(i % 13 != 0), queue_depth=0)
        coherence.check_trace(trace)

    graph = builder.build(traces)
    stab.analyze(traces, state, graph)
    report = engine.assess(traces, state, graph, store, coherence, stab)

    assert 0.0 <= report.entropy.overall <= 1.0
    assert 0.0 <= report.entropy.causal_density <= 1.0
    assert 0.0 <= report.entropy.pattern_explosion <= 1.0
    assert 0.0 <= report.entropy.trace_inflation <= 1.0
    assert report.entropy.overall > 0.0


# ── (c) Confidence degradation ──

def test_degrading_confidence_detected_by_governance():
    engine = GovernanceEngine()
    store = IntelligenceStore()
    coherence = CoherenceMonitor()
    stab = StabilityAnalyzer(store, window_size=100, history_size=20)
    state = RuntimeState()
    state.started_at = 1000.0
    state.status = "running"
    traces = []
    builder = CausalGraphBuilder()

    stab._score_history = [0.9, 0.85, 0.8, 0.72, 0.65, 0.55, 0.45, 0.35]

    for i in range(100):
        risk = 0.1 + (i // 10) * 0.08
        trace = _trace(
            event_id=f"conf-e{i:03d}",
            risk=min(risk, 1.0),
            verdict="BLOCK" if i > 70 else "ALLOW",
            final="P4_BLOCK" if i > 70 else "P4_ALLOW",
            status="FAILED" if i > 80 else "SUCCESS",
        )
        traces.append(trace)
        state.record_cycle(duration_ms=10.0, success=(i <= 80), queue_depth=0)
        coherence.check_trace(trace)

    graph = builder.build(traces)
    stab.analyze(traces, state, graph)
    report = engine.assess(traces, state, graph, store, coherence, stab)

    decay_types = [d.signal_type for d in report.decay_signals]
    assert len(decay_types) > 0


# ── (d) Oscillation prevention (GradientTransitionGuard hysteresis) ──

def test_alternating_risk_does_not_oscillate_wildly():
    engine = GovernanceEngine()
    store = IntelligenceStore()
    coherence = CoherenceMonitor()
    stab = StabilityAnalyzer(store, window_size=100, history_size=20)
    state = RuntimeState()
    state.started_at = 1000.0
    state.status = "running"
    traces = []
    builder = CausalGraphBuilder()

    for i in range(50):
        for risk_val in (0.95, 0.05):
            trace = _trace(
                event_id=f"osc-e{i:03d}-r{int(risk_val*100)}",
                risk=risk_val,
                verdict="BLOCK" if risk_val > 0.5 else "ALLOW",
                final="P4_BLOCK" if risk_val > 0.5 else "P4_ALLOW",
                status="UNKNOWN" if risk_val > 0.5 else "SUCCESS",
            )
            traces.append(trace)
            state.record_cycle(duration_ms=10.0, success=(risk_val <= 0.5), queue_depth=0)
            coherence.check_trace(trace)

    graph = builder.build(traces)
    stab.analyze(traces, state, graph)
    report = engine.assess(traces, state, graph, store, coherence, stab)

    assert report.trend_direction in ("stable", "worsening", "improving")

    scores = engine._score_history
    if len(scores) >= 3:
        oscillations = sum(
            1 for i in range(2, len(scores))
            if (scores[i] - scores[i-1]) * (scores[i-1] - scores[i-2]) < 0
        )
        assert oscillations <= 5


# ── (e) Decay signal detection ──

def test_architectural_decay_signals_in_report():
    engine = GovernanceEngine()
    store = IntelligenceStore()
    coherence = CoherenceMonitor()
    stab = StabilityAnalyzer(store, window_size=100, history_size=20)
    state = RuntimeState()
    state.started_at = 1000.0
    state.status = "running"
    traces = []
    builder = CausalGraphBuilder()

    stab._score_history = [0.95, 0.9, 0.85, 0.78, 0.7, 0.6, 0.5, 0.4, 0.3, 0.25]

    for i in range(100):
        risk = 0.3 + (i // 5) * 0.07
        high_risk = risk > 0.7
        trace = _trace(
            event_id=f"decay-e{i:03d}",
            risk=min(risk, 1.0),
            verdict="BLOCK" if high_risk else "ALLOW",
            final="P4_BLOCK" if high_risk else "P4_ALLOW",
            status="FAILED" if high_risk or i > 85 else "SUCCESS",
            rule="rule_42" if high_risk else None,
        )
        traces.append(trace)
        state.record_cycle(
            duration_ms=10.0 + (i % 20) * 5.0,
            success=(not high_risk and i <= 85),
            queue_depth=0,
        )
        state.consecutive_failures = max(0, i - 70) if i > 70 else 0
        coherence.check_trace(trace)

    graph = builder.build(traces)
    stab.analyze(traces, state, graph)
    report = engine.assess(traces, state, graph, store, coherence, stab)

    assert len(report.decay_signals) > 0
    assert any(d.severity > 0.0 for d in report.decay_signals)
