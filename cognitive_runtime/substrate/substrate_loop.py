import asyncio
import dataclasses
import time
import uuid
from dataclasses import dataclass
from typing import Any, Callable, Optional

from ..contracts.execution_contract import (
    Capability,
    ExecutionProposal,
    ExecutionResult,
    HostEvent,
    PolicyDecision,
)
from ..kernel.time_kernel import TimeKernel
from .event_queue import EventQueue
from .observation_tap import ObservationTap


@dataclass
class Heartbeat:
    timestamp: float
    queue_depth: int
    last_decision: Optional[str]
    status: str
    uptime: float
    traced_events: int = 0
    completed_cycles: int = 0


class SubstrateLoop:
    def __init__(self, queue: EventQueue, time_kernel: TimeKernel,
                 p3_context_builder: Callable,
                 p4_authority: Callable,
                 worker: Callable,
                 tap: ObservationTap):
        self._queue = queue
        self._time = time_kernel
        self._p3 = p3_context_builder
        self._p4 = p4_authority
        self._worker = worker
        self._tap = tap
        self._running = False
        self._started_at: Optional[float] = None
        self._last_decision: Optional[str] = None

    # ──────────────────────────────────────────────
    #  Lifecycle
    # ──────────────────────────────────────────────

    async def run(self) -> None:
        self._running = True
        self._started_at = time.time()
        self._queue.open()

        while self._running:
            event = self._queue.pop()
            if event is None:
                await asyncio.sleep(0.1)
                continue

            try:
                await self._process_event(event)
            except Exception as e:
                enriched = self._tap.get_enriched(event.event_id)
                cid = enriched.correlation_id if enriched else ""
                self._queue.nack(event.event_id, str(e))
                self._tap.tap_execution_result(event.event_id, ExecutionResult(
                    execution_id="", proposal_id="", session_id=event.session_id,
                    correlation_id=cid,
                    status="FAILED", output=None, error=str(e),
                    started_at=time.time(), finished_at=time.time(),
                ))

        self._queue.close()

    async def _process_event(self, event: HostEvent) -> None:
        ts = self._time.stamp(event.event_id)

        # ── Tap: event received into pipeline ──
        self._tap.tap_event_received(event)

        # ── Extract correlation_id from tap (generated once per event) ──
        enriched = self._tap.get_enriched(event.event_id)
        correlation_id = enriched.correlation_id if enriched else str(uuid.uuid4())

        # Step 1: P3 Context Builder (no decision shaping)
        proposal: ExecutionProposal = await self._p3(event)
        proposal = dataclasses.replace(proposal, correlation_id=correlation_id)
        self._tap.tap_p3_proposal(event.event_id, proposal)

        # Step 2: P4 Policy Authority (single source of truth)
        decision: PolicyDecision = await self._p4(proposal)
        decision = dataclasses.replace(decision, correlation_id=correlation_id)
        self._queue.record_decision(decision)
        self._last_decision = decision.verdict

        # ── Tap: P4 decision captured (AFTER P4, BEFORE worker) ──
        self._tap.tap_p4_decision(event.event_id, decision)

        # Step 3: Execute only if ALLOWED
        if decision.verdict == "ALLOW":
            result: ExecutionResult = await self._execute(proposal, decision)
            result = dataclasses.replace(result, correlation_id=correlation_id)
            self._queue.ack(event.event_id, result)
            self._tap.tap_execution_result(event.event_id, result)
        else:
            reason = f"P4 blocked: {decision.verdict} - {decision.reason}"
            self._queue.nack(event.event_id, reason, proposal=proposal)
            self._tap.tap_blocked(event.event_id, reason)

    async def _execute(self, proposal: ExecutionProposal, decision: PolicyDecision) -> ExecutionResult:
        started = time.time()
        try:
            output = await self._worker(proposal, decision)
            return ExecutionResult(
                execution_id=f"exec-{proposal.proposal_id}",
                proposal_id=proposal.proposal_id,
                session_id=proposal.session_id,
                status="SUCCESS",
                output=output,
                error=None,
                started_at=started,
                finished_at=time.time(),
            )
        except Exception as e:
            return ExecutionResult(
                execution_id=f"exec-{proposal.proposal_id}",
                proposal_id=proposal.proposal_id,
                session_id=proposal.session_id,
                status="FAILED",
                output=None,
                error=str(e),
                started_at=started,
                finished_at=time.time(),
            )

    # ──────────────────────────────────────────────
    #  Control
    # ──────────────────────────────────────────────

    def stop(self) -> None:
        self._running = False

    def heartbeat(self) -> Heartbeat:
        uptime = (time.time() - self._started_at) if self._started_at else 0.0
        return Heartbeat(
            timestamp=time.time(),
            queue_depth=self._queue.queue_depth,
            last_decision=self._last_decision,
            status="running" if self._running else "stopped",
            uptime=uptime,
            traced_events=self._tap.total_traced,
            completed_cycles=self._tap.completed_cycles,
        )

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def tap(self) -> ObservationTap:
        return self._tap
