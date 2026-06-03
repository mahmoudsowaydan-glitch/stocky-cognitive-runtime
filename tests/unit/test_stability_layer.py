import math
import uuid

import pytest
from cognitive_runtime.intelligence.intelligence_store import IntelligenceStore, Pattern
from cognitive_runtime.stability.stability_index import (
    StabilityWindow,
    StabilityScore,
    StabilityTrend,
    StabilityReport,
)
from cognitive_runtime.stability.stability_analyzer import StabilityAnalyzer
from cognitive_runtime.contracts.execution_trace import ExecutionTrace
from cognitive_runtime.runtime.runtime_state import RuntimeState


def make_trace(event_id, preflight_valid=True, p4_verdict="ALLOW",
               execution_status="SUCCESS", final_status="P4_ALLOW",
               risk_score=0.1, capabilities=None, total_time=50.0):
    return ExecutionTrace(
        event_id=event_id, session_id="s1", sequence_no=1,
        correlation_id=f"c_{event_id}",
        preflight_valid=preflight_valid, preflight_reason="ok",
        preflight_rules_triggered=[],
        risk_score=risk_score,
        p4_verdict=p4_verdict, p4_reason="test", p4_risk_level="low",
        execution_status=execution_status,
        capabilities_checked=capabilities or [],
        total_time=total_time,
        final_status=final_status,
    )


# ════════════════════════════════════════════
# Dataclass Tests
# ════════════════════════════════════════════

class TestStabilityWindow:
    def test_create(self):
        w = StabilityWindow(
            window_id="w1", trace_count=10, failure_rate=0.1,
            drift_rate=0.05, avg_cycle_ms=100.0, cycle_time_std=20.0,
            new_pattern_ratio=0.3, pattern_repeat_rate=0.7, recovery_speed=0,
        )
        assert w.window_id == "w1"
        assert w.trace_count == 10
        assert w.failure_rate == 0.1
        assert w.drift_rate == 0.05
        assert w.avg_cycle_ms == 100.0
        assert w.cycle_time_std == 20.0
        assert w.new_pattern_ratio == 0.3
        assert w.pattern_repeat_rate == 0.7
        assert w.recovery_speed == 0


class TestStabilityScore:
    def test_create(self):
        s = StabilityScore(
            overall=0.85, failure_score=0.9, drift_score=0.95,
            consistency_score=0.7, timing_stability=0.8,
            novelty_score=0.6, system_regression_score=1.0,
        )
        assert s.overall == 0.85
        assert s.failure_score == 0.9
        assert s.drift_score == 0.95
        assert s.system_regression_score == 1.0


class TestStabilityTrend:
    def test_create(self):
        t = StabilityTrend(
            direction="stable", delta=0.01,
            window_count=5, last_n_scores=[0.8, 0.81, 0.8, 0.82, 0.81],
        )
        assert t.direction == "stable"
        assert t.delta == 0.01
        assert t.window_count == 5
        assert len(t.last_n_scores) == 5


class TestStabilityReport:
    def test_create(self):
        w = StabilityWindow("w1", 0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0)
        s = StabilityScore(0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
        t = StabilityTrend("stable", 0.0, 0, [])
        r = StabilityReport(current_window=w, score=s, trend=t, anomalies=["test"])
        assert r.current_window is w
        assert r.score is s
        assert r.trend is t
        assert r.anomalies == ["test"]


# ════════════════════════════════════════════
# StabilityAnalyzer — Construction
# ════════════════════════════════════════════

class TestStabilityAnalyzerConstruction:
    def test_default_params(self):
        analyzer = StabilityAnalyzer(IntelligenceStore())
        assert analyzer._window_size == 100
        assert analyzer._history_size == 10

    def test_custom_params(self):
        analyzer = StabilityAnalyzer(IntelligenceStore(), window_size=50, history_size=5)
        assert analyzer._window_size == 50
        assert analyzer._history_size == 5


# ════════════════════════════════════════════
# StabilityAnalyzer — analyze()
# ════════════════════════════════════════════

class TestStabilityAnalyzerAnalyze:
    def test_returns_stability_report(self):
        store = IntelligenceStore()
        analyzer = StabilityAnalyzer(store)
        state = RuntimeState()
        traces = [make_trace("e1")]
        report = analyzer.analyze(traces, state)
        assert isinstance(report, StabilityReport)
        assert isinstance(report.current_window, StabilityWindow)
        assert isinstance(report.score, StabilityScore)
        assert isinstance(report.trend, StabilityTrend)
        assert isinstance(report.anomalies, list)

    def test_empty_traces_does_not_crash(self):
        store = IntelligenceStore()
        analyzer = StabilityAnalyzer(store)
        state = RuntimeState()
        report = analyzer.analyze([], state)
        assert report.current_window.trace_count == 0
        assert report.current_window.failure_rate == 0.0
        assert report.score.overall > 0

    def test_single_trace_does_not_crash(self):
        store = IntelligenceStore()
        analyzer = StabilityAnalyzer(store)
        state = RuntimeState()
        report = analyzer.analyze([make_trace("e1")], state)
        assert report.current_window.trace_count == 1

    def test_score_in_zero_one_range(self):
        store = IntelligenceStore()
        analyzer = StabilityAnalyzer(store)
        state = RuntimeState()
        traces = [make_trace("e1"), make_trace("e2")]
        for _ in range(5):
            report = analyzer.analyze(traces, state)
            assert 0.0 <= report.score.overall <= 1.0
            assert 0.0 <= report.score.failure_score <= 1.0
            assert 0.0 <= report.score.drift_score <= 1.0

    def test_failure_score_reflects_failure_rate(self):
        store = IntelligenceStore()
        analyzer = StabilityAnalyzer(store)
        state = RuntimeState()
        traces = [
            make_trace("e1", execution_status="FAILED", final_status="SANDBOX_FAILED"),
            make_trace("e2", execution_status="SUCCESS"),
        ]
        report = analyzer.analyze(traces, state)
        assert report.score.failure_score == 0.5

    def test_drift_score_reflects_drift_rate(self):
        store = IntelligenceStore()
        analyzer = StabilityAnalyzer(store)
        state = RuntimeState()
        traces = [
            make_trace("e1", p4_verdict="BLOCK", final_status="P4_BLOCK"),
            make_trace("e2", p4_verdict="ALLOW", execution_status="SUCCESS"),
        ]
        report = analyzer.analyze(traces, state)
        assert report.score.drift_score == 0.5

    def test_regression_score_with_no_failures(self):
        store = IntelligenceStore()
        analyzer = StabilityAnalyzer(store)
        state = RuntimeState()
        report = analyzer.analyze([make_trace("e1")], state)
        assert report.score.system_regression_score == 1.0

    def test_regression_score_with_consecutive_failures(self):
        store = IntelligenceStore()
        analyzer = StabilityAnalyzer(store)
        state = RuntimeState(consecutive_failures=3)
        report = analyzer.analyze([make_trace("e1")], state)
        assert report.score.system_regression_score == 0.3

    def test_regression_score_critical_failures(self):
        store = IntelligenceStore()
        analyzer = StabilityAnalyzer(store)
        state = RuntimeState(consecutive_failures=5)
        report = analyzer.analyze([make_trace("e1")], state)
        assert report.score.system_regression_score == 0.0

    def test_timing_stability_perfect(self):
        store = IntelligenceStore()
        analyzer = StabilityAnalyzer(store)
        state = RuntimeState()
        traces = [make_trace("e1", total_time=50.0)]
        report = analyzer.analyze(traces, state)
        assert report.score.timing_stability == 1.0

    def test_timing_stability_with_variance(self):
        store = IntelligenceStore()
        analyzer = StabilityAnalyzer(store)
        state = RuntimeState()
        traces = [
            make_trace("e1", total_time=50.0),
            make_trace("e2", total_time=150.0),
        ]
        report = analyzer.analyze(traces, state)
        assert report.score.timing_stability < 1.0

    def test_consistency_score_with_stored_pattern(self):
        store = IntelligenceStore()
        sig = "True::ALLOW::SUCCESS::P4_ALLOW::[]"
        store._patterns[sig] = Pattern(
            pattern_id="p1", frequency=1, structure_signature=sig, context_shape={},
        )
        analyzer = StabilityAnalyzer(store)
        state = RuntimeState()
        traces = [make_trace("e1", p4_verdict="ALLOW", execution_status="SUCCESS")]
        report = analyzer.analyze(traces, state)
        assert report.score.consistency_score > 0

    def test_novelty_score_with_known_pattern(self):
        store = IntelligenceStore()
        sig = "True::ALLOW::SUCCESS::P4_ALLOW::[]"
        store._patterns[sig] = Pattern(
            pattern_id="p1", frequency=1, structure_signature=sig, context_shape={},
        )
        analyzer = StabilityAnalyzer(store)
        state = RuntimeState()
        traces = [make_trace("e1", p4_verdict="ALLOW", execution_status="SUCCESS")]
        report = analyzer.analyze(traces, state)
        assert report.score.novelty_score > 0.5

    def test_overall_score_composition(self):
        store = IntelligenceStore()
        analyzer = StabilityAnalyzer(store)
        state = RuntimeState()
        traces = [make_trace("e1")]
        report = analyzer.analyze(traces, state)
        expected = (
            report.score.failure_score * 0.30
            + report.score.drift_score * 0.20
            + report.score.consistency_score * 0.15
            + report.score.timing_stability * 0.10
            + report.score.novelty_score * 0.10
            + report.score.system_regression_score * 0.15
        )
        assert report.score.overall == round(expected, 4)


# ════════════════════════════════════════════
# StabilityAnalyzer — Score History
# ════════════════════════════════════════════

class TestScoreHistory:
    def test_score_history_accumulates(self):
        store = IntelligenceStore()
        analyzer = StabilityAnalyzer(store)
        state = RuntimeState()
        t = [make_trace("e1")]
        analyzer.analyze(t, state)
        analyzer.analyze(t, state)
        assert len(analyzer._score_history) == 2

    def test_score_history_limited_to_history_size(self):
        store = IntelligenceStore()
        analyzer = StabilityAnalyzer(store, history_size=3)
        state = RuntimeState()
        t = [make_trace("e1")]
        for _ in range(10):
            analyzer.analyze(t, state)
        assert len(analyzer._score_history) == 3


# ════════════════════════════════════════════
# StabilityAnalyzer — Trend Detection
# ════════════════════════════════════════════

class TestTrendDetection:
    def test_trend_stable_with_less_than_two_scores(self):
        store = IntelligenceStore()
        analyzer = StabilityAnalyzer(store)
        state = RuntimeState()
        report = analyzer.analyze([make_trace("e1")], state)
        assert report.trend.direction == "stable"
        assert report.trend.delta == 0.0
        assert report.trend.window_count == 1

    def test_trend_stable_when_delta_below_threshold(self):
        store = IntelligenceStore()
        analyzer = StabilityAnalyzer(store)
        state = RuntimeState()
        t = [make_trace("e1")]
        for _ in range(5):
            analyzer.analyze(t, state)
        # Replace history with stable values (small delta < 0.02)
        analyzer._score_history[:] = [0.80, 0.80, 0.80, 0.80, 0.80]
        report = analyzer.analyze(t, state)
        # After analyze: [0.80, 0.80, 0.80, 0.80, 0.80, computed]
        # recent=last 5=[0.80, 0.80, 0.80, 0.80, computed], mid=2
        # avg_first=(0.80+0.80)/2=0.80, avg_second=(0.80+0.80+computed)/3
        # computed ≈ 0.75, avg_second≈0.783, delta≈-0.017 < 0.02 → stable
        assert report.trend.direction == "stable"

    def test_trend_improving(self):
        store = IntelligenceStore()
        analyzer = StabilityAnalyzer(store)
        state = RuntimeState()
        t = [make_trace("e1")]
        for _ in range(5):
            analyzer.analyze(t, state)
        analyzer._score_history[:] = [0.50, 0.50, 0.50, 0.80, 0.80]
        report = analyzer.analyze(t, state)
        # recent=last 5=[0.50, 0.50, 0.80, 0.80, computed], mid=2
        # avg_first=(0.50+0.50)/2=0.50, avg_second=(0.80+0.80+0.75)/3≈0.783
        # delta≈0.283 > 0.02 → improving
        assert report.trend.direction == "improving"

    def test_trend_degrading(self):
        store = IntelligenceStore()
        analyzer = StabilityAnalyzer(store)
        state = RuntimeState()
        t = [make_trace("e1")]
        for _ in range(5):
            analyzer.analyze(t, state)
        analyzer._score_history[:] = [0.80, 0.80, 0.80, 0.50, 0.50]
        report = analyzer.analyze(t, state)
        # recent=last 5=[0.80, 0.80, 0.50, 0.50, computed], mid=2
        # avg_first=(0.80+0.80)/2=0.80, avg_second=(0.50+0.50+0.75)/3≈0.583
        # delta≈-0.217 < 0 → degrading
        assert report.trend.direction == "degrading"

    def test_trend_window_count(self):
        store = IntelligenceStore()
        analyzer = StabilityAnalyzer(store)
        state = RuntimeState()
        t = [make_trace("e1")]
        for _ in range(5):
            analyzer.analyze(t, state)
        report = analyzer.analyze(t, state)
        assert report.trend.window_count == 6


# ════════════════════════════════════════════
# StabilityAnalyzer — Anomaly Detection
# ════════════════════════════════════════════

class TestAnomalyDetection:
    def test_anomaly_high_failure_rate(self):
        store = IntelligenceStore()
        analyzer = StabilityAnalyzer(store)
        state = RuntimeState()
        traces = [
            make_trace("e1", execution_status="FAILED", final_status="SANDBOX_FAILED"),
            make_trace("e2", execution_status="FAILED", final_status="SANDBOX_FAILED"),
            make_trace("e3", execution_status="FAILED", final_status="SANDBOX_FAILED"),
            make_trace("e4", execution_status="SUCCESS"),
        ]
        report = analyzer.analyze(traces, state)
        assert any("high_failure_rate" in a for a in report.anomalies)

    def test_no_anomaly_low_failure_rate(self):
        store = IntelligenceStore()
        analyzer = StabilityAnalyzer(store)
        state = RuntimeState()
        traces = [
            make_trace("e1", execution_status="FAILED", final_status="SANDBOX_FAILED"),
            make_trace("e2", execution_status="SUCCESS"),
            make_trace("e3", execution_status="SUCCESS"),
            make_trace("e4", execution_status="SUCCESS"),
        ]
        report = analyzer.analyze(traces, state)
        assert not any("high_failure_rate" in a for a in report.anomalies)

    def test_anomaly_elevated_drift_rate(self):
        store = IntelligenceStore()
        analyzer = StabilityAnalyzer(store)
        state = RuntimeState()
        traces = [
            make_trace("e1", p4_verdict="BLOCK", final_status="P4_BLOCK"),
            make_trace("e2", p4_verdict="BLOCK", final_status="P4_BLOCK"),
            make_trace("e3", p4_verdict="BLOCK", final_status="P4_BLOCK"),
            make_trace("e4", p4_verdict="ALLOW", execution_status="SUCCESS"),
        ]
        report = analyzer.analyze(traces, state)
        assert any("elevated_drift_rate" in a for a in report.anomalies)

    def test_anomaly_high_pattern_novelty(self):
        store = IntelligenceStore()
        analyzer = StabilityAnalyzer(store)
        state = RuntimeState()
        traces = [
            make_trace("e1", p4_verdict="ALLOW", execution_status="SUCCESS",
                       capabilities=["a"]),
            make_trace("e2", p4_verdict="BLOCK", final_status="P4_BLOCK",
                       capabilities=["b"]),
        ]
        report = analyzer.analyze(traces, state)
        assert any("high_pattern_novelty" in a for a in report.anomalies)

    def test_anomaly_system_regression(self):
        store = IntelligenceStore()
        analyzer = StabilityAnalyzer(store)
        state = RuntimeState(consecutive_failures=3)
        traces = [make_trace("e1")]
        report = analyzer.analyze(traces, state)
        assert any("system_regression" in a for a in report.anomalies)

    def test_anomaly_stuck_in_failure(self):
        store = IntelligenceStore()
        analyzer = StabilityAnalyzer(store)
        state = RuntimeState(consecutive_failures=5)
        traces = [make_trace("e1")]
        report = analyzer.analyze(traces, state)
        assert any("stuck_in_failure" in a for a in report.anomalies)

    def test_no_false_anomalies_with_perfect_data(self):
        store = IntelligenceStore()
        analyzer = StabilityAnalyzer(store)
        state = RuntimeState()
        # Pre-populate pattern to prevent novelty anomaly on first cycle
        store.upsert_pattern(Pattern(
            pattern_id="existing", frequency=1,
            structure_signature="True::ALLOW::SUCCESS::P4_ALLOW::[]",
            context_shape={},
        ))
        traces = [make_trace("e1")]
        report = analyzer.analyze(traces, state)
        assert len(report.anomalies) == 0

    def test_multiple_anomalies_can_fire(self):
        store = IntelligenceStore()
        analyzer = StabilityAnalyzer(store)
        state = RuntimeState(consecutive_failures=5)
        traces = [
            make_trace("e1", execution_status="FAILED", final_status="SANDBOX_FAILED"),
            make_trace("e2", execution_status="FAILED", final_status="SANDBOX_FAILED"),
            make_trace("e3", execution_status="FAILED", final_status="SANDBOX_FAILED"),
            make_trace("e4", execution_status="FAILED", final_status="SANDBOX_FAILED"),
        ]
        report = analyzer.analyze(traces, state)
        anomaly_types = {a.split(":")[0] for a in report.anomalies}
        assert "high_failure_rate" in anomaly_types
        assert "system_regression" in anomaly_types
        assert "stuck_in_failure" in anomaly_types


# ════════════════════════════════════════════
# StabilityAnalyzer — _trace_signature
# ════════════════════════════════════════════

class TestTraceSignature:
    def test_signature_format(self):
        analyzer = StabilityAnalyzer(IntelligenceStore())
        t = make_trace("e1", preflight_valid=True, p4_verdict="ALLOW",
                       execution_status="SUCCESS", final_status="P4_ALLOW",
                       capabilities=["fs.read"])
        sig = analyzer._trace_signature(t)
        assert "True" in sig
        assert "ALLOW" in sig
        assert "SUCCESS" in sig
        assert "P4_ALLOW" in sig
        assert "fs.read" in sig

    def test_signature_consistency(self):
        analyzer = StabilityAnalyzer(IntelligenceStore())
        t1 = make_trace("e1", p4_verdict="ALLOW")
        t2 = make_trace("e2", p4_verdict="ALLOW")
        assert analyzer._trace_signature(t1) == analyzer._trace_signature(t2)

    def test_signature_different_verdict(self):
        analyzer = StabilityAnalyzer(IntelligenceStore())
        t1 = make_trace("e1", p4_verdict="ALLOW")
        t2 = make_trace("e2", p4_verdict="BLOCK")
        assert analyzer._trace_signature(t1) != analyzer._trace_signature(t2)
