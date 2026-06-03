"""
graph_contract.py — Canonical interface definition for CausalGraph, CausalNode, CausalEdge.

Frozen contract. Do not modify without updating schema_version.
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .schema_version import fingerprint_class, register_fingerprint


# ── CausalNode Contract ──

@dataclass(frozen=True)
class CausalNodeContract:
    node_id: str
    event_id: str
    correlation_id: str
    node_type: str  # host_event | proposal | decision | execution | blocked | outcome
    data: Dict[str, Any]
    timestamp: float
    parent_id: Optional[str]
    children: List[str]

    @classmethod
    def from_instance(cls, node: Any) -> "CausalNodeContract":
        return cls(
            node_id=node.node_id,
            event_id=node.event_id,
            correlation_id=node.correlation_id,
            node_type=node.node_type,
            data=node.data,
            timestamp=node.timestamp,
            parent_id=node.parent_id,
            children=list(node.children),
        )

    def validate(self) -> List[str]:
        violations = []
        if not self.node_id:
            violations.append("node_id must be non-empty")
        if self.node_type not in ("host_event", "proposal", "decision", "execution", "blocked", "outcome"):
            violations.append(f"invalid node_type: {self.node_type}")
        if not isinstance(self.data, dict):
            violations.append("data must be a dict")
        return violations


# ── CausalEdge Contract ──

@dataclass(frozen=True)
class CausalEdgeContract:
    edge_id: str
    source_id: str
    target_id: str
    edge_type: str  # proposes | validates | decides | executes | results | blocks
    meta: Dict[str, Any]

    @classmethod
    def from_instance(cls, edge: Any) -> "CausalEdgeContract":
        return cls(
            edge_id=edge.edge_id,
            source_id=edge.source_id,
            target_id=edge.target_id,
            edge_type=edge.edge_type,
            meta=dict(edge.meta),
        )

    def validate(self) -> List[str]:
        violations = []
        if self.edge_type not in ("proposes", "validates", "decides", "executes", "results", "blocks"):
            violations.append(f"invalid edge_type: {self.edge_type}")
        if not self.edge_id:
            violations.append("edge_id must be non-empty")
        return violations


# ── CausalGraph Contract ──

class GraphContract:
    """
    Defines the canonical interface that CausalGraph must satisfy.
    All consumers (feedback_bridge, entropy_index, etc.) rely on this contract.
    """

    # Expected public properties
    EXPECTED_PROPERTIES = {
        "nodes": Dict[str, Any],
        "edges": list,
        "roots": list,
        "dominant_layers": dict,
        "failure_points": list,
    }

    # Expected public methods (name -> signature pattern)
    EXPECTED_METHODS = [
        "get",
        "traverse",
        "incoming",
        "outgoing",
        "path_to_outcome",
        "filter_by_type",
        "correlation_subgraph",
    ]

    # Expected CausalNode attributes
    NODE_ATTRIBUTES = [
        "node_id", "event_id", "correlation_id",
        "node_type", "data", "timestamp",
        "parent_id", "children",
    ]

    # Expected CausalEdge attributes
    EDGE_ATTRIBUTES = [
        "edge_id", "source_id", "target_id",
        "edge_type", "meta",
    ]

    @classmethod
    def check_graph(cls, graph: Any) -> List[str]:
        violations = []
        for prop in cls.EXPECTED_PROPERTIES:
            if not hasattr(graph, prop):
                violations.append(f"Graph missing property: {prop}")
            else:
                val = getattr(graph, prop)
                if callable(val):
                    violations.append(f"Graph.{prop} is callable, expected property")
        for method in cls.EXPECTED_METHODS:
            if not hasattr(graph, method):
                violations.append(f"Graph missing method: {method}")
            elif not callable(getattr(graph, method)):
                violations.append(f"Graph.{method} is not callable")
        if not violations:
            for nid, node in graph.nodes.items():
                for attr in cls.NODE_ATTRIBUTES:
                    if not hasattr(node, attr):
                        violations.append(f"Node {nid} missing attribute: {attr}")
                        break
            for edge in graph.edges:
                for attr in cls.EDGE_ATTRIBUTES:
                    if not hasattr(edge, attr):
                        violations.append(f"Edge missing attribute: {attr}")
                        break
        return violations

    @classmethod
    def check_node_instance(cls, node: Any) -> List[str]:
        violations = []
        for attr in cls.NODE_ATTRIBUTES:
            if not hasattr(node, attr):
                violations.append(f"Node missing attribute: {attr}")
        return violations

    @classmethod
    def check_edge_instance(cls, edge: Any) -> List[str]:
        violations = []
        for attr in cls.EDGE_ATTRIBUTES:
            if not hasattr(edge, attr):
                violations.append(f"Edge missing attribute: {attr}")
        return violations


# Register fingerprints
register_fingerprint("CausalNode", fingerprint_class(CausalNodeContract))
register_fingerprint("CausalEdge", fingerprint_class(CausalEdgeContract))
register_fingerprint("GraphContract", str(sorted(GraphContract.EXPECTED_PROPERTIES.keys()) + GraphContract.EXPECTED_METHODS))
