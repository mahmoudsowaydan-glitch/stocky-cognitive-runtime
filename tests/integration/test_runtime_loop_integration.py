"""Integration tests for RuntimeLoop — construction, trace building, cycle finalization, event processing, stop, and HAL observation."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from cognitive_runtime.contracts.execution_contract import (
    Capability,
    ExecutionProposal,
    ExecutionResult,
    HostEvent,
    PolicyDecision,
)
from cognitive_runtime.contracts.execution_trace import ExecutionTrace
from cognitive_runtime.runtime.runtime_loop import RuntimeLoop
from cognitive_runtime.runtime.runtime_state import RuntimeState
from cognitive_runtime.sandbox.preflight_analyzer import PreflightResult


class MockObservationTap:
    tap_event_received = MagicMock()
    tap_p3_proposal = MagicMock()
    tap_p4_decision = MagicMock()
    tap_execution_result = MagicMock()
    tap_blocked = MagicMock()
    get_enriched = MagicMock()
    get_by_session = MagicMock()
    get_by_status = MagicMock()
    subscribe = MagicMock()
    total_traced = 0
    completed_cycles = 0


class MockEventQueue:
    def __init__(self):
        self._pop_side_effect = None
        self.stats = MagicMock()
        self.stats.queue_depth = 0
        self.stats.total_events = 0
        self.stats.dead_lettered = 0
        self.stats.processed = 0
        self.stats.failed = 0
        self.stats.average_cycle_ms = 0
        self.stats.last_cycle_ms = 0

    def open(self):
        pass

    def close(self):
        pass

    def pop(self):
        if callable(self._pop_side_effect):
            return self._pop_side_effect()
        if isinstance(self._pop_side_effect, list):
            if self._pop_side_effect:
                return self._pop_side_effect.pop(0)
            return None
        return self._pop_side_effect

    def record_decision(self, decision):
        pass

    def ack(self, event_id, result):
        pass

    def nack(self, event_id, error, proposal=None):
        pass

    @property
    def queue_depth(self):
        return 0


class MockSandboxPool:
    execute = AsyncMock()


def create_minimal_loop(**overrides):
    return RuntimeLoop(
        queue=overrides.get("queue", MockEventQueue()),
        tap=overrides.get("tap", MockObservationTap()),
        p3_context_builder=overrides.get("mock_p3", AsyncMock()),
        sandbox_pool=overrides.get("pool", MockSandboxPool()),
        preflight=overrides.get("preflight"),
        p4_authority=overrides.get("p4_authority"),
        hal_observer=overrides.get("hal_observer"),
    )


# ─── a) Construction ──────────────────────────


def test_construction_creates_all_internal_components():
    loop = create_minimal_loop()
    assert loop._state is not None
    assert isinstance(loop._state, RuntimeState)
    assert loop._orchestrator is not None
    assert loop._coherence is not None
    assert loop._feedback is not None
    assert loop._compression is not None
    assert loop._stability is not None
    assert loop._confidence is not None
    assert loop._governance is not None
    assert loop._contract_guard is not None
    assert loop._checkpoint_manager is not None
    assert loop._recovery_coordinator is not None


def test_construction_initial_state_is_stopped():
    loop = create_minimal_loop()
    assert loop._state.status == "stopped"
    assert loop._state.total_events_processed == 0
    assert loop._state.health_status == "healthy"


def test_construction_traces_list_starts_empty():
    loop = create_minimal_loop()
    assert loop._traces.total_count == 0
    assert loop.traces == []


def test_construction_default_preflight_analyzer_created():
    loop = create_minimal_loop()
    assert loop._preflight is not None


def test_construction_default_causal_builder_created():
    loop = create_minimal_loop()
    assert loop._causal_builder is not None


# ─── b) Trace Building ────────────────────────


def test_build_trace_with_full_data():
    event = HostEvent(
        event_id="e1", session_id="s1", timestamp=1000.0,
        source="test", payload={"cmd": "test"},
    )
    proposal = ExecutionProposal(
        proposal_id="p1", session_id="s1", event_id="e1",
        action="read", target="/tmp/f", params={},
        required_capabilities=[Capability.FILESYSTEM_READ],
        confidence=0.8, risk_score=0.1, metadata={},
    )
    preflight = PreflightResult(valid=True, reason="ok", risk_score=0.1)
    decision = PolicyDecision(
        decision_id="d1", proposal_id="p1", session_id="s1",
        verdict="ALLOW", reason="ok", risk_level="low",
        rule_triggered=None, confidence=0.9,
    )
    result = ExecutionResult(
        execution_id="ex1", proposal_id="p1", session_id="s1",
        status="SUCCESS", output={}, error=None,
        started_at=100.0, finished_at=101.0,
    )
    loop = create_minimal_loop()
    trace = loop._build_trace(event, proposal, preflight, decision, result, start_time=100.0)
    assert trace.event_id == "e1"
    assert trace.session_id == "s1"
    assert trace.p4_verdict == "ALLOW"
    assert trace.final_status == "P4_ALLOW"


def test_build_trace_preflight_blocked():
    event = HostEvent(
        event_id="e2", session_id="s1", timestamp=1000.0,
        source="test", payload={"cmd": "test"},
    )
    proposal = ExecutionProposal(
        proposal_id="p2", session_id="s1", event_id="e2",
        action="write", target="/etc/passwd", params={},
        required_capabilities=[Capability.FILESYSTEM_WRITE],
        confidence=0.5, risk_score=0.9, metadata={},
    )
    preflight = PreflightResult(
        valid=False, reason="BLOCKED_BY_PREFLIGHT: rule_42",
        risk_score=0.9, triggered_rules=["rule_42"],
    )
    loop = create_minimal_loop()
    trace = loop._build_trace(event, proposal, preflight, None, None, start_time=100.0)
    assert trace.event_id == "e2"
    assert trace.p4_verdict == "BLOCKED_BY_PREFLIGHT"
    assert trace.final_status == "P4_BLOCKED_BY_PREFLIGHT"


def test_build_trace_sandbox_failed():
    event = HostEvent(
        event_id="e3", session_id="s1", timestamp=1000.0,
        source="test", payload={"cmd": "test"},
    )
    proposal = ExecutionProposal(
        proposal_id="p3", session_id="s1", event_id="e3",
        action="exec", target="/bad", params={},
        required_capabilities=[Capability.PROCESS_EXECUTE],
        confidence=0.7, risk_score=0.5, metadata={},
    )
    preflight = PreflightResult(valid=True, reason="ok", risk_score=0.5)
    decision = PolicyDecision(
        decision_id="d3", proposal_id="p3", session_id="s1",
        verdict="ALLOW", reason="ok", risk_level="medium",
        rule_triggered=None, confidence=0.8,
    )
    result = ExecutionResult(
        execution_id="ex3", proposal_id="p3", session_id="s1",
        status="FAILED", output=None, error="sandbox_crash",
        started_at=100.0, finished_at=100.5,
    )
    loop = create_minimal_loop()
    trace = loop._build_trace(event, proposal, preflight, decision, result, start_time=100.0)
    assert trace.event_id == "e3"
    assert trace.execution_status == "FAILED"
    assert trace.final_status == "SANDBOX_FAILED"


# ─── c) Finalize Cycle ───────────────────────


def test_finalize_appends_trace_to_traces(sample_trace_allow):
    loop = create_minimal_loop()
    loop._finalize_cycle(sample_trace_allow)
    assert len(loop._traces) == 1
    assert loop._traces[0].event_id == "e1"


def test_finalize_updates_state(sample_trace_allow):
    loop = create_minimal_loop()
    loop._finalize_cycle(sample_trace_allow)
    assert loop._state.last_execution_trace_id == "e1"
    assert loop._state.last_execution_status == "P4_ALLOW"


def test_finalize_coherence_check_runs(sample_trace_allow):
    loop = create_minimal_loop()
    loop._finalize_cycle(sample_trace_allow)
    assert loop._coherence.report is not None


def test_finalize_causal_graph_built_within_first_5(sample_trace_allow):
    loop = create_minimal_loop()
    for _ in range(3):
        loop._finalize_cycle(sample_trace_allow)
    assert len(loop._causal_graph.nodes) > 0


def test_finalize_multiple_appends_all_traces(sample_trace_allow):
    loop = create_minimal_loop()
    for i in range(5):
        t = ExecutionTrace(
            event_id=f"e{i}", session_id="s1", sequence_no=i, correlation_id=f"c{i}",
            preflight_valid=True, p4_verdict="ALLOW",
            execution_status="SUCCESS", final_status="P4_ALLOW",
        )
        loop._finalize_cycle(t)
    assert len(loop._traces) == 5


# ─── d) Process Event (async) ─────────────────


@pytest.mark.asyncio
async def test_process_one_event_cycle():
    event = HostEvent(
        event_id="e1", session_id="s1", timestamp=1000.0,
        source="test", payload={"cmd": "test", "action": "read", "target": "/tmp/f"},
    )
    proposal = ExecutionProposal(
        proposal_id="prop-e1", session_id="s1", event_id="e1",
        action="read", target="/tmp/f", params={"cmd": "test"},
        required_capabilities=[Capability.FILESYSTEM_READ],
        confidence=0.8, risk_score=0.1, metadata={"source": "test"},
    )
    decision = PolicyDecision(
        decision_id="d1", proposal_id="prop-e1", session_id="s1",
        verdict="ALLOW", reason="ok", risk_level="low",
        rule_triggered=None, confidence=0.9,
    )
    result = ExecutionResult(
        execution_id="ex1", proposal_id="prop-e1", session_id="s1",
        status="SUCCESS", output={"done": True}, error=None,
        started_at=1000.0, finished_at=1001.0,
    )
    queue = MockEventQueue()
    queue._pop_side_effect = [event]
    mock_p3 = AsyncMock(return_value=proposal)
    mock_p4 = AsyncMock(return_value=decision)
    pool = MockSandboxPool()
    pool.execute = AsyncMock(return_value=result)
    preflight = MagicMock()
    preflight.analyze.return_value = PreflightResult(valid=True, reason="ok", risk_score=0.1)
    loop = create_minimal_loop(queue=queue, mock_p3=mock_p3, pool=pool,
                                preflight=preflight, p4_authority=mock_p4)
    loop._recovery_completed = True
    task = asyncio.create_task(loop.run())
    await asyncio.sleep(0.3)
    assert loop._state.total_events_processed >= 1
    assert len(loop._traces) >= 1
    assert loop._traces[0].event_id == "e1"
    loop.stop()
    await task


@pytest.mark.asyncio
async def test_process_blocked_event():
    event = HostEvent(
        event_id="e2", session_id="s1", timestamp=1000.0,
        source="test", payload={"cmd": "test"},
    )
    proposal = ExecutionProposal(
        proposal_id="prop-e2", session_id="s1", event_id="e2",
        action="write", target="/etc/pw", params={},
        required_capabilities=[Capability.FILESYSTEM_WRITE],
        confidence=0.5, risk_score=0.9, metadata={"source": "test"},
    )
    decision = PolicyDecision(
        decision_id="d2", proposal_id="prop-e2", session_id="s1",
        verdict="BLOCK", reason="policy_violation", risk_level="high",
        rule_triggered="rule_42", confidence=0.95,
    )
    queue = MockEventQueue()
    queue._pop_side_effect = [event]
    nack_called = False

    def fake_nack(eid, error, proposal=None):
        nonlocal nack_called
        nack_called = True
    queue.nack = fake_nack
    mock_p3 = AsyncMock(return_value=proposal)
    mock_p4 = AsyncMock(return_value=decision)
    pool = MockSandboxPool()
    preflight = MagicMock()
    preflight.analyze.return_value = PreflightResult(valid=True, reason="ok", risk_score=0.9)
    loop = create_minimal_loop(queue=queue, mock_p3=mock_p3, pool=pool,
                                preflight=preflight, p4_authority=mock_p4)
    loop._recovery_completed = True
    task = asyncio.create_task(loop.run())
    await asyncio.sleep(0.3)
    assert loop._state.total_events_processed >= 1
    assert len(loop._traces) >= 1
    trace = loop._traces[0]
    assert trace.p4_verdict == "BLOCK"
    assert trace.execution_status == "FAILED"
    assert nack_called
    loop.stop()
    await task


@pytest.mark.asyncio
async def test_process_preflight_rejected_event():
    event = HostEvent(
        event_id="e3", session_id="s1", timestamp=1000.0,
        source="test", payload={"cmd": "test"},
    )
    proposal = ExecutionProposal(
        proposal_id="prop-e3", session_id="s1", event_id="e3",
        action="exec", target="/malware", params={},
        required_capabilities=[Capability.PROCESS_EXECUTE],
        confidence=0.1, risk_score=0.95, metadata={"source": "test"},
    )
    queue = MockEventQueue()
    queue._pop_side_effect = [event]
    mock_p3 = AsyncMock(return_value=proposal)
    pool = MockSandboxPool()
    preflight = MagicMock()
    preflight.analyze.return_value = PreflightResult(
        valid=False, reason="BLOCKED_BY_PREFLIGHT: bad_action",
        risk_score=0.95, triggered_rules=["bad_action"],
    )
    loop = create_minimal_loop(queue=queue, mock_p3=mock_p3, pool=pool, preflight=preflight)
    loop._recovery_completed = True
    task = asyncio.create_task(loop.run())
    await asyncio.sleep(0.3)
    assert loop._state.total_events_processed >= 1
    assert len(loop._traces) >= 1
    trace = loop._traces[0]
    assert trace.final_status == "P4_BLOCKED_BY_PREFLIGHT"
    loop.stop()
    await task


# ─── e) Stop ──────────────────────────────────


def test_stop_sets_orchestrator_to_stopped():
    loop = create_minimal_loop()
    loop._orchestrator.start()
    assert loop._orchestrator.is_running
    loop.stop()
    assert not loop._orchestrator.is_running
    assert loop._state.status == "stopped"


def test_stop_idempotent():
    loop = create_minimal_loop()
    loop.stop()
    loop.stop()
    assert not loop._orchestrator.is_running


def test_stop_is_running_property():
    loop = create_minimal_loop()
    assert not loop.is_running
    loop._orchestrator.start()
    assert loop.is_running
    loop.stop()
    assert not loop.is_running


# ─── f) HAL Observer ──────────────────────────


def test_hal_receives_cycle_completed(sample_trace_allow):
    collected = []

    def hal(msg):
        collected.append(msg)

    loop = create_minimal_loop(hal_observer=hal)
    loop._finalize_cycle(sample_trace_allow)
    cycle_msgs = [m for m in collected if m.get("type") == "cycle.completed"]
    assert len(cycle_msgs) == 1
    assert cycle_msgs[0]["trace_id"] == "e1"
    assert cycle_msgs[0]["final_status"] == "P4_ALLOW"
    assert "drift" in cycle_msgs[0]


def test_hal_receives_all_cycle_messages(sample_trace_allow):
    collected = []

    def hal(msg):
        collected.append(msg)

    loop = create_minimal_loop(hal_observer=hal)
    loop._finalize_cycle(sample_trace_allow)
    types = {m.get("type") for m in collected}
    assert "cycle.completed" in types


def test_hal_not_called_when_none(sample_trace_allow):
    loop = create_minimal_loop(hal_observer=None)
    loop._finalize_cycle(sample_trace_allow)


def test_hal_receives_cycle_completed_with_drift_flag(sample_trace_failed):
    collected = []

    def hal(msg):
        collected.append(msg)

    loop = create_minimal_loop(hal_observer=hal)
    loop._finalize_cycle(sample_trace_failed)
    cycle_msgs = [m for m in collected if m.get("type") == "cycle.completed"]
    assert len(cycle_msgs) == 1
    assert cycle_msgs[0]["drift"] is not None
