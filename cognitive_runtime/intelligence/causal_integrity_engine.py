from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ..contracts.causal_graph import CausalGraph, CausalEdge


@dataclass(frozen=True)
class IntegrityIssue:
    issue_id: str
    issue_type: str
    severity: str
    description: str
    node_ids: List[str] = field(default_factory=list)
    edge_id: Optional[str] = None


@dataclass(frozen=True)
class CausalIntegrityReport:
    is_healthy: bool
    issue_count: int
    orphan_count: int
    missing_edge_count: int
    cycle_count: int
    impossible_transition_count: int
    replay_divergence_count: int
    issues: List[IntegrityIssue] = field(default_factory=list)
    healthy_event_count: int = 0
    total_event_count: int = 0
    graph_continuity_score: float = 1.0

    @property
    def summary(self) -> str:
        parts = []
        if self.orphan_count:
            parts.append(f"{self.orphan_count} orphan(s)")
        if self.missing_edge_count:
            parts.append(f"{self.missing_edge_count} missing edge(s)")
        if self.cycle_count:
            parts.append(f"{self.cycle_count} cycle(s)")
        if self.impossible_transition_count:
            parts.append(f"{self.impossible_transition_count} impossible transition(s)")
        status = "HEALTHY" if self.is_healthy else "DEGRADED"
        return f"[{status}] " + (", ".join(parts) if parts else "no issues")


class CausalIntegrityEngine:
    """
    Central integrity validation engine for causal graphs.

    Responsibilities:
    - detect orphan nodes (no parent, no children, not a root)
    - detect missing edges (expected path but no connection exists)
    - detect cyclic corruption (self-referencing paths)
    - detect impossible transitions (invalid node type transitions)
    - detect replay divergence (structure differs from expected)
    """

    VALID_TRANSITIONS: Dict[str, List[str]] = {
        "host_event": ["proposal", "blocked"],
        "proposal": ["decision", "blocked"],
        "decision": ["execution", "blocked"],
        "execution": ["outcome"],
        "blocked": ["outcome"],
        "outcome": [],
    }

    def validate(self, graph: CausalGraph) -> CausalIntegrityReport:
        issues: List[IntegrityIssue] = []

        orphans = self._detect_orphans(graph)
        issues.extend(orphans)

        missing = self._detect_missing_edges(graph)
        issues.extend(missing)

        cycles = self._detect_cycles(graph)
        issues.extend(cycles)

        impossible = self._detect_impossible_transitions(graph)
        issues.extend(impossible)

        # Replay divergence requires baseline — not detected here
        # (handled by CausalDriftDetector)

        issue_counts = self._count_by_type(issues)
        unique_events = {n.event_id for n in graph.nodes.values()}
        total_event_count = len(unique_events)
        critical_event_ids: set[str] = set()
        for issue in issues:
            if issue.severity == "critical":
                for nid in issue.node_ids:
                    node = graph.get(nid)
                    if node:
                        critical_event_ids.add(node.event_id)
        healthy_event_count = total_event_count - len(critical_event_ids)
        continuity = healthy_event_count / max(total_event_count, 1)

        return CausalIntegrityReport(
            is_healthy=len(issues) == 0,
            issue_count=len(issues),
            orphan_count=issue_counts.get("orphan", 0),
            missing_edge_count=issue_counts.get("missing_edge", 0),
            cycle_count=issue_counts.get("cycle", 0),
            impossible_transition_count=issue_counts.get("impossible_transition", 0),
            replay_divergence_count=0,
            issues=issues,
            healthy_event_count=healthy_event_count,
            total_event_count=total_event_count,
            graph_continuity_score=round(continuity, 4),
        )

    def _detect_orphans(self, graph: CausalGraph) -> List[IntegrityIssue]:
        issues: List[IntegrityIssue] = []
        for nid, node in graph.nodes.items():
            is_root = node.parent_id is None
            has_children = len(node.children) > 0
            connects_via_edge = any(
                e.source_id == nid or e.target_id == nid
                for e in graph.edges
            )
            if is_root and not has_children and not connects_via_edge:
                continue
            if not has_children and not connects_via_edge and not is_root:
                issues.append(IntegrityIssue(
                    issue_id=f"orphan_{nid}",
                    issue_type="orphan",
                    severity="warning",
                    description=f"Node {nid} ({node.node_type}) has no outgoing connection",
                    node_ids=[nid],
                ))
        return issues

    def _detect_missing_edges(self, graph: CausalGraph) -> List[IntegrityIssue]:
        issues: List[IntegrityIssue] = []
        for nid, node in graph.nodes.items():
            # Check: node has a parent_id but no edge connects them
            if node.parent_id is not None:
                has_parent_edge = any(
                    e.source_id == node.parent_id and e.target_id == nid
                    for e in graph.edges
                )
                if not has_parent_edge:
                    issues.append(IntegrityIssue(
                        issue_id=f"missing_edge_{nid}",
                        issue_type="missing_edge",
                        severity="warning",
                        description=f"Node {nid} ({node.node_type}) has parent_id={node.parent_id} "
                                    f"but no edge connects them",
                        node_ids=[nid, node.parent_id],
                    ))
                    continue
            expected = self.VALID_TRANSITIONS.get(node.node_type, [])
            if not expected:
                continue
            outgoing = {
                graph.get(e.target_id).node_type
                for e in graph.edges
                if e.source_id == nid and graph.get(e.target_id) is not None
            }
            has_valid_transition = any(et in outgoing for et in expected)
            leaf_without_outcome = (
                node.node_type != "outcome"
                and not outgoing
                and graph.incoming(nid)
            )
            if not has_valid_transition and leaf_without_outcome:
                issues.append(IntegrityIssue(
                    issue_id=f"missing_edge_{nid}",
                    issue_type="missing_edge",
                    severity="warning",
                    description=f"Node {nid} ({node.node_type}) has no valid outgoing edge "
                                f"(expected one of {expected})",
                    node_ids=[nid],
                ))
        return issues

    def _detect_cycles(self, graph: CausalGraph) -> List[IntegrityIssue]:
        issues: List[IntegrityIssue] = []
        visited: set = set()
        path: list = []

        def _dfs(nid: str):
            if nid in path:
                cycle_start = path.index(nid)
                cycle = path[cycle_start:] + [nid]
                cycle_ids = list(dict.fromkeys(cycle))
                issues.append(IntegrityIssue(
                    issue_id=f"cycle_{'_'.join(cycle_ids[:3])}",
                    issue_type="cycle",
                    severity="critical",
                    description=f"Cycle detected: {' -> '.join(cycle_ids)}",
                    node_ids=cycle_ids,
                ))
                return
            if nid in visited:
                return
            visited.add(nid)
            path.append(nid)
            for child_id in graph.get(nid).children if graph.get(nid) else []:
                _dfs(child_id)
            path.pop()

        for nid in graph.nodes:
            if nid not in visited:
                _dfs(nid)

        return issues

    def _detect_impossible_transitions(self, graph: CausalGraph) -> List[IntegrityIssue]:
        issues: List[IntegrityIssue] = []
        for edge in graph.edges:
            source = graph.get(edge.source_id)
            target = graph.get(edge.target_id)
            if not source or not target:
                continue
            allowed = self.VALID_TRANSITIONS.get(source.node_type, [])
            if target.node_type not in allowed:
                issues.append(IntegrityIssue(
                    issue_id=f"impossible_{edge.edge_id}",
                    issue_type="impossible_transition",
                    severity="critical",
                    description=f"Impossible transition: {source.node_type} -> {target.node_type} "
                                f"(allowed: {allowed})",
                    node_ids=[edge.source_id, edge.target_id],
                    edge_id=edge.edge_id,
                ))
        return issues

    def _count_by_type(self, issues: List[IntegrityIssue]) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for issue in issues:
            counts[issue.issue_type] = counts.get(issue.issue_type, 0) + 1
        return counts
