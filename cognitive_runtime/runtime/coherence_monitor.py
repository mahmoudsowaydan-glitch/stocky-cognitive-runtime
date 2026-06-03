"""
coherence_monitor.py — Consistency checker between runtime layers.

Detects drift between:
  - Preflight validity vs P4 decision
  - P4 decision vs Sandbox outcome
  - Causal graph dominance patterns
Observational only — never influences execution.
"""

from collections import deque
from dataclasses import dataclass, field
from typing import Any, Deque, Dict, List, Optional

from ..contracts.causal_graph import CausalGraph, CausalNode
from ..contracts.execution_trace import ExecutionTrace


@dataclass
class CoherenceReport:
    drift_detected: bool = False
    drift_count: int = 0
    warnings: List[str] = field(default_factory=list)
    inconsistencies: List[Dict[str, Any]] = field(default_factory=list)


class CoherenceMonitor:
    def __init__(self, max_history: int = 1000):
        self._report = CoherenceReport()
        self._history: Deque[CoherenceReport] = deque(maxlen=max_history)

    def check_trace(self, trace: ExecutionTrace) -> CoherenceReport:
        report = CoherenceReport()

        # Rule 1: Preflight valid but P4 blocked
        if trace.preflight_valid and trace.p4_verdict in ("BLOCK", "DEFER"):
            report.drift_count += 1
            report.warnings.append(
                f"preflight_passed_but_p4_blocked: {trace.event_id}"
            )
            report.inconsistencies.append({
                "type": "preflight_p4_mismatch",
                "event_id": trace.event_id,
                "preflight": "valid",
                "p4": trace.p4_verdict,
            })

        # Rule 2: P4 allowed but sandbox failed
        if trace.p4_verdict == "ALLOW" and trace.execution_status == "FAILED":
            report.drift_count += 1
            report.warnings.append(
                f"p4_allowed_but_sandbox_failed: {trace.event_id}"
            )
            report.inconsistencies.append({
                "type": "p4_sandbox_mismatch",
                "event_id": trace.event_id,
                "p4": "ALLOW",
                "sandbox": "FAILED",
                "error": trace.execution_error,
            })

        # Rule 3: High risk but P4 allowed
        if trace.risk_score > 0.8 and trace.p4_verdict == "ALLOW":
            report.warnings.append(
                f"high_risk_allowed_by_p4: {trace.event_id} risk={trace.risk_score}"
            )

        # Rule 4: Very low confidence but not blocked
        if trace.preflight_valid and trace.p4_verdict == "ALLOW":
            if trace.risk_score > 0.9:
                report.drift_count += 1
                report.warnings.append(
                    f"extreme_risk_not_blocked: {trace.event_id} risk={trace.risk_score}"
                )
                report.inconsistencies.append({
                    "type": "extreme_risk_not_blocked",
                    "event_id": trace.event_id,
                    "risk_score": trace.risk_score,
                })

        report.drift_detected = report.drift_count > 0
        self._report = report
        self._history.append(report)
        return report

    def check_causal_graph(self, graph: CausalGraph) -> CoherenceReport:
        report = CoherenceReport()

        # Check for unexpected dominant layer patterns
        dom = graph.dominant_layers
        if dom.get("decision", 0) > 0 and len(graph.failure_points) > 0:
            for node in graph.failure_points:
                report.warnings.append(
                    f"failure_under_p4_dominant: {node.event_id}"
                )

        report.drift_detected = report.drift_count > 0
        return report

    @property
    def report(self) -> CoherenceReport:
        return self._report

    @property
    def history(self) -> List[CoherenceReport]:
        return list(self._history)

    def reset(self) -> None:
        self._report = CoherenceReport()
        self._history.clear()
