from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from .doctrine_engine import LawResult


@dataclass
class Constraint:
    name: str
    description: str
    priority: int = 0
    check_fn: Optional[Callable[[Any], bool]] = None

    def check(self, context: Any) -> bool:
        if self.check_fn:
            try:
                return self.check_fn(context)
            except Exception:
                return False
        return True


class ConstraintSolverEngine:
    def __init__(self):
        self._constraints: list[Constraint] = []

    def add(self, constraint: Constraint) -> None:
        self._constraints.append(constraint)

    def solve(self, context: Any) -> LawResult:
        violations = []
        sorted_constraints = sorted(self._constraints, key=lambda c: c.priority, reverse=True)
        for constraint in sorted_constraints:
            if not constraint.check(context):
                violations.append(f"constraint_violation: {constraint.name}")
        return LawResult(valid=len(violations) == 0, violations=violations)
