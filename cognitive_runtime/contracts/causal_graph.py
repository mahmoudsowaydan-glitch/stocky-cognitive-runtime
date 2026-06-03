from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Optional

from .execution_trace import ExecutionTrace


NodeType = Literal["host_event", "proposal", "decision", "execution", "blocked", "outcome"]
EdgeType = Literal["proposes", "validates", "decides", "executes", "results", "blocks"]


@dataclass(frozen=True)
class CausalNode:
    node_id: str
    event_id: str
    correlation_id: str
    node_type: NodeType
    data: Dict[str, Any]
    timestamp: float
    parent_id: Optional[str] = None
    children: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class CausalEdge:
    edge_id: str
    source_id: str
    target_id: str
    edge_type: EdgeType
    meta: Dict[str, Any] = field(default_factory=dict)


class CausalGraph:
    """
    Immutable causal graph of a single execution path.
    Constructed by CausalGraphBuilder — never mutated after creation.
    """

    def __init__(self, nodes: Dict[str, CausalNode], edges: List[CausalEdge]):
        self._nodes = dict(nodes)
        self._edges = list(edges)
        self._roots: List[str] = [
            nid for nid, n in self._nodes.items() if n.parent_id is None
        ]

    @property
    def nodes(self) -> Dict[str, CausalNode]:
        return dict(self._nodes)

    @property
    def edges(self) -> List[CausalEdge]:
        return list(self._edges)

    @property
    def roots(self) -> List[str]:
        return list(self._roots)

    @property
    def dominant_layers(self) -> Dict[str, int]:
        layers: Dict[str, int] = {}
        for n in self._nodes.values():
            layers[n.node_type] = layers.get(n.node_type, 0) + 1
        return layers

    @property
    def failure_points(self) -> List[CausalNode]:
        return [
            n for n in self._nodes.values()
            if n.node_type == "outcome"
            and n.data.get("final_status", "").lower() in ("failed", "blocked", "error")
        ]

    def get(self, node_id: str) -> Optional[CausalNode]:
        return self._nodes.get(node_id)

    def traverse(self, node_id: str) -> List[CausalNode]:
        result: List[CausalNode] = []
        current = self._nodes.get(node_id)
        while current:
            result.append(current)
            if not current.children:
                break
            current = self._nodes.get(current.children[0])
        return result

    def incoming(self, node_id: str) -> List[CausalEdge]:
        return [e for e in self._edges if e.target_id == node_id]

    def outgoing(self, node_id: str) -> List[CausalEdge]:
        return [e for e in self._edges if e.source_id == node_id]

    def path_to_outcome(self, node_id: str) -> List[CausalNode]:
        start = self._nodes.get(node_id)
        if not start:
            return []
        visited: set[str] = set()
        result: List[CausalNode] = []

        def _dfs(nid: str) -> bool:
            if nid in visited:
                return False
            visited.add(nid)
            node = self._nodes.get(nid)
            if not node:
                return False
            result.append(node)
            if node.node_type == "outcome":
                return True
            for child_id in node.children:
                if _dfs(child_id):
                    return True
            result.pop()
            return False

        _dfs(node_id)
        return result

    def filter_by_type(self, node_type: NodeType) -> List[CausalNode]:
        return [n for n in self._nodes.values() if n.node_type == node_type]

    def correlation_subgraph(self, correlation_id: str) -> "CausalGraph":
        matching = {
            nid: n for nid, n in self._nodes.items()
            if n.correlation_id == correlation_id
        }
        matching_ids = set(matching.keys())
        filtered_edges = [
            e for e in self._edges
            if e.source_id in matching_ids or e.target_id in matching_ids
        ]
        return CausalGraph(matching, filtered_edges)


class CausalGraphBuilder:
    """
    Read-only builder. Transforms ExecutionTrace data into a CausalGraph.
    No side effects, no state mutation beyond construction.
    """

    def build(self, traces: List[ExecutionTrace]) -> CausalGraph:
        nodes: Dict[str, CausalNode] = {}
        edges: List[CausalEdge] = []

        for trace in traces:
            eid = trace.event_id
            cid = trace.correlation_id

            # Node 1: Host event (root)
            host_node = CausalNode(
                node_id=f"{eid}__host",
                event_id=eid,
                correlation_id=cid,
                node_type="host_event",
                data={},
                timestamp=0.0,
            )
            nodes[host_node.node_id] = host_node
            prev_id = host_node.node_id
            timestamp = 0.0

            # Node 2: Proposal (preflight passed)
            if trace.preflight_valid:
                proposal_node = CausalNode(
                    node_id=f"{eid}__proposal",
                    event_id=eid,
                    correlation_id=cid,
                    node_type="proposal",
                    data={
                        "risk_score": trace.risk_score,
                        "capabilities": trace.capabilities_checked,
                    },
                    timestamp=timestamp,
                    parent_id=prev_id,
                )
                nodes[proposal_node.node_id] = proposal_node
                edges.append(CausalEdge(
                    edge_id=f"{eid}__e_proposal",
                    source_id=prev_id,
                    target_id=proposal_node.node_id,
                    edge_type="proposes",
                    meta={},
                ))
                prev_id = proposal_node.node_id

            # Blocked events
            if trace.final_status in ("BLOCKED_BY_PREFLIGHT",) or (
                trace.p4_verdict in ("BLOCK", "DEFER", "REVIEW") and trace.final_status.startswith("P4_")
            ):
                blocked_node = CausalNode(
                    node_id=f"{eid}__blocked",
                    event_id=eid,
                    correlation_id=cid,
                    node_type="blocked",
                    data={
                        "verdict": trace.p4_verdict if trace.p4_verdict != "UNKNOWN" else "BLOCKED",
                        "reason": trace.p4_reason or trace.preflight_reason or "",
                    },
                    timestamp=timestamp,
                    parent_id=prev_id,
                )
                nodes[blocked_node.node_id] = blocked_node
                edges.append(CausalEdge(
                    edge_id=f"{eid}__e_blocked",
                    source_id=prev_id,
                    target_id=blocked_node.node_id,
                    edge_type="blocks",
                    meta={},
                ))

                outcome_node = CausalNode(
                    node_id=f"{eid}__outcome",
                    event_id=eid,
                    correlation_id=cid,
                    node_type="outcome",
                    data={"final_status": "blocked", "reason": trace.p4_reason or trace.preflight_reason or ""},
                    timestamp=timestamp,
                    parent_id=blocked_node.node_id,
                )
                nodes[outcome_node.node_id] = outcome_node
                edges.append(CausalEdge(
                    edge_id=f"{eid}__e_outcome",
                    source_id=blocked_node.node_id,
                    target_id=outcome_node.node_id,
                    edge_type="results",
                    meta={},
                ))
                nodes[blocked_node.node_id] = CausalNode(
                    node_id=blocked_node.node_id,
                    event_id=blocked_node.event_id,
                    correlation_id=blocked_node.correlation_id,
                    node_type=blocked_node.node_type,
                    data=blocked_node.data,
                    timestamp=blocked_node.timestamp,
                    parent_id=blocked_node.parent_id,
                    children=[outcome_node.node_id],
                )
                continue

            # Node 3: Decision (P4)
            if trace.p4_verdict not in ("UNKNOWN",):
                decision_node = CausalNode(
                    node_id=f"{eid}__decision",
                    event_id=eid,
                    correlation_id=cid,
                    node_type="decision",
                    data={
                        "verdict": trace.p4_verdict,
                        "reason": trace.p4_reason or "",
                        "risk_level": trace.p4_risk_level or "",
                        "rule_triggered": trace.p4_rule_triggered,
                    },
                    timestamp=timestamp,
                    parent_id=prev_id,
                )
                nodes[decision_node.node_id] = decision_node
                edges.append(CausalEdge(
                    edge_id=f"{eid}__e_decision",
                    source_id=prev_id,
                    target_id=decision_node.node_id,
                    edge_type="decides",
                    meta={},
                ))
                prev_id = decision_node.node_id

            # Node 4: Execution
            if trace.execution_status not in ("UNKNOWN",):
                exec_node = CausalNode(
                    node_id=f"{eid}__execution",
                    event_id=eid,
                    correlation_id=cid,
                    node_type="execution",
                    data={
                        "status": trace.execution_status,
                        "error": trace.execution_error,
                    },
                    timestamp=timestamp,
                    parent_id=prev_id,
                )
                nodes[exec_node.node_id] = exec_node
                edges.append(CausalEdge(
                    edge_id=f"{eid}__e_execution",
                    source_id=prev_id,
                    target_id=exec_node.node_id,
                    edge_type="executes",
                    meta={},
                ))
                prev_id = exec_node.node_id

            # Node 5: Outcome
            final_status_val = "success" if trace.execution_status == "SUCCESS" else "failed"
            outcome_node = CausalNode(
                node_id=f"{eid}__outcome",
                event_id=eid,
                correlation_id=cid,
                node_type="outcome",
                data={
                    "final_status": final_status_val,
                    "error": trace.execution_error,
                },
                timestamp=timestamp,
                parent_id=prev_id,
            )
            nodes[outcome_node.node_id] = outcome_node
            edges.append(CausalEdge(
                edge_id=f"{eid}__e_outcome",
                source_id=prev_id,
                target_id=outcome_node.node_id,
                edge_type="results",
                meta={},
            ))

        # Wire children pointers
        for edge in edges:
            source = nodes.get(edge.source_id)
            target = nodes.get(edge.target_id)
            if source and target and target.node_id not in source.children:
                nodes[edge.source_id] = CausalNode(
                    node_id=source.node_id,
                    event_id=source.event_id,
                    correlation_id=source.correlation_id,
                    node_type=source.node_type,
                    data=source.data,
                    timestamp=source.timestamp,
                    parent_id=source.parent_id,
                    children=source.children + [target.node_id],
                )

        return CausalGraph(nodes, edges)
