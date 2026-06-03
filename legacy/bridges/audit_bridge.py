import sys
from datetime import datetime
from typing import Any, Optional

from ..substrate.observation_tap import ObservationTap, EnrichedEvent


class AuditBridge:
    def __init__(self, tap: ObservationTap):
        self._tap = tap
        self._hal_audit_logger = None
        self._tap.subscribe(self._on_enriched_event)

    def bind(self, hal_audit_logger: Any) -> None:
        """ربط AuditBridge مع HAL AuditLogger الموجود في host_abstraction"""
        self._hal_audit_logger = hal_audit_logger

    def _on_enriched_event(self, event: EnrichedEvent) -> None:
        if not self._hal_audit_logger:
            return

        from host_abstraction.audit.audit_event import AuditEvent
        layer = "p3" if event.final_verdict is None else (
            "p4" if event.final_status is None else "substrate"
        )
        event_type = f"cognitive.{event.status}"

        self._hal_audit_logger.log(AuditEvent(
            layer=layer,
            event_type=event_type,
            entity_id=event.event_id,
            payload={
                "event_id": event.event_id,
                "session_id": event.session_id,
                "sequence_no": event.sequence_no,
                "status": event.status,
                "host_event_type": event.host_event.source,
                "proposal_id": event.p3_proposal.proposal_id if event.p3_proposal else None,
                "decision_id": event.p4_decision.decision_id if event.p4_decision else None,
                "verdict": event.final_verdict,
                "execution_status": event.final_status,
                "hal_trace": [
                    {"stage": t.stage, "stage_type": t.stage_type, "data": t.data}
                    for t in event.hal_trace
                ],
            },
            timestamp=datetime.utcnow(),
            correlation_id=event.correlation_id,
        ))

    def get_completed_traces(self, min_trace_length: int = 3) -> list[EnrichedEvent]:
        """رجع الأحداث اللي أكملت دورة حياة كاملة"""
        return [e for e in self._tap._events.values()
                if len(e.hal_trace) >= min_trace_length]
