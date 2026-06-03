import math
import time
from typing import Any, Dict, List, Optional

from .confidence_index import OperationalReadiness


class OperationalReadinessAnalyzer:
    def __init__(self, max_expected_depth: int = 100):
        self._max_depth = max_expected_depth
        self._snapshot_history: List[Dict[str, Any]] = []
        self._time_history: List[float] = []

    def analyze(self, queue_snapshot: Dict[str, Any]) -> OperationalReadiness:
        now = time.time()
        self._snapshot_history.append(queue_snapshot)
        self._time_history.append(now)
        if len(self._snapshot_history) > 10:
            self._snapshot_history.pop(0)
            self._time_history.pop(0)

        queue_health = self._compute_queue_health(queue_snapshot)
        processing_health = self._compute_processing_health(queue_snapshot)
        latency_health = self._compute_latency_health(queue_snapshot)
        backpressure = self._compute_backpressure(queue_snapshot)

        overall = 0.4 * queue_health + 0.3 * processing_health + 0.3 * latency_health

        return OperationalReadiness(
            queue_health=round(queue_health, 4),
            processing_health=round(processing_health, 4),
            latency_health=round(latency_health, 4),
            backpressure_ratio=round(backpressure, 4),
            overall=round(overall, 4),
        )

    def _compute_queue_health(self, snap: Dict[str, Any]) -> float:
        depth = snap.get("queue_depth", 0)
        return max(0.0, 1.0 - min(1.0, depth / max(1, self._max_depth)))

    def _compute_processing_health(self, snap: Dict[str, Any]) -> float:
        total = snap.get("total_events", 1)
        dlq = snap.get("dead_lettered", 0)
        dlq_ratio = dlq / max(1, total)
        failed = snap.get("failed", 0)
        fail_ratio = failed / max(1, total)
        return max(0.0, 1.0 - min(1.0, dlq_ratio + fail_ratio))

    def _compute_latency_health(self, snap: Dict[str, Any]) -> float:
        avg_ms = snap.get("average_cycle_ms", 0.0)
        last_ms = snap.get("last_cycle_ms", 0.0)
        if avg_ms <= 0:
            return 1.0
        cv = abs(last_ms - avg_ms) / avg_ms if avg_ms > 0 else 0.0
        return max(0.0, 1.0 - min(1.0, cv))

    def _compute_backpressure(self, snap: Dict[str, Any]) -> float:
        if len(self._snapshot_history) < 2:
            return 0.0

        prev = self._snapshot_history[-2]
        prev_total = prev.get("total_events", 0)
        cur_total = snap.get("total_events", 0)
        prev_processed = prev.get("processed", 0)
        cur_processed = snap.get("processed", 0)

        ingress = max(0, cur_total - prev_total)
        processed = max(0, cur_processed - prev_processed)

        if ingress <= 0:
            return 0.0

        return max(0.0, (ingress - processed) / ingress)
