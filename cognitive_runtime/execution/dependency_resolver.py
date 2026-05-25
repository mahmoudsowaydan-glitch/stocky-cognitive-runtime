from collections import defaultdict
from typing import Optional

from .execution_graph import ExecutionGraph
from .execution_node import ExecutionNode, RiskLevel


class DependencyResolver:
    def __init__(self, graph: ExecutionGraph):
        self.graph = graph

    def parallel_safe_batches(self) -> list[list[ExecutionNode]]:
        in_degree: dict[str, int] = {nid: 0 for nid in self.graph.nodes}
        adjacency: dict[str, list[str]] = defaultdict(list)

        for edge in self.graph.edges:
            adjacency[edge.from_id].append(edge.to_id)
            in_degree[edge.to_id] += 1

        batches = []
        remaining = set(self.graph.nodes.keys())

        while remaining:
            batch = [self.graph.nodes[nid] for nid in remaining if in_degree.get(nid, 0) == 0]
            if not batch:
                break
            batches.append(batch)
            for node in batch:
                remaining.discard(node.id)
                for dep in adjacency[node.id]:
                    if dep in remaining:
                        in_degree[dep] -= 1

        return batches

    def critical_path(self) -> list[ExecutionNode]:
        adj = defaultdict(list)
        for edge in self.graph.edges:
            adj[edge.from_id].append(edge.to_id)

        memo: dict[str, tuple[int, Optional[str]]] = {}

        def longest(node_id: str) -> tuple[int, Optional[str]]:
            if node_id in memo:
                return memo[node_id]
            max_len = 1
            next_node = None
            for dep in adj[node_id]:
                child_len, _ = longest(dep)
                if child_len + 1 > max_len:
                    max_len = child_len + 1
                    next_node = dep
            memo[node_id] = (max_len, next_node)
            return max_len, next_node

        longest_len = 0
        path_start = None
        for nid in self.graph.nodes:
            l, _ = longest(nid)
            if l > longest_len:
                longest_len = l
                path_start = nid

        path = []
        current = path_start
        while current is not None:
            path.append(self.graph.nodes[current])
            _, next_node = longest(current)
            current = next_node
        return path

    def risk_bottlenecks(self) -> list[ExecutionNode]:
        return [
            node for node in self.graph.nodes.values()
            if node.risk_level in (RiskLevel.HIGH, RiskLevel.CRITICAL)
        ]
