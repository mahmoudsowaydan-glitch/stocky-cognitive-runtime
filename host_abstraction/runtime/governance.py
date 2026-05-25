from typing import Callable, Dict, List, Optional


class SystemLock:

    def __init__(self):
        self.locked = True
        self.allowed_changes = set()

    def enforce(self, context: Dict[str, object]) -> bool:
        if not self.locked:
            return True

        if context.get("policy_override_attempt", False):
            return False

        if context.get("direct_execution", False):
            return False

        return True

    def unlock_temporarily(self, reason: str):
        print(f"[SYSTEM LOCK] Temporary unlock: {reason}")
        self.locked = False

    def relock(self):
        print("[SYSTEM LOCK] Re-enabled")
        self.locked = True


class RuleRegistry:

    def __init__(self):
        self.rules: Dict[str, Callable[[Dict[str, object]], bool]] = {}

    def register(self, name: str, rule_fn: Callable[[Dict[str, object]], bool]):
        self.rules[name] = rule_fn

    def validate(self, context: Dict[str, object]) -> List[str]:
        violations = []
        for name, rule in self.rules.items():
            try:
                if not rule(context):
                    violations.append(name)
            except Exception:
                violations.append(name)
        return violations


def invariant_no_direct_execution(context: Dict[str, object]) -> bool:
    return not bool(context.get("direct_execution", False))


def invariant_p4_is_authority(context: Dict[str, object]) -> bool:
    return context.get("authority") == "P4"


def invariant_bridge_is_observer(context: Dict[str, object]) -> bool:
    return context.get("bridge_final") is False


def invariant_dispatch_after_gate(context: Dict[str, object]) -> bool:
    return context.get("gate_action") is not None
