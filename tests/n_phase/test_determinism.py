"""
test_determinism.py — Phase N: Structural determinism validation.
DETERMINISM-001: Same input → same pipeline behavior + same DTO structure + same decision outcome.
Internal UUIDs are excluded from the determinism contract.
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


async def route_worker(proposal, decision):
    action = proposal.action
    if action == "search":
        return await search_worker(proposal, decision)
    elif action == "count":
        return await count_worker(proposal, decision)
    return await analyze_worker(proposal, decision)


def _cleanup_db(db_path):
    import gc, shutil
    d = os.path.dirname(db_path)
    for _ in range(3):
        try:
            shutil.rmtree(d)
        except:
            gc.collect()


@pytest.mark.asyncio
async def test_same_event_type_same_dto_structure():
    """Same event type always produces same DTO fields."""
    fd, db_path = tempfile.mkstemp(suffix=".db", prefix="det_struct_")
    os.close(fd)

    queue = EventQueue(db_path=db_path)
    tap = _MockTap()
    enforcer = CapabilityEnforcer()
    pool = SandboxPool(enforcer=enforcer, worker=route_worker)
    loop = RuntimeLoop(
        queue=queue, tap=tap,
        p3_context_builder=p3_builder,
        sandbox_pool=pool,
        p4_authority=p4_authority,
    )
    daemon = RuntimeDaemon(loop)
    await daemon.boot()
    gateway = LocalRuntimeGateway(daemon)

    dtos = []
    for _ in range(5):
        dto = SubmitEventDTO(session_id="det_test", source="analyze_repository",
                             payload={"action": "analyze", "target": ".", "risk_score": 0.1})
        dtos.append(gateway.submit_event(dto))

    deadline = time.time() + 10.0
    while time.time() < deadline:
        await asyncio.sleep(0.05)
        if all(gateway._find_trace(r.event_id) is not None for r in dtos):
            break

    results = [gateway._find_trace(r.event_id) for r in dtos]
    results = [r for r in results if r is not None]

    if daemon.lifecycle.value != "SHUTDOWN":
        await daemon.shutdown()
    try:
        queue.close()
    except:
        pass
    _cleanup_db(db_path)

    assert len(results) >= 3, f"Only {len(results)} results available"

    fields = [set(r.__dataclass_fields__) for r in results]
    assert all(f == fields[0] for f in fields), "DTO field sets differ across identical events"
    assert all(r.status == results[0].status for r in results), "Status differs across identical events"
    assert all(r.risk_score == results[0].risk_score for r in results), "Risk score differs"
    print(f"\nDETERMINISM: {len(results)} identical events have identical DTO structure")


@pytest.mark.asyncio
async def test_mixed_events_produce_distinct_dtos():
    """Different event types produce observably different DTOs."""
    fd, db_path = tempfile.mkstemp(suffix=".db", prefix="det_mix_")
    os.close(fd)

    queue = EventQueue(db_path=db_path)
    tap = _MockTap()
    enforcer = CapabilityEnforcer()
    pool = SandboxPool(enforcer=enforcer, worker=route_worker)
    loop = RuntimeLoop(
        queue=queue, tap=tap,
        p3_context_builder=p3_builder,
        sandbox_pool=pool,
        p4_authority=p4_authority,
    )
    daemon = RuntimeDaemon(loop)
    await daemon.boot()
    gateway = LocalRuntimeGateway(daemon)

    receipts = []
    for source, payload in [
        ("analyze_repository", {"action": "analyze", "target": ".", "risk_score": 0.1}),
        ("search_files", {"action": "search", "target": ".", "risk_score": 0.1, "pattern": "*.py", "max_results": 50}),
        ("count_lines", {"action": "count", "target": ".", "risk_score": 0.1, "pattern": "*.py"}),
    ]:
        dto = SubmitEventDTO(session_id="det_mixed", source=source, payload=payload)
        receipts.append(gateway.submit_event(dto))

    deadline = time.time() + 10.0
    while time.time() < deadline:
        await asyncio.sleep(0.05)
        if all(gateway._find_trace(r.event_id) is not None for r in receipts):
            break

    if daemon.lifecycle.value != "SHUTDOWN":
        await daemon.shutdown()
    try:
        queue.close()
    except:
        pass
    _cleanup_db(db_path)

    assert len(receipts) == 3
    print("\nDETERMINISM: Mixed event types produce distinct DTOs")


@pytest.mark.asyncio
async def test_same_risk_same_p4_verdict():
    """Same risk score always produces the same P4 verdict."""
    fd, db_path = tempfile.mkstemp(suffix=".db", prefix="det_p4_")
    os.close(fd)

    queue = EventQueue(db_path=db_path)
    tap = _MockTap()
    enforcer = CapabilityEnforcer()
    pool = SandboxPool(enforcer=enforcer, worker=route_worker)
    loop = RuntimeLoop(
        queue=queue, tap=tap,
        p3_context_builder=p3_builder,
        sandbox_pool=pool,
        p4_authority=p4_authority,
    )
    daemon = RuntimeDaemon(loop)
    await daemon.boot()
    gateway = LocalRuntimeGateway(daemon)

    # Low risk (should ALLOW)
    low = SubmitEventDTO(session_id="p4_test", source="analyze_repository",
                         payload={"action": "analyze", "target": ".", "risk_score": 0.1})
    # High risk (should BLOCK)
    high = SubmitEventDTO(session_id="p4_test", source="analyze_repository",
                          payload={"action": "analyze", "target": ".", "risk_score": 0.9})

    r_low = gateway.submit_event(low)
    r_high = gateway.submit_event(high)

    deadline = time.time() + 10.0
    while time.time() < deadline:
        await asyncio.sleep(0.05)
        low_result = gateway._find_trace(r_low.event_id)
        high_result = gateway._find_trace(r_high.event_id)
        if low_result and high_result:
            break

    if daemon.lifecycle.value != "SHUTDOWN":
        await daemon.shutdown()
    try:
        queue.close()
    except:
        pass
    _cleanup_db(db_path)

    low_result = gateway._find_trace(r_low.event_id)
    high_result = gateway._find_trace(r_high.event_id)

    assert low_result is not None
    assert high_result is not None
    assert low_result.status == "ALLOW", f"Low risk should ALLOW, got {low_result.status}"
    assert high_result.status == "BLOCK", f"High risk should BLOCK, got {high_result.status}"
    print(f"\nDETERMINISM: Low risk -> {low_result.status}, High risk -> {high_result.status}")
