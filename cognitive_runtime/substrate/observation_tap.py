import time
import uuid
from datetime import datetime
from typing import Any, Callable, Optional

from ..contracts.enriched_event import EnrichedEvent, TraceEntry
from ..contracts.execution_contract import (
    ExecutionProposal,
    ExecutionResult,
    HostEvent,
    PolicyDecision,
)
from ..contracts.execution_trace import (
    ExecutionTraceNormalizer,
    ExecutionTraceStore,
    enriched_to_trace_dict,
)
from ..kernel.time_kernel import TimeKernel


class ObservationTap:
    def __init__(self, time_kernel: TimeKernel,
                 on_event: Optional[Callable[[EnrichedEvent], None]] = None,
                 trace_store: Optional[ExecutionTraceStore] = None,
                 trace_normalizer: Optional[ExecutionTraceNormalizer] = None):
        self._time = time_kernel
        self._events: dict[str, EnrichedEvent] = {}
        self._callbacks: list[Callable[[EnrichedEvent], None]] = []
        if on_event:
            self._callbacks.append(on_event)
        self._trace_store = trace_store
        self._trace_normalizer = trace_normalizer or ExecutionTraceNormalizer()

    # ── Tap Points ──

    def tap_event_received(self, event: HostEvent) -> None:
        seq = self._time.sequence_of(event.event_id) or 0
        enriched = EnrichedEvent(
            event_id=event.event_id,
            session_id=event.session_id,
            sequence_no=seq,
            correlation_id=str(uuid.uuid4()),
            host_event=event,
            status="received",
        )
        enriched.add_trace("event_queue", "received", {
            "source": event.source, "timestamp": event.timestamp,
        })
        self._events[event.event_id] = enriched
        self._notify(enriched)

    def tap_p3_proposal(self, event_id: str, proposal: ExecutionProposal) -> None:
        enriched = self._events.get(event_id)
        if not enriched:
            return
        enriched.p3_proposal = proposal
        enriched.add_trace("p3_context", "proposal", {
            "proposal_id": proposal.proposal_id,
            "action": proposal.action,
            "confidence": proposal.confidence,
            "risk_score": proposal.risk_score,
        })
        self._notify(enriched)

    def tap_p4_decision(self, event_id: str, decision: PolicyDecision) -> None:
        enriched = self._events.get(event_id)
        if not enriched:
            return
        enriched.p4_decision = decision
        enriched.add_trace("p4_authority", "decision", {
            "decision_id": decision.decision_id,
            "verdict": decision.verdict,
            "reason": decision.reason,
            "risk_level": decision.risk_level,
        })
        self._notify(enriched)

    def tap_execution_result(self, event_id: str, result: ExecutionResult) -> None:
        enriched = self._events.get(event_id)
        if not enriched:
            return
        enriched.execution_result = result
        enriched.add_trace("execution_substrate", "result", {
            "execution_id": result.execution_id,
            "status": result.status,
            "error": result.error,
        })
        enriched.status = "completed" if result.status == "SUCCESS" else "failed"
        self._emit_trace(enriched)
        self._notify(enriched)

    def tap_blocked(self, event_id: str, reason: str) -> None:
        enriched = self._events.get(event_id)
        if not enriched:
            return
        enriched.status = "blocked"
        enriched.add_trace("p4_authority", "blocked", {
            "reason": reason,
        })
        self._emit_trace(enriched)
        self._notify(enriched)

    # ── Query ──

    def get_enriched(self, event_id: str) -> Optional[EnrichedEvent]:
        return self._events.get(event_id)

    def get_by_session(self, session_id: str) -> list[EnrichedEvent]:
        return [e for e in self._events.values() if e.session_id == session_id]

    def get_by_status(self, status: str) -> list[EnrichedEvent]:
        return [e for e in self._events.values() if e.status == status]

    @property
    def total_traced(self) -> int:
        return len(self._events)

    @property
    def completed_cycles(self) -> int:
        return sum(1 for e in self._events.values() if e.has_full_cycle)

    def subscribe(self, callback: Callable[[EnrichedEvent], None]) -> None:
        self._callbacks.append(callback)

    def _emit_trace(self, enriched: EnrichedEvent) -> None:
        if self._trace_store is None:
            return
        try:
            raw = enriched_to_trace_dict(enriched)
            trace = self._trace_normalizer.normalize(raw)
            self._trace_store.add(trace)
        except Exception:
            pass

    def _notify(self, event: EnrichedEvent) -> None:
        for cb in self._callbacks:
            try:
                cb(event)
            except Exception:
                pass
