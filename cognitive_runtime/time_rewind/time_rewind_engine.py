"""time_rewind_engine.py — Build deterministic timelines and rewind to any point.

Rules:
  TIME-001: Same input traces + same schema = same historical replay
  TIME-002: Time is derived from event order, not system clock
  TIME-003: Rewind must never execute real side effects
  TIME-004: Replay is pure function (no HAL, no runtime mutation)
"""

import hashlib
from typing import Any, Dict, List, Tuple

from ..contracts.execution_trace import ExecutionTrace
from .rewind_event import RewindEvent


def _trace_fingerprint(trace: ExecutionTrace) -> str:
    """Deterministic hash of an ExecutionTrace's identity fields."""
    raw = (
        f"{trace.event_id}|{trace.session_id}|{trace.sequence_no}|"
        f"{trace.correlation_id}|{trace.final_status}|{trace.risk_score}"
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _trace_to_snapshot(trace: ExecutionTrace) -> Dict[str, Any]:
    """Deterministic dict serialization of an ExecutionTrace."""
    return {
        "event_id": trace.event_id,
        "session_id": trace.session_id,
        "sequence_no": trace.sequence_no,
        "correlation_id": trace.correlation_id,
        "risk_score": trace.risk_score,
        "p4_verdict": trace.p4_verdict,
        "execution_status": trace.execution_status,
        "final_status": trace.final_status,
    }


class TimeRewindEngine:
    def build_timeline(self, traces: List[ExecutionTrace]) -> List[RewindEvent]:
        # TIME-002: sort by event order, not timestamps
        sorted_traces = sorted(traces, key=lambda t: (t.session_id, t.sequence_no))
        timeline: List[RewindEvent] = []
        for idx, trace in enumerate(sorted_traces):
            timestamp = float(idx)  # synthetic time from order
            timeline.append(RewindEvent(
                timestamp=timestamp,
                trace_id=trace.event_id,
                node_id=trace.session_id,
                execution_snapshot=_trace_to_snapshot(trace),
                causal_hash=_trace_fingerprint(trace),
            ))
        return timeline

    def rewind(self, target_timestamp: float,
               traces: List[ExecutionTrace]) -> List[ExecutionTrace]:
        # TIME-003: pure filter, no side effects
        timeline = self.build_timeline(traces)
        filtered = [e for e in timeline if e.timestamp <= target_timestamp]
        trace_map: Dict[str, ExecutionTrace] = {t.event_id: t for t in traces}
        result: List[ExecutionTrace] = []
        for event in filtered:
            original = trace_map.get(event.trace_id)
            if original is not None:
                result.append(original)
        return result

    # TIME-001: deterministic validation
    def validate_replay(self, original: List[ExecutionTrace],
                        replayed: List[ExecutionTrace]) -> bool:
        def _hash_list(traces: List[ExecutionTrace]) -> str:
            ordered = sorted(traces, key=lambda t: (t.session_id, t.sequence_no))
            combined = "|".join(_trace_fingerprint(t) for t in ordered)
            return hashlib.sha256(combined.encode("utf-8")).hexdigest()
        return _hash_list(original) == _hash_list(replayed)
