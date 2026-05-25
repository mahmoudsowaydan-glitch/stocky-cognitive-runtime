from collections import defaultdict
from datetime import datetime
from typing import Any, Callable, Optional

from ..events.event_types import Event, EventCategory, EventPriority


class LiveObserver:
    def __init__(self):
        self._trace: list[dict[str, Any]] = []
        self._subscribers: dict[str, list[Callable]] = defaultdict(list)
        self._anomalies: list[dict[str, Any]] = []
        self._metrics: dict[str, float] = {}

    def record(self, event: Event, phase: str = "", metadata: dict[str, Any] | None = None) -> None:
        record = {
            "timestamp": datetime.utcnow().isoformat(),
            "event_id": event.id,
            "event_type": event.type,
            "category": event.category.name,
            "phase": phase,
            "metadata": metadata or {},
        }
        self._trace.append(record)
        self._notify("trace", record)

    def record_node_start(self, node_id: str, action: str) -> None:
        record = {"type": "node_start", "node_id": node_id, "action": action, "timestamp": datetime.utcnow().isoformat()}
        self._trace.append(record)
        self._notify("node", record)

    def record_node_complete(self, node_id: str, result: dict[str, Any] | None = None) -> None:
        record = {"type": "node_complete", "node_id": node_id, "result": result, "timestamp": datetime.utcnow().isoformat()}
        self._trace.append(record)
        self._notify("node", record)

    def record_anomaly(self, anomaly_type: str, details: dict[str, Any]) -> None:
        record = {
            "type": anomaly_type,
            "details": details,
            "timestamp": datetime.utcnow().isoformat(),
            "severity": details.get("severity", "unknown"),
        }
        self._anomalies.append(record)
        self._notify("anomaly", record)

    def record_state_transition(self, from_state: str, to_state: str, trigger: str) -> None:
        record = {
            "type": "state_transition",
            "from": from_state,
            "to": to_state,
            "trigger": trigger,
            "timestamp": datetime.utcnow().isoformat(),
        }
        self._trace.append(record)
        self._notify("state", record)

    def subscribe(self, channel: str, handler: Callable) -> None:
        self._subscribers[channel].append(handler)

    def emit(self, data: Any) -> None:
        self._notify("output", data)

    def get_trace(self, limit: int = 100) -> list[dict[str, Any]]:
        return self._trace[-limit:]

    def get_anomalies(self) -> list[dict[str, Any]]:
        return list(self._anomalies)

    def _notify(self, channel: str, data: Any) -> None:
        for handler in self._subscribers.get(channel, []):
            try:
                handler(data)
            except Exception:
                pass
