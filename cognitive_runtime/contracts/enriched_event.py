from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

from ..contracts.execution_contract import (
    ExecutionProposal,
    ExecutionResult,
    HostEvent,
    PolicyDecision,
)
from ..kernel.time_kernel import TimeStamp


@dataclass
class TraceEntry:
    stage: str
    stage_type: str
    data: dict[str, Any]
    timestamp: float


@dataclass
class EnrichedEvent:
    event_id: str
    session_id: str
    sequence_no: int
    correlation_id: str

    host_event: HostEvent
    p3_proposal: Optional[ExecutionProposal] = None
    p4_decision: Optional[PolicyDecision] = None
    execution_result: Optional[ExecutionResult] = None

    hal_trace: list[TraceEntry] = field(default_factory=list)
    status: str = "received"

    def add_trace(self, stage: str, stage_type: str, data: dict[str, Any]) -> None:
        import time
        self.hal_trace.append(TraceEntry(
            stage=stage,
            stage_type=stage_type,
            data=data,
            timestamp=time.time(),
        ))

    @property
    def has_full_cycle(self) -> bool:
        return (self.p4_decision is not None
                and self.execution_result is not None)

    @property
    def final_verdict(self) -> Optional[str]:
        return self.p4_decision.verdict if self.p4_decision else None

    @property
    def final_status(self) -> Optional[str]:
        return self.execution_result.status if self.execution_result else None
