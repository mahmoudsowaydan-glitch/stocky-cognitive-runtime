"""deterministic_replay_engine.py — Rebuild system state from timeline without side effects.

Key constraints:
  — No sandbox execution
  — No P4 re-evaluation
  — No HAL dependency
  (TIME-003, TIME-004)
"""

import hashlib
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ..contracts.execution_trace import ExecutionTrace
from ..contracts.causal_graph import CausalGraph, CausalGraphBuilder
from ..schema_evolution.evolution_graph import EvolutionGraph
from ..schema_evolution.migration_engine import MigrationEngine
from ..distributed_consensus.consensus_state import ConsensusResult, NodeStateProposal
from ..distributed_consensus.consensus_engine import ConsensusEngine
from .rewind_event import RewindEvent


@dataclass(frozen=True)
class SystemState:
    traces: List[ExecutionTrace] = field(default_factory=list)
    trace_count: int = 0
    schema_version: str = ""
    causal_graph_signature: str = ""
    replayed_at: float = 0.0
    state_hash: str = ""


class DeterministicReplayEngine:
    def __init__(self, evolution_graph: EvolutionGraph, current_version: str):
        self._evolution_graph = evolution_graph
        self._current_version = current_version
        self._migration_engine = MigrationEngine(evolution_graph)

    def replay(self, timeline: List[RewindEvent],
               schema_version: Optional[str] = None) -> SystemState:
        """Reconstruct SystemState from RewindEvent timeline deterministically."""
        # Step 1: Rebuild ExecutionTrace chain from snapshots
        traces: List[ExecutionTrace] = []
        for event in timeline:
            snap = event.execution_snapshot
            trace = ExecutionTrace(
                event_id=snap.get("event_id", event.trace_id),
                session_id=snap.get("session_id", event.node_id),
                sequence_no=snap.get("sequence_no", 0),
                correlation_id=snap.get("correlation_id", ""),
                risk_score=snap.get("risk_score", 0.0),
                p4_verdict=snap.get("p4_verdict", "UNKNOWN"),
                execution_status=snap.get("execution_status", "UNKNOWN"),
                final_status=snap.get("final_status", "UNKNOWN"),
            )
            traces.append(trace)
        traces.sort(key=lambda t: (t.session_id, t.sequence_no))

        # Step 2: Reconstruct CausalGraph incrementally
        builder = CausalGraphBuilder()
        causal_graph = builder.build(traces)
        graph_sig = self._fingerprint_graph(causal_graph)

        # Step 3: Reapply schema migration (Phase C)
        ver = schema_version or self._current_version
        migrated: List[ExecutionTrace] = []
        for trace in traces:
            try:
                plan = self._migration_engine.build_path(
                    ver, self._current_version,
                )
                if plan.is_supported and plan.steps:
                    result = self._migration_engine.migrate_trace(
                        trace, ver, self._current_version,
                    )
                    migrated.append(result)
                else:
                    migrated.append(trace)
            except (ValueError, KeyError):
                migrated.append(trace)

        # Step 4: Compute state hash
        state_hash = self._compute_state_hash(migrated, graph_sig)

        return SystemState(
            traces=migrated,
            trace_count=len(migrated),
            schema_version=self._current_version,
            causal_graph_signature=graph_sig,
            replayed_at=time.time(),
            state_hash=state_hash,
        )

    def replay_deterministic(self, timeline_a: List[RewindEvent],
                              timeline_b: List[RewindEvent]) -> bool:
        """TIME-001: Verify two replays produce identical state hashes."""
        state_a = self.replay(timeline_a)
        state_b = self.replay(timeline_b)
        return state_a.state_hash == state_b.state_hash

    def _fingerprint_graph(self, graph: CausalGraph) -> str:
        roots = sorted(graph.roots)
        nodes_sorted = sorted(graph.nodes.keys())
        raw = f"{roots}|{nodes_sorted}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _compute_state_hash(self, traces: List[ExecutionTrace],
                            graph_sig: str) -> str:
        ordered = sorted(traces, key=lambda t: (t.session_id, t.sequence_no))
        trace_part = "|".join(
            f"{t.event_id},{t.session_id},{t.sequence_no},{t.final_status}"
            for t in ordered
        )
        raw = f"{trace_part}||{graph_sig}||{self._current_version}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()
