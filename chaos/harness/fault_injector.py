"""
fault_injector.py — EventQueue-level fault injection.

Wraps an EventQueue to inject:
- Event duplication
- Event corruption (malformed payloads)
- Delivery delay / starvation
- Partial writes simulation
"""

import copy
import random
import time
from typing import Any, Callable, List, Optional

from cognitive_runtime.substrate.event_queue import EventQueue
from cognitive_runtime.contracts.enriched_event import HostEvent


class FaultInjector:
    """Wraps an EventQueue to inject controlled faults into the event stream."""

    def __init__(self, queue: EventQueue, seed: Optional[int] = None):
        self._queue = queue
        self._rng = random.Random(seed)

        # Fault configuration
        self.delay_range: tuple = (0.0, 0.0)
        self.corruption_rate: float = 0.0
        self.duplication_rate: float = 0.0
        self.starvation_duration: float = 0.0
        self._starvation_until: float = 0.0

    # Passthrough properties
    @property
    def stats(self):
        return self._queue.stats

    @property
    def db_path(self):
        return self._queue.db_path

    def open(self):
        self._queue.open()

    def close(self):
        self._queue.close()

    def push(self, event: HostEvent) -> str:
        if self._rng.random() < self.corruption_rate:
            event = self._corrupt(event)
        eid = self._queue.push(event)
        if self._rng.random() < self.duplication_rate:
            self._queue.push(copy.deepcopy(event))
        return eid

    def pop(self, timeout: float = 1.0) -> Optional[HostEvent]:
        if self.starvation_duration > 0:
            now = time.time()
            if self._starvation_until == 0:
                self._starvation_until = now + self.starvation_duration
            if now < self._starvation_until:
                return None
            self._starvation_until = 0.0

        if self.delay_range != (0.0, 0.0):
            delay = self._rng.uniform(*self.delay_range)
            time.sleep(delay)

        event = self._queue.pop(timeout)
        if event is not None and self._rng.random() < self.corruption_rate:
            event = self._corrupt(event)
        return event

    def ack(self, event_id: str):
        self._queue.ack(event_id)

    def nack(self, event_id: str, error: str, proposal: Any = None):
        self._queue.nack(event_id, error, proposal)

    def dead_letter_count(self) -> int:
        return self._queue.dead_letter_count()

    def _corrupt(self, event: HostEvent) -> HostEvent:
        corrupted = copy.deepcopy(event)
        choice = self._rng.choice(["payload", "source", "event_id", "timestamp"])
        if choice == "payload":
            corrupted.payload = {"chaos_corrupted": True, "original": str(event.payload)}
        elif choice == "source":
            corrupted.source = "CHAOS_CORRUPTED_SOURCE"
        elif choice == "event_id":
            corrupted.event_id = f"chaos_{self._rng.randint(1, 99999)}"
        elif choice == "timestamp":
            corrupted.timestamp = event.timestamp + self._rng.uniform(-100, 100)
        return corrupted

    def inject_starvation(self, duration: float):
        """Queue returns None (empty) for `duration` seconds."""
        self.starvation_duration = duration

    def clear_starvation(self):
        self.starvation_duration = 0.0
        self._starvation_until = 0.0
