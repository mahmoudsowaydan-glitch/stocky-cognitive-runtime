"""
test_load_1000.py — Phase N Step 1: Sustained workload validation.
Success criteria: no panics, no crash, no lifecycle corruption, no memory violations.
Records structured metrics for PHASE_N_STEP1_REPORT.md.
"""

import asyncio
import os
import tempfile
import time

import pytest

from cognitive_runtime.boot.first_boot import p3_builder, p4_authority, _MockTap
from cognitive_runtime.capabilities import analyze_worker, search_worker, count_worker
from cognitive_runtime.contracts.public.dtos import SubmitEventDTO
from cognitive_runtime.runtime.daemon.runtime_daemon import RuntimeDaemon
from cognitive_runtime.runtime.gateway.local_runtime_gateway import LocalRuntimeGateway
from cognitive_runtime.runtime.runtime_loop import RuntimeLoop
from cognitive_runtime.sandbox.capability_enforcer import CapabilityEnforcer
from cognitive_runtime.sandbox.sandbox_pool import SandboxPool
from cognitive_runtime.substrate.event_queue import EventQueue


ANALYZE_PAYLOAD = {"action": "analyze", "target": ".", "risk_score": 0.1}
SEARCH_PAYLOAD = {"action": "search", "target": ".", "risk_score": 0.1, "pattern": "*.py", "max_results": 50}
COUNT_PAYLOAD = {"action": "count", "target": ".", "risk_score": 0.1, "pattern": "*.py"}
EVENT_TYPES = ["analyze_repository", "search_files", "count_lines"]


async def _route_worker(proposal, decision):
    action = proposal.action
    if action == "search":
        return await search_worker(proposal, decision)
    elif action == "count":
        return await count_worker(proposal, decision)
    return await analyze_worker(proposal, decision)


def _generate_payloads(count: int) -> list[dict]:
    payloads = []
    for i in range(count):
        source = EVENT_TYPES[i % len(EVENT_TYPES)]
        if source == "analyze_repository":
            payload = dict(ANALYZE_PAYLOAD)
        elif source == "search_files":
            payload = dict(SEARCH_PAYLOAD)
        elif source == "count_lines":
            payload = dict(COUNT_PAYLOAD)
        payloads.append({"source": source, "payload": payload})
    return payloads


def _cleanup_db(db_path: str) -> None:
    import gc, shutil
    d = os.path.dirname(db_path)
    for _ in range(3):
        try:
            shutil.rmtree(d)
        except (PermissionError, FileNotFoundError):
            gc.collect()


def _traces_completed(receipts: list, gateway) -> int:
    count = 0
    for r in receipts:
        if gateway._find_trace(r.event_id):
            count += 1
    return count


def _collect_metrics(loop, daemon, receipts, gateway, start_time, submit_times) -> dict:
    completed_count = _traces_completed(receipts, gateway)
    elapsed = time.time() - start_time

    successes = 0
    failures = 0
    latencies = []
    for r in receipts:
        trace = gateway._find_trace(r.event_id)
        if trace:
            if trace.status in ("ALLOW", "BLOCK"):
                successes += 1
            else:
                failures += 1
            if r.event_id in submit_times:
                latencies.append((time.time() - submit_times[r.event_id]) * 1000)

    return {
        "total_submitted": len(receipts),
        "completed": completed_count,
        "successes": successes,
        "failures": failures,
        "panics": daemon._panic_count,
        "recoveries": daemon._recovery_count,
        "avg_latency_ms": (sum(latencies) / len(latencies)) if latencies else 0.0,
        "total_elapsed_s": round(elapsed, 1),
        "events_per_second": round(completed_count / elapsed, 1) if elapsed > 0 else 0.0,
        "final_lifecycle": daemon.lifecycle.value,
        "cycle_count": daemon.status.cycle_count,
    }


@pytest.mark.asyncio
async def test_1000_events_no_panics():
    """1000 events with full metrics recording for Phase N Step 1."""
    fd, db_path = tempfile.mkstemp(suffix=".db", prefix="load_1000_")
    os.close(fd)

    queue = EventQueue(db_path=db_path)
    tap = _MockTap()
    enforcer = CapabilityEnforcer()
    pool = SandboxPool(enforcer=enforcer, worker=_route_worker)
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
    submit_times = {}
    for p in payloads:
        dto = SubmitEventDTO(session_id="load_test", source=p["source"], payload=p["payload"])
        r = gateway.submit_event(dto)
        receipts.append(r)
        submit_times[r.event_id] = time.time()

    start_time = time.time()
    deadline = start_time + 120.0
    completed = 0
    lifecycle_corrupted = False
    while time.time() < deadline and completed < len(receipts):
        await asyncio.sleep(0.05)
        if daemon.lifecycle.value not in ("RUNNING", "SHUTDOWN"):
            lifecycle_corrupted = True
            break
        completed = _traces_completed(receipts, gateway)

    metrics = _collect_metrics(loop, daemon, receipts, gateway, start_time, submit_times)
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
    assert len(loop._traces) == metrics["completed"]

    print(f"\n=== LOAD 1000 METRICS ===")
    for k, v in metrics.items():
        print(f"  {k}: {v}")
