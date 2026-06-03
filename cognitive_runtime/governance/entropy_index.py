import math
from typing import List

from ..contracts.causal_graph import CausalGraph
from ..contracts.execution_trace import ExecutionTrace
from ..intelligence.intelligence_store import IntelligenceStore
from .governance_report import EntropyMetrics


class EntropyIndex:
    NODES_PER_TRACE_IDEAL = 5.0

    def analyze(self, traces: List[ExecutionTrace],
                graph: CausalGraph,
                store: IntelligenceStore) -> EntropyMetrics:
        total_traces = len(traces)
        if total_traces == 0:
            return EntropyMetrics(
                causal_density=0.0, pattern_explosion=0.0,
                trace_inflation=0.0, graph_branching=0.0, overall=0.0,
            )

        causal_density = self._causal_density(graph)
        pattern_explosion = self._pattern_explosion(store, total_traces)
        trace_inflation = self._trace_inflation(graph, total_traces)
        graph_branching = self._graph_branching(graph)

        overall = (
            0.30 * causal_density
            + 0.25 * pattern_explosion
            + 0.25 * trace_inflation
            + 0.20 * graph_branching
        )

        return EntropyMetrics(
            causal_density=round(causal_density, 4),
            pattern_explosion=round(pattern_explosion, 4),
            trace_inflation=round(trace_inflation, 4),
            graph_branching=round(graph_branching, 4),
            overall=round(min(1.0, overall), 4),
        )

    def _causal_density(self, graph: CausalGraph) -> float:
        n = len(graph.nodes)
        if n == 0:
            return 0.0
        density = len(graph.edges) / n
        deviation = abs(density - 0.75) / 0.25
        return min(1.0, deviation)

    def _pattern_explosion(self, store: IntelligenceStore, total: int) -> float:
        unique = len(store.patterns)
        if total == 0 or unique == 0:
            return 0.0
        return min(1.0, unique / total)

    def _trace_inflation(self, graph: CausalGraph, total: int) -> float:
        if total == 0:
            return 0.0
        effective = len(graph.nodes) / self.NODES_PER_TRACE_IDEAL
        denominator = max(effective, float(total))
        avg_nodes = len(graph.nodes) / denominator
        if avg_nodes <= self.NODES_PER_TRACE_IDEAL:
            return 0.0
        return min(1.0, (avg_nodes - self.NODES_PER_TRACE_IDEAL) / 10.0)

    def _graph_branching(self, graph: CausalGraph) -> float:
        n = len(graph.nodes)
        if n == 0:
            return 0.0
        children_counts = [len(node.children) for node in graph.nodes.values()]
        avg_children = sum(children_counts) / n
        if avg_children <= 1.0:
            return 0.0
        return min(1.0, (avg_children - 1.0) / 2.0)
