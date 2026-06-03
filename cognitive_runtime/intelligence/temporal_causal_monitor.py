from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ..contracts.causal_graph import CausalGraph
from ..contracts.execution_trace import ExecutionTrace
from .causal_health_score import CausalHealthScore, CausalHealthScorer
from .causal_integrity_engine import CausalIntegrityEngine


@dataclass(frozen=True)
class CausalSnapshot:
    timestamp: float
    node_count: int
    edge_count: int
    integrity_score: float
    health_score: float
    orphan_count: int
    issue_count: int
    event_count: int


@dataclass(frozen=True)
class DegradationTrend:
    is_degrading: bool
    current_health: float
    previous_health: float
    delta: float
    node_delta: int
    edge_delta: int
    snapshots_count: int
    consecutive_degradations: int

    @property
    def summary(self) -> str:
        direction = "degrading" if self.is_degrading else "stable"
        return (
            f"[{direction.upper()}] health={self.current_health:.2f} "
            f"delta={self.delta:+.4f} "
            f"({self.consecutive_degradations}x consecutive)"
        )


class TemporalCausalMonitor:
    """
    Monitors causal degradation over time.

    Tracks:
    - causal degradation over time
    - replay stability decay
    - graph fragmentation
    - edge-loss trends
    """

    def __init__(self, max_snapshots: int = 100,
                 scorer: Optional[CausalHealthScorer] = None):
        self._max_snapshots = max_snapshots
        self._scorer = scorer or CausalHealthScorer()
        self._snapshots: List[CausalSnapshot] = []
        self._consecutive_degradations = 0

    def record(self, timestamp: float,
               traces: List[ExecutionTrace],
               graph: CausalGraph) -> CausalSnapshot:
        engine = CausalIntegrityEngine()
        report = engine.validate(graph)
        health = self._scorer.score(traces, graph)

        prev = self._snapshots[-1] if self._snapshots else None

        snapshot = CausalSnapshot(
            timestamp=timestamp,
            node_count=len(graph.nodes),
            edge_count=len(graph.edges),
            integrity_score=health.integrity,
            health_score=health.overall,
            orphan_count=report.orphan_count,
            issue_count=report.issue_count,
            event_count=len(traces),
        )

        self._snapshots.append(snapshot)
        if len(self._snapshots) > self._max_snapshots:
            self._snapshots.pop(0)

        if prev is not None and snapshot.health_score < prev.health_score:
            self._consecutive_degradations += 1
        elif prev is not None and snapshot.health_score >= prev.health_score:
            self._consecutive_degradations = 0

        return snapshot

    def trend(self) -> DegradationTrend:
        if len(self._snapshots) < 2:
            return DegradationTrend(
                is_degrading=False,
                current_health=self._snapshots[-1].health_score if self._snapshots else 1.0,
                previous_health=self._snapshots[-1].health_score if self._snapshots else 1.0,
                delta=0.0,
                node_delta=0,
                edge_delta=0,
                snapshots_count=len(self._snapshots),
                consecutive_degradations=self._consecutive_degradations,
            )

        current = self._snapshots[-1]
        previous = self._snapshots[0]

        return DegradationTrend(
            is_degrading=self._consecutive_degradations >= 2,
            current_health=current.health_score,
            previous_health=previous.health_score,
            delta=round(current.health_score - previous.health_score, 4),
            node_delta=current.node_count - previous.node_count,
            edge_delta=current.edge_count - previous.edge_count,
            snapshots_count=len(self._snapshots),
            consecutive_degradations=self._consecutive_degradations,
        )

    @property
    def snapshots(self) -> List[CausalSnapshot]:
        return list(self._snapshots)

    def clear(self) -> None:
        self._snapshots.clear()
        self._consecutive_degradations = 0
