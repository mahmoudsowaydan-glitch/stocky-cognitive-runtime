import pytest

from cognitive_runtime.contracts.frozen.compatibility_guard import CompatibilityGuard
from cognitive_runtime.contracts.frozen.schema_version import (
    SchemaVersion,
    FROZEN_SCHEMA_VERSION,
)
from cognitive_runtime.contracts.execution_trace import (
    ExecutionTrace,
    ExecutionTraceNormalizer,
)
from cognitive_runtime.runtime.runtime_state import RuntimeState


class MockRuntimeLoop:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


def test_default_schema_version():
    guard = CompatibilityGuard()
    assert guard.schema_version == FROZEN_SCHEMA_VERSION


def test_custom_schema_version():
    v = SchemaVersion(2, 0, 0)
    guard = CompatibilityGuard(schema_version=v)
    assert guard.schema_version == v


def test_initial_violation_count():
    assert CompatibilityGuard().violation_count == 0


def test_initial_violations():
    assert CompatibilityGuard().violations == []


def test_clear_violations():
    guard = CompatibilityGuard()
    guard._record("test", "error", "msg")
    assert guard.violation_count == 1
    guard.clear()
    assert guard.violation_count == 0


def test_violations_returns_copy():
    guard = CompatibilityGuard()
    guard._record("test", "error", "msg")
    violations = guard.violations
    violations.clear()
    assert guard.violation_count == 1


def test_record_creates_entry():
    guard = CompatibilityGuard()
    guard._record("ComponentA", "warning", "Something is off")
    assert guard.violation_count == 1
    v = guard.violations[0]
    assert v["component"] == "ComponentA"
    assert v["severity"] == "warning"
    assert v["message"] == "Something is off"
    assert v["schema_version"] == str(FROZEN_SCHEMA_VERSION)


def test_record_calls_hal_observer():
    observed = []
    def hal(data):
        observed.append(data)
    guard = CompatibilityGuard(hal_observer=hal)
    guard._record("Test", "error", "msg")
    assert len(observed) == 1
    assert observed[0]["type"] == "contract.violation"


def test_check_graph_valid():
    from cognitive_runtime.contracts.causal_graph import CausalGraph, CausalNode, CausalEdge
    n1 = CausalNode("n1", "e1", "c1", "host_event", {}, 0.0)
    n2 = CausalNode("n2", "e1", "c1", "outcome", {}, 1.0, parent_id="n1", children=[])
    e1 = CausalEdge("e1", "n1", "n2", "proposes", {})
    graph = CausalGraph({"n1": n1, "n2": n2}, [e1])
    guard = CompatibilityGuard()
    assert guard.check_graph("test", graph) is True


def test_check_graph_invalid():
    guard = CompatibilityGuard()
    assert guard.check_graph("bad", object()) is False
    assert guard.violation_count > 0


def test_check_graph_contract_valid():
    from cognitive_runtime.contracts.causal_graph import CausalGraph, CausalNode, CausalEdge
    n1 = CausalNode("n1", "e1", "c1", "host_event", {}, 0.0)
    n2 = CausalNode("n2", "e1", "c1", "outcome", {}, 1.0, parent_id="n1", children=[])
    e1 = CausalEdge("e1", "n1", "n2", "proposes", {})
    graph = CausalGraph({"n1": n1, "n2": n2}, [e1])
    guard = CompatibilityGuard()
    ok, count = guard.check_graph_contract("test", graph)
    assert ok is True
    assert count == 0


def test_check_trace_valid():
    trace = ExecutionTrace(
        event_id="e1", session_id="s1", sequence_no=1, correlation_id="c1",
        preflight_valid=True, p4_verdict="ALLOW", execution_status="SUCCESS", final_status="P4_ALLOW",
    )
    guard = CompatibilityGuard()
    assert guard.check_trace(trace) is True


def test_check_trace_invalid():
    guard = CompatibilityGuard()
    assert guard.check_trace(object()) is False


def test_check_traces_all_valid():
    traces = [ExecutionTrace(event_id=f"e{i}", session_id="s1", sequence_no=i, correlation_id=f"c{i}",
                             preflight_valid=True, p4_verdict="ALLOW", execution_status="SUCCESS",
                             final_status="P4_ALLOW") for i in range(5)]
    guard = CompatibilityGuard()
    passed, failed = guard.check_traces(traces)
    assert passed == 5
    assert failed == 0


def test_check_traces_some_invalid():
    class BadTrace:
        pass
    guard = CompatibilityGuard()
    passed, failed = guard.check_traces([BadTrace(), BadTrace()])
    assert passed == 0
    assert failed == 2


def test_check_normalizer_valid():
    guard = CompatibilityGuard()
    assert guard.check_normalizer(ExecutionTraceNormalizer()) is True


def test_check_normalizer_invalid():
    guard = CompatibilityGuard()
    assert guard.check_normalizer(object()) is False


def test_check_observation_tap_valid():
    class GoodTap:
        total_traced = 0; completed_cycles = 0
        def tap_event_received(self): pass
        def tap_p3_proposal(self): pass
        def tap_p4_decision(self): pass
        def tap_execution_result(self): pass
        def tap_blocked(self): pass
        def get_enriched(self): pass
        def get_by_session(self): pass
        def get_by_status(self): pass
        def subscribe(self): pass
    guard = CompatibilityGuard()
    assert guard.check_observation_tap(GoodTap()) is True


def test_check_observation_tap_invalid():
    guard = CompatibilityGuard()
    assert guard.check_observation_tap(object()) is False


def test_check_feedback_bridge_valid():
    class GoodBridge:
        history = []
        def analyze(self): pass
    guard = CompatibilityGuard()
    assert guard.check_feedback_bridge(GoodBridge()) is True


def test_check_feedback_bridge_invalid():
    guard = CompatibilityGuard()
    assert guard.check_feedback_bridge(object()) is False


def test_check_enriched_event_valid():
    class GoodEvent:
        event_id = ""; session_id = ""; sequence_no = 0; correlation_id = ""
        host_event = None; p3_proposal = None; p4_decision = None
        execution_result = None; hal_trace = None; status = ""
        has_full_cycle = False; final_verdict = ""; final_status = ""
        def add_trace(self): pass
    guard = CompatibilityGuard()
    assert guard.check_enriched_event(GoodEvent()) is True


def test_check_enriched_event_invalid():
    guard = CompatibilityGuard()
    assert guard.check_enriched_event(object()) is False


def test_check_runtime_state_valid():
    guard = CompatibilityGuard()
    assert guard.check_runtime_state(RuntimeState()) is True


def test_check_runtime_state_invalid():
    guard = CompatibilityGuard()
    assert guard.check_runtime_state(object()) is False


def test_check_orchestrator_valid():
    class GoodOrch:
        is_running = True; state = "running"
        def start(self): pass
        def stop(self): pass
        def pause(self): pass
        def resume(self): pass
        def tick_heartbeat(self): pass
    guard = CompatibilityGuard()
    assert guard.check_orchestrator(GoodOrch()) is True


def test_check_orchestrator_invalid():
    guard = CompatibilityGuard()
    assert guard.check_orchestrator(object()) is False


def test_run_all_no_attributes():
    guard = CompatibilityGuard()
    result = guard.run_all(MockRuntimeLoop())
    assert result["passed"] is True
    assert result["violations_found"] == 0


def test_run_all_with_valid_graph():
    from cognitive_runtime.contracts.causal_graph import CausalGraph, CausalNode, CausalEdge
    n1 = CausalNode("n1", "e1", "c1", "host_event", {}, 0.0)
    n2 = CausalNode("n2", "e1", "c1", "outcome", {}, 1.0, parent_id="n1", children=[])
    e1 = CausalEdge("e1", "n1", "n2", "proposes", {})
    graph = CausalGraph({"n1": n1, "n2": n2}, [e1])
    guard = CompatibilityGuard()
    loop = MockRuntimeLoop(_causal_graph=graph, _trace_normalizer=ExecutionTraceNormalizer())
    result = guard.run_all(loop)
    assert result["schema_version"] == str(FROZEN_SCHEMA_VERSION)


def test_run_all_with_invalid_graph():
    guard = CompatibilityGuard()
    loop = MockRuntimeLoop(_causal_graph=object())
    result = guard.run_all(loop)
    assert result["violations_found"] > 0
    assert result["passed"] is False


def test_run_all_with_valid_traces():
    traces = [ExecutionTrace(event_id="e1", session_id="s1", sequence_no=1, correlation_id="c1",
                             preflight_valid=True, p4_verdict="ALLOW", execution_status="SUCCESS",
                             final_status="P4_ALLOW")]
    guard = CompatibilityGuard()
    loop = MockRuntimeLoop(_traces=traces)
    result = guard.run_all(loop)
    assert result["passed"] is True


def test_run_all_with_invalid_traces():
    guard = CompatibilityGuard()
    loop = MockRuntimeLoop(_traces=[object(), object()])
    result = guard.run_all(loop)
    assert result["violations_found"] > 0


def test_run_all_with_valid_tap_feedback_state_orchestrator():
    class GoodTap:
        total_traced = 0; completed_cycles = 0
        def tap_event_received(self): pass
        def tap_p3_proposal(self): pass
        def tap_p4_decision(self): pass
        def tap_execution_result(self): pass
        def tap_blocked(self): pass
        def get_enriched(self): pass
        def get_by_session(self): pass
        def get_by_status(self): pass
        def subscribe(self): pass
    class GoodBridge:
        history = []
        def analyze(self): pass
    class GoodOrch:
        is_running = True; state = "running"
        def start(self): pass
        def stop(self): pass
        def pause(self): pass
        def resume(self): pass
        def tick_heartbeat(self): pass
    guard = CompatibilityGuard()
    loop = MockRuntimeLoop(_tap=GoodTap(), _feedback=GoodBridge(),
                           _state=RuntimeState(), _orchestrator=GoodOrch())
    result = guard.run_all(loop)
    assert result["passed"] is True


def test_violations_includes_schema_version():
    guard = CompatibilityGuard(schema_version=SchemaVersion(1, 2, 3))
    guard.check_trace(object())
    assert guard.violations[0]["schema_version"] == "1.2.3"


def test_run_all_full_integration():
    from cognitive_runtime.contracts.causal_graph import CausalGraph, CausalNode, CausalEdge
    n1 = CausalNode("n1", "e1", "c1", "host_event", {}, 0.0)
    n2 = CausalNode("n2", "e1", "c1", "outcome", {}, 1.0, parent_id="n1", children=[])
    e1 = CausalEdge("e1", "n1", "n2", "proposes", {})
    graph = CausalGraph({"n1": n1, "n2": n2}, [e1])

    class GoodTap:
        total_traced = 0; completed_cycles = 0
        def tap_event_received(self): pass
        def tap_p3_proposal(self): pass
        def tap_p4_decision(self): pass
        def tap_execution_result(self): pass
        def tap_blocked(self): pass
        def get_enriched(self): pass
        def get_by_session(self): pass
        def get_by_status(self): pass
        def subscribe(self): pass
    class GoodBridge:
        history = []
        def analyze(self): pass
    class GoodOrch:
        is_running = True; state = "running"
        def start(self): pass
        def stop(self): pass
        def pause(self): pass
        def resume(self): pass
        def tick_heartbeat(self): pass

    traces = [ExecutionTrace(event_id="e1", session_id="s1", sequence_no=1, correlation_id="c1",
                             preflight_valid=True, p4_verdict="ALLOW", execution_status="SUCCESS",
                             final_status="P4_ALLOW")]
    guard = CompatibilityGuard()
    loop = MockRuntimeLoop(_causal_graph=graph, _trace_normalizer=ExecutionTraceNormalizer(),
                           _tap=GoodTap(), _feedback=GoodBridge(),
                           _state=RuntimeState(), _orchestrator=GoodOrch(), _traces=traces)
    result = guard.run_all(loop)
    assert result["passed"] is True


def test_run_all_none_components():
    guard = CompatibilityGuard()
    # When attributes are set to None, hasattr returns True but checks fail
    loop = MockRuntimeLoop(_causal_graph=object(), _trace_normalizer=object(),
                           _tap=object(), _feedback=object(), _state=object(),
                           _orchestrator=object(), _traces=[object()])
    result = guard.run_all(loop)
    assert result["violations_found"] > 0
    assert result["passed"] is False


def test_run_all_tracks_total_violations():
    guard = CompatibilityGuard()
    pre = guard.violation_count
    loop = MockRuntimeLoop(_causal_graph=object())
    result = guard.run_all(loop)
    assert result["total_violations"] == pre + result["violations_found"]


def test_multiple_run_all_accumulates():
    guard = CompatibilityGuard()
    guard.run_all(MockRuntimeLoop(_causal_graph=object()))
    first = guard.violation_count
    guard.run_all(MockRuntimeLoop(_causal_graph=object()))
    assert guard.violation_count > first
