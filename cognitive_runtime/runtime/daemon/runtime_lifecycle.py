from enum import Enum


class LifecycleState(Enum):
    STOPPED = "STOPPED"
    BOOTING = "BOOTING"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    RECOVERING = "RECOVERING"
    SHUTDOWN = "SHUTDOWN"


class LifecycleTransition:
    _TRANSITIONS = {
        LifecycleState.STOPPED: {LifecycleState.BOOTING},
        LifecycleState.BOOTING: {LifecycleState.RUNNING, LifecycleState.SHUTDOWN},
        LifecycleState.RUNNING: {LifecycleState.PAUSED, LifecycleState.RECOVERING, LifecycleState.SHUTDOWN},
        LifecycleState.PAUSED: {LifecycleState.RUNNING, LifecycleState.RECOVERING, LifecycleState.SHUTDOWN},
        LifecycleState.RECOVERING: {LifecycleState.RUNNING, LifecycleState.SHUTDOWN},
        LifecycleState.SHUTDOWN: set(),
    }

    @staticmethod
    def can_transition(from_: LifecycleState, to: LifecycleState) -> bool:
        return to in LifecycleTransition._TRANSITIONS.get(from_, set())

    @staticmethod
    def assert_transition(from_: LifecycleState, to: LifecycleState) -> None:
        if not LifecycleTransition.can_transition(from_, to):
            raise InvalidLifecycleTransition(from_, to)

    @staticmethod
    def valid_transitions(from_: LifecycleState) -> set:
        return LifecycleTransition._TRANSITIONS.get(from_, set()).copy()


class InvalidLifecycleTransition(Exception):
    def __init__(self, from_: LifecycleState, to: LifecycleState):
        super().__init__(f"Invalid lifecycle transition: {from_.value} -> {to.value}")
        self.from_state = from_
        self.to_state = to
