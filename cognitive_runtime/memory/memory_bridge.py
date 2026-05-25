from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

from ..events.event_types import Event


@dataclass
class MemoryRecord:
    record_id: str
    event_id: str
    event_type: str
    payload: dict[str, Any]
    result: Optional[dict[str, Any]] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    execution_id: str = ""
    trace_id: str = ""
    checksum: str = ""


class MemoryBridge:
    def __init__(self):
        self._store: list[MemoryRecord] = []
        self._writer = MemoryWriter(self._store)
        self._reader = MemoryReader(self._store)
        self._lineage = LineageConnector()

    def write(self, event: Event, result: Optional[dict[str, Any]] = None) -> MemoryRecord:
        return self._writer.write(event, result)

    def read(self, record_id: str) -> Optional[MemoryRecord]:
        return self._reader.read(record_id)

    def query(self, event_type: str = "", limit: int = 100) -> list[MemoryRecord]:
        return self._reader.query(event_type=event_type, limit=limit)

    @property
    def total_records(self) -> int:
        return len(self._store)


class MemoryWriter:
    def __init__(self, store: list[MemoryRecord]):
        self._store = store

    def write(self, event: Event, result: Optional[dict[str, Any]] = None) -> MemoryRecord:
        import hashlib
        payload_str = str(event.payload)
        checksum = hashlib.sha256(payload_str.encode()).hexdigest()[:16]

        record = MemoryRecord(
            record_id=f"mem-{len(self._store) + 1}",
            event_id=event.id,
            event_type=event.type,
            payload=event.payload,
            result=result,
            execution_id=event.trace_id,
            trace_id=event.trace_id,
            checksum=checksum,
        )
        self._store.append(record)
        return record


class MemoryReader:
    def __init__(self, store: list[MemoryRecord]):
        self._store = store

    def read(self, record_id: str) -> Optional[MemoryRecord]:
        for record in self._store:
            if record.record_id == record_id:
                return record
        return None

    def query(self, event_type: str = "", limit: int = 100) -> list[MemoryRecord]:
        results = self._store
        if event_type:
            results = [r for r in results if r.event_type == event_type]
        return results[-limit:]


class LineageConnector:
    def __init__(self):
        self._lineage: dict[str, list[str]] = {}

    def connect(self, parent_event_id: str, child_event_id: str) -> None:
        if parent_event_id not in self._lineage:
            self._lineage[parent_event_id] = []
        self._lineage[parent_event_id].append(child_event_id)

    def get_children(self, event_id: str) -> list[str]:
        return self._lineage.get(event_id, [])

    def get_ancestors(self, event_id: str, all_records: list[MemoryRecord]) -> list[str]:
        ancestors = []
        parent_map = {}
        for record in all_records:
            for child_ids in self._lineage.values():
                if record.event_id in child_ids:
                    parent_map[child_ids] = record.event_id
        current = event_id
        while current in parent_map:
            parent = parent_map[current]
            ancestors.append(parent)
            current = parent
        return ancestors
