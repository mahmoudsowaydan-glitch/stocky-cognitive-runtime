import hashlib
import json
from typing import Any, Dict, List, Optional

from ..contracts.causal_graph import CausalGraph
from ..contracts.execution_trace import ExecutionTrace


class CausalRuntimeFingerprint:
    """
    Deterministic cryptographic fingerprint of the system's causal state.

    fingerprint = hash(events + edges + ordering + replay_flag)

    Properties:
    - deterministic: same causal state → same fingerprint
    - replay-safe: survives serialize → wipe → restore cycle
    - stable across restart: no dependency on wall_time, UUID, or randomness
    """

    def __init__(self):
        self._last_fingerprint: Optional[str] = None

    def compute(self, traces: List[ExecutionTrace],
                graph: CausalGraph,
                is_replay: bool = False) -> str:
        """
        Compute a deterministic hash of the full causal state.

        Traces are sorted by event_id for determinism.
        Graph nodes are sorted by node_id.
        """
        trace_parts = []
        for t in sorted(traces, key=lambda x: x.event_id):
            trace_parts.append({
                "event_id": t.event_id,
                "final_status": t.final_status,
                "p4_verdict": t.p4_verdict,
                "execution_status": t.execution_status,
            })

        node_parts = []
        for nid in sorted(graph.nodes.keys()):
            n = graph.get(nid)
            if n is None:
                continue
            node_parts.append({
                "node_id": n.node_id,
                "node_type": n.node_type,
                "event_id": n.event_id,
                "parent_id": n.parent_id,
                "children": sorted(n.children),
            })

        edge_parts = []
        for e in sorted(graph.edges, key=lambda x: x.edge_id):
            edge_parts.append({
                "edge_id": e.edge_id,
                "source_id": e.source_id,
                "target_id": e.target_id,
                "edge_type": e.edge_type,
            })

        payload = {
            "version": 2,
            "trace_count": len(traces),
            "node_count": len(graph.nodes),
            "edge_count": len(graph.edges),
            "is_replay": is_replay,
            "traces": trace_parts,
            "nodes": node_parts,
            "edges": edge_parts,
        }

        raw = json.dumps(payload, sort_keys=True)
        h = hashlib.sha256(raw.encode()).hexdigest()
        self._last_fingerprint = h
        return h

    @property
    def last_fingerprint(self) -> Optional[str]:
        return self._last_fingerprint

    def matches(self, fp1: str, fp2: str) -> bool:
        return fp1 == fp2


class ReplayFingerprintVerifier:
    """
    Verifies that fingerprint survives replay.
    """

    def __init__(self, fingerprint_builder: CausalRuntimeFingerprint):
        self._builder = fingerprint_builder

    def verify(self, original_fp: str,
               replayed_traces: List[ExecutionTrace],
               replayed_graph: CausalGraph) -> bool:
        replay_fp = self._builder.compute(replayed_traces, replayed_graph,
                                          is_replay=True)
        return self._builder.matches(original_fp, replay_fp)
