"""conflict_resolver.py — Deterministic resolution of consensus conflicts.

Strategies (CONS-004):
  VERSION_PRIORITY           — pick the highest (newest) version
  STABILITY_PRIORITY         — pick the cluster with highest average stability
  MIGRATION_COST_MINIMIZATION — pick the version requiring fewest migrations

No randomness allowed. Tie-breaks use lexicographic node_id ordering.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple

from ..schema_evolution.evolution_graph import EvolutionGraph
from ..schema_evolution.compatibility_rules import CompatibilityRules
from ..schema_evolution.migration_engine import MigrationEngine
from .consensus_state import NodeStateProposal


class ResolutionStrategy(Enum):
    VERSION_PRIORITY = "VERSION_PRIORITY"
    STABILITY_PRIORITY = "STABILITY_PRIORITY"
    MIGRATION_COST_MINIMIZATION = "MIGRATION_COST_MINIMIZATION"


@dataclass(frozen=True)
class ResolutionPlan:
    chosen_version: str
    strategy_used: ResolutionStrategy
    participating_nodes: List[str] = field(default_factory=list)
    rejected_nodes: List[str] = field(default_factory=list)
    resolution_details: str = ""


class ConflictResolver:
    def __init__(self, graph: EvolutionGraph, current_version: str):
        self._graph = graph
        self._current_version = current_version
        self._migration_engine = MigrationEngine(graph)

    def resolve(
        self,
        proposals: List[NodeStateProposal],
        strategy: ResolutionStrategy = ResolutionStrategy.VERSION_PRIORITY,
    ) -> ResolutionPlan:
        if not proposals:
            return ResolutionPlan(
                chosen_version=self._current_version,
                strategy_used=strategy,
                resolution_details="no_proposals_fallback_to_current",
            )

        groups: Dict[str, List[NodeStateProposal]] = {}
        for p in proposals:
            groups.setdefault(p.schema_version, []).append(p)

        if len(groups) == 1:
            ver = list(groups.keys())[0]
            nodes = [p.node_id for p in groups[ver]]
            return ResolutionPlan(
                chosen_version=ver,
                strategy_used=strategy,
                participating_nodes=nodes,
                resolution_details="unanimous",
            )

        if strategy == ResolutionStrategy.VERSION_PRIORITY:
            return self._resolve_by_version_priority(groups)
        elif strategy == ResolutionStrategy.STABILITY_PRIORITY:
            return self._resolve_by_stability(groups)
        elif strategy == ResolutionStrategy.MIGRATION_COST_MINIMIZATION:
            return self._resolve_by_migration_cost(groups)

        return self._resolve_by_version_priority(groups)

    def _parse_version_tuple(self, v: str) -> Tuple[int, int, int]:
        try:
            parts = v.split(".")
            return int(parts[0]), int(parts[1]), int(parts[2]) if len(parts) > 2 else 0
        except (ValueError, IndexError):
            return (0, 0, 0)

    def _tiebreak(self, nodes_a: List[str], nodes_b: List[str]) -> bool:
        """Returns True if nodes_a wins the tiebreak (lexicographic first node_id)."""
        if not nodes_a:
            return False
        if not nodes_b:
            return True
        return min(nodes_a) < min(nodes_b)

    def _resolve_by_version_priority(
        self, groups: Dict[str, List[NodeStateProposal]]
    ) -> ResolutionPlan:
        sorted_versions = sorted(
            groups.keys(), key=lambda v: self._parse_version_tuple(v), reverse=True
        )
        chosen = sorted_versions[0]
        participating = [p.node_id for p in groups[chosen]]
        all_nodes = [p.node_id for ps in groups.values() for p in ps]
        rejected = [n for n in all_nodes if n not in participating]

        tied = [v for v in sorted_versions if self._parse_version_tuple(v) == self._parse_version_tuple(chosen)]
        details = f"version_priority_chosen_{chosen}"
        if len(tied) > 1:
            if self._tiebreak([p.node_id for p in groups[tied[0]]],
                              [p.node_id for p in groups[tied[1]]]):
                chosen = tied[0]
            else:
                chosen = tied[1]
            participating = [p.node_id for p in groups[chosen]]
            rejected = [n for n in all_nodes if n not in participating]
            details = f"version_priority_tiebreak_{chosen}"

        return ResolutionPlan(
            chosen_version=chosen,
            strategy_used=ResolutionStrategy.VERSION_PRIORITY,
            participating_nodes=participating,
            rejected_nodes=rejected,
            resolution_details=details,
        )

    def _resolve_by_stability(
        self, groups: Dict[str, List[NodeStateProposal]]
    ) -> ResolutionPlan:
        best_ver: Optional[str] = None
        best_stability = -1.0

        for ver, group in groups.items():
            avg_stability = sum(p.stability_score for p in group) / len(group)
            if avg_stability > best_stability:
                best_stability = avg_stability
                best_ver = ver
            elif avg_stability == best_stability and best_ver is not None:
                nodes_cur = [p.node_id for p in groups[best_ver]]
                nodes_new = [p.node_id for p in groups[ver]]
                if self._tiebreak(nodes_new, nodes_cur):
                    best_ver = ver

        chosen = best_ver or self._current_version
        participating = [p.node_id for p in groups.get(chosen, [])]
        all_nodes = [p.node_id for ps in groups.values() for p in ps]
        rejected = [n for n in all_nodes if n not in participating]

        return ResolutionPlan(
            chosen_version=chosen,
            strategy_used=ResolutionStrategy.STABILITY_PRIORITY,
            participating_nodes=participating,
            rejected_nodes=rejected,
            resolution_details=f"stability_priority_{best_stability:.3f}",
        )

    def _resolve_by_migration_cost(
        self, groups: Dict[str, List[NodeStateProposal]]
    ) -> ResolutionPlan:
        best_ver: Optional[str] = None
        best_cost = float("inf")

        for ver, group in groups.items():
            total_cost = 0
            for other_ver in groups:
                if other_ver == ver:
                    continue
                if CompatibilityRules.is_backward_compatible(
                    other_ver, ver, self._graph
                ):
                    continue
                plan = self._migration_engine.build_path(other_ver, ver)
                total_cost += len(plan.steps) if plan.is_supported else 10

            if total_cost < best_cost:
                best_cost = total_cost
                best_ver = ver
            elif total_cost == best_cost and best_ver is not None:
                nodes_cur = [p.node_id for p in groups[best_ver]]
                nodes_new = [p.node_id for p in groups[ver]]
                if self._tiebreak(nodes_new, nodes_cur):
                    best_ver = ver

        chosen = best_ver or self._current_version
        participating = [p.node_id for p in groups.get(chosen, [])]
        all_nodes = [p.node_id for ps in groups.values() for p in ps]
        rejected = [n for n in all_nodes if n not in participating]

        return ResolutionPlan(
            chosen_version=chosen,
            strategy_used=ResolutionStrategy.MIGRATION_COST_MINIMIZATION,
            participating_nodes=participating,
            rejected_nodes=rejected,
            resolution_details=f"migration_cost_{best_cost}",
        )
