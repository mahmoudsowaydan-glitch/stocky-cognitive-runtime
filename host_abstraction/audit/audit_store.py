from typing import List
from .audit_event import AuditEvent


class AuditStore:

    def __init__(self):
        self.events: List[AuditEvent] = []

    def write(self, event: AuditEvent):
        self.events.append(event)

    def query_by_layer(self, layer: str):
        return [e for e in self.events if e.layer == layer]

    def query_by_trace(self, trace_id: str):
        return [e for e in self.events if e.correlation_id == trace_id]

    def query_by_entity(self, entity_id: str):
        return [e for e in self.events if e.entity_id == entity_id]
