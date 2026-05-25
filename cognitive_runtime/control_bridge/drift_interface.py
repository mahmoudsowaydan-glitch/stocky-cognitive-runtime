from typing import Any

from ..events.event_types import Event


class DriftDetector:
    def __init__(self, alpha: float = 0.3, threshold: float = 0.8):
        self._alpha = alpha
        self._threshold = threshold
        self._baseline = 0.0
        self._current_drift = 0.0
        self._history: list[float] = []

    def evaluate(self, event: Event) -> tuple[bool, str]:
        event_risk = event.risk_score()
        error = abs(event_risk - self._baseline)
        self._current_drift = self._alpha * error + (1 - self._alpha) * self._current_drift
        self._history.append(self._current_drift)

        if self._current_drift > self._threshold:
            return False, f"drift {self._current_drift:.3f} exceeds threshold {self._threshold}"
        return True, ""

    def update_baseline(self, value: float) -> None:
        self._baseline = value

    @property
    def drift_score(self) -> float:
        return self._current_drift

    def reset(self) -> None:
        self._current_drift = 0.0
        self._history.clear()
