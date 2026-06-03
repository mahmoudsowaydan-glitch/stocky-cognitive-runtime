from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class AwaitStall:
    phase: str
    id: str
    duration_ms: float
    cycle_no: int


@dataclass
class PhaseAwaitStats:
    count: int
    p50_ms: float
    p95_ms: float
    max_ms: float


@dataclass
class CycleDurationStats:
    p50_ms: float
    p95_ms: float
    p99_ms: float
    count: int


@dataclass
class LivenessReport:
    cycle_no: int
    timestamp: float
    pending_asyncio_tasks: int
    event_loop_lag_ms: float
    heartbeat_skew_ms: float
    heartbeat_delta_variance: float
    queue_starvation_cycles: int
    max_starvation_cycles: int
    cycle_durations: CycleDurationStats
    phase_await_stats: Dict[str, PhaseAwaitStats]
    stall_events: List[AwaitStall]
    total_cycles: int
    total_idle: int
    is_stalled: bool
