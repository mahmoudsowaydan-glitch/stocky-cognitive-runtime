import hashlib
from collections import OrderedDict
from typing import Any, Dict, List

from .intelligence_store import IntelligenceStore, Pattern
from ..contracts.causal_graph import CausalGraph
from ..contracts.execution_trace import ExecutionTrace


class PatternMiner:
    MAX_SEEN_SIGNATURES = 100000

    def __init__(self, store: IntelligenceStore):
        self._store = store
        self._seen_signatures: OrderedDict[str, None] = OrderedDict()
        self._patterns_mined = 0

    def _prune_seen(self) -> None:
        while len(self._seen_signatures) > self.MAX_SEEN_SIGNATURES:
            self._seen_signatures.popitem(last=False)

    def mine(self, graph: CausalGraph, traces: List[ExecutionTrace]) -> int:
        new_count = 0

        for trace in traces:
            sig = self._trace_structure_signature(trace)
            if sig in self._seen_signatures:
                self._seen_signatures.move_to_end(sig)
                existing = self._store.get_pattern(sig)
                if existing:
                    self._store.upsert_pattern(existing)
                continue
            self._seen_signatures[sig] = None
            self._prune_seen()

            ctx = self._build_context_shape(trace)
            pattern = Pattern(
                pattern_id=f"pat_{self._patterns_mined}",
                frequency=1,
                structure_signature=sig,
                context_shape=ctx,
            )
            self._store.upsert_pattern(pattern)
            self._patterns_mined += 1
            new_count += 1

        return new_count

    def _trace_structure_signature(self, trace: ExecutionTrace) -> str:
        parts = [
            str(trace.preflight_valid),
            trace.p4_verdict,
            trace.execution_status,
            trace.final_status,
            str(sorted(trace.capabilities_checked)),
        ]
        raw = "::".join(parts)
        return hashlib.md5(raw.encode()).hexdigest()

    def _build_context_shape(self, trace: ExecutionTrace) -> Dict[str, Any]:
        return {
            "preflight_valid": trace.preflight_valid,
            "p4_verdict": trace.p4_verdict,
            "execution_status": trace.execution_status,
            "final_status": trace.final_status,
            "risk_score": round(trace.risk_score, 2),
            "capabilities": sorted(trace.capabilities_checked),
            "has_error": trace.execution_error is not None,
        }
