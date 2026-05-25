from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any


class RuntimeMetrics:
    def __init__(self):
        self._counters: dict[str, int] = defaultdict(int)
        self._gauges: dict[str, float] = {}
        self._histograms: dict[str, list[float]] = defaultdict(list)
        self._started_at: datetime = datetime.utcnow()

    def increment(self, metric: str, value: int = 1) -> None:
        self._counters[metric] += value

    def gauge(self, metric: str, value: float) -> None:
        self._gauges[metric] = value

    def observe(self, metric: str, value: float) -> None:
        self._histograms[metric].append(value)

    def get_counter(self, metric: str) -> int:
        return self._counters.get(metric, 0)

    def get_gauge(self, metric: str) -> float:
        return self._gauges.get(metric, 0.0)

    def get_histogram(self, metric: str) -> dict[str, float]:
        values = self._histograms.get(metric, [])
        if not values:
            return {"min": 0, "max": 0, "avg": 0, "count": 0}
        return {
            "min": min(values),
            "max": max(values),
            "avg": sum(values) / len(values),
            "count": len(values),
            "latest": values[-1],
        }

    def snapshot(self) -> dict[str, Any]:
        uptime = (datetime.utcnow() - self._started_at).total_seconds()
        return {
            "uptime_seconds": uptime,
            "counters": dict(self._counters),
            "gauges": dict(self._gauges),
            "histograms": {k: self.get_histogram(k) for k in self._histograms},
        }
