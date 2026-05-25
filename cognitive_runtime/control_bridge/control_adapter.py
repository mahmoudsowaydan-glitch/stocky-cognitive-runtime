from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Optional

from ..events.event_types import Event


class Verdict(Enum):
    ALLOW = auto()
    BLOCK = auto()
    SANDBOX = auto()
    DEFER = auto()


@dataclass
class ControlDecision:
    verdict: Verdict
    reason: str = ""
    constraints: dict[str, Any] = field(default_factory=dict)


class ControlAdapter:
    def __init__(self):
        self._budget = BudgetInterface()
        self._drift = DriftInterface()
        self._stability = StabilityInterface()

    def evaluate(self, event: Event) -> ControlDecision:
        budget_ok, budget_msg = self._budget.check(event)
        if not budget_ok:
            return ControlDecision(Verdict.BLOCK, reason=f"budget: {budget_msg}")

        drift_ok, drift_msg = self._drift.check(event)
        if not drift_ok:
            return ControlDecision(Verdict.BLOCK, reason=f"drift: {drift_msg}")

        stability_ok, stability_msg = self._stability.check(event)
        if not stability_ok:
            return ControlDecision(Verdict.BLOCK, reason=f"stability: {stability_msg}")

        return ControlDecision(Verdict.ALLOW)


class BudgetInterface:
    def __init__(self, max_operations: int = 100):
        self._max_operations = max_operations
        self._current_operations = 0

    def check(self, event: Event) -> tuple[bool, str]:
        if self._current_operations >= self._max_operations:
            return False, "budget exhausted"
        return True, ""

    def consume(self, amount: int = 1) -> None:
        self._current_operations += amount

    def reset(self) -> None:
        self._current_operations = 0


class DriftInterface:
    def __init__(self, threshold: float = 0.3):
        self._threshold = threshold
        self._drift_score = 0.0

    def check(self, event: Event) -> tuple[bool, str]:
        event_risk = event.risk_score()
        if event_risk > self._threshold:
            self._drift_score += event_risk * 0.1
        if self._drift_score > 0.8:
            return False, f"drift score {self._drift_score:.2f} exceeds threshold"
        return True, ""

    def update(self, score: float) -> None:
        self._drift_score = score


class StabilityInterface:
    def __init__(self, min_stability: float = 0.6):
        self._min_stability = min_stability
        self._stability_score = 1.0

    def check(self, event: Event) -> tuple[bool, str]:
        if self._stability_score < self._min_stability:
            return False, f"stability {self._stability_score:.2f} below minimum {self._min_stability}"
        return True, ""

    def update(self, score: float) -> None:
        self._stability_score = score
