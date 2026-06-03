from .audit_store import AuditStore


class AuditQueryEngine:

    def __init__(self, store: AuditStore):
        self.store = store

    def get_decision_chain(self, trace_id: str):
        chain = self.store.query_by_trace(trace_id)
        return sorted(chain, key=lambda x: x.timestamp)

    def detect_anomalies(self):
        risks = []
        for event in self.store.events:
            if event.layer == "P4" and event.payload.get("risk", 0) > 0.9:
                risks.append(event)
        return risks

    def summary(self, trace_id: str):
        chain = self.get_decision_chain(trace_id)
        return {
            "trace_id": trace_id,
            "events": [
                {
                    "layer": event.layer,
                    "event_type": event.event_type,
                    "entity_id": event.entity_id,
                    "payload": event.payload,
                    "timestamp": event.timestamp.isoformat(),
                }
                for event in chain
            ],
        }
