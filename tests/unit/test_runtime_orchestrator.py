import time
from unittest.mock import Mock

import pytest

from cognitive_runtime.runtime.runtime_state import RuntimeState
from cognitive_runtime.runtime.runtime_orchestrator import RuntimeOrchestrator, Heartbeat


@pytest.fixture
def state():
    return RuntimeState()


@pytest.fixture
def orch(state):
    return RuntimeOrchestrator(state)


def test_creation(state):
    orch = RuntimeOrchestrator(state)
    assert orch._state is state
    assert orch._running is False
    assert orch._on_start is None
    assert orch._on_stop is None
    assert orch._on_heartbeat is None


def test_creation_with_callbacks(state):
    on_start = Mock()
    on_stop = Mock()
    on_hb = Mock()
    orch = RuntimeOrchestrator(state, on_start=on_start, on_stop=on_stop, on_heartbeat=on_hb)
    assert orch._on_start is on_start
    assert orch._on_stop is on_stop
    assert orch._on_heartbeat is on_hb


def test_start(orch):
    assert orch.is_running is False
    orch.start()
    assert orch.is_running is True
    assert orch._state.status == "running"
    assert orch._state.started_at is not None


def test_start_idempotent(orch):
    orch.start()
    started_at = orch._state.started_at
    orch.start()
    assert orch._state.started_at == started_at


def test_start_calls_on_start(state):
    on_start = Mock()
    orch = RuntimeOrchestrator(state, on_start=on_start)
    orch.start()
    on_start.assert_called_once()


def test_stop(orch):
    orch.start()
    orch.stop()
    assert orch.is_running is False
    assert orch._state.status == "stopped"


def test_stop_idempotent(orch):
    orch.stop()
    assert orch.is_running is False


def test_stop_calls_on_stop(state):
    on_stop = Mock()
    orch = RuntimeOrchestrator(state, on_stop=on_stop)
    orch.start()
    orch.stop()
    on_stop.assert_called_once()


def test_stop_no_callback_when_not_started(state):
    on_stop = Mock()
    orch = RuntimeOrchestrator(state, on_stop=on_stop)
    orch.stop()
    on_stop.assert_not_called()


def test_pause(orch):
    orch.start()
    orch.pause()
    assert orch._state.status == "paused"


def test_pause_when_stopped(orch):
    orch.pause()
    assert orch._state.status == "stopped"


def test_resume(orch):
    orch.start()
    orch.pause()
    orch.resume()
    assert orch._state.status == "running"


def test_resume_when_not_paused(orch):
    orch.resume()
    assert orch._state.status == "stopped"


def test_tick_heartbeat(orch):
    orch.start()
    hb = orch.tick_heartbeat()
    assert isinstance(hb, Heartbeat)
    assert hb.status == "running"
    assert hb.uptime >= 0
    assert hb.queue_depth == 0
    assert hb.events_processed == 0
    assert hb.health_status == "healthy"
    assert hb.average_cycle_ms == 0.0
    assert hb.drift_detected is False


def test_tick_heartbeat_updates_uptime(orch):
    orch.start()
    time.sleep(0.01)
    orch.tick_heartbeat()
    assert orch._state.uptime_seconds > 0


def test_tick_heartbeat_reflects_state(state, orch):
    state.queue_depth = 5
    state.total_events_processed = 10
    state.average_cycle_ms = 42.0
    state.drift_detected = True
    orch.start()
    hb = orch.tick_heartbeat()
    assert hb.queue_depth == 5
    assert hb.events_processed == 10
    assert hb.average_cycle_ms == 42.0
    assert hb.drift_detected is True


def test_tick_heartbeat_calls_callback(state):
    on_hb = Mock()
    orch = RuntimeOrchestrator(state, on_heartbeat=on_hb)
    orch.start()
    hb = orch.tick_heartbeat()
    on_hb.assert_called_once_with(hb)


def test_tick_heartbeat_no_callback(orch):
    orch.start()
    assert orch.tick_heartbeat() is not None


def test_state_property(state, orch):
    assert orch.state is state


def test_state_mutable(state, orch):
    orch.state.status = "paused"
    assert state.status == "paused"
