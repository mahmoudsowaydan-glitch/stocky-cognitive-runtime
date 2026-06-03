from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class PublicTraceDTO:
    event_id: str = ""
    session_id: str = ""
    status: str = "UNKNOWN"
    risk_score: float = 0.0
    total_time_ms: float = 0.0
    error: Optional[str] = None
    created_at: float = 0.0


@dataclass(frozen=True)
class ReceiptDTO:
    receipt_id: str = ""
    event_id: str = ""
    correlation_id: str = ""
    submitted_at: float = 0.0


@dataclass(frozen=True)
class EventStatusDTO:
    event_id: str = ""
    status: str = "pending"
    receipt_id: str = ""


@dataclass(frozen=True)
class DaemonStatusDTO:
    lifecycle: str = "STOPPED"
    uptime_seconds: float = 0.0
    cycle_count: int = 0
    health: str = "healthy"
    panic_count: int = 0


@dataclass(frozen=True)
class AgentProfileDTO:
    agent_id: str = ""
    name: str = ""
    capabilities: List[str] = field(default_factory=list)
    active: bool = True
    registered_at: float = 0.0


@dataclass(frozen=True)
class HealthDTO:
    status: str = "healthy"
    cycle_count: int = 0
    uptime_seconds: float = 0.0
    panic_count: int = 0
    recovery_count: int = 0


@dataclass(frozen=True)
class SubmitEventDTO:
    session_id: str = ""
    source: str = ""
    payload: Dict[str, Any] = field(default_factory=dict)
    correlation_id: str = ""


@dataclass(frozen=True)
class RegisterAgentDTO:
    agent_id: str = ""
    name: str = ""
    capabilities: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class PaginatedTracesDTO:
    traces: List[PublicTraceDTO] = field(default_factory=list)
    next_cursor: Optional[str] = None
    total: int = 0


