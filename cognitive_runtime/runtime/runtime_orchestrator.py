"""
runtime_orchestrator.py — Lifecycle manager for the runtime loop.

Controls:
  - start / stop / pause of the main loop
  - heartbeat state
  - system health tracking
  - graceful shutdown
"""

import time
from dataclasses import dataclass
from typing import Any, Callable, Optional

from .runtime_state import RuntimeState


@dataclass
class Heartbeat:
    timestamp: float
    status: str
    uptime: float
    queue_depth: int
    events_processed: int
    health_status: str
    average_cycle_ms: float
    drift_detected: bool


class RuntimeOrchestrator:
    def __init__(self, state: RuntimeState,
                 on_start: Optional[Callable] = None,
                 on_stop: Optional[Callable] = None,
                 on_heartbeat: Optional[Callable[[Heartbeat], None]] = None):
        self._state = state
        self._on_start = on_start
        self._on_stop = on_stop
        self._on_heartbeat = on_heartbeat
        self._running = False

    def start(self) -> None:
        if self._running:
            return
        self._state.status = "running"
        self._state.started_at = time.time()
        self._running = True
        if self._on_start:
            self._on_start()

    def stop(self) -> None:
        if not self._running:
            return
        self._state.status = "stopped"
        self._running = False
        if self._on_stop:
            self._on_stop()

    def pause(self) -> None:
        if self._state.status == "running":
            self._state.status = "paused"

    def resume(self) -> None:
        if self._state.status == "paused":
            self._state.status = "running"

    def tick_heartbeat(self) -> Heartbeat:
        uptime = time.time() - (self._state.started_at or time.time())
        self._state.uptime_seconds = uptime

        hb = Heartbeat(
            timestamp=time.time(),
            status=self._state.status,
            uptime=uptime,
            queue_depth=self._state.queue_depth,
            events_processed=self._state.total_events_processed,
            health_status=self._state.health_status,
            average_cycle_ms=self._state.average_cycle_ms,
            drift_detected=self._state.drift_detected,
        )
        if self._on_heartbeat:
            self._on_heartbeat(hb)
        return hb

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def state(self) -> RuntimeState:
        return self._state
