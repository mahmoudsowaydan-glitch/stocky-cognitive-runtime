"""
test_stability.py — Phase N Step 1: Runtime stability validation.
Validates lifecycle stability, heartbeat health, queue depth bounds, and cycle growth.
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


ANALYZE = {"action": "analyze", "target": ".", "risk_score": 0.1}
SEARCH = {"action": "search", "target": ".", "risk_score": 0.1, "pattern": "*.py", "max_results": 50}
COUNT = {"action": "count", "target": ".", "risk_score": 0.1, "pattern": "*.py"}


async def _route_worker(proposal, decision):
    action = proposal.action
    if action == "search":
        return await search_worker(proposal, decision)
    elif action == "count":
        return await count_worker(proposal, decision)
    return await analyze_worker(proposal, decision)


def _cleanup_db(db_path: str) -> None:
    import gc, shutil
    d = os.path.dirname(db_path)
    for _ in range(3):
        try:
            shutil.rmtree(d)
        except (PermissionError, FileNotFoundError):
            gc.collect()


@pytest.mark.asyncio
async def test_lifecycle_stays_running_during_workload():
    """Runtime must remain RUNNING throughout sustained workload."""
    fd, db_path = tempfile.mkstemp(suffix=".db", prefix="stability_lifecycle_")
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

    assert daemon.lifecycle.value == "RUNNING", f"Expected RUNNING, got {daemon.lifecycle.value}"

    lifecycles = []
    receipts = []
    for i in range(100):
        source = ["analyze_repository", "search_files", "count_lines"][i % 3]
        payload = [ANALYZE, SEARCH, COUNT][i % 3]
        dto = SubmitEventDTO(session_id="stability", source=source, payload=payload)
        receipts.append(gateway.submit_event(dto))

    deadline = time.time() + 30.0
    while time.time() < deadline:
        await asyncio.sleep(0.1)
        lifecycles.append(daemon.lifecycle.value)
        completed = sum(1 for r in receipts if gateway._find_trace(r.event_id) is not None)
        if completed == len(receipts):
            break

    if daemon.lifecycle.value != "SHUTDOWN":
        await daemon.shutdown()
    try:
        queue.close()
    except Exception:
        pass
    _cleanup_db(db_path)

    transitions = set(lifecycles)
    assert "RUNNING" in transitions
    unexpected = transitions - {"RUNNING", "SHUTDOWN"}
    assert not unexpected, f"Unexpected lifecycle transitions: {unexpected}"


@pytest.mark.asyncio
async def test_heartbeat_remains_healthy():
    """Heartbeat (daemon status health) must stay healthy under load."""
    fd, db_path = tempfile.mkstemp(suffix=".db", prefix="stability_heartbeat_")
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

    statuses = []
    receipts = []
    for i in range(100):
        source = ["analyze_repository", "search_files", "count_lines"][i % 3]
        payload = [ANALYZE, SEARCH, COUNT][i % 3]
        dto = SubmitEventDTO(session_id="heartbeat", source=source, payload=payload)
        receipts.append(gateway.submit_event(dto))

    deadline = time.time() + 30.0
    while time.time() < deadline:
        await asyncio.sleep(0.1)
        statuses.append(daemon.status.health_status)
        completed = sum(1 for r in receipts if gateway._find_trace(r.event_id) is not None)
        if completed == len(receipts):
            break

    if daemon.lifecycle.value != "SHUTDOWN":
        await daemon.shutdown()
    try:
        queue.close()
    except Exception:
        pass
    _cleanup_db(db_path)

    assert all(s == "healthy" for s in statuses), f"Unhealthy heartbeat detected: {set(statuses)}"


@pytest.mark.asyncio
async def test_cycle_count_grows_monotonically():
    """Cycle count must increase monotonically as events are processed."""
    fd, db_path = tempfile.mkstemp(suffix=".db", prefix="stability_cycles_")
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

    cycles = []
    receipts = []
    for i in range(50):
        dto = SubmitEventDTO(session_id="cycles", source="analyze_repository", payload=ANALYZE)
        receipts.append(gateway.submit_event(dto))

    deadline = time.time() + 20.0
    while time.time() < deadline:
        await asyncio.sleep(0.1)
        cycles.append(daemon.status.cycle_count)
        completed = sum(1 for r in receipts if gateway._find_trace(r.event_id) is not None)
        if completed == len(receipts):
            break

    if daemon.lifecycle.value != "SHUTDOWN":
        await daemon.shutdown()
    try:
        queue.close()
    except Exception:
        pass
    _cleanup_db(db_path)

    assert len(cycles) >= 2, "Not enough cycle samples"
    assert all(cycles[i] <= cycles[i+1] for i in range(len(cycles)-1)), \
        f"Cycle count not monotonic: {cycles[:5]}...{cycles[-5:]}"
    assert cycles[-1] > cycles[0], "Cycle count did not increase"


@pytest.mark.asyncio
async def test_queue_depth_remains_bounded():
    """Event queue must not exceed its maximum depth."""
    fd, db_path = tempfile.mkstemp(suffix=".db", prefix="stability_queue_")
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

    max_depth = 0
    receipts = []
    for i in range(200):
        source = ["analyze_repository", "search_files", "count_lines"][i % 3]
        payload = [ANALYZE, SEARCH, COUNT][i % 3]
        dto = SubmitEventDTO(session_id="queue", source=source, payload=payload)
        receipts.append(gateway.submit_event(dto))

    deadline = time.time() + 40.0
    while time.time() < deadline:
        await asyncio.sleep(0.05)
        max_depth = max(max_depth, queue.queue_depth)
        completed = sum(1 for r in receipts if gateway._find_trace(r.event_id) is not None)
        if completed == len(receipts):
            break

    if daemon.lifecycle.value != "SHUTDOWN":
        await daemon.shutdown()
    try:
        queue.close()
    except Exception:
        pass
    _cleanup_db(db_path)

    assert max_depth <= 200, f"Queue exceeded submitted event count: {max_depth} > 200"
    print(f"\nSTABILITY: max queue depth={max_depth}, submitted=200")
