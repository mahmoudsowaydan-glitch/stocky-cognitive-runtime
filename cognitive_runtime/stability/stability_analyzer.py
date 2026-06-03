import math
import uuid
from typing import Dict, List, Optional

from ..contracts.execution_trace import ExecutionTrace
from ..contracts.causal_graph import CausalGraph
from ..runtime.runtime_state import RuntimeState
from ..intelligence.intelligence_store import IntelligenceStore
from .stability_index import StabilityWindow, StabilityScore, StabilityTrend, StabilityReport


class StabilityAnalyzer:
    def __init__(self, store: IntelligenceStore,
                 window_size: int = 100,
                 history_size: int = 10):
        self._store = store
        self._window_size = window_size
        self._history_size = history_size
        self._window_history: List[StabilityWindow] = []
        self._score_history: List[float] = []

    def analyze(self, traces: List[ExecutionTrace],
                state: RuntimeState,
                graph: Optional[CausalGraph] = None) -> StabilityReport:
        window = self._compute_window(traces, state)
        self._window_history.append(window)
        if len(self._window_history) > self._history_size:
            self._window_history.pop(0)

        score = self._compute_score(window, state)
        self._score_history.append(score.overall)
        if len(self._score_history) > self._history_size:
            self._score_history.pop(0)

        trend = self._compute_trend()
        anomalies = self._detect_anomalies(window, score, state)

        return StabilityReport(
            current_window=window,
            score=score,
            trend=trend,
            anomalies=anomalies,
        )

    def _compute_window(self, traces: List[ExecutionTrace],
                        state: RuntimeState) -> StabilityWindow:
        window = traces[-self._window_size:] if len(traces) > self._window_size else traces
        total = len(window)
        if total == 0:
            return StabilityWindow(
                window_id=str(uuid.uuid4()), trace_count=0,
                failure_rate=0.0, drift_rate=0.0,
                avg_cycle_ms=0.0, cycle_time_std=0.0,
                new_pattern_ratio=0.0, pattern_repeat_rate=0.0,
                recovery_speed=0,
            )

        failures = sum(1 for t in window if t.execution_status in ("FAILED",))
        failure_rate = failures / total

        drift_count = 0
        for t in window:
            if t.preflight_valid and t.p4_verdict in ("BLOCK", "DEFER"):
                drift_count += 1
            elif t.p4_verdict == "ALLOW" and t.execution_status == "FAILED":
                drift_count += 1
            elif t.risk_score > 0.9 and t.p4_verdict == "ALLOW":
                drift_count += 1
        drift_rate = drift_count / total

        times = [t.total_time for t in window if t.total_time > 0]
        avg_ms = sum(times) / len(times) if times else 0.0
        if len(times) > 1:
            variance = sum((t - avg_ms) ** 2 for t in times) / len(times)
            std_ms = math.sqrt(variance)
        else:
            std_ms = 0.0

        repeats = 0
        for t in window:
            sig = self._trace_signature(t)
            if self._store.get_pattern(sig) is not None:
                repeats += 1
        pattern_repeat_rate = repeats / total if total > 0 else 0.0

        seen = set()
        new_count = 0
        for t in window:
            sig = self._trace_signature(t)
            if sig not in seen:
                seen.add(sig)
                if self._store.get_pattern(sig) is None:
                    new_count += 1
        new_pattern_ratio = new_count / len(seen) if seen else 0.0

        return StabilityWindow(
            window_id=str(uuid.uuid4()),
            trace_count=total,
            failure_rate=round(failure_rate, 6),
            drift_rate=round(drift_rate, 6),
            avg_cycle_ms=round(avg_ms, 6),
            cycle_time_std=round(std_ms, 6),
            new_pattern_ratio=round(new_pattern_ratio, 6),
            pattern_repeat_rate=round(pattern_repeat_rate, 6),
            recovery_speed=state.consecutive_failures,
        )

    def _compute_score(self, window: StabilityWindow,
                       state: RuntimeState) -> StabilityScore:
        failure_score = 1.0 - window.failure_rate
        drift_score = 1.0 - window.drift_rate
        consistency_score = window.pattern_repeat_rate

        if window.avg_cycle_ms > 0 and window.cycle_time_std > 0:
            cv = window.cycle_time_std / window.avg_cycle_ms
            timing_stability = max(0.0, 1.0 - min(1.0, cv))
        else:
            timing_stability = 1.0

        novelty_score = 1.0 - window.new_pattern_ratio

        if state.consecutive_failures >= 5:
            regression_score = 0.0
        elif state.consecutive_failures >= 3:
            regression_score = 0.3
        elif state.consecutive_failures >= 1:
            regression_score = 0.7
        else:
            regression_score = 1.0

        overall = (
            failure_score * 0.30
            + drift_score * 0.20
            + consistency_score * 0.15
            + timing_stability * 0.10
            + novelty_score * 0.10
            + regression_score * 0.15
        )

        return StabilityScore(
            overall=round(overall, 4),
            failure_score=round(failure_score, 4),
            drift_score=round(drift_score, 4),
            consistency_score=round(consistency_score, 4),
            timing_stability=round(timing_stability, 4),
            novelty_score=round(novelty_score, 4),
            system_regression_score=round(regression_score, 4),
        )

    def _compute_trend(self) -> StabilityTrend:
        if len(self._score_history) < 2:
            return StabilityTrend(
                direction="stable", delta=0.0,
                window_count=len(self._score_history),
                last_n_scores=list(self._score_history),
            )

        recent = self._score_history[-min(5, len(self._score_history)):]
        mid = len(recent) // 2
        avg_first = sum(recent[:mid]) / mid
        avg_second = sum(recent[mid:]) / (len(recent) - mid)

        delta = avg_second - avg_first
        abs_delta = abs(delta)

        if abs_delta < 0.02:
            direction = "stable"
        elif delta > 0:
            direction = "improving"
        else:
            direction = "degrading"

        return StabilityTrend(
            direction=direction,
            delta=round(delta, 4),
            window_count=len(self._score_history),
            last_n_scores=list(self._score_history),
        )

    def _detect_anomalies(self, window: StabilityWindow,
                          score: StabilityScore,
                          state: RuntimeState) -> List[str]:
        anomalies = []

        if window.failure_rate > 0.3:
            anomalies.append(f"high_failure_rate: {window.failure_rate:.1%} in last {window.trace_count} cycles")
        if window.drift_rate > 0.2:
            anomalies.append(f"elevated_drift_rate: {window.drift_rate:.1%}")
        if window.new_pattern_ratio > 0.5:
            anomalies.append(f"high_pattern_novelty: {window.new_pattern_ratio:.1%} of structures are new")
        if score.system_regression_score < 0.5:
            anomalies.append(f"system_regression: consecutive_failures={state.consecutive_failures}")
        if window.cycle_time_std > window.avg_cycle_ms * 2 and window.avg_cycle_ms > 0:
            anomalies.append(f"timing_instability: std={window.cycle_time_std:.1f}ms exceeds 2x avg={window.avg_cycle_ms:.1f}ms")
        if window.recovery_speed >= 5:
            anomalies.append(f"stuck_in_failure: {window.recovery_speed} consecutive failures without recovery")

        return anomalies

    def _trace_signature(self, trace: ExecutionTrace) -> str:
        parts = [
            str(trace.preflight_valid),
            trace.p4_verdict,
            trace.execution_status,
            trace.final_status,
            str(sorted(trace.capabilities_checked)),
        ]
        return "::".join(parts)

    @property
    def score_history(self) -> List[float]:
        return list(self._score_history)
