from typing import List

from ..contracts.execution_trace import ExecutionTrace
from .governance_report import PressureMetrics


class GovernancePressure:
    def analyze(self, traces: List[ExecutionTrace]) -> PressureMetrics:
        total = len(traces)
        if total == 0:
            return PressureMetrics(
                rule_conflict_rate=0.0, p4_overload_rate=0.0,
                ambiguity_rate=0.0, escalation_rate=0.0, overall=0.0,
            )

        rule_conflict_rate = self._rule_conflict_rate(traces)
        p4_overload_rate = self._p4_overload_rate(traces)
        ambiguity_rate = self._ambiguity_rate(traces)
        escalation_rate = self._escalation_rate(traces)

        overall = (
            0.30 * rule_conflict_rate
            + 0.30 * p4_overload_rate
            + 0.25 * ambiguity_rate
            + 0.15 * escalation_rate
        )

        return PressureMetrics(
            rule_conflict_rate=round(rule_conflict_rate, 4),
            p4_overload_rate=round(p4_overload_rate, 4),
            ambiguity_rate=round(ambiguity_rate, 4),
            escalation_rate=round(escalation_rate, 4),
            overall=round(min(1.0, overall), 4),
        )

    def _rule_conflict_rate(self, traces: List[ExecutionTrace]) -> float:
        triggered = sum(1 for t in traces if t.p4_rule_triggered is not None)
        return min(1.0, triggered / len(traces))

    def _p4_overload_rate(self, traces: List[ExecutionTrace]) -> float:
        triggered = [t.p4_rule_triggered for t in traces if t.p4_rule_triggered is not None]
        if not triggered:
            return 0.0
        freq: dict = {}
        for r in triggered:
            freq[r] = freq.get(r, 0) + 1
        max_repeated = max(freq.values())
        return min(1.0, (max_repeated - 1) / max(1, len(triggered)))

    def _ambiguity_rate(self, traces: List[ExecutionTrace]) -> float:
        ambiguous = sum(1 for t in traces if t.p4_verdict in ("DEFER", "REVIEW"))
        return min(1.0, ambiguous / len(traces))

    def _escalation_rate(self, traces: List[ExecutionTrace]) -> float:
        escalated = sum(1 for t in traces if t.p4_verdict in ("BLOCK", "DEFER", "REVIEW"))
        return min(1.0, escalated / len(traces))
