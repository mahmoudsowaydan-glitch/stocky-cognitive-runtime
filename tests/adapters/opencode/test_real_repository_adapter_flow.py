import asyncio
import os
import tempfile
import time

import pytest

from cognitive_runtime.boot.first_boot import p3_builder, p4_authority, _MockTap
from cognitive_runtime.capabilities import analyze_worker, search_worker, count_worker
from cognitive_runtime.sandbox.capability_enforcer import CapabilityEnforcer
from cognitive_runtime.sandbox.sandbox_pool import SandboxPool
from cognitive_runtime.substrate.event_queue import EventQueue
from cognitive_runtime.runtime.runtime_loop import RuntimeLoop
from cognitive_runtime.runtime.daemon.runtime_daemon import RuntimeDaemon
from cognitive_runtime.runtime.gateway.local_runtime_gateway import (
    LocalRuntimeGateway,
)
from cognitive_runtime.adapters.opencode import OpenCodeAdapter


REPO_ROOT = os.path.abspath(".")


async def _route_worker(proposal, decision):
    action = proposal.action
    if action == "search":
        return await search_worker(proposal, decision)
    elif action == "count":
        return await count_worker(proposal, decision)
    return await analyze_worker(proposal, decision)


def _cleanup(db_path):
    import gc, shutil
    d = os.path.dirname(db_path)
    for _ in range(3):
        try:
            shutil.rmtree(d)
        except (PermissionError, FileNotFoundError):
            gc.collect()


@pytest.mark.asyncio
async def test_adapter_e2e_001_real_repository_flow():
    """ADAPTER-E2E-001: OpenCodeAdapter + real Runtime + real Repository.

    Full pipeline:
      Stocky Repository
        -> WorkspaceSnapshot
          -> OpenCodeAdapter
            -> LocalRuntimeGateway
              -> RuntimeDaemon -> RuntimeLoop -> Sandbox -> Capability
                -> PublicTraceDTO
    """
    fd, db_path = tempfile.mkstemp(
        suffix=".db", prefix="adapter_e2e_"
    )
    os.close(fd)

    try:
        queue = EventQueue(db_path=db_path)
        tap = _MockTap()
        enforcer = CapabilityEnforcer()
        pool = SandboxPool(
            enforcer=enforcer, worker=_route_worker
        )
        loop = RuntimeLoop(
            queue=queue,
            tap=tap,
            p3_context_builder=p3_builder,
            sandbox_pool=pool,
            p4_authority=p4_authority,
        )
        daemon = RuntimeDaemon(loop)
        await daemon.boot()
        gateway = LocalRuntimeGateway(daemon)

        adapter = OpenCodeAdapter(gateway, session_id="e2e_test")

        ws = adapter.capture_workspace(REPO_ROOT)
        assert ws.root_path == REPO_ROOT
        assert ws.collected_at > 0

        receipt = adapter.submit_analyze(ws.root_path)
        assert receipt.receipt_id != ""
        assert receipt.event_id != ""

        result = None
        deadline = time.time() + 15.0
        while time.time() < deadline:
            if daemon.lifecycle.value != "RUNNING":
                break
            result = adapter.poll_result(
                receipt.receipt_id, max_attempts=1
            )
            if result is not None:
                break
            await asyncio.sleep(0.1)

        assert result is not None, (
            "ADAPTER-E2E-001 FAILED: "
            "No PublicTraceDTO returned within deadline"
        )
        assert result.event_id != ""
        assert result.status in (
            "ALLOW", "BLOCK", "FAILED", "UNKNOWN"
        )
        assert result.total_time_ms >= 0

        assert not hasattr(result, "p4_verdict")
        assert not hasattr(result, "preflight_valid")
        assert not hasattr(result, "governance_score")

        assert daemon.lifecycle.value == "RUNNING"

    finally:
        try:
            if daemon and daemon.lifecycle.value != "SHUTDOWN":
                await daemon.shutdown()
        except Exception:
            pass
        try:
            queue.close()
        except Exception:
            pass
        _cleanup(db_path)
