from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Any, Optional


class EventPriority(Enum):
    CRITICAL = auto()
    HIGH = auto()
    MEDIUM = auto()
    LOW = auto()


class EventCategory(Enum):
    SYSTEM_BOOT = auto()
    EXECUTION_PLAN = auto()
    EXECUTION_STEP = auto()
    STATE_TRANSITION = auto()
    CONTROL_CHECK = auto()
    DOCTRINE_VALIDATION = auto()
    AGENT_DISPATCH = auto()
    AGENT_OUTPUT = auto()
    MEMORY_WRITE = auto()
    COHERENCE_UPDATE = auto()
    OBSERVATION = auto()
    RECOVERY = auto()
    ANOMALY = auto()
    ERROR = auto()


@dataclass
class Event:
    id: str
    type: str
    category: EventCategory
    priority: EventPriority = EventPriority.MEDIUM
    payload: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    source: str = ""
    trace_id: str = ""

    def risk_score(self) -> float:
        scores = {
            EventPriority.CRITICAL: 1.0,
            EventPriority.HIGH: 0.75,
            EventPriority.MEDIUM: 0.4,
            EventPriority.LOW: 0.1,
        }
        return scores.get(self.priority, 0.4)
