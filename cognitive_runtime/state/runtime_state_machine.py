from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Any, Optional


class RuntimeState(Enum):
    IDLE = auto()
    PLANNING = auto()
    EXECUTING = auto()
    VERIFYING = auto()
    RECOVERING = auto()
    FAILED = auto()
    COMPLETED = auto()


TRANSITION_MATRIX: dict[RuntimeState, set[RuntimeState]] = {
    RuntimeState.IDLE: {RuntimeState.PLANNING},
    RuntimeState.PLANNING: {RuntimeState.EXECUTING},
    RuntimeState.EXECUTING: {RuntimeState.EXECUTING, RuntimeState.VERIFYING,
                              RuntimeState.RECOVERING, RuntimeState.FAILED},
    RuntimeState.VERIFYING: {RuntimeState.COMPLETED, RuntimeState.RECOVERING},
    RuntimeState.RECOVERING: {RuntimeState.PLANNING, RuntimeState.FAILED, RuntimeState.IDLE},
    RuntimeState.FAILED: {RuntimeState.IDLE},
    RuntimeState.COMPLETED: {RuntimeState.IDLE},
}

FORBIDDEN_TRANSITIONS: dict[RuntimeState, set[RuntimeState]] = {
    RuntimeState.IDLE: {RuntimeState.EXECUTING, RuntimeState.COMPLETED, RuntimeState.FAILED,
                        RuntimeState.VERIFYING, RuntimeState.RECOVERING},
    RuntimeState.PLANNING: {RuntimeState.COMPLETED, RuntimeState.RECOVERING, RuntimeState.FAILED,
                            RuntimeState.VERIFYING},
    RuntimeState.EXECUTING: {RuntimeState.COMPLETED, RuntimeState.IDLE, RuntimeState.PLANNING},
    RuntimeState.VERIFYING: {RuntimeState.EXECUTING, RuntimeState.PLANNING, RuntimeState.FAILED,
                             RuntimeState.IDLE},
    RuntimeState.RECOVERING: {RuntimeState.COMPLETED, RuntimeState.EXECUTING, RuntimeState.VERIFYING},
    RuntimeState.FAILED: {RuntimeState.EXECUTING, RuntimeState.COMPLETED, RuntimeState.PLANNING,
                          RuntimeState.VERIFYING, RuntimeState.RECOVERING},
    RuntimeState.COMPLETED: {RuntimeState.EXECUTING, RuntimeState.PLANNING, RuntimeState.VERIFYING,
                             RuntimeState.RECOVERING, RuntimeState.FAILED},
}

STATE_TIMEOUTS: dict[RuntimeState, float] = {
    RuntimeState.PLANNING: 5.0,
    RuntimeState.EXECUTING: 30.0,
    RuntimeState.VERIFYING: 10.0,
    RuntimeState.RECOVERING: 30.0,
    RuntimeState.IDLE: float("inf"),
    RuntimeState.FAILED: float("inf"),
    RuntimeState.COMPLETED: float("inf"),
}


@dataclass
class StateTransitionRecord:
    from_state: RuntimeState
    to_state: RuntimeState
    timestamp: datetime
    trigger: str
    duration_ms: float


@dataclass
class StateData:
    current: RuntimeState = RuntimeState.IDLE
    previous: Optional[RuntimeState] = None
    transitions: list[StateTransitionRecord] = field(default_factory=list)
    execution_id: str = ""
    started_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    error: Optional[dict[str, Any]] = None
    entry_time: Optional[datetime] = None
