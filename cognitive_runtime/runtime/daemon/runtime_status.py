from dataclasses import dataclass, field
from typing import Optional

from .runtime_lifecycle import LifecycleState


@dataclass(frozen=True)
class RuntimeStatus:
    lifecycle_state: LifecycleState = LifecycleState.STOPPED
    uptime_seconds: float = 0.0
    cycle_count: int = 0
    last_heartbeat_at: Optional[float] = None
    last_heartbeat_skew_ms: float = 0.0
    panic_count: int = 0
    recovery_count: int = 0
    health_status: str = "healthy"
    consecutive_failures: int = 0
    last_error: Optional[str] = None
