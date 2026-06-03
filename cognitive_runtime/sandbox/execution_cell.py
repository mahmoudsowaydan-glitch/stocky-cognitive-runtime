"""
execution_cell.py — Isolated Execution Unit.

Wraps a worker in:
  - Immutable context (no mutation of proposal/decision)
  - Capability gate
  - Timeout enforcement
  - Side-effect audit
Produces ExecutionResult with full traceability.
"""

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from ..contracts.execution_contract import (
    Capability,
    ExecutionProposal,
    ExecutionResult,
    PolicyDecision,
)
from .capability_enforcer import CapabilityEnforcer, EnforcementVerdict


@dataclass
class CellContext:
    cell_id: str
    proposal: ExecutionProposal
    decision: PolicyDecision
    created_at: float
    frozen: bool = False


class ExecutionCell:
    def __init__(self, enforcer: CapabilityEnforcer,
                 worker: Callable,
                 max_time_ms: int = 30000,
                 on_audit: Optional[Callable[[str, dict[str, Any]], None]] = None):
        self._enforcer = enforcer
        self._worker = worker
        self._max_time_ms = max_time_ms
        self._on_audit = on_audit
        self._context: Optional[CellContext] = None

    async def execute(self, proposal: ExecutionProposal,
                      decision: PolicyDecision) -> ExecutionResult:
        self._context = CellContext(
            cell_id=str(uuid.uuid4()),
            proposal=proposal,
            decision=decision,
            created_at=time.time(),
        )

        enforcement = self._enforcer.check(proposal.required_capabilities)
        if enforcement.verdict == EnforcementVerdict.BLOCK:
            self._audit("capability_blocked", {
                "cell_id": self._context.cell_id,
                "capability": enforcement.capability,
                "reason": enforcement.reason,
            })
            return ExecutionResult(
                execution_id=f"cell-{self._context.cell_id}",
                proposal_id=proposal.proposal_id,
                session_id=proposal.session_id,
                status="FAILED",
                output=None,
                error=f"capability_blocked: {enforcement.reason}",
                started_at=self._context.created_at,
                finished_at=time.time(),
            )

        self._context.frozen = True

        started = time.time()
        try:
            output = await asyncio.wait_for(
                self._worker(proposal, decision),
                timeout=self._max_time_ms / 1000,
            )
            return ExecutionResult(
                execution_id=f"cell-{self._context.cell_id}",
                proposal_id=proposal.proposal_id,
                session_id=proposal.session_id,
                status="SUCCESS",
                output=output,
                error=None,
                started_at=started,
                finished_at=time.time(),
            )
        except asyncio.TimeoutError:
            self._audit("timeout", {"cell_id": self._context.cell_id, "max_time_ms": self._max_time_ms})
            return ExecutionResult(
                execution_id=f"cell-{self._context.cell_id}",
                proposal_id=proposal.proposal_id,
                session_id=proposal.session_id,
                status="FAILED",
                output=None,
                error=f"execution_timeout_exceeded_{self._max_time_ms}ms",
                started_at=started,
                finished_at=time.time(),
            )
        except Exception as e:
            self._audit("execution_error", {"cell_id": self._context.cell_id, "error": str(e)})
            return ExecutionResult(
                execution_id=f"cell-{self._context.cell_id}",
                proposal_id=proposal.proposal_id,
                session_id=proposal.session_id,
                status="FAILED",
                output=None,
                error=str(e),
                started_at=started,
                finished_at=time.time(),
            )

    def _audit(self, event_type: str, payload: dict[str, Any]) -> None:
        if self._on_audit:
            self._on_audit(event_type, payload)

    @property
    def context(self) -> Optional[CellContext]:
        return self._context
