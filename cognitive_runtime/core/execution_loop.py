from datetime import datetime
from typing import Any, Optional

from ..events.event_bus import EventBus
from ..events.event_types import Event, EventCategory, EventPriority
from ..observation.live_observer import LiveObserver
from ..observation.runtime_metrics import RuntimeMetrics
from .orchestrator import CentralOrchestrator


class ExecutionLoop:
    def __init__(self, orchestrator: CentralOrchestrator,
                 event_bus: EventBus,
                 observer: LiveObserver,
                 metrics: RuntimeMetrics):
        self.orchestrator = orchestrator
        self.event_bus = event_bus
        self.observer = observer
        self.metrics = metrics
        self._running = False
        self._iteration_count = 0
        self._max_idle_iterations = 100

    def start(self) -> None:
        self._running = True
        self._iteration_count = 0

    def iterate(self) -> Optional[dict[str, Any]]:
        if not self._running:
            return None
        self._iteration_count += 1
        event = self.event_bus.next_event()
        if not event:
            return None
        self.metrics.increment("loop.iterations")
        start = datetime.utcnow()
        result = self.orchestrator.handle(event)
        duration = (datetime.utcnow() - start).total_seconds() * 1000
        self.metrics.observe("loop.duration_ms", duration)
        return result

    def run(self, max_iterations: int = 0) -> int:
        self.start()
        processed = 0
        while self._running:
            result = self.iterate()
            if result is not None:
                processed += 1
            if max_iterations and processed >= max_iterations:
                break
        return processed

    def stop(self) -> None:
        self._running = False

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def iteration_count(self) -> int:
        return self._iteration_count
