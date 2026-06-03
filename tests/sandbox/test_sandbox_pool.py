import pytest

from cognitive_runtime.sandbox.sandbox_pool import SandboxPool, SandboxStats
from cognitive_runtime.sandbox.capability_enforcer import CapabilityEnforcer
from cognitive_runtime.contracts.execution_contract import (
    Capability,
    ExecutionProposal,
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
    raise RuntimeError("worker_failure")


@pytest.fixture
def success_pool(enforcer):
    return SandboxPool(enforcer=enforcer, worker=successful_worker)


@pytest.fixture
def fail_pool(enforcer):
    return SandboxPool(enforcer=enforcer, worker=failing_worker)


class TestSandboxStats:
    def test_defaults(self):
        stats = SandboxStats()
        assert stats.active_cells == 0
        assert stats.completed_cells == 0
        assert stats.failed_cells == 0
        assert stats.total_executions == 0

    def test_custom_values(self):
        stats = SandboxStats(active_cells=2, completed_cells=5, failed_cells=1, total_executions=6)
        assert stats.active_cells == 2
        assert stats.completed_cells == 5
        assert stats.failed_cells == 1
        assert stats.total_executions == 6


@pytest.mark.asyncio
class TestSandboxPool:
    async def test_acquire_returns_execution_cell(self, success_pool):
        cell = success_pool.acquire()
        from cognitive_runtime.sandbox.execution_cell import ExecutionCell
        assert isinstance(cell, ExecutionCell)

    async def test_acquire_increments_active_count(self, success_pool):
        initial = success_pool.active_count
        success_pool.acquire()
        assert success_pool.active_count == initial + 1

    async def test_execute_returns_success(self, success_pool, sample_proposal, allow_decision):
        result = await success_pool.execute(sample_proposal, allow_decision)
        assert result.status == "SUCCESS"
        assert result.output == {"result": "ok"}

    async def test_execute_increments_completed_cells(self, success_pool, sample_proposal, allow_decision):
        before = success_pool.stats.completed_cells
        await success_pool.execute(sample_proposal, allow_decision)
        assert success_pool.stats.completed_cells == before + 1

    async def test_execute_increments_total_executions(self, success_pool, sample_proposal, allow_decision):
        before = success_pool.stats.total_executions
        await success_pool.execute(sample_proposal, allow_decision)
        assert success_pool.stats.total_executions == before + 1

    async def test_execute_with_failing_worker(self, fail_pool, sample_proposal, allow_decision):
        result = await fail_pool.execute(sample_proposal, allow_decision)
        assert result.status == "FAILED"
        assert "worker_failure" in result.error

    async def test_execute_with_failing_worker_increments_failed(self, fail_pool, sample_proposal, allow_decision):
        before = fail_pool.stats.failed_cells
        await fail_pool.execute(sample_proposal, allow_decision)
        assert fail_pool.stats.failed_cells == before + 1

    async def test_execute_releases_cell(self, success_pool, sample_proposal, allow_decision):
        initial = success_pool.active_count
        await success_pool.execute(sample_proposal, allow_decision)
        assert success_pool.active_count == initial

    async def test_stats_property(self, success_pool):
        stats = success_pool.stats
        assert isinstance(stats, SandboxStats)

    async def test_active_count_property(self, success_pool):
        assert isinstance(success_pool.active_count, int)
        assert success_pool.active_count >= 0

    async def test_audit_called(self, enforcer, sample_proposal, allow_decision):
        audit_events = []
        pool = SandboxPool(
            enforcer=enforcer, worker=successful_worker,
            on_audit=lambda e, p: audit_events.append((e, p)),
        )
        await pool.execute(sample_proposal, allow_decision)
        assert any(e == "cell_completed" for e, _ in audit_events)

    async def test_multiple_executions(self, success_pool, sample_proposal, allow_decision):
        r1 = await success_pool.execute(sample_proposal, allow_decision)
        r2 = await success_pool.execute(sample_proposal, allow_decision)
        assert r1.status == "SUCCESS"
        assert r2.status == "SUCCESS"
        assert success_pool.stats.total_executions == 2
        assert success_pool.stats.completed_cells == 2

    async def test_low_confidence_does_not_block(self, enforcer, allow_decision):
        pool = SandboxPool(enforcer=enforcer, worker=successful_worker)
        low_conf_proposal = ExecutionProposal(
            proposal_id="p1", session_id="s1", event_id="e1",
            action="read", target="/tmp/file", params={},
            required_capabilities=[Capability.FILESYSTEM_READ],
            confidence=0.1, risk_score=0.1, metadata={},
        )
        result = await pool.execute(low_conf_proposal, allow_decision)
        assert result.status == "SUCCESS"
        assert pool.stats.failed_cells == 0
        assert pool.stats.completed_cells == 1
