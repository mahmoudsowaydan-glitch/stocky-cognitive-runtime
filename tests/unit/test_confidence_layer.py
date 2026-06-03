import pytest
from cognitive_runtime.confidence.confidence_index import (
    ExecutionConfidenceGradient,
    DecisionCertainty,
    OperationalReadiness,
    RuntimeConfidenceScore,
    ConfidenceReport,
)
from cognitive_runtime.confidence.decision_certainty import DecisionCertaintyAnalyzer
from cognitive_runtime.confidence.operational_readiness import OperationalReadinessAnalyzer
from cognitive_runtime.confidence.gradient_transition_guard import GradientTransitionGuard
from cognitive_runtime.confidence.runtime_confidence import RuntimeConfidenceEngine
from cognitive_runtime.contracts.execution_trace import ExecutionTrace
from cognitive_runtime.runtime.runtime_state import RuntimeState


def make_trace(event_id, p4_verdict="ALLOW", execution_status="SUCCESS",
               risk_score=0.1, p4_rule_triggered=None, preflight_valid=True,
               p4_risk_level="low"):
    return ExecutionTrace(
        event_id=event_id, session_id="s1", sequence_no=1,
        correlation_id=f"c_{event_id}",
        preflight_valid=preflight_valid, preflight_reason="ok",
        preflight_rules_triggered=[],
        risk_score=risk_score,
        p4_verdict=p4_verdict, p4_reason="test", p4_risk_level=p4_risk_level,
        p4_rule_triggered=p4_rule_triggered,
        execution_status=execution_status, execution_error=None,
        capabilities_checked=[], resource_usage={},
        preflight_time=0.0, p4_time=0.0, execution_time=0.0, total_time=0.0,
        final_status=f"P4_{p4_verdict}" if p4_verdict != "UNKNOWN" else "UNKNOWN",
    )


# ════════════════════════════════════════════
# ExecutionConfidenceGradient
# ════════════════════════════════════════════

class TestExecutionConfidenceGradient:
    def test_enum_values(self):
        assert ExecutionConfidenceGradient.HIGH.value == "HIGH"
        assert ExecutionConfidenceGradient.MEDIUM.value == "MEDIUM"
        assert ExecutionConfidenceGradient.LOW.value == "LOW"
        assert ExecutionConfidenceGradient.CRITICAL.value == "CRITICAL"

    def test_enum_members(self):
        assert len(ExecutionConfidenceGradient) == 4


# ════════════════════════════════════════════
# Dataclass Tests
# ════════════════════════════════════════════

class TestDecisionCertainty:
    def test_create(self):
        dc = DecisionCertainty(
            risk_proximity=0.8, verdict_clarity=0.9,
            rule_conflict_density=0.1, overall=0.85,
        )
        assert dc.risk_proximity == 0.8
        assert dc.verdict_clarity == 0.9
        assert dc.rule_conflict_density == 0.1
        assert dc.overall == 0.85


class TestOperationalReadiness:
    def test_create(self):
        opr = OperationalReadiness(
            queue_health=0.9, processing_health=0.8,
            latency_health=0.95, backpressure_ratio=0.0, overall=0.88,
        )
        assert opr.queue_health == 0.9
        assert opr.processing_health == 0.8
        assert opr.latency_health == 0.95
        assert opr.backpressure_ratio == 0.0
        assert opr.overall == 0.88


class TestRuntimeConfidenceScore:
    def test_create(self):
        rcs = RuntimeConfidenceScore(
            decision_confidence=0.85, operational_confidence=0.75,
            execution_confidence=0.9, overall=0.83,
            gradient=ExecutionConfidenceGradient.HIGH,
        )
        assert rcs.decision_confidence == 0.85
        assert rcs.operational_confidence == 0.75
        assert rcs.execution_confidence == 0.9
        assert rcs.overall == 0.83
        assert rcs.gradient == ExecutionConfidenceGradient.HIGH


class TestConfidenceReport:
    def test_create(self):
        rcs = RuntimeConfidenceScore(
            0.8, 0.7, 0.9, 0.8, ExecutionConfidenceGradient.HIGH,
        )
        report = ConfidenceReport(
            score=rcs,
            gradient=ExecutionConfidenceGradient.HIGH,
            referenced_stability_snapshot=0.75,
            trend_direction="stable",
            trend_delta=0.01,
            degradation_detected=False,
        )
        assert report.score is rcs
        assert report.gradient == ExecutionConfidenceGradient.HIGH
        assert report.referenced_stability_snapshot == 0.75
        assert report.trend_direction == "stable"
        assert report.trend_delta == 0.01
        assert report.degradation_detected is False


# ════════════════════════════════════════════
# DecisionCertaintyAnalyzer
# ════════════════════════════════════════════

class TestDecisionCertaintyAnalyzer:
    def test_analyze_empty_traces_returns_defaults(self):
        analyzer = DecisionCertaintyAnalyzer()
        result = analyzer.analyze([])
        assert result.risk_proximity == 1.0
        assert result.verdict_clarity == 1.0
        assert result.rule_conflict_density == 0.0
        assert result.overall == 1.0

    def test_risk_certainty_with_clear_scores(self):
        analyzer = DecisionCertaintyAnalyzer()
        traces = [
            make_trace("e1", risk_score=0.1),
            make_trace("e2", risk_score=0.9),
        ]
        result = analyzer.analyze(traces)
        assert result.risk_proximity == 0.8

    def test_risk_certainty_at_threshold(self):
        analyzer = DecisionCertaintyAnalyzer()
        traces = [make_trace("e1", risk_score=0.5)]
        result = analyzer.analyze(traces)
        assert result.risk_proximity == 0.0

    def test_risk_certainty_capped_at_one(self):
        analyzer = DecisionCertaintyAnalyzer()
        traces = [make_trace("e1", risk_score=0.0)]
        result = analyzer.analyze(traces)
        assert result.risk_proximity == 1.0

    def test_verdict_clarity_all_same(self):
        analyzer = DecisionCertaintyAnalyzer()
        traces = [make_trace("e1", p4_verdict="ALLOW") for _ in range(5)]
        result = analyzer.analyze(traces)
        assert result.verdict_clarity == 1.0

    def test_verdict_clarity_mixed(self):
        analyzer = DecisionCertaintyAnalyzer()
        traces = [
            make_trace("e1", p4_verdict="ALLOW"),
            make_trace("e2", p4_verdict="ALLOW"),
            make_trace("e3", p4_verdict="ALLOW"),
            make_trace("e4", p4_verdict="BLOCK"),
        ]
        result = analyzer.analyze(traces)
        assert result.verdict_clarity == 0.75

    def test_verdict_clarity_all_unknown(self):
        analyzer = DecisionCertaintyAnalyzer()
        traces = [make_trace("e1", p4_verdict="UNKNOWN")]
        result = analyzer.analyze(traces)
        assert result.verdict_clarity == 1.0

    def test_rule_conflict_no_triggers(self):
        analyzer = DecisionCertaintyAnalyzer()
        traces = [make_trace("e1"), make_trace("e2")]
        result = analyzer.analyze(traces)
        assert result.rule_conflict_density == 0.0

    def test_rule_conflict_all_triggers(self):
        analyzer = DecisionCertaintyAnalyzer()
        traces = [
            make_trace("e1", p4_rule_triggered="rule_1"),
            make_trace("e2", p4_rule_triggered="rule_2"),
        ]
        result = analyzer.analyze(traces)
        assert result.rule_conflict_density == 1.0

    def test_rule_conflict_partial(self):
        analyzer = DecisionCertaintyAnalyzer()
        traces = [
            make_trace("e1", p4_rule_triggered="rule_1"),
            make_trace("e2"),
            make_trace("e3"),
            make_trace("e4", p4_rule_triggered="rule_2"),
        ]
        result = analyzer.analyze(traces)
        assert result.rule_conflict_density == 0.5

    def test_overall_composition(self):
        analyzer = DecisionCertaintyAnalyzer()
        traces = [make_trace("e1", risk_score=0.1, p4_verdict="ALLOW")]
        result = analyzer.analyze(traces)
        expected = 0.5 * result.risk_proximity + 0.3 * result.verdict_clarity + 0.2 * (1.0 - result.rule_conflict_density)
        assert result.overall == round(expected, 4)


# ════════════════════════════════════════════
# OperationalReadinessAnalyzer
# ════════════════════════════════════════════

class TestOperationalReadinessAnalyzer:
    def test_analyze_returns_operational_readiness(self):
        analyzer = OperationalReadinessAnalyzer()
        snap = {"queue_depth": 10, "total_events": 100, "dead_lettered": 0,
                "failed": 0, "processed": 50, "average_cycle_ms": 100.0, "last_cycle_ms": 100.0}
        result = analyzer.analyze(snap)
        assert isinstance(result, OperationalReadiness)

    def test_queue_health_full(self):
        analyzer = OperationalReadinessAnalyzer(max_expected_depth=100)
        snap = {"queue_depth": 0, "total_events": 100, "dead_lettered": 0, "failed": 0,
                "processed": 50, "average_cycle_ms": 100.0, "last_cycle_ms": 100.0}
        result = analyzer.analyze(snap)
        assert result.queue_health == 1.0

    def test_queue_health_half(self):
        analyzer = OperationalReadinessAnalyzer(max_expected_depth=100)
        snap = {"queue_depth": 50, "total_events": 100, "dead_lettered": 0, "failed": 0,
                "processed": 50, "average_cycle_ms": 100.0, "last_cycle_ms": 100.0}
        result = analyzer.analyze(snap)
        assert result.queue_health == 0.5

    def test_queue_health_exhausted(self):
        analyzer = OperationalReadinessAnalyzer(max_expected_depth=100)
        snap = {"queue_depth": 200, "total_events": 100, "dead_lettered": 0, "failed": 0,
                "processed": 50, "average_cycle_ms": 100.0, "last_cycle_ms": 100.0}
        result = analyzer.analyze(snap)
        assert result.queue_health == 0.0

    def test_processing_health_perfect(self):
        analyzer = OperationalReadinessAnalyzer()
        snap = {"queue_depth": 0, "total_events": 100, "dead_lettered": 0, "failed": 0,
                "processed": 50, "average_cycle_ms": 100.0, "last_cycle_ms": 100.0}
        result = analyzer.analyze(snap)
        assert result.processing_health == 1.0

    def test_processing_health_with_failures(self):
        analyzer = OperationalReadinessAnalyzer()
        snap = {"queue_depth": 0, "total_events": 100, "dead_lettered": 10, "failed": 20,
                "processed": 50, "average_cycle_ms": 100.0, "last_cycle_ms": 100.0}
        result = analyzer.analyze(snap)
        assert result.processing_health == 0.7

    def test_processing_health_zero(self):
        analyzer = OperationalReadinessAnalyzer()
        snap = {"queue_depth": 0, "total_events": 100, "dead_lettered": 50, "failed": 100,
                "processed": 50, "average_cycle_ms": 100.0, "last_cycle_ms": 100.0}
        result = analyzer.analyze(snap)
        assert result.processing_health == 0.0

    def test_latency_health_stable(self):
        analyzer = OperationalReadinessAnalyzer()
        snap = {"queue_depth": 0, "total_events": 100, "dead_lettered": 0, "failed": 0,
                "processed": 50, "average_cycle_ms": 100.0, "last_cycle_ms": 105.0}
        result = analyzer.analyze(snap)
        assert result.latency_health > 0.9

    def test_latency_health_divergent(self):
        analyzer = OperationalReadinessAnalyzer()
        snap = {"queue_depth": 0, "total_events": 100, "dead_lettered": 0, "failed": 0,
                "processed": 50, "average_cycle_ms": 100.0, "last_cycle_ms": 300.0}
        result = analyzer.analyze(snap)
        assert result.latency_health == 0.0

    def test_latency_health_zero_avg(self):
        analyzer = OperationalReadinessAnalyzer()
        snap = {"queue_depth": 0, "total_events": 100, "dead_lettered": 0, "failed": 0,
                "processed": 50, "average_cycle_ms": 0.0, "last_cycle_ms": 200.0}
        result = analyzer.analyze(snap)
        assert result.latency_health == 1.0

    def test_backpressure_zero_with_single_snapshot(self):
        analyzer = OperationalReadinessAnalyzer()
        snap = {"queue_depth": 0, "total_events": 100, "dead_lettered": 0, "failed": 0,
                "processed": 50, "average_cycle_ms": 100.0, "last_cycle_ms": 100.0}
        result = analyzer.analyze(snap)
        assert result.backpressure_ratio == 0.0

    def test_backpressure_computed_with_two_snapshots(self):
        analyzer = OperationalReadinessAnalyzer()
        s1 = {"queue_depth": 0, "total_events": 100, "dead_lettered": 0, "failed": 0,
              "processed": 50, "average_cycle_ms": 100.0, "last_cycle_ms": 100.0}
        s2 = {"queue_depth": 0, "total_events": 150, "dead_lettered": 0, "failed": 0,
              "processed": 80, "average_cycle_ms": 100.0, "last_cycle_ms": 100.0}
        analyzer.analyze(s1)
        result = analyzer.analyze(s2)
        assert result.backpressure_ratio > 0.0

    def test_backpressure_no_ingress(self):
        analyzer = OperationalReadinessAnalyzer()
        s1 = {"queue_depth": 0, "total_events": 100, "dead_lettered": 0, "failed": 0,
              "processed": 50, "average_cycle_ms": 100.0, "last_cycle_ms": 100.0}
        s2 = {"queue_depth": 0, "total_events": 100, "dead_lettered": 0, "failed": 0,
              "processed": 80, "average_cycle_ms": 100.0, "last_cycle_ms": 100.0}
        analyzer.analyze(s1)
        result = analyzer.analyze(s2)
        assert result.backpressure_ratio == 0.0

    def test_overall_composition(self):
        analyzer = OperationalReadinessAnalyzer()
        snap = {"queue_depth": 0, "total_events": 100, "dead_lettered": 0, "failed": 0,
                "processed": 50, "average_cycle_ms": 100.0, "last_cycle_ms": 100.0}
        result = analyzer.analyze(snap)
        expected = 0.4 * result.queue_health + 0.3 * result.processing_health + 0.3 * result.latency_health
        assert result.overall == round(expected, 4)

    def test_history_accumulates_and_limits(self):
        analyzer = OperationalReadinessAnalyzer()
        snap = {"queue_depth": 0, "total_events": 100, "dead_lettered": 0, "failed": 0,
                "processed": 50, "average_cycle_ms": 100.0, "last_cycle_ms": 100.0}
        for _ in range(15):
            analyzer.analyze(snap)
        assert len(analyzer._snapshot_history) == 10


# ════════════════════════════════════════════
# GradientTransitionGuard
# ════════════════════════════════════════════

class TestGradientTransitionGuard:
    def test_initial_resolve_sets_gradient(self):
        guard = GradientTransitionGuard()
        result = guard.resolve(0.9)
        assert result == ExecutionConfidenceGradient.HIGH
        assert guard.current_gradient == ExecutionConfidenceGradient.HIGH

    def test_same_gradient_repeated_clears_pending(self):
        guard = GradientTransitionGuard()
        guard.resolve(0.9)
        result = guard.resolve(0.95)
        assert result == ExecutionConfidenceGradient.HIGH

    def test_transition_requires_threshold_hits(self):
        guard = GradientTransitionGuard()
        guard.resolve(0.9)
        result = guard.resolve(0.5)
        assert result == ExecutionConfidenceGradient.HIGH
        result = guard.resolve(0.5)
        assert result == ExecutionConfidenceGradient.MEDIUM

    def test_transition_high_to_low_requires_three_hits(self):
        guard = GradientTransitionGuard()
        guard.resolve(0.9)
        guard.resolve(0.3)
        assert guard.current_gradient == ExecutionConfidenceGradient.HIGH
        guard.resolve(0.3)
        assert guard.current_gradient == ExecutionConfidenceGradient.HIGH
        guard.resolve(0.3)
        assert guard.current_gradient == ExecutionConfidenceGradient.LOW

    def test_transition_high_to_critical_one_hit(self):
        guard = GradientTransitionGuard()
        guard.resolve(0.9)
        result = guard.resolve(0.1)
        assert result == ExecutionConfidenceGradient.CRITICAL

    def test_transition_critical_to_high_requires_three_hits(self):
        guard = GradientTransitionGuard()
        guard.resolve(0.1)
        assert guard.current_gradient == ExecutionConfidenceGradient.CRITICAL
        guard.resolve(0.9)
        assert guard.current_gradient == ExecutionConfidenceGradient.CRITICAL
        guard.resolve(0.9)
        assert guard.current_gradient == ExecutionConfidenceGradient.CRITICAL
        result = guard.resolve(0.9)
        assert result == ExecutionConfidenceGradient.HIGH

    def test_transition_medium_to_critical_one_hit(self):
        guard = GradientTransitionGuard()
        guard.resolve(0.6)
        result = guard.resolve(0.1)
        assert result == ExecutionConfidenceGradient.CRITICAL

    def test_transition_low_to_medium_two_hits(self):
        guard = GradientTransitionGuard()
        guard.resolve(0.3)
        guard.resolve(0.6)
        assert guard.current_gradient == ExecutionConfidenceGradient.LOW
        result = guard.resolve(0.6)
        assert result == ExecutionConfidenceGradient.MEDIUM

    def test_classify_high(self):
        guard = GradientTransitionGuard()
        assert guard._classify(1.0) == ExecutionConfidenceGradient.HIGH
        assert guard._classify(0.8) == ExecutionConfidenceGradient.HIGH
        assert guard._classify(0.85) == ExecutionConfidenceGradient.HIGH

    def test_classify_medium(self):
        guard = GradientTransitionGuard()
        assert guard._classify(0.79) == ExecutionConfidenceGradient.MEDIUM
        assert guard._classify(0.5) == ExecutionConfidenceGradient.MEDIUM
        assert guard._classify(0.6) == ExecutionConfidenceGradient.MEDIUM

    def test_classify_low(self):
        guard = GradientTransitionGuard()
        assert guard._classify(0.49) == ExecutionConfidenceGradient.LOW
        assert guard._classify(0.2) == ExecutionConfidenceGradient.LOW
        assert guard._classify(0.35) == ExecutionConfidenceGradient.LOW

    def test_classify_critical(self):
        guard = GradientTransitionGuard()
        assert guard._classify(0.19) == ExecutionConfidenceGradient.CRITICAL
        assert guard._classify(0.0) == ExecutionConfidenceGradient.CRITICAL
        assert guard._classify(0.1) == ExecutionConfidenceGradient.CRITICAL

    def test_current_gradient_initially_none(self):
        guard = GradientTransitionGuard()
        assert guard.current_gradient is None


# ════════════════════════════════════════════
# RuntimeConfidenceEngine
# ════════════════════════════════════════════

class TestRuntimeConfidenceEngine:
    def test_assess_returns_confidence_report(self):
        engine = RuntimeConfidenceEngine()
        traces = [make_trace("e1", p4_verdict="ALLOW", execution_status="SUCCESS")]
        state = RuntimeState()
        snap = {"queue_depth": 0, "total_events": 100, "dead_lettered": 0,
                "failed": 0, "processed": 50, "average_cycle_ms": 100.0, "last_cycle_ms": 100.0}
        report = engine.assess(traces, state, snap)
        assert isinstance(report, ConfidenceReport)
        assert isinstance(report.score, RuntimeConfidenceScore)
        assert isinstance(report.gradient, ExecutionConfidenceGradient)

    def test_assess_with_empty_traces(self):
        engine = RuntimeConfidenceEngine()
        state = RuntimeState()
        snap = {"queue_depth": 0, "total_events": 100, "dead_lettered": 0,
                "failed": 0, "processed": 50, "average_cycle_ms": 100.0, "last_cycle_ms": 100.0}
        report = engine.assess([], state, snap)
        assert report.score.decision_confidence == 1.0
        assert report.score.execution_confidence == 1.0

    def test_assess_execution_confidence_all_success(self):
        engine = RuntimeConfidenceEngine()
        traces = [make_trace("e1", p4_verdict="ALLOW", execution_status="SUCCESS")]
        state = RuntimeState()
        snap = {"queue_depth": 0, "total_events": 100, "dead_lettered": 0,
                "failed": 0, "processed": 50, "average_cycle_ms": 100.0, "last_cycle_ms": 100.0}
        report = engine.assess(traces, state, snap)
        assert report.score.execution_confidence == 1.0

    def test_assess_execution_confidence_no_allows(self):
        engine = RuntimeConfidenceEngine()
        traces = [make_trace("e1", p4_verdict="BLOCK")]
        state = RuntimeState()
        snap = {"queue_depth": 0, "total_events": 100, "dead_lettered": 0,
                "failed": 0, "processed": 50, "average_cycle_ms": 100.0, "last_cycle_ms": 100.0}
        report = engine.assess(traces, state, snap)
        assert report.score.execution_confidence == 0.5

    def test_assess_overall_bounded(self):
        engine = RuntimeConfidenceEngine()
        traces = [make_trace("e1", p4_verdict="ALLOW", execution_status="SUCCESS")]
        state = RuntimeState()
        snap = {"queue_depth": 0, "total_events": 100, "dead_lettered": 0,
                "failed": 0, "processed": 50, "average_cycle_ms": 100.0, "last_cycle_ms": 100.0}
        report = engine.assess(traces, state, snap)
        assert 0.0 <= report.score.overall <= 1.0

    def test_assess_stores_stability_snapshot(self):
        engine = RuntimeConfidenceEngine()
        traces = [make_trace("e1")]
        state = RuntimeState()
        snap = {"queue_depth": 0, "total_events": 100, "dead_lettered": 0,
                "failed": 0, "processed": 50, "average_cycle_ms": 100.0, "last_cycle_ms": 100.0}
        report = engine.assess(traces, state, snap, stability_snapshot=0.85)
        assert report.referenced_stability_snapshot == 0.85

    def test_assess_persists_stability_snapshot(self):
        engine = RuntimeConfidenceEngine()
        traces = [make_trace("e1")]
        state = RuntimeState()
        snap = {"queue_depth": 0, "total_events": 100, "dead_lettered": 0,
                "failed": 0, "processed": 50, "average_cycle_ms": 100.0, "last_cycle_ms": 100.0}
        engine.assess(traces, state, snap, stability_snapshot=0.85)
        report = engine.assess(traces, state, snap)
        assert report.referenced_stability_snapshot == 0.85

    def test_trend_stable_with_single_call(self):
        engine = RuntimeConfidenceEngine()
        traces = [make_trace("e1")]
        state = RuntimeState()
        snap = {"queue_depth": 0, "total_events": 100, "dead_lettered": 0,
                "failed": 0, "processed": 50, "average_cycle_ms": 100.0, "last_cycle_ms": 100.0}
        report = engine.assess(traces, state, snap)
        assert report.trend_direction == "stable"
        assert report.trend_delta == 0.0

    def test_trend_improving(self):
        engine = RuntimeConfidenceEngine()
        state = RuntimeState()
        snap = {"queue_depth": 0, "total_events": 100, "dead_lettered": 0,
                "failed": 0, "processed": 50, "average_cycle_ms": 100.0, "last_cycle_ms": 100.0}
        t = [make_trace("e1")]
        for _ in range(5):
            engine.assess(t, state, snap)
        engine._score_history[:] = [0.40, 0.40, 0.40, 0.90, 0.90]
        report = engine.assess(t, state, snap)
        assert report.trend_direction == "improving"

    def test_trend_degrading(self):
        engine = RuntimeConfidenceEngine()
        state = RuntimeState()
        snap = {"queue_depth": 0, "total_events": 100, "dead_lettered": 0,
                "failed": 0, "processed": 50, "average_cycle_ms": 100.0, "last_cycle_ms": 100.0}
        t = [make_trace("e1")]
        for _ in range(5):
            engine.assess(t, state, snap)
        engine._score_history[:] = [0.90, 0.90, 0.90, 0.40, 0.40]
        report = engine.assess(t, state, snap)
        assert report.trend_direction == "degrading"

    def test_degradation_detected_three_decreasing(self):
        engine = RuntimeConfidenceEngine()
        engine._score_history = [0.9, 0.85, 0.8]
        assert engine._detect_degradation() is True

    def test_degradation_not_detected_less_than_three(self):
        engine = RuntimeConfidenceEngine()
        engine._score_history = [0.9, 0.85]
        assert engine._detect_degradation() is False

    def test_degradation_not_detected_increasing(self):
        engine = RuntimeConfidenceEngine()
        engine._score_history = [0.7, 0.8, 0.9]
        assert engine._detect_degradation() is False

    def test_degradation_not_detected_empty(self):
        engine = RuntimeConfidenceEngine()
        assert engine._detect_degradation() is False

    def test_score_history_limited_to_20(self):
        engine = RuntimeConfidenceEngine()
        state = RuntimeState()
        snap = {"queue_depth": 0, "total_events": 100, "dead_lettered": 0,
                "failed": 0, "processed": 50, "average_cycle_ms": 100.0, "last_cycle_ms": 100.0}
        t = [make_trace("e1")]
        for _ in range(30):
            engine.assess(t, state, snap)
        assert len(engine._score_history) == 20

    def test_current_gradient_property(self):
        engine = RuntimeConfidenceEngine()
        assert engine.current_gradient is None
        t = [make_trace("e1")]
        state = RuntimeState()
        snap = {"queue_depth": 0, "total_events": 100, "dead_lettered": 0,
                "failed": 0, "processed": 50, "average_cycle_ms": 100.0, "last_cycle_ms": 100.0}
        engine.assess(t, state, snap)
        assert engine.current_gradient is not None
