"""temporal_consensus_engine.py — Time-aware consensus that extends Phase E.

Runs consensus on the reconstructed state at any historical point T.
TIME-005: Historical consensus must match original execution decisions.
"""

from typing import List, Optional

from ..contracts.execution_trace import ExecutionTrace
from ..schema_evolution.evolution_graph import EvolutionGraph
from ..distributed_consensus.consensus_state import (
    ConsensusResult, NodeStateProposal,
)
from ..distributed_consensus.consensus_engine import ConsensusEngine
from .time_rewind_engine import TimeRewindEngine


class TemporalConsensusEngine:
    def __init__(self, graph: EvolutionGraph, current_version: str):
        self._graph = graph
        self._current_version = current_version
        self._rewind_engine = TimeRewindEngine()
        self._consensus_engine = ConsensusEngine(graph, current_version)

    def consensus_at_time(self, t: float,
                          all_traces: List[ExecutionTrace]) -> ConsensusResult:
        traces_up_to_t = self._rewind_engine.rewind(t, all_traces)

        # Build node proposals from traces at time T
        node_groups: dict = {}
        for trace in traces_up_to_t:
            session = trace.session_id
            if session not in node_groups:
                node_groups[session] = {
                    "versions": set(),
                    "stability": 0.0,
                    "confidence": 0.0,
                    "count": 0,
                }
            node_groups[session]["versions"].add(trace.final_status)
            node_groups[session]["stability"] += 0.5  # placeholder from replayed state
            node_groups[session]["confidence"] += 0.5
            node_groups[session]["count"] += 1

        proposals: List[NodeStateProposal] = []
        for node_id, data in node_groups.items():
            avg_s = data["stability"] / data["count"] if data["count"] else 0.5
            avg_c = data["confidence"] / data["count"] if data["count"] else 0.5
            proposals.append(NodeStateProposal(
                node_id=node_id,
                schema_version=self._current_version,
                causal_snapshot_hash=f"temporal_{t}",
                stability_score=min(avg_s, 1.0),
                confidence_score=min(avg_c, 1.0),
            ))

        return self._consensus_engine.propose(proposals)
