import time
import uuid
from collections import OrderedDict
from typing import Dict, List, Optional, Tuple

from ...contracts.execution_contract import Capability, HostEvent
from ...contracts.public.agent_api import AgentAPI
from ...contracts.public.dtos import (
    AgentProfileDTO,
    DaemonStatusDTO,
    EventStatusDTO,
    HealthDTO,
    PaginatedTracesDTO,
    PublicTraceDTO,
    ReceiptDTO,
    RegisterAgentDTO,
    SubmitEventDTO,
)
from ...contracts.public.execution_api import ExecutionAPI
from ...contracts.public.observation_api import ObservationAPI
from ...contracts.public.runtime_api import RuntimeAPI
from ..daemon.runtime_daemon import RuntimeDaemon


def trace_to_public(trace) -> PublicTraceDTO:
    v = getattr(trace, "p4_verdict", "UNKNOWN")
    es = getattr(trace, "execution_status", "UNKNOWN")

    if v == "ALLOW" and es == "SUCCESS":
        status = "ALLOW"
    elif v in ("BLOCK", "NACK"):
        status = "BLOCK"
    elif es == "FAILED":
        status = "FAILED"
    else:
        status = "UNKNOWN"

    return PublicTraceDTO(
        event_id=getattr(trace, "event_id", ""),
        session_id=getattr(trace, "session_id", ""),
        status=status,
        risk_score=getattr(trace, "risk_score", 0.0),
        total_time_ms=getattr(trace, "total_time", 0.0) * 1000,
        error=getattr(trace, "execution_error", None) or getattr(trace, "p4_reason", None),
        created_at=getattr(trace, "total_time", 0.0),
    )


class LocalRuntimeGateway(RuntimeAPI, ExecutionAPI, ObservationAPI, AgentAPI):
    MAX_PENDING = 1000

    def __init__(self, daemon: RuntimeDaemon):
        self._daemon = daemon
        self._loop = daemon.loop
        self._pending: OrderedDict[str, Tuple[str, float]] = OrderedDict()
        self._agents: Dict[str, AgentProfileDTO] = {}

    # ── RuntimeAPI ──

    def get_daemon_status(self) -> DaemonStatusDTO:
        s = self._daemon.status
        return DaemonStatusDTO(
            lifecycle=s.lifecycle_state.value,
            uptime_seconds=s.uptime_seconds,
            cycle_count=s.cycle_count,
            health=s.health_status,
            panic_count=s.panic_count,
        )

    def get_health(self) -> HealthDTO:
        s = self._daemon.status
        return HealthDTO(
            status=s.health_status,
            cycle_count=s.cycle_count,
            uptime_seconds=s.uptime_seconds,
            panic_count=s.panic_count,
            recovery_count=s.recovery_count,
        )

    def get_version(self) -> str:
        return "0.1.0"

    # ── ExecutionAPI ──

    def submit_event(self, dto: SubmitEventDTO) -> ReceiptDTO:
        receipt_id = str(uuid.uuid4())
        event_id = str(uuid.uuid4())
        correlation_id = dto.correlation_id or receipt_id

        event = HostEvent(
            event_id=event_id,
            session_id=dto.session_id,
            timestamp=time.time(),
            source=dto.source,
            payload=dto.payload,
        )

        self._loop._queue.push(event)
        self._pending[receipt_id] = (event_id, time.time())
        if len(self._pending) > self.MAX_PENDING:
            self._pending.popitem(last=False)

        return ReceiptDTO(
            receipt_id=receipt_id,
            event_id=event_id,
            correlation_id=correlation_id,
            submitted_at=time.time(),
        )

    def get_status(self, receipt_id: str) -> Optional[EventStatusDTO]:
        pending = self._pending.get(receipt_id)
        if pending is None:
            return None
        event_id, _ = pending
        trace = self._find_trace(event_id)
        if trace is None:
            return EventStatusDTO(event_id=event_id, status="pending", receipt_id=receipt_id)
        self._pending.pop(receipt_id, None)
        return EventStatusDTO(
            event_id=event_id,
            status="completed" if trace.status != "UNKNOWN" else "failed",
            receipt_id=receipt_id,
        )

    def get_result(self, receipt_id: str) -> Optional[PublicTraceDTO]:
        pending = self._pending.get(receipt_id)
        if pending is None:
            return None
        event_id, _ = pending
        trace = self._find_trace(event_id)
        if trace is None:
            return None
        self._pending.pop(receipt_id, None)
        return trace

    def await_result(self, receipt_id: str, timeout: Optional[float] = None) -> Optional[PublicTraceDTO]:
        deadline = (time.time() + timeout) if timeout else None
        while True:
            result = self.get_result(receipt_id)
            if result is not None:
                return result
            if deadline and time.time() > deadline:
                return None
            time.sleep(0.1)

    def get_capabilities(self) -> List[str]:
        return [c.value for c in Capability]

    # ── ObservationAPI ──

    def get_trace_by_id(self, event_id: str) -> Optional[PublicTraceDTO]:
        return self._find_trace(event_id)

    def list_traces(self, session_id: str, limit: int = 50, cursor: Optional[str] = None) -> PaginatedTracesDTO:
        traces = list(self._loop._traces)
        if cursor:
            try:
                idx = int(cursor)
                traces = traces[idx:]
            except (ValueError, IndexError):
                pass
        filtered = [t for t in traces if t.session_id == session_id or not session_id]
        page = filtered[:limit]
        next_cursor = str(limit) if len(filtered) > limit else None
        return PaginatedTracesDTO(
            traces=[trace_to_public(t) for t in page],
            next_cursor=next_cursor,
            total=len(filtered),
        )

    # ── AgentAPI ──

    def register_agent(self, dto: RegisterAgentDTO) -> AgentProfileDTO:
        profile = AgentProfileDTO(
            agent_id=dto.agent_id,
            name=dto.name,
            capabilities=dto.capabilities,
            active=True,
            registered_at=time.time(),
        )
        self._agents[dto.agent_id] = profile
        return profile

    def get_agent(self, agent_id: str) -> Optional[AgentProfileDTO]:
        return self._agents.get(agent_id)

    def list_agents(self) -> List[AgentProfileDTO]:
        return list(self._agents.values())

    def deactivate_agent(self, agent_id: str) -> bool:
        profile = self._agents.get(agent_id)
        if profile is None:
            return False
        self._agents[agent_id] = AgentProfileDTO(
            agent_id=profile.agent_id,
            name=profile.name,
            capabilities=profile.capabilities,
            active=False,
            registered_at=profile.registered_at,
        )
        return True

    # ── Internal ──

    def _find_trace(self, event_id: str) -> Optional[PublicTraceDTO]:
        for t in self._loop._traces:
            if t.event_id == event_id:
                return trace_to_public(t)
        return None

    @property
    def daemon(self) -> RuntimeDaemon:
        return self._daemon
