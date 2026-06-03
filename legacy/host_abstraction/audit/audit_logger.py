from datetime import datetime
from .audit_event import AuditEvent
from .audit_store import AuditStore

from host_abstraction.governance import check_governance_invariants


class AuditLogger:

    def __init__(self, store: AuditStore, printer=None):
        self.store = store
        self.printer = printer

    def log(self, event: AuditEvent):
        self.store.write(event)
        self._audit_governance(event)

        message = f"[AUDIT] {event.layer} | {event.event_type} | {event.entity_id} | trace={event.correlation_id}"
        if self.printer:
            self.printer(message)
        else:
            print(message)

    def _audit_governance(self, event: AuditEvent):
        violations = check_governance_invariants(event)
        if not violations:
            return

        violation_payload = {
            "original_event_type": event.event_type,
            "original_layer": event.layer,
            "violations": [
                {
                    "invariant": v.invariant,
                    "reason": v.reason,
                    "layer": v.layer,
                    "entity_id": v.entity_id,
                    "event_type": v.event_type,
                }
                for v in violations
            ],
        }

        critical_event = AuditEvent(
            layer="audit",
            event_type="CRITICAL_GOVERNANCE_VIOLATION",
            entity_id=event.entity_id,
            payload=violation_payload,
            timestamp=datetime.utcnow(),
            correlation_id=event.correlation_id,
        )

        self.store.write(critical_event)
        alert_message = (
            f"[AUDIT][CRITICAL] Governance violation detected for {event.entity_id} "
            f"(trace={event.correlation_id}): {[v.invariant for v in violations]}"
        )
        if self.printer:
            self.printer(alert_message)
        else:
            print(alert_message)
