import pytest

from cognitive_runtime.runtime.runtime_state import RuntimeState


def test_default_values():
    s = RuntimeState()
    assert s.status == "stopped"
    assert s.health_status == "healthy"
    assert s.started_at is None
    assert s.uptime_seconds == 0.0
    assert s.queue_depth == 0
    assert s.total_events_processed == 0
    assert s.active_sessions == 0
    assert s.total_sessions == 0
    assert s.last_execution_trace_id == ""
    assert s.last_execution_status == ""
    assert s.last_execution_at is None
    assert s.consecutive_failures == 0
    assert s.total_failures == 0
    assert s.drift_detected is False
    assert s.drift_count == 0
    assert s.average_cycle_ms == 0.0
    assert s.last_cycle_ms == 0.0
    assert s.last_error is None
    assert s.errors == []


def test_record_cycle_increments_processed():
    s = RuntimeState()
    s.record_cycle(100.0, True, 5)
    assert s.total_events_processed == 1
    s.record_cycle(50.0, True, 3)
    assert s.total_events_processed == 2


def test_record_cycle_updates_last_and_queue():
    s = RuntimeState()
    s.record_cycle(100.0, True, 5)
    assert s.last_cycle_ms == 100.0
    assert s.queue_depth == 5


def test_average_cycle_ms_first_call():
    s = RuntimeState()
    s.record_cycle(200.0, True, 0)
    assert s.average_cycle_ms == 200.0


def test_average_cycle_ms_weighted():
    s = RuntimeState()
    s.record_cycle(100.0, True, 0)
    assert s.average_cycle_ms == 100.0
    s.record_cycle(200.0, True, 0)
    expected = 100.0 * 0.9 + 200.0 * 0.1
    assert s.average_cycle_ms == expected


def test_average_cycle_ms_stable():
    s = RuntimeState()
    for _ in range(5):
        s.record_cycle(100.0, True, 0)
    assert s.average_cycle_ms == 100.0


def test_consecutive_failures_increments():
    s = RuntimeState()
    s.record_cycle(100.0, False, 0)
    assert s.consecutive_failures == 1
    assert s.total_failures == 1


def test_health_degraded_after_3_failures():
    s = RuntimeState()
    for _ in range(3):
        s.record_cycle(100.0, False, 0)
    assert s.health_status == "degraded"


def test_health_critical_after_5_failures():
    s = RuntimeState()
    for _ in range(5):
        s.record_cycle(100.0, False, 0)
    assert s.health_status == "critical"


def test_health_degraded_after_4_failures():
    s = RuntimeState()
    for _ in range(4):
        s.record_cycle(100.0, False, 0)
    assert s.health_status == "degraded"


def test_success_resets_consecutive_failures():
    s = RuntimeState()
    for _ in range(3):
        s.record_cycle(100.0, False, 0)
    assert s.consecutive_failures == 3
    s.record_cycle(100.0, True, 0)
    assert s.consecutive_failures == 0
    assert s.health_status == "healthy"


def test_success_resets_health():
    s = RuntimeState()
    s.record_cycle(100.0, False, 0)
    s.record_cycle(100.0, False, 0)
    s.record_cycle(100.0, False, 0)
    assert s.health_status == "degraded"
    s.record_cycle(100.0, True, 0)
    assert s.health_status == "healthy"


def test_success_keeps_healthy():
    s = RuntimeState()
    s.record_cycle(100.0, True, 0)
    assert s.health_status == "healthy"


def test_total_failures_accumulates():
    s = RuntimeState()
    s.record_cycle(100.0, False, 0)
    s.record_cycle(100.0, True, 0)
    s.record_cycle(100.0, False, 0)
    assert s.total_failures == 2


def test_record_error():
    s = RuntimeState()
    s.record_error("error 1")
    assert len(s.errors) == 1
    assert s.errors[0] == "error 1"
    assert s.last_error == "error 1"


def test_record_error_caps_at_100():
    s = RuntimeState()
    for i in range(105):
        s.record_error(f"error {i}")
    assert len(s.errors) == 100
    assert s.errors[0] == "error 5"
    assert s.errors[-1] == "error 104"


def test_record_error_updates_last():
    s = RuntimeState()
    s.record_error("first")
    assert s.last_error == "first"
    s.record_error("second")
    assert s.last_error == "second"


def test_snapshot_returns_10_fields():
    s = RuntimeState()
    s.status = "running"
    s.uptime_seconds = 42.5
    s.queue_depth = 7
    s.total_events_processed = 100
    s.active_sessions = 3
    s.health_status = "healthy"
    s.consecutive_failures = 0
    s.drift_detected = True
    s.average_cycle_ms = 150.25
    s.last_error = "something bad"
    snap = s.snapshot()
    assert snap["status"] == "running"
    assert snap["uptime_seconds"] == 42.5
    assert snap["queue_depth"] == 7
    assert snap["total_events_processed"] == 100
    assert snap["active_sessions"] == 3
    assert snap["health_status"] == "healthy"
    assert snap["consecutive_failures"] == 0
    assert snap["drift_detected"] is True
    assert snap["average_cycle_ms"] == 150.25
    assert snap["last_error"] == "something bad"


def test_snapshot_rounds_average():
    s = RuntimeState()
    s.average_cycle_ms = 123.4567
    assert s.snapshot()["average_cycle_ms"] == 123.46


def test_snapshot_has_exactly_10_keys():
    s = RuntimeState()
    assert len(s.snapshot()) == 10
