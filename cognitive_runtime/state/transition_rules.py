from typing import Any, Callable, Optional

from .runtime_state_machine import RuntimeState


GuardCheck = Callable[[RuntimeState, RuntimeState], tuple[bool, Optional[str]]]


class TransitionRule:
    def __init__(self, source: RuntimeState, target: RuntimeState,
                 condition: Optional[GuardCheck] = None,
                 description: str = ""):
        self.source = source
        self.target = target
        self.condition = condition
        self.description = description

    def evaluate(self, current: RuntimeState, target: RuntimeState) -> tuple[bool, Optional[str]]:
        if current != self.source or target != self.target:
            return True, None
        if self.condition:
            return self.condition(current, target)
        return True, None


class TransitionGuard:
    def __init__(self):
        self._pre_rules: list[TransitionRule] = []
        self._post_rules: list[TransitionRule] = []

    def add_pre_rule(self, rule: TransitionRule) -> None:
        self._pre_rules.append(rule)

    def add_post_rule(self, rule: TransitionRule) -> None:
        self._post_rules.append(rule)

    def check_pre(self, current: RuntimeState, target: RuntimeState) -> tuple[bool, Optional[str]]:
        for rule in self._pre_rules:
            ok, err = rule.evaluate(current, target)
            if not ok:
                return False, err
        return True, None

    def check_post(self, current: RuntimeState, target: RuntimeState) -> tuple[bool, Optional[str]]:
        for rule in self._post_rules:
            ok, err = rule.evaluate(current, target)
            if not ok:
                return False, err
        return True, None

    @staticmethod
    def no_pending_locks() -> GuardCheck:
        def check(current: RuntimeState, target: RuntimeState) -> tuple[bool, Optional[str]]:
            return True, None
        return check

    @staticmethod
    def execution_id_present(get_execution_id: Callable[[], str]) -> GuardCheck:
        def check(current: RuntimeState, target: RuntimeState) -> tuple[bool, Optional[str]]:
            if get_execution_id():
                return True, None
            return False, "no_execution_id"
        return check
