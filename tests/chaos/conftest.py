"""
Chaos test fixtures — shared across diagnostic and survival suites.
"""

import os
import tempfile
from unittest.mock import MagicMock, AsyncMock

import pytest

from cognitive_runtime.contracts.execution_contract import (
    Capability, ExecutionProposal, ExecutionResult, HostEvent, PolicyDecision,
)
from cognitive_runtime.contracts.execution_trace import ExecutionTrace
from cognitive_runtime.runtime.runtime_loop import RuntimeLoop
from cognitive_runtime.runtime.runtime_state import RuntimeState
from cognitive_runtime.recovery.checkpoint_manager import CheckpointManager
from cognitive_runtime.recovery.runtime_snapshot import RuntimeSnapshot
from cognitive_runtime.recovery.recovery_coordinator import RecoveryCoordinator
from chaos.harness.fault_injector import FaultInjector
from chaos.harness.wal_mutator import WALMutator
from chaos.harness.causal_mutator import CausalMutator
from chaos.harness.timing_distorter import TimingDistorter


class MockEventQueue:
    """Simple mock queue with configurable side effects."""

    def __init__(self):
        self._events = []
        self._pop_side_effect = None
        self.stats = MagicMock()
        self.stats.processed = 0
        self.stats.dead = 0
        self._nack_calls = []
        self._ack_calls = []

    def push(self, event):
        self._events.append(event)
        return event.event_id

    def pop(self, timeout=1.0):
        if self._pop_side_effect:
            if isinstance(self._pop_side_effect, list):
                if self._pop_side_effect:
                    return self._pop_side_effect.pop(0)
                return None
            return self._pop_side_effect
        if self._events:
            return self._events.pop(0)
        return None

    def ack(self, event_id):
        self._ack_calls.append(event_id)

    def nack(self, event_id, error, proposal=None):
        self._nack_calls.append((event_id, error))

    def dead_letter_count(self):
        return self.stats.dead

    def open(self):
        pass

    def close(self):
        pass


class MockSandboxPool:
    def __init__(self):
        self.execute = AsyncMock(return_value=ExecutionResult(
            execution_id="ex1", proposal_id="p1", session_id="s1",
            status="SUCCESS", output={}, error=None,
            started_at=0.0, finished_at=0.1,
        ))
        self._available = 5

    async def acquire(self, *args, **kwargs):
        return MagicMock()

    def release(self, cell):
        pass

    @property
    def available_count(self):
        return self._available


class MockObservationTap:
    def __init__(self):
        self.observe = MagicMock()
        self.emit = MagicMock()


@pytest.fixture
def tmp_dir():
    path = tempfile.mkdtemp()
    yield path
    import gc, shutil
    for _ in range(3):
        try:
            shutil.rmtree(path)
        except (PermissionError, FileNotFoundError):
            gc.collect()


@pytest.fixture
def checkpoint_dir(tmp_dir):
    return os.path.join(tmp_dir, "checkpoints")


@pytest.fixture
def checkpoint_manager(checkpoint_dir):
    return CheckpointManager(checkpoint_dir=checkpoint_dir, max_checkpoints=10)


@pytest.fixture
def fault_injector(event_queue):
    return FaultInjector(event_queue, seed=42)


@pytest.fixture
def wal_mutator(checkpoint_dir):
    return WALMutator(checkpoint_dir, seed=42)


@pytest.fixture
def causal_mutator():
    return CausalMutator(seed=42)


@pytest.fixture
def timing_distorter():
    return TimingDistorter(seed=42)


@pytest.fixture
def sample_event():
    return HostEvent(
        event_id="e1", session_id="s1", timestamp=1000.0,
        source="test", payload={"cmd": "test"},
    )


@pytest.fixture
def sample_proposal():
    return ExecutionProposal(
        proposal_id="p1", session_id="s1", event_id="e1",
        action="read", target="/tmp/file",
        params={}, required_capabilities=[Capability.FILESYSTEM_READ],
        confidence=0.8, risk_score=0.1, metadata={},
    )


@pytest.fixture
def sample_decision_allow():
    return PolicyDecision(
        decision_id="d1", proposal_id="p1", session_id="s1",
        verdict="ALLOW", reason="ok", risk_level="low",
        rule_triggered=None, confidence=0.9,
    )


@pytest.fixture
def sample_trace_allow():
    return ExecutionTrace(
        event_id="e1", session_id="s1", sequence_no=1,
        correlation_id="c1",
        preflight_valid=True, preflight_reason="ok",
        risk_score=0.1,
        p4_verdict="ALLOW", p4_reason="ok", p4_risk_level="low",
        execution_status="SUCCESS",
        final_status="P4_ALLOW",
    )


def make_traces(count: int, base_id: str = "e") -> list:
    return [
        ExecutionTrace(
            event_id=f"{base_id}{i}", session_id="s1", sequence_no=i,
            correlation_id=f"c{i}",
            preflight_valid=True, preflight_reason="ok",
            risk_score=0.1,
            p4_verdict="ALLOW", p4_reason="ok", p4_risk_level="low",
            execution_status="SUCCESS",
            final_status="P4_ALLOW",
        ) for i in range(count)
    ]
