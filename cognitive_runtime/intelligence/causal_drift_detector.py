from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ..contracts.causal_graph import CausalGraph
from ..contracts.execution_trace import ExecutionTrace
from .causal_runtime_fingerprint import CausalRuntimeFingerprint


@dataclass(frozen=True)
class DriftReport:
    has_drift: bool
    event_id: Optional[str] = None
    baseline_status: Optional[str] = None
    current_status: Optional[str] = None
    baseline_node_count: Optional[int] = None
    current_node_count: Optional[int] = None
    baseline_edge_count: Optional[int] = None
    current_edge_count: Optional[int] = None
    fingerprint_match: bool = True
    mismatched_events: List[str] = field(default_factory=list)
    reason: str = ""

    @property
    def summary(self) -> str:
        if not self.has_drift:
            return "[OK] No drift detected"
        return f"[DRIFT] {self.reason} ({len(self.mismatched_events)} mismatched events)"


@dataclass(frozen=True)
class ReplayDivergenceReport:
    has_divergence: bool
    diverged_events: List[str] = field(default_factory=list)
    fingerprint_before: Optional[str] = None
    fingerprint_after: Optional[str] = None
    integrity_before: int = 0
    integrity_after: int = 0
    node_count_before: int = 0
    node_count_after: int = 0

    @property
    def summary(self) -> str:
        if not self.has_divergence:
            return "[OK] No replay divergence"
        return (
            f"[DIVERGENCE] {len(self.diverged_events)} events "
            f"(fp_match={self.fingerprint_before == self.fingerprint_after})"
        )


class CausalDriftDetector:
    """
    Detects behavioral drift without structural cause.

    A drift occurs when:
    - same inputs produce different causal output
    - replay produces different trace structure
    - hidden mutation changes causal flow
    """

    def __init__(self, fingerprint_builder: Optional[CausalRuntimeFingerprint] = None):
        self._fp_builder = fingerprint_builder or CausalRuntimeFingerprint()

    def detect_drift(self,
                     baseline_traces: List[ExecutionTrace],
                     baseline_graph: CausalGraph,
                     current_traces: List[ExecutionTrace],
                     current_graph: CausalGraph) -> DriftReport:
        baseline_by_event = {t.event_id: t for t in baseline_traces}
        current_by_event = {t.event_id: t for t in current_traces}

        all_event_ids = set(baseline_by_event.keys()) | set(current_by_event.keys())
        mismatched: List[str] = []

        for eid in all_event_ids:
            b = baseline_by_event.get(eid)
            c = current_by_event.get(eid)
            if b is None and c is not None:
                mismatched.append(f"{eid}:new_in_current")
            elif c is None and b is not None:
                mismatched.append(f"{eid}:missing_in_current")
            elif b is not None and c is not None:
                if b.final_status != c.final_status:
                    mismatched.append(f"{eid}:status({b.final_status}->{c.final_status})")
                elif b.p4_verdict != c.p4_verdict:
                    mismatched.append(f"{eid}:verdict({b.p4_verdict}->{c.p4_verdict})")

        has_drift = len(mismatched) > 0

        fp_b = self._fp_builder.compute(baseline_traces, baseline_graph)
        fp_c = self._fp_builder.compute(current_traces, current_graph)
        fp_match = fp_b == fp_c

        first_mismatch = mismatched[0] if mismatched else ""
        parts = first_mismatch.split(":", 1)
        meid = parts[0] if len(parts) > 0 else None
        mstatus = parts[1] if len(parts) > 1 else ""

        return DriftReport(
            has_drift=has_drift or not fp_match,
            event_id=meid,
            baseline_status=baseline_by_event.get(meid).final_status if meid and meid in baseline_by_event else None,
            current_status=current_by_event.get(meid).final_status if meid and meid in current_by_event else None,
            baseline_node_count=len(baseline_graph.nodes),
            current_node_count=len(current_graph.nodes),
            baseline_edge_count=len(baseline_graph.edges),
            current_edge_count=len(current_graph.edges),
            fingerprint_match=fp_match,
            mismatched_events=mismatched,
            reason=f"Drift detected: {len(mismatched)} event(s) differ"
                   if has_drift
                   else "Fingerprint mismatch without structural change"
                   if not fp_match and not has_drift
                   else "No drift",
        )

    def detect_replay_divergence(self,
                                 before_traces: List[ExecutionTrace],
                                 before_graph: CausalGraph,
                                 after_traces: List[ExecutionTrace],
                                 after_graph: CausalGraph) -> ReplayDivergenceReport:
        fp_before = self._fp_builder.compute(before_traces, before_graph)
        fp_after = self._fp_builder.compute(after_traces, after_graph, is_replay=True)

        before_by_eid = {t.event_id: t for t in before_traces}
        after_by_eid = {t.event_id: t for t in after_traces}

        diverged = []
        for eid in before_by_eid:
            b = before_by_eid[eid]
            a = after_by_eid.get(eid)
            if a is not None and b.final_status != a.final_status:
                diverged.append(eid)

        has_divergence = len(diverged) > 0

        return ReplayDivergenceReport(
            has_divergence=has_divergence or fp_before != fp_after,
            diverged_events=diverged,
            fingerprint_before=fp_before,
            fingerprint_after=fp_after,
            integrity_before=len(before_graph.nodes),
            integrity_after=len(after_graph.nodes),
            node_count_before=len(before_graph.nodes),
            node_count_after=len(after_graph.nodes),
        )

    def detect_hidden_mutation(self,
                               traces: List[ExecutionTrace],
                               graph: CausalGraph,
                               reference_graph: CausalGraph) -> bool:
        if len(graph.nodes) != len(reference_graph.nodes):
            return True
        fp_traces = self._fp_builder.compute(traces, graph)
        fp_ref = self._fp_builder.compute(traces, reference_graph)
        return fp_traces != fp_ref
