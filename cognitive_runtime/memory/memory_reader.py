from datetime import datetime, timedelta
from typing import Any, Optional

from .memory_bridge import MemoryRecord


class QueryReader:
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

    def query_by_time(self, since: datetime, until: Optional[datetime] = None) -> list[MemoryRecord]:
        until = until or datetime.utcnow()
        return [r for r in self._store if since <= r.timestamp <= until]

    def query_by_execution(self, execution_id: str) -> list[MemoryRecord]:
        return [r for r in self._store if r.execution_id == execution_id]

    def count(self) -> int:
        return len(self._store)
