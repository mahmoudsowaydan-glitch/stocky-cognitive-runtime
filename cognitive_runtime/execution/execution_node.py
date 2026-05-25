from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Any, Optional


class ActionType(Enum):
    MODIFY_FILE = auto()
    RUN_COMMAND = auto()
    READ_ANALYSIS = auto()
    VALIDATE = auto()
    NETWORK_CALL = auto()


class RiskLevel(Enum):
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


class NodeStatus(Enum):
    PENDING = auto()
    RUNNING = auto()
    SUCCESS = auto()
    FAILED = auto()
    ROLLED_BACK = auto()
    SKIPPED = auto()


class ConditionType(Enum):
    FILE_EXISTS = auto()
    STATE_IS = auto()
    DEP_CLEAN = auto()
    PERMISSION_OK = auto()
    FILE_COMPILES = auto()
    TEST_PASSES = auto()
    STATE_VALID = auto()
    DEP_OK = auto()


class RollbackStrategy(Enum):
    REVERT_FILE = auto()
    UNDO_COMMAND = auto()
    COMPENSATE = auto()
    RESTORE_SNAPSHOT = auto()


@dataclass
class Condition:
    type: ConditionType
    target: str
    expected: str


@dataclass
class RollbackAction:
    strategy: RollbackStrategy
    action: str
    data: Optional[dict[str, Any]] = None


@dataclass
class ExecutionNode:
    id: str
    action: str
    action_type: ActionType
    preconditions: list[Condition] = field(default_factory=list)
    postconditions: list[Condition] = field(default_factory=list)
    risk_level: RiskLevel = RiskLevel.LOW
    rollback: Optional[RollbackAction] = None
    timeout_ms: int = 10000
    retry_count: int = 1
    retry_attempts: int = 0
    checkpoint: bool = False
    dependencies: list[str] = field(default_factory=list)
    status: NodeStatus = NodeStatus.PENDING
    result: Optional[dict[str, Any]] = None
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_ms: float = 0.0

    @property
    def elapsed_ms(self) -> float:
        if self.started_at is None:
            return 0.0
        end = self.completed_at or datetime.utcnow()
        return (end - self.started_at).total_seconds() * 1000

    @property
    def is_timeout(self) -> bool:
        if self.started_at is None or self.status in (NodeStatus.SUCCESS, NodeStatus.FAILED,
                                                        NodeStatus.ROLLED_BACK):
            return False
        return self.elapsed_ms > self.timeout_ms

    def can_retry(self) -> bool:
        return self.retry_attempts < self.retry_count

    def __repr__(self) -> str:
        return f"ExecutionNode({self.id}, {self.action_type.name}, {self.status.name})"
