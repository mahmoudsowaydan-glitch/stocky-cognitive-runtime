from typing import Any

from ..events.event_types import Event


class StabilityMonitor:
    def __init__(self, min_stability: float = 0.6, window_size: int = 10):
        self._min_stability = min_stability
        self._window_size = window_size
        self._scores: list[float] = []
        self._current_score = 1.0
        self._anomaly_count = 0

    def evaluate(self, event: Event) -> tuple[bool, str]:
        event_risk = event.risk_score()
        step_stability = 1.0 - event_risk
        self._scores.append(step_stability)
        if len(self._scores) > self._window_size:
            self._scores.pop(0)
        self._current_score = sum(self._scores) / len(self._scores)

        if event_risk > 0.7:
            self._anomaly_count += 1

        if self._current_score < self._min_stability:
            return False, (f"stability {self._current_score:.3f} below "
                           f"minimum {self._min_stability}")
        return True, ""

    @property
    def stability_score(self) -> float:
        return self._current_score

    @property
    def anomalies_detected(self) -> int:
        return self._anomaly_count

    def reset(self) -> None:
        self._scores.clear()
        self._current_score = 1.0
        self._anomaly_count = 0
