from collections import defaultdict
from datetime import datetime
from typing import Any, Optional


class TraceCollector:
    def __init__(self):
        self._traces: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self._spans: dict[str, dict[str, Any]] = {}

    def start_span(self, span_id: str, operation: str,
                   parent_span_id: Optional[str] = None) -> None:
        self._spans[span_id] = {
            "span_id": span_id,
            "operation": operation,
            "parent_span_id": parent_span_id,
            "started_at": datetime.utcnow().isoformat(),
            "completed_at": None,
            "duration_ms": None,
        }

    def end_span(self, span_id: str, metadata: dict[str, Any] | None = None) -> None:
        span = self._spans.get(span_id)
        if span:
            now = datetime.utcnow()
            start = datetime.fromisoformat(span["started_at"])
            span["completed_at"] = now.isoformat()
            span["duration_ms"] = (now - start).total_seconds() * 1000
            if metadata:
                span["metadata"] = metadata

    def collect(self, trace_id: str, event: dict[str, Any]) -> None:
        self._traces[trace_id].append({
            **event,
            "collected_at": datetime.utcnow().isoformat(),
        })

    def get_trace(self, trace_id: str) -> list[dict[str, Any]]:
        return list(self._traces.get(trace_id, []))

    def get_spans(self) -> list[dict[str, Any]]:
        return list(self._spans.values())

    def export(self) -> dict[str, Any]:
        return {
            "traces": dict(self._traces),
            "spans": list(self._spans.values()),
        }
