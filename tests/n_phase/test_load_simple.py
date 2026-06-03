"""Minimal reproduction of load test issue."""
import asyncio, os, tempfile, time

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


def _generate_payloads(count):
    payloads = []
    types = ["analyze_repository", "search_files", "count_lines"]
    for i in range(count):
        s = types[i % 3]
        if s == "analyze_repository":
            p = {"action": "analyze", "target": ".", "risk_score": 0.1}
        elif s == "search_files":
            p = {"action": "search", "target": ".", "risk_score": 0.1, "pattern": "*.py", "max_results": 50}
        else:
            p = {"action": "count", "target": ".", "risk_score": 0.1, "pattern": "*.py"}
        payloads.append({"source": s, "payload": p})
    return payloads


def _cleanup_db(db_path):
    import gc, shutil
    d = os.path.dirname(db_path)
    for _ in range(3):
        try:
            shutil.rmtree(d)
        except:
            gc.collect()


@pytest.mark.asyncio
async def test_debug_5():
    """Run 5 events with debug output."""
    fd, db_path = tempfile.mkstemp(suffix=".db", prefix="dbg_")
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

    print(f"\nBoot done: lifecycle={daemon.lifecycle.value}", flush=True)
    print(f"Daemon task: {daemon._daemon_task}", flush=True)

    payloads = _generate_payloads(5)
    receipts = []
    for p in payloads:
        dto = SubmitEventDTO(session_id="dbg", source=p["source"], payload=p["payload"])
        r = gateway.submit_event(dto)
        receipts.append(r)

    print(f"Submitted {len(receipts)} events, lifecycle={daemon.lifecycle.value}", flush=True)

    for i in range(100):
        await asyncio.sleep(0.05)
        if daemon.lifecycle.value != "RUNNING":
            print(f"  Iter {i}: DAEMON STOPPED: {daemon.lifecycle.value}", flush=True)
            print(f"  Panic count: {daemon._panic_count}", flush=True)
            break
        completed = sum(1 for r in receipts if gateway.get_result(r.receipt_id) is not None)
        if completed == len(receipts):
            print(f"  Iter {i}: ALL {completed} events completed", flush=True)
            break
        if i % 20 == 0:
            print(f"  Iter {i}: completed={completed}, traces={len(loop._traces)}", flush=True)

    print(f"Final: traces={len(loop._traces)}, lifecycle={daemon.lifecycle.value}", flush=True)
    print(f"Panics: {daemon._panic_count}, Recoveries: {daemon._recovery_count}", flush=True)

    if daemon.lifecycle.value != "SHUTDOWN":
        await daemon.shutdown()
    try:
        queue.close()
    except:
        pass
    _cleanup_db(db_path)

