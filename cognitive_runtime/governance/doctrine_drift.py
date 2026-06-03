from typing import List

from ..contracts.execution_trace import ExecutionTrace
from ..runtime.coherence_monitor import CoherenceReport
from .governance_report import DriftMetrics


class DoctrineDrift:
    def analyze(self, traces: List[ExecutionTrace],
                coherence_reports: List[CoherenceReport]) -> DriftMetrics:
        total = len(traces)
        if total == 0:
            return DriftMetrics(
                preflight_overreach=0.0, p4_avoidance=0.0,
                risk_influence=0.0, coherence_drift_rate=0.0, overall=0.0,
            )

        preflight_overreach = self._preflight_overreach(traces)
        p4_avoidance = self._p4_avoidance(traces)
        risk_influence = self._risk_influence(traces)
        coherence_drift_rate = self._coherence_drift(coherence_reports)

        overall = (
            0.30 * preflight_overreach
            + 0.30 * p4_avoidance
            + 0.20 * risk_influence
            + 0.20 * coherence_drift_rate
        )

        return DriftMetrics(
            preflight_overreach=round(preflight_overreach, 4),
            p4_avoidance=round(p4_avoidance, 4),
            risk_influence=round(risk_influence, 4),
            coherence_drift_rate=round(coherence_drift_rate, 4),
            overall=round(min(1.0, overall), 4),
        )

    def _preflight_overreach(self, traces: List[ExecutionTrace]) -> float:
        blocked = sum(1 for t in traces if t.preflight_valid is False)
        return min(1.0, blocked / len(traces))

    def _p4_avoidance(self, traces: List[ExecutionTrace]) -> float:
        non_allow = sum(1 for t in traces if t.p4_verdict not in ("ALLOW", "UNKNOWN"))
        return min(1.0, non_allow / len(traces))

    def _risk_influence(self, traces: List[ExecutionTrace]) -> float:
        blocked = [t for t in traces if t.p4_verdict in ("BLOCK", "DEFER")]
        if not blocked:
            return 0.0
        high_risk_blocked = sum(1 for t in blocked if t.risk_score > 0.5)
        return min(1.0, high_risk_blocked / len(blocked))

    def _coherence_drift(self, reports: List[CoherenceReport]) -> float:
        if len(reports) < 5:
            return 0.0
        recent = reports[-5:]
        total_drift = sum(r.drift_count for r in recent)
        max_possible = len(recent)
        return min(1.0, total_drift / max_possible) if max_possible > 0 else 0.0
