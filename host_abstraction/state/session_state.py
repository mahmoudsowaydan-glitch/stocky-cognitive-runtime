from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Deque, Dict, Iterable, List, Optional

from ..core.contracts import HostEvent


@dataclass
class IntentHypothesis:
    intent_type: str
    confidence: float
    supporting_signals: List[HostEvent] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, object]:
        return {
            "intent_type": self.intent_type,
            "confidence": self.confidence,
            "supporting_signals": [
                {
                    "source": event.source.value,
                    "type": event.type,
                    "payload": event.payload,
                    "timestamp": event.timestamp.isoformat(),
                }
                for event in self.supporting_signals
            ],
            "created_at": self.created_at.isoformat(),
        }


class HALSessionState:
    def __init__(self, window_size: int = 50) -> None:
        self.active_session_id: Optional[str] = None
        self.event_history_window: Deque[HostEvent] = deque(maxlen=window_size)
        self.last_interaction_timestamp: Optional[datetime] = None
        self.workspace_snapshot_ref: Optional[str] = None

    def start_session(self, session_id: str) -> None:
        self.active_session_id = session_id
        self.event_history_window.clear()
        self.last_interaction_timestamp = datetime.utcnow()
        self.workspace_snapshot_ref = None

    def close_session(self) -> None:
        self.active_session_id = None
        self.event_history_window.clear()
        self.last_interaction_timestamp = None
        self.workspace_snapshot_ref = None

    def record_event(self, event: HostEvent) -> None:
        self.event_history_window.append(event)
        self.last_interaction_timestamp = event.timestamp

    def get_recent_events(self, count: int = 10) -> List[HostEvent]:
        return list(self.event_history_window)[-count:]

    def query_recent_events(self, predicate: callable, count: int = 10) -> List[HostEvent]:
        events = list(self.event_history_window)
        return [event for event in reversed(events) if predicate(event)][:count]

    def update_workspace_snapshot_ref(self, snapshot_ref: str) -> None:
        self.workspace_snapshot_ref = snapshot_ref

    def snapshot(self) -> Dict[str, object]:
        return {
            "active_session_id": self.active_session_id,
            "event_count": len(self.event_history_window),
            "last_interaction_timestamp": self.last_interaction_timestamp.isoformat()
            if self.last_interaction_timestamp
            else None,
            "workspace_snapshot_ref": self.workspace_snapshot_ref,
        }


class IntentHypothesisGenerator:
    def __init__(self) -> None:
        self._intent_map = {
            "file.opened": ["review", "analyze"],
            "file.changed": ["edit", "refactor", "debug"],
            "selection.changed": ["copy", "compare", "refactor", "debug"],
            "command.invoked": ["execute", "analyze", "refactor", "debug"],
            "focus.in": ["review", "edit", "analyze"],
            "focus.out": ["pause", "review"],
            "host.connected": ["initialize"],
            "host.disconnected": ["terminate"],
        }

    def generate(self, events: Iterable[HostEvent]) -> List[IntentHypothesis]:
        candidates: Dict[str, IntentHypothesis] = {}

        for event in events:
            intent_types = self._intent_map.get(event.type, ["other"])
            for intent_type in intent_types:
                if intent_type not in candidates:
                    candidates[intent_type] = IntentHypothesis(
                        intent_type=intent_type,
                        confidence=0.0,
                        supporting_signals=[],
                    )
                hypothesis = candidates[intent_type]
                hypothesis.supporting_signals.append(event)
                hypothesis.confidence += self._score_event(event, intent_type)

        for hypothesis in candidates.values():
            hypothesis.confidence = min(1.0, hypothesis.confidence)

        return sorted(
            [hypothesis for hypothesis in candidates.values() if hypothesis.confidence > 0],
            key=lambda hypothesis: hypothesis.confidence,
            reverse=True,
        )

    def _score_event(self, event: HostEvent, intent_type: str) -> float:
        score = 0.2
        if event.type == "selection.changed" and intent_type in {"copy", "compare", "refactor", "debug"}:
            score += 0.4
        if event.type == "file.changed" and intent_type in {"edit", "refactor", "debug"}:
            score += 0.5
        if event.type == "file.opened" and intent_type in {"review", "analyze"}:
            score += 0.5
        if event.type == "command.invoked" and intent_type in {"execute", "refactor", "debug"}:
            score += 0.6
        if event.type == "focus.in" and intent_type == "review":
            score += 0.4
        if event.type == "focus.out" and intent_type == "pause":
            score += 0.4
        if event.source == event.source.HEADLESS and intent_type in {"initialize", "terminate"}:
            score += 0.2
        if event.payload.get("priority") == "high":
            score += 0.2
        return min(1.0, score)
