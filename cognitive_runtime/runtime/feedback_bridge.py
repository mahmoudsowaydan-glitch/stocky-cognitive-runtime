"""
feedback_bridge.py — Advisory feedback from CausalGraph to runtime.

Analyzes causal graph output and produces:
  - failure pattern insights
  - decision dominance trends
  - structural recommendations

Observational + advisory only — NEVER influences P4 or execution.
"""

from collections import deque
from dataclasses import dataclass, field
from typing import Any, Deque, Dict, List, Optional

from ..contracts.causal_graph import CausalGraph, CausalNode


@dataclass
class FeedbackInsight:
    insight_type: str
    description: str
    severity: str  # "info" / "warning" / "alert"
    data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class FeedbackReport:
    insights: List[FeedbackInsight] = field(default_factory=list)
    failure_clusters: List[Dict[str, Any]] = field(default_factory=list)
    dominant_layer_trends: Dict[str, int] = field(default_factory=dict)


class FeedbackBridge:
    def __init__(self, max_history: int = 1000):
        self._history: Deque[FeedbackReport] = deque(maxlen=max_history)

    def analyze(self, graph: CausalGraph) -> FeedbackReport:
        report = FeedbackReport()

        # Pattern 1: Layer dominance distribution
        report.dominant_layer_trends = graph.dominant_layers
        total = sum(report.dominant_layer_trends.values()) or 1
        for layer, count in report.dominant_layer_trends.items():
            pct = (count / total) * 100
            if pct > 50:
                report.insights.append(FeedbackInsight(
                    insight_type="layer_dominance",
                    description=f"{layer} dominates {pct:.0f}% of decisions",
                    severity="info",
                    data={"layer": layer, "percentage": pct, "count": count},
                ))

        # Pattern 2: Failure clusters
        failures = graph.failure_points
        if failures:
            failure_layers: Dict[str, int] = {}
            for f in failures:
                layer = f.data.get("reason", "") or f.node_type or "unknown"
                failure_layers[layer] = failure_layers.get(layer, 0) + 1

            report.failure_clusters = [
                {"layer": layer, "count": count, "percentage": round(count / len(failures) * 100, 1)}
                for layer, count in sorted(failure_layers.items(), key=lambda x: -x[1])
            ]

            for fc in report.failure_clusters:
                severity = "alert" if fc["percentage"] > 40 else "warning"
                report.insights.append(FeedbackInsight(
                    insight_type="failure_cluster",
                    description=f"{fc['layer']}: {fc['count']} failures ({fc['percentage']}%)",
                    severity=severity,
                    data=fc,
                ))

        # Pattern 3: Sandbox enforcement activity (by execution count)
        exec_nodes = [n for n in graph.nodes.values() if n.node_type == "execution"]
        sandbox_count = sum(1 for n in exec_nodes if n.data.get("status") != "SUCCESS")
        if sandbox_count > 0:
            report.insights.append(FeedbackInsight(
                insight_type="sandbox_enforcement_active",
                description=f"Sandbox had non-success outcomes in {sandbox_count} executions",
                severity="info",
                data={"count": sandbox_count},
            ))

        # Pattern 4: Preflight blocking patterns
        preflight_blocked = [
            n for n in graph.nodes.values()
            if n.node_type == "blocked"
            and n.data.get("verdict", "") in ("BLOCKED", "BLOCKED_BY_PREFLIGHT")
        ]
        if preflight_blocked:
            report.insights.append(FeedbackInsight(
                insight_type="preflight_blocking",
                description=f"Preflight blocked {len(preflight_blocked)} proposals",
                severity="info",
                data={"count": len(preflight_blocked)},
            ))

        self._history.append(report)
        return report

    @property
    def history(self) -> List[FeedbackReport]:
        return list(self._history)
