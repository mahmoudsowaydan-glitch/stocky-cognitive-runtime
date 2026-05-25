from typing import Any, Optional

from ..events.event_types import Event
from .memory_bridge import MemoryRecord


class AppendOnlyWriter:
    def __init__(self, store: list[MemoryRecord]):
        self._store = store

    def append(self, event: Event, result: Optional[dict[str, Any]] = None) -> MemoryRecord:
        import hashlib
        import uuid
        payload_str = str(event.payload)
        checksum = hashlib.sha256(payload_str.encode()).hexdigest()[:16]
        record = MemoryRecord(
            record_id=str(uuid.uuid4()),
            event_id=event.id,
            event_type=event.type,
            payload=event.payload.copy(),
            result=result.copy() if result else None,
            execution_id=event.trace_id,
            trace_id=event.trace_id,
            checksum=checksum,
        )
        self._store.append(record)
        return record

    def integrity_check(self) -> list[str]:
        violations = []
        for record in self._store:
            payload_str = str(record.payload)
            expected = hashlib.sha256(payload_str.encode()).hexdigest()[:16]
            if record.checksum != expected:
                violations.append(f"integrity violation: {record.record_id}")
        return violations
