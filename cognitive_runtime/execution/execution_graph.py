from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

from .execution_node import ActionType, ExecutionNode, NodeStatus, RiskLevel


class EdgeType:
    SEQUENTIAL = "SEQUENTIAL"
    PARALLEL_SAFE = "PARALLEL_SAFE"
    DATA_DEPENDENCY = "DATA_DEPENDENCY"


@dataclass
class Edge:
    from_id: str
    to_id: str
    type: str = EdgeType.SEQUENTIAL


class ExecutionGraphBuildError(Exception):
    pass


class ExecutionGraph:
    def __init__(self, id: str = "", plan_id: str = ""):
        self.id = id
        self.plan_id = plan_id
        self.nodes: dict[str, ExecutionNode] = {}
        self.edges: list[Edge] = []
        self.created_at: datetime = datetime.utcnow()

    def add_node(self, node: ExecutionNode) -> None:
        self.nodes[node.id] = node

    def add_edge(self, from_id: str, to_id: str,
                 edge_type: str = EdgeType.SEQUENTIAL) -> None:
        if from_id not in self.nodes or to_id not in self.nodes:
            raise ExecutionGraphBuildError(f"edge references unknown node: {from_id} -> {to_id}")
        self.edges.append(Edge(from_id=from_id, to_id=to_id, type=edge_type))

    def get_dependencies(self, node_id: str) -> list[str]:
        return [e.from_id for e in self.edges if e.to_id == node_id]

    def get_dependents(self, node_id: str) -> list[str]:
        return [e.to_id for e in self.edges if e.from_id == node_id]

    def topological_sort(self) -> list[ExecutionNode]:
        in_degree: dict[str, int] = {nid: 0 for nid in self.nodes}
        adjacency: dict[str, list[str]] = defaultdict(list)

        for edge in self.edges:
            adjacency[edge.from_id].append(edge.to_id)
            in_degree[edge.to_id] = in_degree.get(edge.to_id, 0) + 1

        queue = deque([nid for nid, deg in in_degree.items() if deg == 0])
        sorted_nodes = []

        while queue:
            nid = queue.popleft()
            sorted_nodes.append(self.nodes[nid])
            for dep in adjacency[nid]:
                in_degree[dep] -= 1
                if in_degree[dep] == 0:
                    queue.append(dep)

        if len(sorted_nodes) != len(self.nodes):
            raise ExecutionGraphBuildError("graph contains a cycle")

        return sorted_nodes

    def detect_cycles(self) -> list[list[str]]:
        visited: dict[str, int] = {nid: 0 for nid in self.nodes}
        adjacency = defaultdict(list)
        for edge in self.edges:
            adjacency[edge.from_id].append(edge.to_id)

        cycles = []
        path: list[str] = []

        def dfs(node: str):
            visited[node] = 1
            path.append(node)
            for neighbor in adjacency[node]:
                if visited.get(neighbor) == 1:
                    cycle_start = path.index(neighbor)
                    cycles.append(path[cycle_start:] + [neighbor])
                elif visited.get(neighbor) == 0:
                    dfs(neighbor)
            path.pop()
            visited[node] = 2

        for nid in self.nodes:
            if visited[nid] == 0:
                dfs(nid)

        return cycles

    def orphan_nodes(self) -> list[ExecutionNode]:
        all_referenced = set()
        for edge in self.edges:
            all_referenced.add(edge.from_id)
            all_referenced.add(edge.to_id)
        return [n for nid, n in self.nodes.items() if nid not in all_referenced]

    @property
    def node_count(self) -> int:
        return len(self.nodes)

    @property
    def estimated_risk_level(self) -> RiskLevel:
        if not self.nodes:
            return RiskLevel.LOW
        return max((n.risk_level for n in self.nodes.values()), key=lambda r: r.value)

    def validate(self) -> list[str]:
        errors = []
        cycles = self.detect_cycles()
        if cycles:
            errors.append(f"cycles detected: {cycles}")
        for nid, node in self.nodes.items():
            if node.rollback is None and node.action_type in (
                ActionType.MODIFY_FILE, ActionType.RUN_COMMAND):
                errors.append(f"node {nid} has mutable action but no rollback defined")
            if node.timeout_ms <= 0:
                errors.append(f"node {nid} has no valid timeout")
        return errors

