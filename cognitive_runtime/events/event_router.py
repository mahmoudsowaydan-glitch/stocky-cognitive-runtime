from collections import defaultdict
from typing import Any, Optional

from .event_types import Event, EventCategory, EventPriority


class RoutingRule:
    def __init__(self, source: str = "", category: Optional[EventCategory] = None,
                 min_priority: EventPriority = EventPriority.LOW,
                 target: str = ""):
        self.source = source
        self.category = category
        self.min_priority = min_priority
        self.target = target

    def matches(self, event: Event) -> bool:
        if self.source and event.source != self.source:
            return False
        if self.category and event.category != self.category:
            return False
        if event.priority.value < self.min_priority.value:
            return False
        return True


class EventRouter:
    def __init__(self):
        self._routes: list[tuple[RoutingRule, str]] = []

    def add_route(self, rule: RoutingRule, target: str) -> None:
        self._routes.append((rule, target))

    def route(self, event: Event) -> list[str]:
        targets = []
        for rule, target in self._routes:
            if rule.matches(event):
                targets.append(target)
        return targets

    def route_table(self) -> list[dict[str, Any]]:
        return [
            {"target": t, "source": r.source, "category": r.category, "min_priority": r.min_priority.name}
            for r, t in self._routes
        ]
