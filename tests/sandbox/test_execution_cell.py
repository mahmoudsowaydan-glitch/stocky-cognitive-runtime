import asyncio
import pytest

from cognitive_runtime.sandbox.execution_cell import ExecutionCell, CellContext
from cognitive_runtime.sandbox.capability_enforcer import CapabilityEnforcer
from cognitive_runtime.contracts.execution_contract import (
    Capability,
    ExecutionProposal,
    ExecutionResult,
    PolicyDecision,
)


@pytest.fixture
def enforcer():
    return CapabilityEnforcer()


@pytest.fixture
def sample_proposal():
    return ExecutionProposal(
        proposal_id="p1", session_id="s1", event_id="e1",
        action="read", target="/tmp/file", params={},
        required_capabilities=[Capability.FILESYSTEM_READ],
        confidence=0.8, risk_score=0.1, metadata={},
    )


@pytest.fixture
def allow_decision():
    return PolicyDecision(
        decision_id="d1", proposal_id="p1", session_id="s1",
        verdict="ALLOW", reason="ok", risk_level="low",
        rule_triggered=None, confidence=0.9,
    )


async def successful_worker(proposal, decision):
    return {"result": "ok"}


async def failing_worker(proposal, decision):
    raise RuntimeError("worker_crashed")


async def slow_worker(proposal, decision):
    await asyncio.sleep(10)
    return {"result": "too_late"}


@pytest.mark.asyncio
class TestExecutionCell:
    async def test_successful_execution(self, enforcer, sample_proposal, allow_decision):
        cell = ExecutionCell(enforcer=enforcer, worker=successful_worker, max_time_ms=30000)
        result = await cell.execute(sample_proposal, allow_decision)
        assert result.status == "SUCCESS"
        assert result.output == {"result": "ok"}
        assert result.error is None
        assert result.proposal_id == "p1"
        assert result.session_id == "s1"

    async def test_context_after_successful_execution(self, enforcer, sample_proposal, allow_decision):
        cell = ExecutionCell(enforcer=enforcer, worker=successful_worker, max_time_ms=30000)
        await cell.execute(sample_proposal, allow_decision)
        ctx = cell.context
        assert ctx is not None
        assert isinstance(ctx, CellContext)
        assert ctx.proposal == sample_proposal
        assert ctx.decision == allow_decision
        assert ctx.frozen is True

    async def test_capability_block_returns_failed(self, enforcer, sample_proposal, allow_decision):
        enforcer.restrict(Capability.FILESYSTEM_READ)
        cell = ExecutionCell(enforcer=enforcer, worker=successful_worker, max_time_ms=30000)
        result = await cell.execute(sample_proposal, allow_decision)
        assert result.status == "FAILED"
        assert result.error is not None
        assert "capability_blocked" in result.error

    async def test_capability_block_sets_context(self, enforcer, sample_proposal, allow_decision):
        enforcer.restrict(Capability.FILESYSTEM_READ)
        cell = ExecutionCell(enforcer=enforcer, worker=successful_worker, max_time_ms=30000)
        await cell.execute(sample_proposal, allow_decision)
        ctx = cell.context
        assert ctx is not None
        assert ctx.proposal == sample_proposal
        assert ctx.decision == allow_decision

    async def test_timeout_returns_failed(self, enforcer, sample_proposal, allow_decision):
        cell = ExecutionCell(enforcer=enforcer, worker=slow_worker, max_time_ms=50)
        result = await cell.execute(sample_proposal, allow_decision)
        assert result.status == "FAILED"
        assert result.error is not None
        assert "execution_timeout_exceeded" in result.error

    async def test_worker_exception_returns_failed(self, enforcer, sample_proposal, allow_decision):
        cell = ExecutionCell(enforcer=enforcer, worker=failing_worker, max_time_ms=30000)
        result = await cell.execute(sample_proposal, allow_decision)
        assert result.status == "FAILED"
        assert "worker_crashed" in result.error

    async def test_execution_id_format(self, enforcer, sample_proposal, allow_decision):
        cell = ExecutionCell(enforcer=enforcer, worker=successful_worker, max_time_ms=30000)
        result = await cell.execute(sample_proposal, allow_decision)
        assert result.execution_id.startswith("cell-")

    async def test_result_types(self, enforcer, sample_proposal, allow_decision):
        cell = ExecutionCell(enforcer=enforcer, worker=successful_worker, max_time_ms=30000)
        result = await cell.execute(sample_proposal, allow_decision)
        assert isinstance(result, ExecutionResult)

    async def test_context_before_execute_is_none(self, enforcer):
        cell = ExecutionCell(enforcer=enforcer, worker=successful_worker, max_time_ms=30000)
        assert cell.context is None

    async def test_on_audit_called_for_capability_block(self, enforcer, sample_proposal, allow_decision):
        audit_events = []
        enforcer.restrict(Capability.FILESYSTEM_READ)
        cell = ExecutionCell(
            enforcer=enforcer, worker=successful_worker, max_time_ms=30000,
            on_audit=lambda e, p: audit_events.append((e, p)),
        )
        await cell.execute(sample_proposal, allow_decision)
        assert any(e == "capability_blocked" for e, _ in audit_events)

    async def test_on_audit_called_for_worker_error(self, enforcer, sample_proposal, allow_decision):
        audit_events = []
        cell = ExecutionCell(
            enforcer=enforcer, worker=failing_worker, max_time_ms=30000,
            on_audit=lambda e, p: audit_events.append((e, p)),
        )
        await cell.execute(sample_proposal, allow_decision)
        assert any(e == "execution_error" for e, _ in audit_events)

    async def test_timestamps_set(self, enforcer, sample_proposal, allow_decision):
        cell = ExecutionCell(enforcer=enforcer, worker=successful_worker, max_time_ms=30000)
        result = await cell.execute(sample_proposal, allow_decision)
        assert result.started_at > 0
        assert result.finished_at >= result.started_at
