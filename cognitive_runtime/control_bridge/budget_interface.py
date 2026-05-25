from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class BudgetState:
    total_allocated: int = 0
    total_consumed: int = 0
    remaining: int = 0
    elasticity_mode: str = "normal"
    operations: list[dict[str, Any]] = field(default_factory=list)


class BudgetManager:
    def __init__(self, default_budget: int = 100):
        self._default_budget = default_budget
        self._state = BudgetState(remaining=default_budget)

    def allocate(self, amount: int) -> bool:
        if amount <= self._state.remaining:
            self._state.total_allocated += amount
            self._state.remaining -= amount
            return True
        return False

    def consume(self, amount: int, operation: str = "") -> bool:
        if amount <= self._state.remaining:
            self._state.total_consumed += amount
            self._state.remaining -= amount
            self._state.operations.append({"operation": operation, "amount": amount})
            return True
        return False

    @property
    def utilization(self) -> float:
        if self._default_budget == 0:
            return 0.0
        return self._state.total_consumed / self._default_budget

    @property
    def is_exhausted(self) -> bool:
        return self._state.remaining <= 0

    def reset(self) -> None:
        self._state = BudgetState(remaining=self._default_budget)
