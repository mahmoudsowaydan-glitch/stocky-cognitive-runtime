import asyncio
import statistics
import time
from collections import deque
from typing import Any, Dict, List, Optional, Tuple

from .liveness_report import (
    AwaitStall,
    CycleDurationStats,
    LivenessReport,
    PhaseAwaitStats,
)


class NullLivenessMonitor:
    """No-op default — zero overhead when liveness tracking is not needed."""

    STALL_THRESHOLD_MS: float = 5000.0

    def on_cycle_start(self, timestamp: float) -> None:
        pass

    def on_cycle_end(self, timestamp: float) -> None:
        pass

    def on_idle(self) -> None:
        pass

    def on_event_received(self) -> None:
        pass

    def on_await_start(self, phase: str, id: str, timestamp: float) -> None:
        pass

    def on_await_end(self, phase: str, id: str, timestamp: float) -> None:
        pass

    def on_heartbeat(self, timestamp: float) -> None:
        pass

    def get_report(self) -> Optional[LivenessReport]:
        return None


class LivenessMonitor:
    """Tracks runtime physiological metrics for liveness and hang detection.

    Observation points (called by RuntimeLoop):
      - on_cycle_start/end  : bounds of one full event-processing cycle
      - on_idle             : queue.pop() returned None
      - on_event_received   : queue.pop() returned an event (resets idle streak)
      - on_await_start/end  : before/after each async phase (P3/P4/sandbox)
      - on_heartbeat        : every tick_heartbeat() call

    Use get_report() to snapshot current health. The report is purely
    observational — it never modifies runtime control flow.
    """

    STALL_THRESHOLD_MS: float = 5000.0

    def __init__(self, max_history: int = 100) -> None:
        self._max_history = max_history
        self._cycle_durations: deque = deque(maxlen=max_history)
        self._await_records: deque = deque(maxlen=max_history)
        self._heartbeat_timestamps: deque = deque(maxlen=max_history)
        self._idle_streak: int = 0
        self._max_idle_streak: int = 0
        self._cycle_no: int = 0
        self._last_cycle_start: Optional[float] = None
        self._current_await: Optional[Dict[str, Any]] = None
        self._total_idle_cycles: int = 0

    def on_cycle_start(self, timestamp: float) -> None:
        self._cycle_no += 1
        self._last_cycle_start = timestamp

    def on_cycle_end(self, timestamp: float) -> None:
        if self._last_cycle_start is not None:
            duration_ms = (timestamp - self._last_cycle_start) * 1000.0
            self._cycle_durations.append(duration_ms)

    def on_idle(self) -> None:
        self._idle_streak += 1
        self._total_idle_cycles += 1
        if self._idle_streak > self._max_idle_streak:
            self._max_idle_streak = self._idle_streak

    def on_event_received(self) -> None:
        self._idle_streak = 0

    def on_heartbeat(self, timestamp: float) -> None:
        self._heartbeat_timestamps.append(timestamp)

    def on_await_start(self, phase: str, id: str, timestamp: float) -> None:
        self._current_await = {
            "phase": phase,
            "id": id,
            "started_at": timestamp,
        }

    def on_await_end(self, phase: str, id: str, timestamp: float) -> None:
        if self._current_await is not None and self._current_await["phase"] == phase:
            duration_ms = (timestamp - self._current_await["started_at"]) * 1000.0
            self._current_await["duration_ms"] = duration_ms
            self._current_await["ended_at"] = timestamp
            self._await_records.append(self._current_await)
        self._current_await = None

    def get_report(self) -> LivenessReport:
        return LivenessReport(
            cycle_no=self._cycle_no,
            timestamp=time.time(),
            pending_asyncio_tasks=self._count_pending_tasks(),
            event_loop_lag_ms=self._compute_loop_lag(),
            heartbeat_skew_ms=self._compute_heartbeat_skew(),
            heartbeat_delta_variance=self._compute_heartbeat_variance(),
            queue_starvation_cycles=self._idle_streak,
            max_starvation_cycles=self._max_idle_streak,
            cycle_durations=self._compute_cycle_duration_stats(),
            phase_await_stats=self._compute_phase_await_stats(),
            stall_events=self._detect_stalls(),
            total_cycles=self._cycle_no,
            total_idle=self._total_idle_cycles,
            is_stalled=self._current_await is not None,
        )

    def _count_pending_tasks(self) -> int:
        try:
            loop = asyncio.get_running_loop()
            return len(asyncio.all_tasks(loop))
        except RuntimeError:
            return 0

    def _compute_loop_lag(self) -> float:
        if self._last_cycle_start is not None:
            return round((time.time() - self._last_cycle_start) * 1000.0, 2)
        return 0.0

    def _heartbeat_intervals(self) -> List[float]:
        if len(self._heartbeat_timestamps) < 2:
            return []
        return [
            self._heartbeat_timestamps[i] - self._heartbeat_timestamps[i - 1]
            for i in range(1, len(self._heartbeat_timestamps))
        ]

    def _compute_heartbeat_skew(self) -> float:
        intervals = self._heartbeat_intervals()
        if not intervals:
            return 0.0
        mean_interval = sum(intervals) / len(intervals)
        return round(max(abs(i - mean_interval) for i in intervals) * 1000.0, 2)

    def _compute_heartbeat_variance(self) -> float:
        intervals = self._heartbeat_intervals()
        if len(intervals) < 2:
            return 0.0
        return round(statistics.variance(intervals) * 1000.0, 2)

    def _compute_cycle_duration_stats(self) -> CycleDurationStats:
        if not self._cycle_durations:
            return CycleDurationStats(p50_ms=0.0, p95_ms=0.0, p99_ms=0.0, count=0)
        sorted_durs = sorted(self._cycle_durations)
        n = len(sorted_durs)

        def percentile(k: int) -> float:
            idx = max(0, min(n - 1, int(n * k / 100)))
            return round(sorted_durs[idx], 2)

        return CycleDurationStats(
            p50_ms=percentile(50),
            p95_ms=percentile(95),
            p99_ms=percentile(99),
            count=n,
        )

    def _compute_phase_await_stats(self) -> Dict[str, PhaseAwaitStats]:
        phase_durations: Dict[str, List[float]] = {}
        for rec in self._await_records:
            dur = rec.get("duration_ms")
            if dur is not None:
                phase_durations.setdefault(rec["phase"], []).append(dur)

        result: Dict[str, PhaseAwaitStats] = {}
        for phase, durs in phase_durations.items():
            sorted_durs = sorted(durs)
            n = len(sorted_durs)

            def p(k: int) -> float:
                return round(sorted_durs[max(0, min(n - 1, int(n * k / 100)))], 2) if n > 0 else 0.0

            result[phase] = PhaseAwaitStats(
                count=n,
                p50_ms=p(50),
                p95_ms=p(95),
                max_ms=round(max(durs), 2) if durs else 0.0,
            )
        return result

    def _detect_stalls(self) -> List[AwaitStall]:
        stalls: List[AwaitStall] = []
        for rec in self._await_records:
            dur = rec.get("duration_ms")
            if dur is not None and dur > self.STALL_THRESHOLD_MS:
                stalls.append(AwaitStall(
                    phase=rec["phase"],
                    id=rec["id"],
                    duration_ms=round(dur, 2),
                    cycle_no=self._cycle_no,
                ))
        return stalls
