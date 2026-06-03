import pytest

from cognitive_runtime.runtime.daemon.runtime_lifecycle import (
    LifecycleState,
    LifecycleTransition,
    InvalidLifecycleTransition,
)


class TestLifecycleState:
    def test_stopped_to_booting(self):
        assert LifecycleTransition.can_transition(LifecycleState.STOPPED, LifecycleState.BOOTING)

    def test_booting_to_running(self):
        assert LifecycleTransition.can_transition(LifecycleState.BOOTING, LifecycleState.RUNNING)

    def test_booting_to_shutdown(self):
        assert LifecycleTransition.can_transition(LifecycleState.BOOTING, LifecycleState.SHUTDOWN)

    def test_running_to_paused(self):
        assert LifecycleTransition.can_transition(LifecycleState.RUNNING, LifecycleState.PAUSED)

    def test_running_to_recovering(self):
        assert LifecycleTransition.can_transition(LifecycleState.RUNNING, LifecycleState.RECOVERING)

    def test_running_to_shutdown(self):
        assert LifecycleTransition.can_transition(LifecycleState.RUNNING, LifecycleState.SHUTDOWN)

    def test_paused_to_running(self):
        assert LifecycleTransition.can_transition(LifecycleState.PAUSED, LifecycleState.RUNNING)

    def test_paused_to_recovering(self):
        assert LifecycleTransition.can_transition(LifecycleState.PAUSED, LifecycleState.RECOVERING)

    def test_paused_to_shutdown(self):
        assert LifecycleTransition.can_transition(LifecycleState.PAUSED, LifecycleState.SHUTDOWN)

    def test_recovering_to_running(self):
        assert LifecycleTransition.can_transition(LifecycleState.RECOVERING, LifecycleState.RUNNING)

    def test_recovering_to_shutdown(self):
        assert LifecycleTransition.can_transition(LifecycleState.RECOVERING, LifecycleState.SHUTDOWN)

    def test_shutdown_is_terminal(self):
        assert LifecycleTransition.can_transition(LifecycleState.SHUTDOWN, LifecycleState.STOPPED) is False
        assert LifecycleTransition.can_transition(LifecycleState.SHUTDOWN, LifecycleState.BOOTING) is False
        assert LifecycleTransition.can_transition(LifecycleState.SHUTDOWN, LifecycleState.RUNNING) is False
        assert LifecycleTransition.can_transition(LifecycleState.SHUTDOWN, LifecycleState.PAUSED) is False
        assert LifecycleTransition.can_transition(LifecycleState.SHUTDOWN, LifecycleState.RECOVERING) is False
        assert LifecycleTransition.can_transition(LifecycleState.SHUTDOWN, LifecycleState.SHUTDOWN) is False


class TestInvalidTransitions:
    INVALID_PAIRS = [
        (LifecycleState.STOPPED, LifecycleState.RUNNING),
        (LifecycleState.STOPPED, LifecycleState.PAUSED),
        (LifecycleState.STOPPED, LifecycleState.RECOVERING),
        (LifecycleState.STOPPED, LifecycleState.SHUTDOWN),
        (LifecycleState.BOOTING, LifecycleState.STOPPED),
        (LifecycleState.BOOTING, LifecycleState.PAUSED),
        (LifecycleState.BOOTING, LifecycleState.RECOVERING),
        (LifecycleState.RUNNING, LifecycleState.STOPPED),
        (LifecycleState.RUNNING, LifecycleState.BOOTING),
        (LifecycleState.PAUSED, LifecycleState.STOPPED),
        (LifecycleState.PAUSED, LifecycleState.BOOTING),
        (LifecycleState.RECOVERING, LifecycleState.STOPPED),
        (LifecycleState.RECOVERING, LifecycleState.BOOTING),
        (LifecycleState.RECOVERING, LifecycleState.PAUSED),
    ]

    @pytest.mark.parametrize("from_state,to_state", INVALID_PAIRS)
    def test_invalid_transitions_are_rejected(self, from_state, to_state):
        assert LifecycleTransition.can_transition(from_state, to_state) is False

    @pytest.mark.parametrize("from_state,to_state", INVALID_PAIRS)
    def test_assert_transition_raises(self, from_state, to_state):
        with pytest.raises(InvalidLifecycleTransition) as exc:
            LifecycleTransition.assert_transition(from_state, to_state)
        assert from_state.value in str(exc.value)
        assert to_state.value in str(exc.value)


class TestValidTransitions:
    VALID_PAIRS = [
        (LifecycleState.STOPPED, LifecycleState.BOOTING),
        (LifecycleState.BOOTING, LifecycleState.RUNNING),
        (LifecycleState.BOOTING, LifecycleState.SHUTDOWN),
        (LifecycleState.RUNNING, LifecycleState.PAUSED),
        (LifecycleState.RUNNING, LifecycleState.RECOVERING),
        (LifecycleState.RUNNING, LifecycleState.SHUTDOWN),
        (LifecycleState.PAUSED, LifecycleState.RUNNING),
        (LifecycleState.PAUSED, LifecycleState.RECOVERING),
        (LifecycleState.PAUSED, LifecycleState.SHUTDOWN),
        (LifecycleState.RECOVERING, LifecycleState.RUNNING),
        (LifecycleState.RECOVERING, LifecycleState.SHUTDOWN),
    ]

    @pytest.mark.parametrize("from_state,to_state", VALID_PAIRS)
    def test_valid_transitions_accepted(self, from_state, to_state):
        assert LifecycleTransition.can_transition(from_state, to_state) is True

    @pytest.mark.parametrize("from_state,to_state", VALID_PAIRS)
    def test_assert_transition_passes(self, from_state, to_state):
        LifecycleTransition.assert_transition(from_state, to_state)


class TestInvalidLifecycleTransition:
    def test_exception_message(self):
        exc = InvalidLifecycleTransition(LifecycleState.RUNNING, LifecycleState.STOPPED)
        assert "RUNNING" in str(exc)
        assert "STOPPED" in str(exc)

    def test_exception_attributes(self):
        exc = InvalidLifecycleTransition(LifecycleState.PAUSED, LifecycleState.BOOTING)
        assert exc.from_state == LifecycleState.PAUSED
        assert exc.to_state == LifecycleState.BOOTING
