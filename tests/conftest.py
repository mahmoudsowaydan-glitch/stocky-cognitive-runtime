import gc
import os
import shutil
import sys
import tempfile
import uuid
from typing import Any, Callable, Dict, List, Optional

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from cognitive_runtime.contracts.execution_contract import (
    Capability, ExecutionProposal, ExecutionResult, HostEvent, PolicyDecision,
)
from cognitive_runtime.contracts.execution_trace import ExecutionTrace
from cognitive_runtime.contracts.causal_graph import CausalGraphBuilder
from cognitive_runtime.substrate.event_queue import EventQueue
from cognitive_runtime.substrate.observation_tap import ObservationTap
from cognitive_runtime.kernel.time_kernel import TimeKernel


# ── Fixtures: Temporary Directories ──

@pytest.fixture
def tmp_dir():
    path = tempfile.mkdtemp()
    yield path
    for _ in range(3):
        try:
            shutil.rmtree(path)
        except PermissionError:
            gc.collect()


@pytest.fixture
def db_path(tmp_dir):
    return os.path.join(tmp_dir, "test_queue.db")


# ── Fixtures: Kernel ──

@pytest.fixture
def time_kernel():
    return TimeKernel()


# ── Fixtures: Core Contracts ──

@pytest.fixture
def sample_host_event():
    return HostEvent(
        event_id="e1", session_id="s1", timestamp=1000.0,
        source="test", payload={"cmd": "test"},
    )


@pytest.fixture
def sample_proposal():
    return ExecutionProposal(
        proposal_id="p1", session_id="s1", event_id="e1",
        action="read", target="/tmp/file",
        params={"path": "/tmp/file"},
        required_capabilities=[Capability.FILESYSTEM_READ],
        confidence=0.8, risk_score=0.1,
        metadata={"source": "test"},
    )


@pytest.fixture
def sample_decision_allow():
    return PolicyDecision(
        decision_id="d1", proposal_id="p1", session_id="s1",
        verdict="ALLOW", reason="ok", risk_level="low",
        rule_triggered=None, confidence=0.9,
    )


@pytest.fixture
def sample_decision_block():
    return PolicyDecision(
        decision_id="d2", proposal_id="p1", session_id="s1",
        verdict="BLOCK", reason="policy_violation", risk_level="high",
        rule_triggered="rule_42", confidence=0.95,
    )


@pytest.fixture
def sample_result_success():
    return ExecutionResult(
        execution_id="ex1", proposal_id="p1", session_id="s1",
        status="SUCCESS", output={"data": "ok"}, error=None,
        started_at=1000.0, finished_at=1001.0,
    )


@pytest.fixture
def sample_result_failed():
    return ExecutionResult(
        execution_id="ex2", proposal_id="p1", session_id="s1",
        status="FAILED", output=None, error="execution_error",
        started_at=1000.0, finished_at=1000.5,
    )


# ── Fixtures: Complex Objects ──

@pytest.fixture
def sample_trace_allow():
    return ExecutionTrace(
        event_id="e1", session_id="s1", sequence_no=1,
        correlation_id="c1",
        preflight_valid=True, preflight_reason="preflight_passed",
        risk_score=0.1,
        p4_verdict="ALLOW", p4_reason="ok", p4_risk_level="low",
        execution_status="SUCCESS",
        final_status="P4_ALLOW",
    )


@pytest.fixture
def sample_trace_blocked():
    return ExecutionTrace(
        event_id="e2", session_id="s1", sequence_no=2,
        correlation_id="c2",
        preflight_valid=True, preflight_reason="preflight_passed",
        risk_score=0.8,
        p4_verdict="BLOCK", p4_reason="policy_violation",
        p4_risk_level="high", p4_rule_triggered="rule_42",
        execution_status="UNKNOWN",
        final_status="P4_BLOCK",
    )


@pytest.fixture
def sample_trace_failed():
    return ExecutionTrace(
        event_id="e3", session_id="s1", sequence_no=3,
        correlation_id="c3",
        preflight_valid=True, preflight_reason="preflight_passed",
        risk_score=0.5,
        p4_verdict="ALLOW", p4_reason="ok", p4_risk_level="medium",
        execution_status="FAILED",
        execution_error="sandbox_crash",
        final_status="SANDBOX_FAILED",
    )


@pytest.fixture
def sample_traces_10(sample_trace_allow):
    return [
        ExecutionTrace(
            event_id=f"e{i}", session_id="s1", sequence_no=i,
            correlation_id=f"c{i}",
            preflight_valid=True, preflight_reason="preflight_passed",
            risk_score=0.1,
            p4_verdict="ALLOW", p4_reason="ok", p4_risk_level="low",
            execution_status="SUCCESS",
            final_status="P4_ALLOW",
        ) for i in range(10)
    ]


# ── Fixtures: Event Queue ──

@pytest.fixture
def event_queue(db_path):
    q = EventQueue(db_path=db_path)
    q.open()
    yield q
    q.close()


# ── Fixtures: Causal Graph ──

@pytest.fixture
def causal_builder():
    return CausalGraphBuilder()


@pytest.fixture
def sample_graph(causal_builder, sample_traces_10):
    return causal_builder.build(sample_traces_10)


# ── Fixtures: Observation Tap ──

@pytest.fixture
def obs_tap(time_kernel):
    return ObservationTap(time_kernel)


# ── Helper: Async P3 Context Builder ──

async def mock_p3(event: HostEvent) -> ExecutionProposal:
    return ExecutionProposal(
        proposal_id=f"prop-{event.event_id}",
        session_id=event.session_id,
        event_id=event.event_id,
        action=event.payload.get("action", "read"),
        target=event.payload.get("target", "/tmp/test"),
        params=event.payload,
        required_capabilities=[Capability.FILESYSTEM_READ],
        confidence=0.8,
        risk_score=0.1,
        metadata={"source": event.source},
    )


@pytest.fixture
def mock_p3_fn():
    return mock_p3
