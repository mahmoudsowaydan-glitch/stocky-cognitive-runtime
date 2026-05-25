import asyncio
import uuid
from collections import defaultdict
from datetime import datetime
from typing import Callable, Optional

from .event_types import Event, EventCategory, EventPriority


EventHandler = Callable[[Event], None]


class EventBus:
    def __init__(self):
        self._queue: list[Event] = []
        self._subscribers: dict[str, list[EventHandler]] = defaultdict(list)
        self._history: list[Event] = []
        self._running = False
        self._lock = asyncio.Lock()

    def publish(self, event: Event) -> None:
        if not event.id:
            event.id = str(uuid.uuid4())
        if not event.timestamp:
            event.timestamp = datetime.utcnow()
        self._queue.append(event)
        self._history.append(event)
        self._notify(event)

    def publish_sync(self, event_type: str, category: EventCategory,
                     payload: dict | None = None,
                     priority: EventPriority = EventPriority.MEDIUM,
                     source: str = "", trace_id: str = "") -> Event:
        event = Event(
            id=str(uuid.uuid4()),
            type=event_type,
            category=category,
            priority=priority,
            payload=payload or {},
            source=source,
            trace_id=trace_id or str(uuid.uuid4()),
        )
        self.publish(event)
        return event

    def next_event(self) -> Optional[Event]:
        if self._queue:
            return self._queue.pop(0)
        return None

    async def next_event_async(self) -> Optional[Event]:
        async with self._lock:
            return self.next_event()

    def subscribe(self, event_type: str, handler: EventHandler) -> None:
        self._subscribers[event_type].append(handler)

    def subscribe_category(self, category: EventCategory, handler: EventHandler) -> None:
        self.subscribe(f"category:{category.name}", handler)

    def unsubscribe(self, event_type: str, handler: EventHandler) -> None:
        self._subscribers[event_type] = [
            h for h in self._subscribers[event_type] if h is not handler
        ]

    def _notify(self, event: Event) -> None:
        for handler in self._subscribers.get(event.type, []):
            try:
                handler(event)
            except Exception:
                pass
        for handler in self._subscribers.get(f"category:{event.category.name}", []):
            try:
                handler(event)
            except Exception:
                pass

    @property
    def pending_count(self) -> int:
        return len(self._queue)

    @property
    def total_processed(self) -> int:
        return len(self._history)

    def clear(self) -> None:
        self._queue.clear()
        self._history.clear()
