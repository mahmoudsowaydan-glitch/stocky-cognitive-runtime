from cognitive_runtime.contracts.frozen.runtime_contract import RuntimeContract
from cognitive_runtime.contracts.frozen.schema_version import get_expected_fingerprint
from cognitive_runtime.runtime.runtime_state import RuntimeState


def test_runtime_state_fields_defined():
    fields = RuntimeContract.STATE_FIELDS
    for f in ("started_at", "uptime_seconds", "status",
               "queue_depth", "total_events_processed",
               "active_sessions", "total_sessions",
               "last_execution_trace_id", "last_execution_status", "last_execution_at",
               "consecutive_failures", "total_failures", "health_status",
               "drift_detected", "drift_count",
               "average_cycle_ms", "last_cycle_ms",
               "last_error", "errors"):
        assert f in fields


def test_runtime_state_methods_defined():
    for m in ("record_cycle", "record_error", "snapshot"):
        assert m in RuntimeContract.STATE_METHODS
    assert len(RuntimeContract.STATE_METHODS) == 3


def test_check_runtime_state_valid():
    assert RuntimeContract.check_runtime_state(RuntimeState()) == []


def test_check_runtime_state_missing_field():
    violations = RuntimeContract.check_runtime_state(object())
    assert any("missing field" in v for v in violations)


def test_check_runtime_state_missing_method():
    class PartialState:
        started_at = None; uptime_seconds = 0.0; status = "stopped"
        queue_depth = 0; total_events_processed = 0
        active_sessions = 0; total_sessions = 0
        last_execution_trace_id = ""; last_execution_status = ""; last_execution_at = None
        consecutive_failures = 0; total_failures = 0; health_status = "healthy"
        drift_detected = False; drift_count = 0
        average_cycle_ms = 0.0; last_cycle_ms = 0.0
        last_error = None; errors = []
    violations = RuntimeContract.check_runtime_state(PartialState())
    assert any("missing method" in v for v in violations)


def test_check_runtime_state_method_not_callable():
    class BadState:
        started_at = None; uptime_seconds = 0.0; status = "stopped"
        queue_depth = 0; total_events_processed = 0
        active_sessions = 0; total_sessions = 0
        last_execution_trace_id = ""; last_execution_status = ""; last_execution_at = None
        consecutive_failures = 0; total_failures = 0; health_status = "healthy"
        drift_detected = False; drift_count = 0
        average_cycle_ms = 0.0; last_cycle_ms = 0.0
        last_error = None; errors = []
        record_cycle = "not_callable"; record_error = "not_callable"; snapshot = "not_callable"
    violations = RuntimeContract.check_runtime_state(BadState())
    assert any("not callable" in v for v in violations)


def test_orchestrator_methods():
    for m in ("start", "stop", "pause", "resume", "tick_heartbeat"):
        assert m in RuntimeContract.ORCHESTRATOR_METHODS
    assert len(RuntimeContract.ORCHESTRATOR_METHODS) == 5


def test_orchestrator_properties():
    assert "is_running" in RuntimeContract.ORCHESTRATOR_PROPERTIES
    assert "state" in RuntimeContract.ORCHESTRATOR_PROPERTIES
    assert len(RuntimeContract.ORCHESTRATOR_PROPERTIES) == 2


def test_check_orchestrator_valid():
    class GoodOrch:
        is_running = True
        state = "running"
        def start(self): pass
        def stop(self): pass
        def pause(self): pass
        def resume(self): pass
        def tick_heartbeat(self): pass
    assert RuntimeContract.check_orchestrator(GoodOrch()) == []


def test_check_orchestrator_missing_method():
    violations = RuntimeContract.check_orchestrator(object())
    assert len(violations) == 7


def test_check_orchestrator_missing_property():
    class BadOrch:
        def start(self): pass
        def stop(self): pass
        def pause(self): pass
        def resume(self): pass
        def tick_heartbeat(self): pass
    violations = RuntimeContract.check_orchestrator(BadOrch())
    assert any("missing property" in v for v in violations)


def test_check_orchestrator_method_not_callable():
    class BadOrch:
        is_running = True
        state = "running"
        start = "nc"; stop = "nc"; pause = "nc"; resume = "nc"; tick_heartbeat = "nc"
    violations = RuntimeContract.check_orchestrator(BadOrch())
    assert any("not callable" in v for v in violations)


def test_heartbeat_fields():
    for f in ("timestamp", "status", "uptime", "queue_depth",
               "events_processed", "health_status",
               "average_cycle_ms", "drift_detected"):
        assert f in RuntimeContract.HEARTBEAT_FIELDS
    assert len(RuntimeContract.HEARTBEAT_FIELDS) == 8


def test_check_heartbeat_valid():
    class GoodHB:
        timestamp = 100.0; status = "running"; uptime = 500.0
        queue_depth = 0; events_processed = 100; health_status = "healthy"
        average_cycle_ms = 5.0; drift_detected = False
    assert RuntimeContract.check_heartbeat(GoodHB()) == []


def test_check_heartbeat_missing():
    assert len(RuntimeContract.check_heartbeat(object())) == 8


def test_periodic_schedule_6_tasks():
    assert len(RuntimeContract.PERIODIC_SCHEDULE) == 6


def test_periodic_schedule_has_all_tasks():
    sched = RuntimeContract.PERIODIC_SCHEDULE
    for task in ("causal_graph_rebuild", "intelligence_compression", "feedback_analysis",
                  "stability_index", "confidence_assessment", "governance_entropy"):
        assert task in sched


def test_periodic_schedule_cycle_values():
    sched = RuntimeContract.PERIODIC_SCHEDULE
    assert sched["causal_graph_rebuild"] == 10
    assert sched["intelligence_compression"] == 10
    assert sched["feedback_analysis"] == 20
    assert sched["stability_index"] == 50
    assert sched["confidence_assessment"] == 75
    assert sched["governance_entropy"] == 100


def test_check_periodic_schedule_returns_dict():
    class MockLoop:
        def _finalize_cycle(self): pass
    result = RuntimeContract.check_periodic_schedule(MockLoop())
    assert isinstance(result, dict)
    assert all(isinstance(v, bool) for v in result.values())


def test_check_periodic_schedule_no_method():
    result = RuntimeContract.check_periodic_schedule(object())
    assert all(v is False for v in result.values())


def test_lifecycle_invariants_9_items():
    assert len(RuntimeContract.LIFECYCLE_INVARIANTS) == 9


def test_lifecycle_invariants_content():
    inv = RuntimeContract.LIFECYCLE_INVARIANTS
    assert any("P4 is the single authority" in i for i in inv)
    assert any("HAL is strictly observational" in i for i in inv)
    assert any("P3 is context builder only" in i for i in inv)
    assert any("Sandbox is dumb executor" in i for i in inv)
    assert any("risk_score is observability-only" in i for i in inv)
    assert any("Intelligence layer is read-only compression" in i for i in inv)
    assert any("Stability layer is measurement-only" in i for i in inv)
    assert any("Confidence layer is observational" in i for i in inv)
    assert any("Governance layer is observational" in i for i in inv)


def test_verify_lifecycle_invariants_returns_all():
    violations = RuntimeContract.verify_lifecycle_invariants(object())
    assert len(violations) == 9
    assert all("Invariant not verifiable at runtime" in v for v in violations)


def test_cycle_guarantees_have_all_keys():
    g = RuntimeContract.CYCLE_GUARANTEES
    for key in ("ordering", "trace_appended_before_checks", "drift_detected_before_periodic",
                 "hal_observer_invoked_each_cycle", "exception_does_not_lose_trace"):
        assert key in g
    assert len(g) == 5


def test_runtime_contract_fingerprint_registered():
    fp = get_expected_fingerprint("RuntimeContract")
    assert fp is not None
    assert isinstance(fp, str)


def test_runtime_state_from_runtime_package_passes():
    state = RuntimeState()
    assert RuntimeContract.check_runtime_state(state) == []
