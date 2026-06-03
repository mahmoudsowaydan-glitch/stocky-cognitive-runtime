from typing import Any, Dict, List, Optional

from ..contracts.execution_trace import ExecutionTrace
from ..runtime.runtime_state import RuntimeState
from .confidence_index import (
    ConfidenceReport,
    ExecutionConfidenceGradient,
    RuntimeConfidenceScore,
)
from .decision_certainty import DecisionCertaintyAnalyzer
from .gradient_transition_guard import GradientTransitionGuard
from .operational_readiness import OperationalReadinessAnalyzer


class RuntimeConfidenceEngine:
    def __init__(self):
        self._decision = DecisionCertaintyAnalyzer()
        self._operational = OperationalReadinessAnalyzer()
        self._guard = GradientTransitionGuard()
        self._score_history: List[float] = []
        self._last_stability_snapshot: Optional[float] = None

    def assess(self, traces: List[ExecutionTrace],
               state: RuntimeState,
               queue_snapshot: Dict[str, Any],
               stability_snapshot: Optional[float] = None) -> ConfidenceReport:
        if stability_snapshot is not None:
            self._last_stability_snapshot = stability_snapshot

        decision_score = self._decision.analyze(traces)
        operational_score = self._operational.analyze(queue_snapshot)
        execution_score = self._compute_execution_confidence(traces)

        runtime_confidence = (
            0.4 * decision_score.overall
            + 0.3 * operational_score.overall
            + 0.3 * execution_score
        )
        runtime_confidence = round(min(1.0, max(0.0, runtime_confidence)), 4)

        gradient = self._guard.resolve(runtime_confidence)

        self._score_history.append(runtime_confidence)
        if len(self._score_history) > 20:
            self._score_history.pop(0)

        trend = self._detect_trend()
        degradation = self._detect_degradation()

        score = RuntimeConfidenceScore(
            decision_confidence=decision_score.overall,
            operational_confidence=operational_score.overall,
            execution_confidence=round(execution_score, 4),
            overall=runtime_confidence,
            gradient=gradient,
        )

        return ConfidenceReport(
            score=score,
            gradient=gradient,
            referenced_stability_snapshot=self._last_stability_snapshot,
            trend_direction=trend["direction"],
            trend_delta=trend["delta"],
            degradation_detected=degradation,
        )

    def _compute_execution_confidence(self, traces: List[ExecutionTrace]) -> float:
        if not traces:
            return 1.0

        allowed = [t for t in traces if t.p4_verdict == "ALLOW"]
        total_allowed = len(allowed)
        total = len(traces)

        if total_allowed == 0:
            return 0.5

        succeeded = sum(1 for t in allowed if t.execution_status == "SUCCESS")
        success_rate = succeeded / total_allowed
        allow_rate = total_allowed / total

        return success_rate * (0.5 + 0.5 * allow_rate)

    def _detect_trend(self) -> Dict[str, float]:
        if len(self._score_history) < 2:
            return {"direction": "stable", "delta": 0.0}

        recent = self._score_history[-min(10, len(self._score_history)):]
        mid = len(recent) // 2
        avg_first = sum(recent[:mid]) / mid
        avg_second = sum(recent[mid:]) / (len(recent) - mid)
        delta = avg_second - avg_first

        if abs(delta) < 0.02:
            return {"direction": "stable", "delta": round(delta, 4)}
        elif delta > 0:
            return {"direction": "improving", "delta": round(delta, 4)}
        else:
            return {"direction": "degrading", "delta": round(delta, 4)}

    def _detect_degradation(self) -> bool:
        if len(self._score_history) < 3:
            return False
        recent = self._score_history[-3:]
        return all(recent[i] <= recent[i - 1] for i in range(1, 3))

    @property
    def current_gradient(self) -> Optional[ExecutionConfidenceGradient]:
        return self._guard.current_gradient

    @property
    def score_history(self) -> List[float]:
        return list(self._score_history)
