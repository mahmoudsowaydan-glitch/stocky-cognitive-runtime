from typing import Dict, Optional, Tuple

from .confidence_index import ExecutionConfidenceGradient


class GradientTransitionGuard:
    _THRESHOLDS: Dict[Tuple[str, str], int] = {
        ("HIGH", "MEDIUM"): 2,
        ("HIGH", "LOW"): 3,
        ("HIGH", "CRITICAL"): 1,
        ("MEDIUM", "HIGH"): 2,
        ("MEDIUM", "LOW"): 2,
        ("MEDIUM", "CRITICAL"): 1,
        ("LOW", "HIGH"): 2,
        ("LOW", "MEDIUM"): 2,
        ("LOW", "CRITICAL"): 1,
        ("CRITICAL", "LOW"): 1,
        ("CRITICAL", "MEDIUM"): 2,
        ("CRITICAL", "HIGH"): 3,
    }

    def __init__(self):
        self._current_gradient: Optional[ExecutionConfidenceGradient] = None
        self._pending: Dict[Tuple[str, str], int] = {}

    def resolve(self, raw_score: float) -> ExecutionConfidenceGradient:
        desired = self._classify(raw_score)

        if self._current_gradient is None:
            self._current_gradient = desired
            self._pending.clear()
            return desired

        if desired == self._current_gradient:
            self._pending.clear()
            return desired

        key = (self._current_gradient.value, desired.value)
        self._pending[key] = self._pending.get(key, 0) + 1

        threshold = self._THRESHOLDS.get(key, 2)
        if self._pending[key] >= threshold:
            self._current_gradient = desired
            self._pending.clear()
            return desired

        return self._current_gradient

    @property
    def current_gradient(self) -> Optional[ExecutionConfidenceGradient]:
        return self._current_gradient

    def _classify(self, score: float) -> ExecutionConfidenceGradient:
        if score >= 0.8:
            return ExecutionConfidenceGradient.HIGH
        elif score >= 0.5:
            return ExecutionConfidenceGradient.MEDIUM
        elif score >= 0.2:
            return ExecutionConfidenceGradient.LOW
        else:
            return ExecutionConfidenceGradient.CRITICAL
