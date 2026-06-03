"""
test_capability_workload.py — Phase N Step 2: Mixed capability workload.
1000+ events across all 5 registered capabilities: analyze, search, count,
discover_tests, generate_report.
"""

import asyncio
import os
import tempfile
import time

import pytest

from cognitive_runtime.boot.first_boot import p3_builder, p4_authority, _MockTap
from cognitive_runtime.capabilities import CapabilityRegistry
from cognitive_runtime.capabilities import analyze_worker, count_worker
from cognitive_runtime.capabilities.report import execute as report_execute
from cognitive_runtime.capabilities.search import search_worker
from cognitive_runtime.capabilities.discovery import execute as discovery_execute
from cognitive_runtime.contracts.public.dtos import SubmitEventDTO
from cognitive_runtime.runtime.daemon.runtime_daemon import RuntimeDaemon
from cognitive_runtime.runtime.gateway.local_runtime_gateway import LocalRuntimeGateway
from cognitive_runtime.runtime.runtime_loop import RuntimeLoop
from cognitive_runtime.sandbox.capability_enforcer import CapabilityEnforcer
from cognitive_runtime.sandbox.sandbox_pool import SandboxPool
from cognitive_runtime.substrate.event_queue import EventQueue


ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "cognitive_runtime")


async def _capability_router(proposal, decision):
    """Route using CapabilityRegistry for all 5 actions."""
    reg = CapabilityRegistry()
    worker = reg.resolve(proposal.action)
    if worker:
        return await worker(proposal, decision)
    return {"error": f"Unknown capability: {proposal.action}", "status": "FAILED"}


CAPABILITY_PAYLOADS = [
    {"source": "analyze_repository", "payload": {"action": "analyze", "target": ROOT, "risk_score": 0.1}},
    {"source": "search_files", "payload": {"action": "search", "target": ROOT, "risk_score": 0.1, "pattern": "*.py", "max_results": 30}},
    {"source": "count_lines", "payload": {"action": "count", "target": ROOT, "risk_score": 0.1, "pattern": "*.py"}},
    {"source": "discover_tests", "payload": {"action": "discover_tests", "target": ROOT, "risk_score": 0.1, "test_pattern": "test_*.py"}},
    {"source": "generate_report", "payload": {"action": "generate_report", "target": ROOT, "risk_score": 0.1, "max_depth": 2}},
]


def _generate_payloads(count: int) -> list[dict]:
    return [CAPABILITY_PAYLOADS[i % len(CAPABILITY_PAYLOADS)] for i in range(count)]


def _cleanup_db(db_path: str) -> None:
    import gc, shutil
    d = os.path.dirname(db_path)
    for _ in range(3):
        try:
            shutil.rmtree(d)
        except (PermissionError, FileNotFoundError):
            gc.collect()


def _collect_metrics(receipts, gateway, start_time) -> dict:
    completed_count = 0
    successes = 0
    failures = 0
    for r in receipts:
        trace = gateway._find_trace(r.event_id)
        if trace:
            completed_count += 1
            if trace.status in ("ALLOW", "BLOCK"):
                successes += 1
            else:
                failures += 1
    elapsed = time.time() - start_time
    return {
        "total_submitted": len(receipts),
        "completed": completed_count,
        "successes": successes,
        "failures": failures,
        "total_elapsed_s": round(elapsed, 1),
        "events_per_second": round(completed_count / elapsed, 1) if elapsed > 0 else 0.0,
    }


@pytest.mark.asyncio
async def test_mixed_capability_workload():
    """1000 events across all 5 capability types."""
    fd, db_path = tempfile.mkstemp(suffix=".db", prefix="cap_workload_")
    os.close(fd)

    queue = EventQueue(db_path=db_path)
    tap = _MockTap()
    enforcer = CapabilityEnforcer()
    pool = SandboxPool(enforcer=enforcer, worker=_capability_router)
    loop = RuntimeLoop(
        queue=queue, tap=tap,
        p3_context_builder=p3_builder,
        sandbox_pool=pool,
        p4_authority=p4_authority,
    )
    daemon = RuntimeDaemon(loop)
    await daemon.boot()
    gateway = LocalRuntimeGateway(daemon)

    payloads = _generate_payloads(1000)
    receipts = []
    for p in payloads:
        dto = SubmitEventDTO(session_id="cap_workload", source=p["source"], payload=p["payload"])
        receipts.append(gateway.submit_event(dto))

    start_time = time.time()
    deadline = start_time + 300.0
    completed = 0
    lifecycle_corrupted = False
    while time.time() < deadline and completed < len(receipts):
        await asyncio.sleep(0.05)
        if daemon.lifecycle.value not in ("RUNNING", "SHUTDOWN"):
            lifecycle_corrupted = True
            break
        completed = sum(1 for r in receipts if gateway._find_trace(r.event_id) is not None)

    metrics = _collect_metrics(receipts, gateway, start_time)
    metrics["panics"] = daemon._panic_count
    metrics["recoveries"] = daemon._recovery_count
    metrics["final_lifecycle"] = daemon.lifecycle.value
    metrics["lifecycle_corrupted"] = lifecycle_corrupted

    if daemon.lifecycle.value != "SHUTDOWN":
        await daemon.shutdown()
    try:
        queue.close()
    except Exception:
        pass
    _cleanup_db(db_path)

    assert metrics["panics"] == 0, f"Daemon panicked: {metrics['panics']}"
    assert not lifecycle_corrupted, "Lifecycle left RUNNING during workload"
    assert metrics["recoveries"] == 0, f"Unexpected recoveries: {metrics['recoveries']}"
    assert metrics["completed"] >= 950, f"Only {metrics['completed']}/1000 events completed"

    print(f"\n=== CAPABILITY WORKLOAD METRICS ===")
    for k, v in metrics.items():
        print(f"  {k}: {v}")
