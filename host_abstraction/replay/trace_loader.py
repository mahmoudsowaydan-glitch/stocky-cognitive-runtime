from typing import List, Any

from host_abstraction.audit.audit_store import AuditStore
from host_abstraction.audit.audit_event import AuditEvent


class TraceLoader:
    def __init__(self, audit_store: AuditStore):
        self.audit_store = audit_store

    def load(self, trace_id: str) -> List[AuditEvent]:
        if hasattr(self.audit_store, "query_by_trace"):
            return self.audit_store.query_by_trace(trace_id)

        if hasattr(self.audit_store, "get_trace"):
            return self.audit_store.get_trace(trace_id)

        raise RuntimeError("AuditStore does not support trace queries")
