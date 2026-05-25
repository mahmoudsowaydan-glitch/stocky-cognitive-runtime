from datetime import datetime
from typing import Any, Callable, Optional

from .runtime_state_machine import (
    FORBIDDEN_TRANSITIONS,
    STATE_TIMEOUTS,
    TRANSITION_MATRIX,
    RuntimeState,
    StateData,
    StateTransitionRecord,
)


StateHook = Callable[[RuntimeState, RuntimeState, str], None]


class StateContext:
    def __init__(self):
        self._data = StateData()
        self._on_enter_hooks: dict[RuntimeState, list[StateHook]] = {}
        self._on_exit_hooks: dict[RuntimeState, list[StateHook]] = {}
        self._on_error_hooks: list[Callable[[RuntimeState, RuntimeState, str, Exception], None]] = []

    @property
    def current(self) -> RuntimeState:
        return self._data.current

    @property
    def previous(self) -> Optional[RuntimeState]:
        return self._data.previous

    @property
    def transitions(self) -> list[StateTransitionRecord]:
        return list(self._data.transitions)

    @property
    def execution_id(self) -> str:
        return self._data.execution_id

    @property
    def time_in_current_state(self) -> float:
        if self._data.entry_time is None:
            return 0.0
        return (datetime.utcnow() - self._data.entry_time).total_seconds()

    def can_transition_to(self, target: RuntimeState) -> bool:
        allowed = TRANSITION_MATRIX.get(self._data.current, set())
        return target in allowed

    def transition(self, target: RuntimeState, trigger: str = "") -> tuple[bool, Optional[str]]:
        source = self._data.current

        if target == source:
            return True, None

        if not self.can_transition_to(target):
            forbidden = FORBIDDEN_TRANSITIONS.get(source, set())
            if target in forbidden:
                return False, f"forbidden_transition: {source.name} -> {target.name}"
            return False, f"disallowed_transition: {source.name} -> {target.name}"

        timeout = STATE_TIMEOUTS.get(source, float("inf"))
        if self.time_in_current_state > timeout:
            return False, f"state_timeout: {source.name} exceeded {timeout}s"

        now = datetime.utcnow()
        duration_ms = 0.0
        if self._data.entry_time:
            duration_ms = (now - self._data.entry_time).total_seconds() * 1000

        self._run_exit_hooks(source, target, trigger)

        self._data.previous = source
        old_state = self._data.current
        self._data.current = target
        self._data.entry_time = now
        self._data.updated_at = now

        record = StateTransitionRecord(
            from_state=old_state,
            to_state=target,
            timestamp=now,
            trigger=trigger,
            duration_ms=duration_ms,
        )
        self._data.transitions.append(record)

        self._run_enter_hooks(target, source, trigger)

        return True, None

    def on_enter(self, state: RuntimeState, hook: StateHook) -> None:
        self._on_enter_hooks.setdefault(state, []).append(hook)

    def on_exit(self, state: RuntimeState, hook: StateHook) -> None:
        self._on_exit_hooks.setdefault(state, []).append(hook)

    def on_error(self, hook: Callable) -> None:
        self._on_error_hooks.append(hook)

    def set_execution_id(self, execution_id: str) -> None:
        self._data.execution_id = execution_id

    def set_error(self, error: dict[str, Any]) -> None:
        self._data.error = error

    def _run_enter_hooks(self, state: RuntimeState, from_state: RuntimeState, trigger: str) -> None:
        for hook in self._on_enter_hooks.get(state, []):
            try:
                hook(state, from_state, trigger)
            except Exception:
                pass

    def _run_exit_hooks(self, state: RuntimeState, to_state: RuntimeState, trigger: str) -> None:
        for hook in self._on_exit_hooks.get(state, []):
            try:
                hook(state, to_state, trigger)
            except Exception:
                pass

    def __repr__(self) -> str:
        return f"StateContext({self._data.current.name})"
