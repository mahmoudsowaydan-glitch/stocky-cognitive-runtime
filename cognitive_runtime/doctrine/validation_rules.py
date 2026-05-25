from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from .doctrine_engine import LawResult


@dataclass
class ValidationRule:
    name: str
    description: str
    severity: str = "error"
    check_fn: Optional[Callable[[Any], bool]] = None

    def check(self, context: Any) -> bool:
        if self.check_fn:
            try:
                return self.check_fn(context)
            except Exception:
                return False
        return True


class ValidationRuleEngine:
    def __init__(self):
        self._rules: list[ValidationRule] = []

    def add(self, rule: ValidationRule) -> None:
        self._rules.append(rule)

    def check(self, context: Any) -> LawResult:
        violations = []
        for rule in self._rules:
            if not rule.check(context):
                label = f"BLOCK" if rule.severity == "error" else "WARN"
                violations.append(f"{label}: {rule.name} - {rule.description}")
        return LawResult(valid=len(violations) == 0, violations=violations)
