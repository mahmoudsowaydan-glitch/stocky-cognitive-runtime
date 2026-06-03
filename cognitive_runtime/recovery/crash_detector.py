"""
crash_detector.py — Detects unclean shutdown, corrupted cycles, partial execution, orphan traces.

Uses WAL state + trace continuity to determine if the last runtime session ended cleanly.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class CrashIndicator:
    unclean_shutdown: bool
    corrupted_cycles: int
    partial_executions: int
    orphan_traces: int
    gap_in_sequence: bool
    last_trace_id: Optional[str] = None
    expected_trace_count: int = 0
    actual_trace_count: int = 0
    details: str = ""


class CrashDetector:
    def __init__(self):
        self._last_check: Optional[CrashIndicator] = None

    def detect(self, runtime_loop: Any) -> CrashIndicator:
        traces = []
        if hasattr(runtime_loop, "_traces"):
            traces = list(runtime_loop._traces)

        state = None
        if hasattr(runtime_loop, "_state"):
            state = runtime_loop._state

        tc = len(traces)

        # Check 1: Gap in event_id sequence
        gap_found = False
        last_tid = None
        if tc >= 2:
            ids = []
            import re
            for t in traces:
                eid = getattr(t, "event_id", "")
                try:
                    numeric = re.search(r'\d+$', eid)
                    if numeric:
                        ids.append(int(numeric.group()))
                except (ValueError, IndexError):
                    pass
            if ids:
                ids.sort()
                expected = list(range(ids[0], ids[-1] + 1))
                gap_found = len(ids) != len(expected) or ids != expected
                last_tid = traces[-1].event_id if hasattr(traces[-1], "event_id") else None

        # Check 2: Orphan traces (traces without corresponding WAL event)
        orphan_count = 0
        if hasattr(runtime_loop, "_queue") and hasattr(runtime_loop._queue, "stats"):
            qs = runtime_loop._queue.stats
            orphan_count = max(0, tc - qs.processed if hasattr(qs, 'processed') else 0)

        # Check 3: Partial executions (traces with UNKNOWN final_status)
        partial = sum(1 for t in traces if getattr(t, "final_status", "") == "UNKNOWN")

        # Check 4: Corrupted cycles (status mismatch or invalid timings)
        corrupted = 0
        for t in traces:
            fs = getattr(t, "final_status", "")
            if fs == "UNKNOWN":
                corrupted += 1
                continue
            es = getattr(t, "execution_status", "")
            pv = getattr(t, "preflight_valid", None)
            if pv is not None and fs.startswith("P4_") and es == "UNKNOWN":
                corrupted += 1

        # Check 5: Health status indicates unclean shutdown
        status_str = "stopped"
        health = "healthy"
        if state:
            status_str = getattr(state, "status", "stopped")
            health = getattr(state, "health_status", "healthy")

        unclean = (status_str != "stopped" and status_str != "")
        if health == "critical" and status_str == "stopped":
            unclean = True

        detail_parts = []
        if unclean:
            detail_parts.append(f"last_status={status_str}")
        if gap_found:
            detail_parts.append("sequence_gap")
        if orphan_count > 0:
            detail_parts.append(f"orphans={orphan_count}")
        if partial > 0:
            detail_parts.append(f"partial={partial}")

        indicator = CrashIndicator(
            unclean_shutdown=unclean or gap_found or partial > 0,
            corrupted_cycles=corrupted,
            partial_executions=partial,
            orphan_traces=orphan_count,
            gap_in_sequence=gap_found,
            last_trace_id=last_tid,
            expected_trace_count=tc,
            actual_trace_count=tc,
            details="; ".join(detail_parts) if detail_parts else "clean",
        )
        self._last_check = indicator
        return indicator

    @property
    def last_check(self) -> Optional[CrashIndicator]:
        return self._last_check
