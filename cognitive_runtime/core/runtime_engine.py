from typing import Optional

from ..events.event_bus import EventBus
from ..events.event_types import Event, EventCategory, EventPriority
from ..observation.live_observer import LiveObserver
from ..observation.runtime_metrics import RuntimeMetrics
from .orchestrator import CentralOrchestrator


class RuntimeEngine:
    def __init__(self, orchestrator: Optional[CentralOrchestrator] = None,
                 event_bus: Optional[EventBus] = None,
                 observer: Optional[LiveObserver] = None,
                 metrics: Optional[RuntimeMetrics] = None):
        self.orchestrator = orchestrator or CentralOrchestrator()
        self.event_bus = event_bus or EventBus()
        self.observer = observer or LiveObserver()
        self.metrics = metrics or RuntimeMetrics()
        self.running = False

    def start(self) -> None:
        self.running = True
        self.orchestrator.initialize()

        boot_event = self.event_bus.publish_sync(
            event_type="system.boot",
            category=EventCategory.SYSTEM_BOOT,
            payload={"status": "starting"},
            source="runtime_engine",
        )
        self.observer.record(boot_event, phase="boot")
        self.metrics.increment("system.boots")

    def tick(self) -> None:
        event = self.event_bus.next_event()
        if event:
            self.metrics.increment("events.processed")
            self.orchestrator.handle(event)

    def run_forever(self, max_iterations: int = 0) -> None:
        self.start()
        iterations = 0
        while self.running:
            self.tick()
            iterations += 1
            if max_iterations and iterations >= max_iterations:
                break

    def stop(self) -> None:
        self.running = False
        self.event_bus.publish_sync(
            event_type="system.shutdown",
            category=EventCategory.SYSTEM_BOOT,
            payload={"status": "stopping"},
            source="runtime_engine",
        )

    def submit(self, event_type: str, payload: dict,
               priority: EventPriority = EventPriority.MEDIUM,
               source: str = "") -> Event:
        return self.event_bus.publish_sync(
            event_type=event_type,
            category=EventCategory.EXECUTION_PLAN,
            payload=payload,
            priority=priority,
            source=source or "runtime_engine",
        )

    @property
    def is_running(self) -> bool:
        return self.running
