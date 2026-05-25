from dataclasses import dataclass, field
from typing import Any, Optional

from ..events.event_types import Event


@dataclass
class DoctrineValidationResult:
    valid: bool
    violations: list[str] = field(default_factory=list)
    blocked: bool = False
    sandbox: bool = False


class DoctrineEngine:
    def __init__(self):
        self._law_interpreter = LawInterpreter()
        self._constraint_solver = ConstraintSolver()
        self._validation_rules = ValidationRules()

    def validate(self, event: Event) -> DoctrineValidationResult:
        violations = []
        law_result = self._law_interpreter.validate(event)
        if not law_result.valid:
            violations.extend(law_result.violations)

        constraint_result = self._constraint_solver.solve(event)
        if not constraint_result.valid:
            violations.extend(constraint_result.violations)

        rule_result = self._validation_rules.check(event)
        if not rule_result.valid:
            violations.extend(rule_result.violations)

        blocked = any("BLOCK" in v for v in violations)
        sandbox = any("SANDBOX" in v for v in violations) and not blocked

        return DoctrineValidationResult(
            valid=len(violations) == 0,
            violations=violations,
            blocked=blocked,
            sandbox=sandbox,
        )


@dataclass
class LawResult:
    valid: bool
    violations: list[str] = field(default_factory=list)


class LawInterpreter:
    def __init__(self):
        self._laws: list[Law] = []

    def register(self, law: "Law") -> None:
        self._laws.append(law)

    def validate(self, event: Event) -> LawResult:
        violations = []
        for law in self._laws:
            if not law.check(event):
                violations.append(f"violates law: {law.name}")
        return LawResult(valid=len(violations) == 0, violations=violations)


@dataclass
class Law:
    name: str
    description: str
    check_fn: Any

    def check(self, event: Event) -> bool:
        try:
            return self.check_fn(event)
        except Exception:
            return False


class ConstraintSolver:
    def solve(self, event: Event) -> LawResult:
        return LawResult(valid=True)


class ValidationRules:
    def check(self, event: Event) -> LawResult:
        return LawResult(valid=True)
