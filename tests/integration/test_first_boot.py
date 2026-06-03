"""First Boot — clean startup, first event processing, and graceful shutdown."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from cognitive_runtime.contracts.execution_contract import (
    Capability, ExecutionProposal, ExecutionResult, HostEvent, PolicyDecision,
)
from cognitive_runtime.contracts.execution_trace import ExecutionTrace
from cognitive_runtime.runtime.runtime_loop import RuntimeLoop
from cognitive_runtime.runtime.runtime_state import RuntimeState


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


class MockSandboxPool:
    execute = AsyncMock(return_value=ExecutionResult(
        execution_id="ex1", proposal_id="p1", session_id="s1",
        status="SUCCESS", output={}, error=None,
        started_at=1000.0, finished_at=1001.0,
    ))


@pytest.fixture
def queue_with_event():
    from cognitive_runtime.substrate.event_queue import EventQueue
    import tempfile, os
    db = os.path.join(tempfile.mkdtemp(), "boot_test.db")
    q = EventQueue(db_path=db)
    q.open()
    q.push(HostEvent(
        event_id="boot1", session_id="s1", timestamp=1000.0,
        source="first_boot", payload={"action": "read", "target": "/tmp/f"},
    ))
    yield q
    try:
        import gc, shutil
        d = os.path.dirname(db)
        q.close()
        for _ in range(3):
            try:
                shutil.rmtree(d)
            except (PermissionError, FileNotFoundError):
                gc.collect()
    except Exception:
        pass


@pytest.mark.asyncio
async def test_first_boot_constructs_all_components():
    loop = RuntimeLoop(
        queue=MagicMock(),
        tap=MockObservationTap(),
        p3_context_builder=AsyncMock(),
        sandbox_pool=MockSandboxPool(),
    )
    assert loop._state is not None
    assert loop._state.status == "stopped"
    assert loop._state.health_status == "healthy"
    assert loop._orchestrator is not None
    assert loop._governance is not None
    assert loop._confidence is not None
    assert loop._stability is not None
    assert loop._contract_guard is not None
    assert loop._checkpoint_manager is not None
    assert loop._recovery_coordinator is not None
    assert loop._recovery_completed is False
    assert loop._traces.total_count == 0


@pytest.mark.asyncio
async def test_first_boot_recovery_runs_clean_start():
    from cognitive_runtime.substrate.event_queue import EventQueue
    import tempfile, os
    db = os.path.join(tempfile.mkdtemp(), "boot_rec.db")
    q = EventQueue(db_path=db)

    p3 = AsyncMock(return_value=ExecutionProposal(
        proposal_id="p1", session_id="s1", event_id="boot1",
        action="read", target="/tmp/f", params={},
        required_capabilities=[Capability.FILESYSTEM_READ],
        confidence=0.8, risk_score=0.1, metadata={},
    ))
    p4 = AsyncMock(return_value=PolicyDecision(
        decision_id="d1", proposal_id="p1", session_id="s1",
        verdict="ALLOW", reason="ok", risk_level="low",
        rule_triggered=None, confidence=0.9,
    ))

    loop = RuntimeLoop(
        queue=q, tap=MockObservationTap(),
        p3_context_builder=p3, sandbox_pool=MockSandboxPool(),
        p4_authority=p4,
    )

    assert loop._recovery_completed is False
    report = loop._recovery_coordinator.recover(loop)
    assert report.recovery_mode == "clean_start"
    assert report.corruption_detected is False
    assert report.contract_violations_during_recovery == 0
    assert report.replay_valid is True

    d = os.path.dirname(db)
    try:
        import gc, shutil
        q.close()
        for _ in range(3):
            try:
                shutil.rmtree(d)
            except (PermissionError, FileNotFoundError):
                gc.collect()
    except Exception:
        pass


@pytest.mark.asyncio
async def test_first_boot_processes_event_and_shuts_down(queue_with_event):
    p3 = AsyncMock(return_value=ExecutionProposal(
        proposal_id="p1", session_id="s1", event_id="boot1",
        action="read", target="/tmp/f", params={},
        required_capabilities=[Capability.FILESYSTEM_READ],
        confidence=0.8, risk_score=0.1, metadata={},
    ))
    p4 = AsyncMock(return_value=PolicyDecision(
        decision_id="d1", proposal_id="p1", session_id="s1",
        verdict="ALLOW", reason="ok", risk_level="low",
        rule_triggered=None, confidence=0.9,
    ))
    hal_events = []
    loop = RuntimeLoop(
        queue=queue_with_event, tap=MockObservationTap(),
        p3_context_builder=p3, sandbox_pool=MockSandboxPool(),
        p4_authority=p4,
        hal_observer=lambda e: hal_events.append(e),
    )

    async def run_with_stop():
        task = asyncio.create_task(loop.run())
        await asyncio.sleep(0.3)
        loop.stop()
        await task

    await run_with_stop()

    assert loop._state.total_events_processed >= 1
    assert len(loop._traces) >= 1
    assert loop._traces[0].event_id == "boot1"
    assert loop._traces[0].final_status == "P4_ALLOW"

    startup_hal = [e for e in hal_events if isinstance(e, dict) and e.get("type") == "startup.recovery"]
    assert len(startup_hal) == 1

    assert loop._recovery_completed is True
    assert loop._state.status == "stopped"


@pytest.mark.asyncio
async def test_first_boot_no_false_crash_detection():
    from cognitive_runtime.substrate.event_queue import EventQueue
    import tempfile, os
    db = os.path.join(tempfile.mkdtemp(), "boot_crash.db")
    q = EventQueue(db_path=db)
    q.open()
    q.push(HostEvent(
        event_id="crash_test", session_id="s1", timestamp=1000.0,
        source="boot", payload={"action": "read", "target": "/tmp/f"},
    ))

    p3 = AsyncMock(return_value=ExecutionProposal(
        proposal_id="p1", session_id="s1", event_id="crash_test",
        action="read", target="/tmp/f", params={},
        required_capabilities=[Capability.FILESYSTEM_READ],
        confidence=0.8, risk_score=0.1, metadata={},
    ))
    p4 = AsyncMock(return_value=PolicyDecision(
        decision_id="d1", proposal_id="p1", session_id="s1",
        verdict="ALLOW", reason="ok", risk_level="low",
        rule_triggered=None, confidence=0.9,
    ))

    loop = RuntimeLoop(
        queue=q, tap=MockObservationTap(),
        p3_context_builder=p3, sandbox_pool=MockSandboxPool(),
        p4_authority=p4,
    )

    report = loop._recovery_coordinator.recover(loop)
    assert report.recovery_mode == "clean_start"
    assert report.corruption_detected is False
    assert report.orphan_events_found == 0

    d = os.path.dirname(db)
    try:
        import gc, shutil
        q.close()
        for _ in range(3):
            try:
                shutil.rmtree(d)
            except (PermissionError, FileNotFoundError):
                gc.collect()
    except Exception:
        pass


@pytest.mark.asyncio
async def test_first_boot_contract_guard_verifies_frozen_invariants():
    from cognitive_runtime.contracts.frozen.doctrine_runtime_guard import DoctrineRuntimeGuard
    loop = RuntimeLoop(
        queue=MagicMock(),
        tap=MockObservationTap(),
        p3_context_builder=AsyncMock(),
        sandbox_pool=MockSandboxPool(),
    )
    guard = DoctrineRuntimeGuard()
    passed, message = guard.ci_gate(loop)
    assert passed is True, f"CI gate failed: {message}"
