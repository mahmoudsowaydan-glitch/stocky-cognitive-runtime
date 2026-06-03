"""consensus_engine.py — Deterministic weighted voting engine for schema consensus.

Flow:
  Step 1 — Group proposals by schema_version
  Step 2 — Compute weighted vote for each cluster:
      weight = stability_score * 0.4 + confidence_score * 0.4 + graph_freshness * 0.2
  Step 3 — Select dominant version (highest weight, must >= 0.7)
  Step 4 — Conflict detection: close margin, orphan schema, incompatible paths

Invariants:
  CONS-001: Consensus must be deterministic
  CONS-002: No single node can override consensus
  CONS-003: All nodes evaluated symmetrically
  CONS-004: Conflicts explicitly resolved, never ignored
  CONS-005: Consensus result reproducible from same inputs
"""

from typing import Dict, List, Tuple

from ..schema_evolution.evolution_graph import EvolutionGraph
from ..schema_evolution.compatibility_rules import CompatibilityRules
from ..schema_evolution.migration_engine import MigrationEngine
from .consensus_state import NodeStateProposal, ConsensusResult


class ConsensusEngine:
    """Deterministic consensus engine using weighted voting on schema proposals."""

    CONSENSUS_THRESHOLD = 0.7
    CONFLICT_MARGIN = 0.05

    def __init__(self, graph: EvolutionGraph, current_version: str):
        self._graph = graph
        self._current_version = current_version

    def _graph_freshness(self, version: str) -> float:
        """Higher score = version is closer to the current version in the graph."""
        if version == self._current_version:
            return 1.0

        try:
            if self._current_version in self._graph.get_ancestors(version):
                # version is ahead of current — distance from current
                return 0.5
            if version in self._graph.get_ancestors(self._current_version):
                # current is ahead of version — compute distance
                ancestors = self._graph.get_ancestors(self._current_version)
                path: List[str] = []
                v = self._current_version
                while v != version:
                    node = self._graph.get_node(v)
                    if node is None or not node.parent_versions:
                        break
                    v = node.parent_versions[0]
                    path.append(v)
                depth = len(path)
                if depth == 0:
                    return 0.5
                return max(0.1, 1.0 - (depth * 0.3))
        except (ValueError, KeyError):
            pass

        return 0.0

    def _weight(self, proposal: NodeStateProposal) -> float:
        return (
            proposal.stability_score * 0.4
            + proposal.confidence_score * 0.4
            + self._graph_freshness(proposal.schema_version) * 0.2
        )

    def propose(self, proposals: List[NodeStateProposal]) -> ConsensusResult:
        if not proposals:
            return ConsensusResult(
                agreed_version=self._current_version,
                consensus_strength=0.0,
                conflict_reasons=["no_proposals"],
            )

        # Step 1: Group by schema_version
        groups: Dict[str, List[NodeStateProposal]] = {}
        for p in proposals:
            groups.setdefault(p.schema_version, []).append(p)

        # Step 2: Compute weighted scores per version
        version_scores: List[Tuple[str, float, List[str]]] = []
        for ver, group in groups.items():
            node_ids = [p.node_id for p in group]
            total_weight = sum(self._weight(p) for p in group)
            avg_weight = total_weight / len(group)
            version_scores.append((ver, avg_weight, node_ids))

        # Descending by weight
        version_scores.sort(key=lambda x: x[1], reverse=True)

        if not version_scores:
            return ConsensusResult(
                agreed_version=self._current_version,
                consensus_strength=0.0,
                conflict_reasons=["no_valid_groups"],
            )

        dominant_ver, dominant_weight, dominant_nodes = version_scores[0]

        # Step 3: Threshold check
        if dominant_weight < self.CONSENSUS_THRESHOLD:
            return ConsensusResult(
                agreed_version=self._current_version,
                participating_nodes=dominant_nodes,
                rejected_nodes=[n for _, _, ns in version_scores[1:] for n in ns],
                consensus_strength=dominant_weight,
                conflict_reasons=[f"dominant_weight_{dominant_weight:.3f}_below_threshold"],
            )

        # Step 4: Conflict detection
        conflict_reasons: List[str] = []

        # 4a: Close margin conflicts
        for ver, weight, _ in version_scores[1:]:
            if dominant_weight - weight < self.CONFLICT_MARGIN:
                conflict_reasons.append(
                    f"close_margin_{dominant_ver}_{ver}_diff_{dominant_weight - weight:.3f}"
                )

        # 4b: Unknown or orphan schema check
        for ver, _, _ in version_scores:
            if ver == dominant_ver:
                continue
            node = self._graph.get_node(ver)
            if node is None:
                conflict_reasons.append(f"unknown_schema_{ver}")
            elif self._graph.is_orphan(ver):
                conflict_reasons.append(f"orphan_schema_{ver}")

        # 4c: Incompatible migration paths
        for ver, _, _ in version_scores:
            if ver == dominant_ver:
                continue
            if not CompatibilityRules.is_backward_compatible(ver, dominant_ver, self._graph):
                path_possible = False
                try:
                    engine = MigrationEngine(self._graph)
                    plan = engine.build_path(ver, dominant_ver)
                    path_possible = plan.is_supported
                except Exception:
                    path_possible = False
                if not path_possible:
                    conflict_reasons.append(f"incompatible_path_{ver}_to_{dominant_ver}")

        # Build rejected list: all nodes not in the dominant group
        all_nodes = [p.node_id for p in proposals]
        rejected = [n for n in all_nodes if n not in dominant_nodes]

        return ConsensusResult(
            agreed_version=dominant_ver,
            participating_nodes=dominant_nodes,
            rejected_nodes=rejected,
            consensus_strength=dominant_weight,
            conflict_reasons=conflict_reasons,
        )
