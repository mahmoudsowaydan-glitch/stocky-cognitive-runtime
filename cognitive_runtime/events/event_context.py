from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

from .event_types import Event


@dataclass
class EventContext:
    event: Event
    entered_at: datetime = field(default_factory=datetime.utcnow)
    duration_ms: float = 0.0
    status: str = "pending"
    result: Optional[dict[str, Any]] = None
    error: Optional[str] = None
    parent_context_id: Optional[str] = None
    child_contexts: list[str] = field(default_factory=list)
    tags: dict[str, str] = field(default_factory=dict)

    def complete(self, result: dict[str, Any] | None = None) -> None:
        self.duration_ms = (datetime.utcnow() - self.entered_at).total_seconds() * 1000
        self.status = "completed"
        self.result = result

    def fail(self, error: str) -> None:
        self.duration_ms = (datetime.utcnow() - self.entered_at).total_seconds() * 1000
        self.status = "failed"
        self.error = error


class ContextStore:
    def __init__(self):
        self._contexts: dict[str, EventContext] = {}

    def register(self, context: EventContext) -> None:
        self._contexts[context.event.id] = context

    def get(self, event_id: str) -> Optional[EventContext]:
        return self._contexts.get(event_id)

    def link(self, parent_id: str, child_id: str) -> None:
        parent = self._contexts.get(parent_id)
        child = self._contexts.get(child_id)
        if parent and child:
            child.parent_context_id = parent_id
            parent.child_contexts.append(child_id)
