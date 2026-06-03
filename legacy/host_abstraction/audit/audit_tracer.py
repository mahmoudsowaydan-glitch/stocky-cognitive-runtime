import uuid
from .audit_event import AuditEvent
from datetime import datetime
from typing import Dict, Any


class AuditTracer:

    def __init__(self):
        self.current_trace_id: str = ""

    def start_trace(self) -> str:
        self.current_trace_id = str(uuid.uuid4())
        return self.current_trace_id

    def attach(self, event_payload: Dict[str, Any]) -> Dict[str, Any]:
        return {
            **event_payload,
            "correlation_id": self.current_trace_id,
        }

    def create_event(
        self,
        layer: str,
        event_type: str,
        entity_id: str,
        payload: Dict[str, Any],
    ) -> AuditEvent:
        return AuditEvent(
            layer=layer,
            event_type=event_type,
            entity_id=entity_id,
            payload=self.attach(payload),
            timestamp=datetime.utcnow(),
            correlation_id=self.current_trace_id,
        )
