import pytest
from cognitive_runtime.contracts.enriched_event import TraceEntry, EnrichedEvent
from cognitive_runtime.contracts.execution_contract import (
    Capability,
    HostEvent,
    ExecutionProposal,
    ExecutionResult,
    PolicyDecision,
)


@pytest.fixture
def host_event():
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
def result():
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
def enriched(host_event):
    return EnrichedEvent(
        event_id="e1",
        session_id="s1",
        sequence_no=1,
        correlation_id="c1",
        host_event=host_event,
        status="received",
    )


class TestTraceEntry:
    def test_create(self):
        te = TraceEntry(
            stage="p3_context",
            stage_type="proposal",
            data={"proposal_id": "p1"},
            timestamp=100.0,
        )
        assert te.stage == "p3_context"
        assert te.stage_type == "proposal"
        assert te.data == {"proposal_id": "p1"}
        assert te.timestamp == 100.0


class TestEnrichedEvent:
    def test_create(self, host_event):
        ee = EnrichedEvent(
            event_id="e1",
            session_id="s1",
            sequence_no=1,
            correlation_id="c1",
            host_event=host_event,
        )
        assert ee.event_id == "e1"
        assert ee.session_id == "s1"
        assert ee.sequence_no == 1
        assert ee.correlation_id == "c1"
        assert ee.host_event == host_event
        assert ee.p3_proposal is None
        assert ee.p4_decision is None
        assert ee.execution_result is None
        assert ee.hal_trace == []
        assert ee.status == "received"

    def test_create_with_all_fields(self, host_event, proposal, decision, result):
        ee = EnrichedEvent(
            event_id="e1",
            session_id="s1",
            sequence_no=1,
            correlation_id="c1",
            host_event=host_event,
            p3_proposal=proposal,
            p4_decision=decision,
            execution_result=result,
            status="completed",
        )
        assert ee.p3_proposal == proposal
        assert ee.p4_decision == decision
        assert ee.execution_result == result
        assert ee.status == "completed"

    def test_add_trace(self, enriched):
        enriched.add_trace("p3_context", "proposal", {"proposal_id": "p1"})
        assert len(enriched.hal_trace) == 1
        entry = enriched.hal_trace[0]
        assert entry.stage == "p3_context"
        assert entry.stage_type == "proposal"
        assert entry.data == {"proposal_id": "p1"}

    def test_add_trace_multiple(self, enriched):
        enriched.add_trace("a", "t1", {})
        enriched.add_trace("b", "t2", {})
        assert len(enriched.hal_trace) == 2

    def test_has_full_cycle_false_when_missing_both(self, enriched):
        assert enriched.has_full_cycle is False

    def test_has_full_cycle_false_when_missing_decision(self, enriched, result):
        enriched.execution_result = result
        assert enriched.has_full_cycle is False

    def test_has_full_cycle_false_when_missing_result(self, enriched, decision):
        enriched.p4_decision = decision
        assert enriched.has_full_cycle is False

    def test_has_full_cycle_true(self, enriched, decision, result):
        enriched.p4_decision = decision
        enriched.execution_result = result
        assert enriched.has_full_cycle is True

    def test_final_verdict_returns_none_when_no_decision(self, enriched):
        assert enriched.final_verdict is None

    def test_final_verdict_returns_verdict(self, enriched, decision):
        enriched.p4_decision = decision
        assert enriched.final_verdict == "ALLOW"

    def test_final_verdict_block(self, enriched):
        dec = PolicyDecision(
            decision_id="d2", proposal_id="p1", session_id="s1",
            verdict="BLOCK", reason="no", risk_level="high",
            rule_triggered="r1", confidence=0.9,
        )
        enriched.p4_decision = dec
        assert enriched.final_verdict == "BLOCK"

    def test_final_status_returns_none_when_no_result(self, enriched):
        assert enriched.final_status is None

    def test_final_status_returns_status(self, enriched, result):
        enriched.execution_result = result
        assert enriched.final_status == "SUCCESS"

    def test_final_status_failed(self, enriched):
        res = ExecutionResult(
            execution_id="ex2", proposal_id="p1", session_id="s1",
            status="FAILED", output=None, error="err",
            started_at=0.0, finished_at=1.0,
        )
        enriched.execution_result = res
        assert enriched.final_status == "FAILED"

    def test_correlation_id_set(self, enriched):
        assert enriched.correlation_id == "c1"

    def test_status_defaults_to_received(self, host_event):
        ee = EnrichedEvent(
            event_id="e1", session_id="s1", sequence_no=1,
            correlation_id="c1", host_event=host_event,
        )
        assert ee.status == "received"
