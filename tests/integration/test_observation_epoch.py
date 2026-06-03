"""Observation Epoch — multi-cycle telemetry, state transitions, and deterministic observability."""

import asyncio
import tempfile
import os
from unittest.mock import AsyncMock, MagicMock

import pytest

from cognitive_runtime.contracts.execution_contract import (
    Capability, ExecutionProposal, ExecutionResult, HostEvent, PolicyDecision,
)
from cognitive_runtime.runtime.runtime_loop import RuntimeLoop


class ObservationCatcher:
    def __init__(self):
        self.events = []

    def __call__(self, event):
        self.events.append(event)


def _make_pool():
    p = MagicMock()
    p.execute = AsyncMock(return_value=ExecutionResult(
        execution_id="ex1", proposal_id="p1", session_id="s1",
        status="SUCCESS", output={}, error=None,
        started_at=1000.0, finished_at=1001.0,
    ))
    return p


@pytest.fixture
def observation_harness():
    hal = ObservationCatcher()
    async def mock_p3(event):
        return ExecutionProposal(
            proposal_id=f"p-{event.event_id}", session_id=event.session_id,
            event_id=event.event_id,
            action="read", target="/tmp/f", params={},
            required_capabilities=[Capability.FILESYSTEM_READ],
            confidence=0.8, risk_score=0.1, metadata={},
        )
    p3 = mock_p3
    _p4_count = 0
    async def mock_p4(proposal):
        nonlocal _p4_count
        _p4_count += 1
        return PolicyDecision(
            decision_id=f"d{_p4_count}", proposal_id=proposal.proposal_id,
            session_id=proposal.session_id,
            verdict="ALLOW", reason="ok", risk_level="low",
            rule_triggered=None, confidence=0.9,
        )
    p4 = mock_p4
    db = os.path.join(tempfile.mkdtemp(), "epoch.db")
    from cognitive_runtime.substrate.event_queue import EventQueue
    q = EventQueue(db_path=db)
    q.open()
    for i in range(10):
        q.push(HostEvent(
            event_id=f"e{i}", session_id="s1", timestamp=1000.0 + i,
            source="epoch", payload={"action": "read", "target": "/tmp/f", "seq": i},
        ))
    return q, p3, p4, hal, db


@pytest.mark.asyncio
async def test_epoch_multiple_events_produce_traces(observation_harness):
    q, p3, p4, hal, db = observation_harness
    tap = MagicMock()
    tap.total_traced = 0
    tap.completed_cycles = 0
    loop = RuntimeLoop(queue=q, tap=tap, p3_context_builder=p3,
                       sandbox_pool=_make_pool(), p4_authority=p4, hal_observer=hal)
    task = asyncio.create_task(loop.run())
    while q.queue_depth > 0:
        await asyncio.sleep(0.05)
    await asyncio.sleep(0.1)
    loop.stop()
    await task

    assert len(loop._traces) >= 5
    assert loop._state.total_events_processed >= 5
    assert loop._state.status == "stopped"
    q.close()
    _cleanup(db)


@pytest.mark.asyncio
async def test_epoch_hal_receives_all_telemetry(observation_harness):
    q, p3, p4, hal, db = observation_harness
    t = MagicMock()
    t.total_traced = 0
    t.completed_cycles = 0
    loop = RuntimeLoop(queue=q, tap=t, p3_context_builder=p3,
                       sandbox_pool=_make_pool(), p4_authority=p4, hal_observer=hal)
    task = asyncio.create_task(loop.run())
    while q.queue_depth > 0:
        await asyncio.sleep(0.05)
    await asyncio.sleep(0.1)
    loop.stop()
    await task

    startup = [e for e in hal.events if isinstance(e, dict) and e.get("type") == "startup.recovery"]
    cycles = [e for e in hal.events if isinstance(e, dict) and e.get("type") == "cycle.completed"]
    assert len(startup) == 1
    assert len(cycles) >= 5
    q.close()
    _cleanup(db)


@pytest.mark.asyncio
async def test_epoch_state_transitions_tracked(observation_harness):
    q, p3, p4, hal, db = observation_harness
    loop = RuntimeLoop(queue=q, tap=MagicMock(), p3_context_builder=p3,
                       sandbox_pool=_make_pool(), p4_authority=p4, hal_observer=hal)
    assert loop._state.status == "stopped"
    task = asyncio.create_task(loop.run())
    await asyncio.sleep(0.05)
    assert loop._state.status == "running"
    assert loop._state.started_at is not None
    while q.queue_depth > 0:
        await asyncio.sleep(0.05)
    await asyncio.sleep(0.1)
    loop.stop()
    await task
    assert loop._state.status == "stopped"
    q.close()
    _cleanup(db)


@pytest.mark.asyncio
async def test_epoch_causal_graph_built_over_time(observation_harness):
    q, p3, p4, hal, db = observation_harness
    loop = RuntimeLoop(queue=q, tap=MagicMock(), p3_context_builder=p3,
                       sandbox_pool=_make_pool(), p4_authority=p4, hal_observer=hal)
    task = asyncio.create_task(loop.run())
    while q.queue_depth > 0:
        await asyncio.sleep(0.05)
    await asyncio.sleep(0.1)
    loop.stop()
    await task

    assert loop._causal_graph is not None
    assert len(loop._causal_graph.nodes) >= 1
    q.close()
    _cleanup(db)


@pytest.mark.asyncio
async def test_epoch_health_stays_healthy(observation_harness):
    q, p3, p4, hal, db = observation_harness
    t = MagicMock()
    t.total_traced = 0
    t.completed_cycles = 0
    loop = RuntimeLoop(queue=q, tap=t, p3_context_builder=p3,
                       sandbox_pool=_make_pool(), p4_authority=p4, hal_observer=hal)
    task = asyncio.create_task(loop.run())
    while q.queue_depth > 0:
        await asyncio.sleep(0.05)
    await asyncio.sleep(0.1)
    loop.stop()
    await task
    assert loop._state.health_status == "healthy"
    assert loop._state.consecutive_failures == 0
    q.close()
    _cleanup(db)


@pytest.mark.asyncio
async def test_epoch_no_recovery_on_subsequent_boot(observation_harness):
    """After clean stop, next boot should still be clean."""
    q, p3, p4, hal, db = observation_harness
    from tests.integration.test_first_boot import MockObservationTap
    loop = RuntimeLoop(queue=q, tap=MockObservationTap(), p3_context_builder=p3,
                       sandbox_pool=_make_pool(), p4_authority=p4, hal_observer=hal)
    report = loop._recovery_coordinator.recover(loop)
    assert report.recovery_mode == "clean_start"
    assert report.corruption_detected is False
    q.close()
    _cleanup(db)


@pytest.mark.asyncio
async def test_epoch_coherence_monitor_has_report(observation_harness):
    q, p3, p4, hal, db = observation_harness
    loop = RuntimeLoop(queue=q, tap=MagicMock(), p3_context_builder=p3,
                       sandbox_pool=_make_pool(), p4_authority=p4, hal_observer=hal)
    task = asyncio.create_task(loop.run())
    while q.queue_depth > 0:
        await asyncio.sleep(0.05)
    await asyncio.sleep(0.1)
    loop.stop()
    await task
    assert loop._coherence is not None
    assert loop._coherence.report is not None
    q.close()
    _cleanup(db)


def _cleanup(db):
    try:
        import gc, shutil
        d = os.path.dirname(db)
        for _ in range(3):
            try:
                shutil.rmtree(d)
            except (PermissionError, FileNotFoundError):
                gc.collect()
    except Exception:
        pass
