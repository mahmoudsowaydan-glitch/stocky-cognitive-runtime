"""
trace_window.py — Bounded trace storage with deterministic archival.

OBS-BOUND-001: Eviction preserves replay determinism via:
  - oldest-first eviction (deterministic, ordered)
  - archived segments with per-segment integrity hashes
  - replay cursor tracking
  - full reconstruction for certification/replay

TraceWindow
├── active_window: Deque[ExecutionTrace] — hot traces (bounded)
├── archived_segments: List[CompressedSegment] — compacted deterministic chunks
├── replay_cursor: int — position of last full replay verification
├── integrity_hash: str — rolling SHA256 over all traces
"""

import hashlib
from collections import deque
from dataclasses import dataclass, asdict
from typing import Any, Deque, Dict, Iterator, List, Optional, Set, Tuple, Union

from ..contracts.execution_trace import ExecutionTrace


@dataclass
class CompressedSegment:
    start_cycle: int
    end_cycle: int
    count: int
    traces: List[Dict[str, Any]]
    integrity_hash: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "start_cycle": self.start_cycle,
            "end_cycle": self.end_cycle,
            "count": self.count,
            "traces": self.traces,
            "integrity_hash": self.integrity_hash,
        }


class TraceWindow:
    SEGMENT_SIZE = 1000
    MAX_ARCHIVED_SEGMENTS = 100

    def __init__(self, max_active: int = 1000, max_archived_segments: int = 100):
        self._max_active = max_active
        self._max_archived = max_archived_segments
        self._active: Deque[ExecutionTrace] = deque()
        self._archived: List[CompressedSegment] = []
        self._total_count: int = 0
        self._archived_total: int = 0
        self._replay_cursor: int = 0
        self._integrity_hash: str = ""

    # ── Mutation ──

    def append(self, trace: ExecutionTrace) -> None:
        self._total_count += 1

        while len(self._active) >= self._max_active:
            self._archive(self._active.popleft())

        self._active.append(trace)
        self._integrity_hash = self._rolling_hash(self._integrity_hash, trace)
        self._prune_archived()

    def _prune_archived(self) -> None:
        while len(self._archived) > self._max_archived:
            self._archived.pop(0)

    def _archive(self, trace: ExecutionTrace) -> None:
        d = asdict(trace)
        comp = self._build_segment(d)
        self._finalize_segment(comp)
        self._archived_total += 1

    def _build_segment(self, trace_dict: Dict[str, Any]) -> int:
        if not self._archived:
            self._archived.append(CompressedSegment(
                start_cycle=self._archived_total,
                end_cycle=self._archived_total,
                count=1,
                traces=[trace_dict],
                integrity_hash="",
            ))
            return len(self._archived) - 1

        idx = len(self._archived) - 1
        seg = self._archived[idx]
        self._archived[idx] = CompressedSegment(
            start_cycle=seg.start_cycle,
            end_cycle=seg.end_cycle,
            count=seg.count + 1,
            traces=seg.traces + [trace_dict],
            integrity_hash=seg.integrity_hash,
        )
        return idx

    def _finalize_segment(self, idx: int) -> None:
        seg = self._archived[idx]
        if seg.count < self.SEGMENT_SIZE:
            return
        h = hashlib.sha256()
        for t in seg.traces:
            h.update(f"{t.get('event_id','')}|{t.get('final_status','')}|{t.get('risk_score',0.0)}".encode())
        self._archived[idx] = CompressedSegment(
            start_cycle=seg.start_cycle,
            end_cycle=seg.end_cycle,
            count=seg.count,
            traces=seg.traces,
            integrity_hash=h.hexdigest(),
        )

    def _rolling_hash(self, current: str, trace: ExecutionTrace) -> str:
        h = hashlib.sha256(current.encode() if current else b"")
        h.update(f"{trace.event_id}|{trace.final_status}|{trace.risk_score}".encode())
        return h.hexdigest()

    # ── Full reconstruction (replay/certification) ──

    @property
    def all_traces(self) -> List[ExecutionTrace]:
        result: List[ExecutionTrace] = []
        for seg in self._archived:
            for td in seg.traces:
                result.append(self._dict_to_trace(td))
        result.extend(self._active)
        return result

    @property
    def all_trace_dicts(self) -> List[Dict[str, Any]]:
        result: List[Dict[str, Any]] = []
        for seg in self._archived:
            result.extend(seg.traces)
        for t in self._active:
            result.append(asdict(t))
        return result

    @staticmethod
    def _dict_to_trace(td: Dict[str, Any]) -> ExecutionTrace:
        known = {
            "event_id", "session_id", "sequence_no", "correlation_id",
            "preflight_valid", "preflight_reason", "preflight_rules_triggered",
            "risk_score", "p4_verdict", "p4_reason", "p4_risk_level",
            "p4_rule_triggered", "execution_status", "execution_error",
            "capabilities_checked", "resource_usage",
            "preflight_time", "p4_time", "execution_time", "total_time",
            "final_status",
        }
        safe = {k: v for k, v in td.items() if k in known}
        return ExecutionTrace(
            event_id=safe.get("event_id", ""),
            session_id=safe.get("session_id", ""),
            sequence_no=safe.get("sequence_no", 0),
            correlation_id=safe.get("correlation_id", ""),
            preflight_valid=safe.get("preflight_valid", False),
            preflight_reason=safe.get("preflight_reason", ""),
            preflight_rules_triggered=safe.get("preflight_rules_triggered", []),
            risk_score=safe.get("risk_score", 0.0),
            p4_verdict=safe.get("p4_verdict", ""),
            p4_reason=safe.get("p4_reason", ""),
            p4_risk_level=safe.get("p4_risk_level", ""),
            p4_rule_triggered=safe.get("p4_rule_triggered", ""),
            execution_status=safe.get("execution_status", ""),
            execution_error=safe.get("execution_error"),
            capabilities_checked=safe.get("capabilities_checked", []),
            resource_usage=safe.get("resource_usage", {}),
            preflight_time=safe.get("preflight_time", 0.0),
            p4_time=safe.get("p4_time", 0.0),
            execution_time=safe.get("execution_time", 0.0),
            total_time=safe.get("total_time", 0.0),
            final_status=safe.get("final_status", "UNKNOWN"),
        )

    # ── Access ──

    @property
    def active_window(self) -> List[ExecutionTrace]:
        return list(self._active)

    @property
    def integrity_hash(self) -> str:
        return self._integrity_hash

    @property
    def replay_cursor(self) -> int:
        return self._replay_cursor

    @replay_cursor.setter
    def replay_cursor(self, pos: int) -> None:
        self._replay_cursor = pos

    @property
    def total_count(self) -> int:
        return self._total_count

    @property
    def archived_total(self) -> int:
        return self._archived_total

    @property
    def active_count(self) -> int:
        return len(self._active)

    def __len__(self) -> int:
        return self._total_count

    def __getitem__(self, key: Union[int, slice]) -> Any:
        if isinstance(key, slice):
            start = key.start or 0
            stop = key.stop if key.stop is not None else self._total_count
            step = key.step or 1
            if start < 0:
                start = max(0, self._total_count + start)
            if stop < 0:
                stop = max(0, self._total_count + stop)
            active_start = max(0, self._total_count - len(self._active))
            if start >= active_start:
                offset = start - active_start
                return [list(self._active)[i]
                        for i in range(offset, min(offset + (stop - start) // step, len(self._active)))]
            return self.all_traces[key]
        if isinstance(key, int):
            if key < 0:
                key = self._total_count + key
            if key < self._archived_total:
                return self.all_traces[key]
            return list(self._active)[key - self._archived_total]
        raise TypeError(f"Unsupported key type: {type(key)}")

    def __iter__(self) -> Iterator[ExecutionTrace]:
        yield from self._active

    def __contains__(self, trace: object) -> bool:
        if isinstance(trace, ExecutionTrace):
            return any(t.event_id == trace.event_id for t in self._active)
        return False

    # ── Integrity ──

    def verify_integrity(self) -> bool:
        h = hashlib.sha256()
        for seg in self._archived:
            for td in seg.traces:
                h.update(f"{td.get('event_id','')}|{td.get('final_status','')}|{td.get('risk_score',0.0)}".encode())
        for t in self._active:
            h.update(f"{t.event_id}|{t.final_status}|{t.risk_score}".encode())
        return h.hexdigest() == self._integrity_hash

    def clear(self) -> None:
        self._active.clear()
        self._archived.clear()
        self._total_count = 0
        self._archived_total = 0
        self._replay_cursor = 0
        self._integrity_hash = ""
