import pytest
from cognitive_runtime.substrate.observation_tap import ObservationTap
from cognitive_runtime.contracts.enriched_event import EnrichedEvent
from cognitive_runtime.contracts.execution_contract import (
    Capability,
    HostEvent,
    ExecutionProposal,
    ExecutionResult,
    PolicyDecision,
)
from cognitive_runtime.contracts.execution_trace import (
    ExecutionTraceStore,
    ExecutionTraceNormalizer,
)
from cognitive_runtime.kernel.time_kernel import TimeKernel


@pytest.fixture
def time_kernel():
    tk = TimeKernel(session_id="s1")
    return tk


@pytest.fixture
def host_event(time_kernel):
    time_kernel.stamp("e1")
    return HostEvent(
        event_id="e1",
        session_id="s1",
        timestamp=100.0,
        source="test",
        payload={"cmd": "ls"},
    )


@pytest.fixture
def proposal():
    return ExecutionProposal(
        proposal_id="p1",
        session_id="s1",
        event_id="e1",
        action="read",
        target="/tmp/x",
        params={},
        required_capabilities=[Capability.FILESYSTEM_READ],
        confidence=0.8,
        risk_score=0.1,
        metadata={},
    )


@pytest.fixture
def decision():
    return PolicyDecision(
        decision_id="d1",
        proposal_id="p1",
        session_id="s1",
        verdict="ALLOW",
        reason="ok",
        risk_level="low",
        rule_triggered=None,
        confidence=0.9,
    )


@pytest.fixture
def result_success():
    return ExecutionResult(
        execution_id="ex1",
        proposal_id="p1",
        session_id="s1",
        status="SUCCESS",
        output={"data": "ok"},
        error=None,
        started_at=100.0,
        finished_at=101.0,
    )


@pytest.fixture
def result_failed():
    return ExecutionResult(
        execution_id="ex2",
        proposal_id="p1",
        session_id="s1",
        status="FAILED",
        output=None,
        error="execution_error",
        started_at=100.0,
        finished_at=100.5,
    )


@pytest.fixture
def obs_tap(time_kernel):
    return ObservationTap(time_kernel)


class TestObservationTap:
    def test_tap_event_received_creates_enriched(self, obs_tap, host_event):
        obs_tap.tap_event_received(host_event)
        enriched = obs_tap.get_enriched("e1")
        assert enriched is not None
        assert enriched.event_id == "e1"
        assert enriched.status == "received"
        assert enriched.session_id == "s1"

    def test_tap_event_received_adds_trace(self, obs_tap, host_event):
        obs_tap.tap_event_received(host_event)
        enriched = obs_tap.get_enriched("e1")
        assert len(enriched.hal_trace) >= 1
        entry = enriched.hal_trace[0]
        assert entry.stage == "event_queue"
        assert entry.stage_type == "received"

    def test_tap_p3_proposal_sets_proposal(self, obs_tap, host_event, proposal):
        obs_tap.tap_event_received(host_event)
        obs_tap.tap_p3_proposal("e1", proposal)
        enriched = obs_tap.get_enriched("e1")
        assert enriched.p3_proposal == proposal
        assert enriched.hal_trace[-1].stage == "p3_context"

    def test_tap_p3_proposal_noop_for_unknown(self, obs_tap, proposal):
        obs_tap.tap_p3_proposal("unknown", proposal)

    def test_tap_p4_decision_sets_decision(self, obs_tap, host_event, proposal, decision):
        obs_tap.tap_event_received(host_event)
        obs_tap.tap_p3_proposal("e1", proposal)
        obs_tap.tap_p4_decision("e1", decision)
        enriched = obs_tap.get_enriched("e1")
        assert enriched.p4_decision == decision
        assert enriched.hal_trace[-1].stage == "p4_authority"

    def test_tap_p4_decision_noop_for_unknown(self, obs_tap, decision):
        obs_tap.tap_p4_decision("unknown", decision)

    def test_tap_execution_result_completed(self, obs_tap, host_event, proposal, decision, result_success):
        obs_tap.tap_event_received(host_event)
        obs_tap.tap_p3_proposal("e1", proposal)
        obs_tap.tap_p4_decision("e1", decision)
        obs_tap.tap_execution_result("e1", result_success)
        enriched = obs_tap.get_enriched("e1")
        assert enriched.execution_result == result_success
        assert enriched.status == "completed"
        assert enriched.hal_trace[-1].stage == "execution_substrate"

    def test_tap_execution_result_failed(self, obs_tap, host_event, proposal, decision, result_failed):
        obs_tap.tap_event_received(host_event)
        obs_tap.tap_p3_proposal("e1", proposal)
        obs_tap.tap_p4_decision("e1", decision)
        obs_tap.tap_execution_result("e1", result_failed)
        enriched = obs_tap.get_enriched("e1")
        assert enriched.execution_result == result_failed
        assert enriched.status == "failed"

    def test_tap_execution_result_noop_for_unknown(self, obs_tap, result_success):
        obs_tap.tap_execution_result("unknown", result_success)

    def test_tap_blocked_sets_status(self, obs_tap, host_event, proposal):
        obs_tap.tap_event_received(host_event)
        obs_tap.tap_p3_proposal("e1", proposal)
        obs_tap.tap_blocked("e1", "policy_violation")
        enriched = obs_tap.get_enriched("e1")
        assert enriched.status == "blocked"
        assert enriched.hal_trace[-1].stage_type == "blocked"

    def test_tap_blocked_noop_for_unknown(self, obs_tap):
        obs_tap.tap_blocked("unknown", "reason")

    def test_get_enriched_returns_none_for_unknown(self, obs_tap):
        assert obs_tap.get_enriched("nonexistent") is None

    def test_get_by_session_filters(self, obs_tap, host_event, time_kernel):
        host_event2 = HostEvent(
            event_id="e2", session_id="s2", timestamp=200.0,
            source="test", payload={},
        )
        time_kernel.stamp("e2")
        obs_tap.tap_event_received(host_event)
        obs_tap.tap_event_received(host_event2)
        s1_events = obs_tap.get_by_session("s1")
        s2_events = obs_tap.get_by_session("s2")
        assert len(s1_events) == 1
        assert s1_events[0].event_id == "e1"
        assert len(s2_events) == 1
        assert s2_events[0].event_id == "e2"

    def test_get_by_status_filters(self, obs_tap, host_event, proposal, decision, result_success):
        host_event2 = HostEvent(
            event_id="e2", session_id="s1", timestamp=200.0,
            source="test", payload={},
        )
        host_event3 = HostEvent(
            event_id="e3", session_id="s1", timestamp=300.0,
            source="test", payload={},
        )
        obs_tap._time.stamp("e2")
        obs_tap._time.stamp("e3")

        obs_tap.tap_event_received(host_event)
        obs_tap.tap_p3_proposal("e1", proposal)
        obs_tap.tap_p4_decision("e1", decision)
        obs_tap.tap_execution_result("e1", result_success)

        obs_tap.tap_event_received(host_event2)

        obs_tap.tap_event_received(host_event3)
        obs_tap.tap_blocked("e3", "blocked")

        received = obs_tap.get_by_status("received")
        completed = obs_tap.get_by_status("completed")
        blocked = obs_tap.get_by_status("blocked")

        assert len(received) == 1
        assert received[0].event_id == "e2"
        assert len(completed) == 1
        assert completed[0].event_id == "e1"
        assert len(blocked) == 1
        assert blocked[0].event_id == "e3"

    def test_total_traced(self, obs_tap, host_event):
        assert obs_tap.total_traced == 0
        obs_tap.tap_event_received(host_event)
        assert obs_tap.total_traced == 1

        host_event2 = HostEvent(
            event_id="e2", session_id="s1", timestamp=200.0,
            source="test", payload={},
        )
        obs_tap._time.stamp("e2")
        obs_tap.tap_event_received(host_event2)
        assert obs_tap.total_traced == 2

    def test_completed_cycles_counts_full_cycles(self, obs_tap, host_event, proposal, decision, result_success):
        obs_tap.tap_event_received(host_event)
        obs_tap.tap_p3_proposal("e1", proposal)
        obs_tap.tap_p4_decision("e1", decision)

        assert obs_tap.completed_cycles == 0

        obs_tap.tap_execution_result("e1", result_success)
        assert obs_tap.completed_cycles == 1

    def test_completed_cycles_counts_only_full(self, obs_tap, host_event, proposal):
        host_event2 = HostEvent(
            event_id="e2", session_id="s1", timestamp=200.0,
            source="test", payload={},
        )
        obs_tap._time.stamp("e2")
        obs_tap.tap_event_received(host_event)
        obs_tap.tap_p3_proposal("e1", proposal)
        obs_tap.tap_event_received(host_event2)

        assert obs_tap.completed_cycles == 0

    def test_subscribe_callback_fires(self, obs_tap, host_event):
        received_events = []

        def callback(ee):
            received_events.append(ee)

        obs_tap.subscribe(callback)
        obs_tap.tap_event_received(host_event)
        assert len(received_events) == 1
        assert received_events[0].event_id == "e1"

    def test_subscribe_multiple_callbacks(self, obs_tap, host_event):
        calls = []
        obs_tap.subscribe(lambda ee: calls.append("cb1"))
        obs_tap.subscribe(lambda ee: calls.append("cb2"))
        obs_tap.tap_event_received(host_event)
        assert "cb1" in calls
        assert "cb2" in calls
        assert len(calls) == 2

    def test_callback_receives_enriched_event(self, obs_tap, host_event):
        captured = []

        def cb(ee):
            captured.append(ee)

        obs_tap.subscribe(cb)
        obs_tap.tap_event_received(host_event)
        assert isinstance(captured[0], EnrichedEvent)
        assert captured[0].host_event == host_event

    def test_constructor_with_on_event(self, time_kernel, host_event):
        captured = []

        def on_event(ee):
            captured.append(ee)

        tap = ObservationTap(time_kernel, on_event=on_event)
        tap.tap_event_received(host_event)
        assert len(captured) == 1

    def test_constructor_with_trace_store(self, time_kernel, host_event, proposal, decision, result_success):
        store = ExecutionTraceStore()
        tap = ObservationTap(time_kernel, trace_store=store)
        tap.tap_event_received(host_event)
        tap.tap_p3_proposal("e1", proposal)
        tap.tap_p4_decision("e1", decision)
        tap.tap_execution_result("e1", result_success)
        assert len(store) == 1
        trace = store.by_event_id("e1")
        assert trace is not None
        assert trace.execution_status == "SUCCESS"
        assert trace.final_status == "P4_ALLOW"

    def test_blocked_emits_trace(self, time_kernel, host_event, proposal):
        store = ExecutionTraceStore()
        tap = ObservationTap(time_kernel, trace_store=store)
        tap.tap_event_received(host_event)
        tap.tap_p3_proposal("e1", proposal)
        tap.tap_blocked("e1", "policy_violation")
        assert len(store) == 1
        trace = store.by_event_id("e1")
        assert trace is not None
        assert trace.final_status == "P4_BLOCKED_BY_PREFLIGHT"
