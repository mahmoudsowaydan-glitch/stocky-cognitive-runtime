"""
replay_validator.py — Verifies recovered replay determinism.

Compares original traces vs replayed traces for:
  - Causal integrity (same event_id sequence, same final_status)
  - Trace equivalence (fingerprint matching)
  - No divergence (same decisions, same outcomes)
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import hashlib

from ..contracts.execution_trace import ExecutionTrace
from ..contracts.causal_graph import CausalGraphBuilder
from .runtime_snapshot import RuntimeSnapshot


@dataclass
class ReplayValidation:
    valid: bool
    total_original: int
    total_replayed: int
    divergence_count: int
    divergences: List[Dict[str, Any]]
    causal_integrity: bool
    trace_fingerprint_match: bool
    original_fingerprint: str
    replayed_fingerprint: str
    details: str


class ReplayValidator:
    def __init__(self):
        self._builder = CausalGraphBuilder()

    def validate(self, snapshot: RuntimeSnapshot,
                 replayed_traces: List[ExecutionTrace]) -> ReplayValidation:
        divergences = []

        # Build original traces from snapshot
        original = snapshot.traces

        if len(original) != len(replayed_traces):
            divergences.append({
                "type": "count_mismatch",
                "detail": f"original={len(original)} replayed={len(replayed_traces)}",
            })

        # Compare trace-by-trace
        min_len = min(len(original), len(replayed_traces))
        for i in range(min_len):
            orig = original[i]
            repl = replayed_traces[i]

            orig_eid = orig.get("event_id", "") if isinstance(orig, dict) else getattr(orig, "event_id", "")
            repl_eid = repl.event_id if hasattr(repl, "event_id") else ""

            orig_fs = orig.get("final_status", "") if isinstance(orig, dict) else getattr(orig, "final_status", "")
            repl_fs = repl.final_status if hasattr(repl, "final_status") else ""

            if orig_eid != repl_eid:
                divergences.append({
                    "type": "event_id_mismatch",
                    "index": i,
                    "original": orig_eid,
                    "replayed": repl_eid,
                })
            elif orig_fs != repl_fs:
                divergences.append({
                    "type": "final_status_mismatch",
                    "index": i,
                    "event_id": orig_eid,
                    "original_fs": orig_fs,
                    "replayed_fs": repl_fs,
                })

        # Causal integrity: build causal graphs and compare structural fingerprints
        causal_ok = True
        if min_len > 0:
            try:
                orig_graph = self._builder.build(
                    [self._dict_to_trace(t) for t in original[:min_len]]
                )
                repl_graph = self._builder.build(replayed_traces[:min_len])

                def _sh(s: str) -> str:
                    return hashlib.sha256(s.encode()).hexdigest()[:16]
                orig_fp = _sh(str(sorted(orig_graph.nodes.keys())))
                repl_fp = _sh(str(sorted(repl_graph.nodes.keys())))
                if orig_fp != repl_fp:
                    causal_ok = False
                    divergences.append({
                        "type": "causal_graph_mismatch",
                        "detail": "node structure differs between original and replayed",
                    })
            except Exception as e:
                causal_ok = False
                divergences.append({
                    "type": "causal_graph_error",
                    "detail": str(e),
                })

        # Overall trace fingerprint
        def compute_trace_fingerprint(traces: List) -> str:
            raw = ""
            for t in traces:
                if isinstance(t, dict):
                    raw += f"{t.get('event_id','')}:{t.get('final_status','')}|"
                else:
                    raw += f"{getattr(t, 'event_id', '')}:{getattr(t, 'final_status', '')}|"
            return hashlib.sha256(raw.encode()).hexdigest()[:16]

        orig_fp_total = compute_trace_fingerprint(original)
        repl_fp_total = compute_trace_fingerprint(replayed_traces)
        fp_match = orig_fp_total == repl_fp_total

        if not fp_match and not divergences:
            divergences.append({
                "type": "fingerprint_mismatch",
                "detail": "overall trace fingerprint differs",
            })

        valid = len(divergences) == 0 and causal_ok
        return ReplayValidation(
            valid=valid,
            total_original=len(original),
            total_replayed=len(replayed_traces),
            divergence_count=len(divergences),
            divergences=divergences,
            causal_integrity=causal_ok,
            trace_fingerprint_match=fp_match,
            original_fingerprint=orig_fp_total,
            replayed_fingerprint=repl_fp_total,
            details="valid" if valid else f"{len(divergences)} divergence(s) found",
        )

    def _dict_to_trace(self, d: Any) -> ExecutionTrace:
        if isinstance(d, ExecutionTrace):
            return d
        if isinstance(d, dict):
            return ExecutionTrace(
                event_id=d.get("event_id", ""),
                session_id=d.get("session_id", ""),
                sequence_no=d.get("sequence_no", 0),
                correlation_id=d.get("correlation_id", ""),
                preflight_valid=d.get("preflight_valid", False),
                preflight_reason=d.get("preflight_reason"),
                preflight_rules_triggered=d.get("preflight_rules_triggered", []),
                risk_score=d.get("risk_score", 0.0),
                p4_verdict=d.get("p4_verdict", "UNKNOWN"),
                p4_reason=d.get("p4_reason"),
                p4_risk_level=d.get("p4_risk_level"),
                p4_rule_triggered=d.get("p4_rule_triggered"),
                execution_status=d.get("execution_status", "UNKNOWN"),
                execution_error=d.get("execution_error"),
                capabilities_checked=d.get("capabilities_checked", []),
                resource_usage=d.get("resource_usage", {}),
                preflight_time=d.get("preflight_time", 0.0),
                p4_time=d.get("p4_time", 0.0),
                execution_time=d.get("execution_time", 0.0),
                total_time=d.get("total_time", 0.0),
                final_status=d.get("final_status", "UNKNOWN"),
            )
        return ExecutionTrace()

    def _build_trace_list(self, traces_data: List[Any]) -> List[ExecutionTrace]:
        return [self._dict_to_trace(t) for t in traces_data]
