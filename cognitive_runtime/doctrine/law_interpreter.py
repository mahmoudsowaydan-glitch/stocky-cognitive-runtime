from typing import Any, Callable, Optional

from .doctrine_engine import Law, LawResult


class LawInterpreterEngine:
    def __init__(self):
        self._laws: dict[str, Law] = {}

    def define_law(self, name: str, description: str,
                   check_fn: Callable[[Any], bool]) -> Law:
        law = Law(name=name, description=description, check_fn=check_fn)
        self._laws[name] = law
        return law

    def validate(self, event: Any) -> LawResult:
        violations = []
        for law in self._laws.values():
            try:
                if not law.check(event):
                    violations.append(f"BLOCK: {law.name} - {law.description}")
            except Exception as e:
                violations.append(f"BLOCK: {law.name} - evaluation error: {e}")
        return LawResult(valid=len(violations) == 0, violations=violations)

    def get_law(self, name: str) -> Optional[Law]:
        return self._laws.get(name)
