"""
runtime_state.py — Live system state model.

Lightweight in-memory snapshot of runtime health and activity.
No persistence — used for heartbeat, monitoring, and HAL observation.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional


@dataclass
class RuntimeState:
    # Identity
    started_at: Optional[float] = None
    uptime_seconds: float = 0.0
    status: str = "stopped"  # stopped / running / paused / degraded

    # Queue
    queue_depth: int = 0
    total_events_processed: int = 0

    # Sessions
    active_sessions: int = 0
    total_sessions: int = 0

    # Execution
    last_execution_trace_id: str = ""
    last_execution_status: str = ""
    last_execution_at: Optional[float] = None

    # Health
    consecutive_failures: int = 0
    total_failures: int = 0
    health_status: str = "healthy"  # healthy / degraded / critical

    # Coherence
    drift_detected: bool = False
    drift_count: int = 0

    # Timing
    average_cycle_ms: float = 0.0
    last_cycle_ms: float = 0.0

    # Errors
    last_error: Optional[str] = None
    errors: list[str] = field(default_factory=list)

    def record_cycle(self, duration_ms: float, success: bool,
                     queue_depth: int) -> None:
        self.total_events_processed += 1
        self.last_cycle_ms = duration_ms
        self.queue_depth = queue_depth

        # Running average
        if self.total_events_processed == 1:
            self.average_cycle_ms = duration_ms
        else:
            self.average_cycle_ms = (
                self.average_cycle_ms * 0.9 + duration_ms * 0.1
            )

        if not success:
            self.consecutive_failures += 1
            self.total_failures += 1
            if self.consecutive_failures >= 5:
                self.health_status = "critical"
            elif self.consecutive_failures >= 3:
                self.health_status = "degraded"
        else:
            self.consecutive_failures = 0
            if self.health_status != "healthy":
                self.health_status = "healthy"

    def record_error(self, error: str) -> None:
        self.last_error = error
        self.errors.append(error)
        if len(self.errors) > 100:
            self.errors.pop(0)

    def snapshot(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "uptime_seconds": self.uptime_seconds,
            "queue_depth": self.queue_depth,
            "total_events_processed": self.total_events_processed,
            "active_sessions": self.active_sessions,
            "health_status": self.health_status,
            "consecutive_failures": self.consecutive_failures,
            "drift_detected": self.drift_detected,
            "average_cycle_ms": round(self.average_cycle_ms, 2),
            "last_error": self.last_error,
        }
