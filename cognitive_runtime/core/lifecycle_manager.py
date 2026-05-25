from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Any, Optional

from ..events.event_bus import EventBus
from ..events.event_types import EventCategory
from ..observation.live_observer import LiveObserver
from ..state.runtime_state_machine import RuntimeState
from ..state.state_context import StateContext


class SystemStatus(Enum):
    STOPPED = auto()
    BOOTING = auto()
    RUNNING = auto()
    SUSPENDED = auto()
    RECOVERING = auto()
    SHUTTING_DOWN = auto()
    FAILED = auto()


@dataclass
class LifecycleState:
    status: SystemStatus = SystemStatus.STOPPED
    started_at: Optional[datetime] = None
    stopped_at: Optional[datetime] = None
    uptime_seconds: float = 0.0
    error_count: int = 0
    last_error: Optional[str] = None


class LifecycleManager:
    def __init__(self, event_bus: EventBus, observer: LiveObserver):
        self._state = LifecycleState()
        self._state_context = StateContext()
        self._event_bus = event_bus
        self._observer = observer

    def boot(self) -> bool:
        if self._state.status != SystemStatus.STOPPED:
            return False
        self._state.status = SystemStatus.BOOTING
        self._state.started_at = datetime.utcnow()
        self._state_context.transition(RuntimeState.PLANNING, trigger="system_boot")
        self._state.status = SystemStatus.RUNNING
        self._observer.record_state_transition("STOPPED", "RUNNING", "boot_complete")
        return True

    def shutdown(self) -> bool:
        if self._state.status != SystemStatus.RUNNING:
            return False
        self._state.status = SystemStatus.SHUTTING_DOWN
        self._state.stopped_at = datetime.utcnow()
        self._state.uptime_seconds = (self._state.stopped_at - self._state.started_at).total_seconds()
        self._state_context.transition(RuntimeState.COMPLETED, trigger="system_shutdown")
        self._state.status = SystemStatus.STOPPED
        return True

    def suspend(self) -> bool:
        if self._state.status != SystemStatus.RUNNING:
            return False
        self._state.status = SystemStatus.SUSPENDED
        self._observer.record_state_transition("RUNNING", "SUSPENDED", "suspend")
        return True

    def resume(self) -> bool:
        if self._state.status != SystemStatus.SUSPENDED:
            return False
        self._state.status = SystemStatus.RUNNING
        self._observer.record_state_transition("SUSPENDED", "RUNNING", "resume")
        return True

    def record_error(self, error: str) -> None:
        self._state.error_count += 1
        self._state.last_error = error
        if self._state.error_count > 5:
            self._state.status = SystemStatus.FAILED

    @property
    def status(self) -> SystemStatus:
        return self._state.status

    @property
    def uptime(self) -> float:
        if self._state.started_at is None:
            return 0.0
        end = self._state.stopped_at or datetime.utcnow()
        return (end - self._state.started_at).total_seconds()
