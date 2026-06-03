from dataclasses import dataclass
from typing import List, Optional

from ..contracts.causal_graph import CausalGraph
from ..contracts.execution_trace import ExecutionTrace
from .causal_integrity_engine import CausalIntegrityEngine, CausalIntegrityReport


@dataclass(frozen=True)
class CausalHealthScore:
    integrity: float
    continuity: float
    determinism: float
    replay_fidelity: float
    blocked_propagation_integrity: float

    @property
    def overall(self) -> float:
        return round(
            self.integrity * 0.30
            + self.continuity * 0.25
            + self.determinism * 0.20
            + self.replay_fidelity * 0.15
            + self.blocked_propagation_integrity * 0.10,
            4,
        )

    @property
    def is_healthy(self) -> bool:
        return self.overall >= 0.85

    @property
    def summary(self) -> str:
        status = "HEALTHY" if self.is_healthy else "DEGRADED"
        return (
            f"[{status}] overall={self.overall:.2f} "
            f"integrity={self.integrity:.2f} continuity={self.continuity:.2f} "
            f"determinism={self.determinism:.2f} fidelity={self.replay_fidelity:.2f}"
        )


class CausalHealthScorer:
    """
    Computes live health metrics from traces + graph.
    """

    def __init__(self, integrity_engine: Optional[CausalIntegrityEngine] = None):
        self._engine = integrity_engine or CausalIntegrityEngine()

    def score(self, traces: List[ExecutionTrace],
              graph: CausalGraph,
              baseline: Optional[CausalHealthScore] = None) -> CausalHealthScore:
        report = self._engine.validate(graph)

        integrity = self._score_integrity(report)
        continuity = self._score_continuity(graph, report)
        determinism = self._score_determinism(traces)
        replay_fidelity = self._score_replay_fidelity(
            traces, graph, baseline) if baseline else 1.0
        blocked = self._score_blocked_propagation(traces)

        return CausalHealthScore(
            integrity=round(integrity, 4),
            continuity=round(continuity, 4),
            determinism=round(determinism, 4),
            replay_fidelity=round(replay_fidelity, 4),
            blocked_propagation_integrity=round(blocked, 4),
        )

    def _score_integrity(self, report: CausalIntegrityReport) -> float:
        if report.total_event_count == 0:
            return 1.0
        return report.healthy_event_count / report.total_event_count

    def _score_continuity(self, graph: CausalGraph,
                          report: CausalIntegrityReport) -> float:
        if len(graph.nodes) == 0:
            return 1.0
        return report.graph_continuity_score

    def _score_determinism(self, traces: List[ExecutionTrace]) -> float:
        if len(traces) < 2:
            return 1.0
        statuses = [t.final_status for t in traces]
        unique = set(statuses)
        total = len(statuses)
        ratio = len(unique) / max(total, 1)
        # high determinism = low ratio (few unique states for many events)
        return round(1.0 - ratio, 4) if ratio > 0 else 1.0

    def _score_replay_fidelity(self, traces: List[ExecutionTrace],
                               graph: CausalGraph,
                               baseline: CausalHealthScore) -> float:
        if baseline is None:
            return 1.0
        score = self.score(traces, graph)
        diffs = 0
        if score.integrity != baseline.integrity:
            diffs += 1
        if score.continuity != baseline.continuity:
            diffs += 1
        if score.determinism != baseline.determinism:
            diffs += 1
        return max(0.0, 1.0 - diffs * 0.33)

    def _score_blocked_propagation(self, traces: List[ExecutionTrace]) -> float:
        blocked = [t for t in traces if "BLOCK" in t.final_status]
        if not blocked:
            return 1.0
        valid = sum(1 for t in blocked if t.p4_verdict in ("BLOCK", "DEFER", "REVIEW"))
        return valid / len(blocked)
