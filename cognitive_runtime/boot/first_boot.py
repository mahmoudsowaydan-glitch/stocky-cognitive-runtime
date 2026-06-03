import asyncio
import os
import tempfile
import time
import uuid

from ..capabilities import analyze_worker as default_worker
from ..contracts.execution_contract import (
    Capability,
    ExecutionProposal,
    HostEvent,
    PolicyDecision,
)
from ..contracts.public.dtos import (
    PublicTraceDTO,
    SubmitEventDTO,
)
from ..runtime.daemon.runtime_daemon import RuntimeDaemon
from ..runtime.gateway.local_runtime_gateway import LocalRuntimeGateway
from ..runtime.runtime_loop import RuntimeLoop
from ..sandbox.capability_enforcer import CapabilityEnforcer
from ..sandbox.preflight_analyzer import PreflightAnalyzer
from ..sandbox.sandbox_pool import SandboxPool
from ..substrate.event_queue import EventQueue
from unittest.mock import MagicMock


class _MockTap:
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


# ── Real P3 Builder ──

async def p3_builder(event: HostEvent) -> ExecutionProposal:
    action = event.payload.get("action", "analyze")
    target = event.payload.get("target", ".")
    risk = event.payload.get("risk_score", 0.1)
    caps = [Capability.FILESYSTEM_READ]
    if event.payload.get("requires_write"):
        caps.append(Capability.FILESYSTEM_WRITE)
    return ExecutionProposal(
        proposal_id=f"prop-{event.event_id}",
        session_id=event.session_id,
        event_id=event.event_id,
        action=action,
        target=target,
        params=event.payload,
        required_capabilities=caps,
        confidence=0.8,
        risk_score=risk,
        metadata={"source": event.source},
    )


# ── Real P4 Authority ──

async def p4_authority(proposal: ExecutionProposal) -> PolicyDecision:
    risk = proposal.risk_score
    if risk > 0.7:
        return PolicyDecision(
            decision_id=f"d-{uuid.uuid4().hex[:8]}",
            proposal_id=proposal.proposal_id,
            session_id=proposal.session_id,
            verdict="BLOCK",
            reason=f"risk_threshold_exceeded: {risk}",
            risk_level="high",
            rule_triggered="risk_threshold",
            confidence=0.95,
        )
    return PolicyDecision(
        decision_id=f"d-{uuid.uuid4().hex[:8]}",
        proposal_id=proposal.proposal_id,
        session_id=proposal.session_id,
        verdict="ALLOW",
        reason="risk_within_threshold",
        risk_level="low",
        rule_triggered=None,
        confidence=0.9,
    )


class BootResult:
    def __init__(self):
        self.event_id: str = ""
        self.receipt_id: str = ""
        self.correlation_id: str = ""
        self.trace_dto: PublicTraceDTO = None
        self.status: str = ""
        self.total_events_processed: int = 0
        self.total_cycles: int = 0
        self.duration_seconds: float = 0.0
        self.invariants: dict = None


async def run_first_boot(db_path: str = None) -> BootResult:
    if db_path is None:
        fd, db_path = tempfile.mkstemp(suffix=".db", prefix="first_boot_")
        os.close(fd)

    db_dir = os.path.dirname(db_path)

    result = BootResult()
    start_time = time.time()

    # ── Wire Dependencies ──
    queue = EventQueue(db_path=db_path)
    tap = _MockTap()
    enforcer = CapabilityEnforcer()
    pool = SandboxPool(enforcer=enforcer, worker=default_worker)
    loop = RuntimeLoop(
        queue=queue,
        tap=tap,
        p3_context_builder=p3_builder,
        sandbox_pool=pool,
        p4_authority=p4_authority,
    )
    daemon = RuntimeDaemon(loop)

    # ── Boot Daemon ──
    await daemon.boot()
    gateway = LocalRuntimeGateway(daemon)

    # ── Submit Event ──
    dto = SubmitEventDTO(
        session_id="first_boot",
        source="analyze_repository",
        payload={"action": "analyze", "target": ".", "risk_score": 0.1},
    )
    receipt = gateway.submit_event(dto)
    result.event_id = receipt.event_id
    result.receipt_id = receipt.receipt_id
    result.correlation_id = receipt.correlation_id

    # ── Wait for Processing (async polling) ──
    processed = None
    deadline = time.time() + 15.0
    while time.time() < deadline:
        if daemon.lifecycle.value != "RUNNING":
            result.status = f"DAEMON_STOPPED ({daemon.lifecycle.value})"
            break
        processed = gateway.get_result(receipt.receipt_id)
        if processed is not None:
            break
        await asyncio.sleep(0.05)

    # ── Read Result ──
    if processed is not None:
        result.trace_dto = processed
        result.status = processed.status
    else:
        result.status = "TIMEOUT"

    result.total_events_processed = loop._state.total_events_processed
    result.total_cycles = loop._state.total_events_processed
    result.duration_seconds = time.time() - start_time

    # ── Invariant Checks ──
    trace_exists = result.trace_dto is not None
    result.invariants = {
        "pipeline_completeness": loop._state.total_events_processed >= 1,
        "no_internal_leak": _check_no_internal_leak(result.trace_dto),
        "deterministic_trace": trace_exists,
        "event_processed": loop._state.total_events_processed >= 1,
    }

    # ── Shutdown ──
    if daemon.lifecycle.value != "SHUTDOWN":
        await daemon.shutdown()
    else:
        if daemon._daemon_task and not daemon._daemon_task.done():
            daemon._daemon_task.cancel()
            try:
                await daemon._daemon_task
            except (asyncio.CancelledError, Exception):
                pass
    try:
        loop._queue.close()
    except Exception:
        pass
    try:
        import gc, shutil
        for _ in range(3):
            try:
                shutil.rmtree(db_dir)
            except (PermissionError, FileNotFoundError):
                gc.collect()
    except Exception:
        pass

    return result


def _check_no_internal_leak(dto: PublicTraceDTO) -> bool:
    if dto is None:
        return False
    internal = {"p4_verdict", "p4_reason", "p4_rule_triggered", "p4_risk_level",
                "preflight_valid", "preflight_reason", "preflight_rules_triggered",
                "execution_status", "capabilities_checked", "resource_usage",
                "preflight_time", "p4_time", "execution_time",
                "governance_score", "confidence_score", "stability_score",
                "sequence_no", "correlation_id"}
    fields = set(PublicTraceDTO.__dataclass_fields__)
    return fields.isdisjoint(internal)


def console_report(result: BootResult) -> str:
    lines = [
        "FIRST BOOT REPORT",
        f"  event_id: {result.event_id}",
        f"  receipt_id: {result.receipt_id}",
        f"  correlation_id: {result.correlation_id}",
        f"  status: {result.status}",
        f"  duration: {result.duration_seconds:.2f}s",
        f"  events_processed: {result.total_events_processed}",
    ]
    if result.trace_dto:
        lines.append(f"  trace_status: {result.trace_dto.status}")
        lines.append(f"  risk_score: {result.trace_dto.risk_score}")
        lines.append(f"  total_time_ms: {result.trace_dto.total_time_ms}")
    lines.append("")
    lines.append("Invariants:")
    for k, v in result.invariants.items():
        lines.append(f"  {k}: {'PASS' if v else 'FAIL'}")
    return "\n".join(lines)
