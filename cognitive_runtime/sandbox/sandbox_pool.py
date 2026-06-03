"""
sandbox_pool.py — Pool of isolated Execution Cells.

Manages cell lifecycle:
  - Acquire cell from pool
  - Execute within isolated context
  - Release and recycle cell
  - No shared state between cells
"""

from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from ..contracts.execution_contract import ExecutionProposal, ExecutionResult, PolicyDecision
from .capability_enforcer import CapabilityEnforcer
from .execution_cell import ExecutionCell
from .resource_monitor import ResourceMonitor


@dataclass
class SandboxStats:
    active_cells: int = 0
    completed_cells: int = 0
    failed_cells: int = 0
    total_executions: int = 0


class SandboxPool:
    def __init__(self, enforcer: CapabilityEnforcer,
                 worker: Callable,
                 resource_monitor: Optional[ResourceMonitor] = None,
                 max_cells: int = 10,
                 default_timeout_ms: int = 30000,
                 on_audit: Optional[Callable[[str, dict[str, Any]], None]] = None):
        self._enforcer = enforcer
        self._worker = worker
        self._monitor = resource_monitor or ResourceMonitor()
        self._max_cells = max_cells
        self._default_timeout_ms = default_timeout_ms
        self._on_audit = on_audit
        self._active: list[ExecutionCell] = []
        self._stats = SandboxStats()

    def acquire(self) -> ExecutionCell:
        cell = ExecutionCell(
            enforcer=self._enforcer,
            worker=self._worker,
            max_time_ms=self._default_timeout_ms,
            on_audit=self._on_audit,
        )
        self._active.append(cell)
        return cell

    async def execute(self, proposal: ExecutionProposal,
                      decision: PolicyDecision) -> ExecutionResult:
        cell = self.acquire()
        self._stats.total_executions += 1

        guard = self._monitor.create_guard()

        preflight_check = self._monitor.pre_check({
            "action": proposal.action,
            "confidence": proposal.confidence,
        })
        if preflight_check:
            self._stats.failed_cells += 1
            self._release(cell)
            return ExecutionResult(
                execution_id="", proposal_id=proposal.proposal_id,
                session_id=proposal.session_id, status="FAILED",
                output=None, error=preflight_check,
                started_at=0.0, finished_at=0.0,
            )

        result = await cell.execute(proposal, decision)

        runtime_violation = self._monitor.check_time(guard, result.finished_at - result.started_at)
        finalize = self._monitor.finalize(guard)

        if runtime_violation:
            result = ExecutionResult(
                execution_id=result.execution_id,
                proposal_id=result.proposal_id,
                session_id=result.session_id,
                status="FAILED", output=result.output,
                error=runtime_violation,
                started_at=result.started_at,
                finished_at=result.finished_at,
            )

        if result.status == "SUCCESS":
            self._stats.completed_cells += 1
        else:
            self._stats.failed_cells += 1

        if self._on_audit:
            self._on_audit("cell_completed", {
                "execution_id": result.execution_id,
                "status": result.status,
                "resource_finalize": finalize,
            })

        self._release(cell)
        return result

    def _release(self, cell: ExecutionCell) -> None:
        if cell in self._active:
            self._active.remove(cell)

    @property
    def stats(self) -> SandboxStats:
        return self._stats

    @property
    def active_count(self) -> int:
        return len(self._active)
