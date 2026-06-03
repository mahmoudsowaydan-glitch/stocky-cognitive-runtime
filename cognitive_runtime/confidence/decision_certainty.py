from typing import Dict, List, Optional

from ..contracts.execution_trace import ExecutionTrace
from .confidence_index import DecisionCertainty


class DecisionCertaintyAnalyzer:
    BLOCK_THRESHOLD = 0.5

    def analyze(self, traces: List[ExecutionTrace]) -> DecisionCertainty:
        if not traces:
            return DecisionCertainty(
                risk_proximity=1.0, verdict_clarity=1.0,
                rule_conflict_density=0.0, overall=1.0,
            )

        risk_certainty = self._compute_risk_certainty(traces)
        verdict_clarity = self._compute_verdict_clarity(traces)
        rule_conflict = self._compute_rule_conflict(traces)

        overall = (
            0.5 * risk_certainty
            + 0.3 * verdict_clarity
            + 0.2 * (1.0 - rule_conflict)
        )

        return DecisionCertainty(
            risk_proximity=round(risk_certainty, 4),
            verdict_clarity=round(verdict_clarity, 4),
            rule_conflict_density=round(rule_conflict, 4),
            overall=round(overall, 4),
        )

    def _compute_risk_certainty(self, traces: List[ExecutionTrace]) -> float:
        scores = [t.risk_score for t in traces if 0 <= t.risk_score <= 1]
        if not scores:
            return 1.0
        avg_proximity = sum(2.0 * abs(s - self.BLOCK_THRESHOLD) for s in scores) / len(scores)
        return min(1.0, avg_proximity)

    def _compute_verdict_clarity(self, traces: List[ExecutionTrace]) -> float:
        verdicts = [t.p4_verdict for t in traces if t.p4_verdict not in ("UNKNOWN", "")]
        if not verdicts:
            return 1.0

        counts: dict = {}
        for v in verdicts:
            counts[v] = counts.get(v, 0) + 1

        dominant_count = max(counts.values())
        return dominant_count / len(verdicts)

    def _compute_rule_conflict(self, traces: List[ExecutionTrace]) -> float:
        triggered = sum(1 for t in traces if t.p4_rule_triggered is not None)
        return triggered / len(traces) if traces else 0.0
