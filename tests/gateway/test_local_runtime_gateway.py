from unittest.mock import MagicMock, PropertyMock

import pytest

from cognitive_runtime.contracts.public.dtos import (
    RegisterAgentDTO,
    SubmitEventDTO,
)
from cognitive_runtime.runtime.daemon.runtime_daemon import RuntimeDaemon
from cognitive_runtime.runtime.daemon.runtime_lifecycle import LifecycleState
from cognitive_runtime.runtime.daemon.runtime_status import RuntimeStatus
from cognitive_runtime.runtime.gateway.local_runtime_gateway import (
    LocalRuntimeGateway,
)


def make_mock_daemon(**overrides):
    daemon = MagicMock(spec=RuntimeDaemon)

    daemon.status = RuntimeStatus(
        lifecycle_state=LifecycleState.RUNNING,
        uptime_seconds=100.0,
        cycle_count=42,
        health_status="healthy",
        panic_count=1,
        recovery_count=1,
    )
    daemon.lifecycle = LifecycleState.RUNNING

    loop = MagicMock()
    loop._traces = []
    loop._queue = MagicMock()
    loop._queue.push = MagicMock()
    daemon.loop = loop

    for k, v in overrides.items():
        setattr(daemon, k, v)

    return daemon


@pytest.fixture
def mock_daemon():
    return make_mock_daemon()


@pytest.fixture
def gateway(mock_daemon):
    return LocalRuntimeGateway(mock_daemon)


class TestRuntimeAPI:
    def test_get_daemon_status(self, gateway):
        status = gateway.get_daemon_status()
        assert status.lifecycle == "RUNNING"
        assert status.health == "healthy"
        assert status.cycle_count == 42
        assert status.panic_count == 1
        assert status.uptime_seconds > 0

    def test_get_health(self, gateway):
        health = gateway.get_health()
        assert health.status == "healthy"
        assert health.cycle_count == 42
        assert health.panic_count == 1
        assert health.recovery_count == 1

    def test_get_version(self, gateway):
        version = gateway.get_version()
        assert isinstance(version, str)
        assert len(version) > 0


class TestExecutionAPI:
    def test_submit_event_returns_receipt(self, gateway, mock_daemon):
        dto = SubmitEventDTO(
            session_id="s1",
            source="test",
            payload={"cmd": "analyze"},
            correlation_id="corr-1",
        )
        receipt = gateway.submit_event(dto)
        assert receipt.receipt_id != ""
        assert receipt.event_id != ""
        assert receipt.correlation_id == "corr-1"
        assert receipt.submitted_at > 0

    def test_submit_event_pushes_to_queue(self, gateway, mock_daemon):
        dto = SubmitEventDTO(session_id="s1", source="test", payload={})
        gateway.submit_event(dto)
        mock_daemon.loop._queue.push.assert_called_once()

    def test_submit_event_auto_correlation_id(self, gateway):
        dto = SubmitEventDTO(session_id="s1", source="test", payload={})
        receipt = gateway.submit_event(dto)
        assert receipt.correlation_id == receipt.receipt_id

    def test_get_status_pending(self, gateway):
        dto = SubmitEventDTO(session_id="s1", source="test", payload={})
        receipt = gateway.submit_event(dto)
        status = gateway.get_status(receipt.receipt_id)
        assert status is not None
        assert status.status == "pending"

    def test_get_status_unknown_receipt(self, gateway):
        status = gateway.get_status("nonexistent")
        assert status is None

    def test_get_result_unknown_receipt(self, gateway):
        result = gateway.get_result("nonexistent")
        assert result is None

    def test_get_result_pending_returns_none(self, gateway):
        dto = SubmitEventDTO(session_id="s1", source="test", payload={})
        receipt = gateway.submit_event(dto)
        result = gateway.get_result(receipt.receipt_id)
        assert result is None

    def test_get_result_completed(self, gateway, mock_daemon):
        from cognitive_runtime.contracts.execution_trace import ExecutionTrace

        trace = ExecutionTrace(
            event_id="e1", session_id="s1", sequence_no=1,
            preflight_valid=True, risk_score=0.1,
            p4_verdict="ALLOW", execution_status="SUCCESS",
            total_time=1.0,
        )
        mock_daemon.loop._traces = [trace]

        dto = SubmitEventDTO(session_id="s1", source="test", payload={})
        receipt = gateway.submit_event(dto)
        mock_daemon.loop._traces[0].event_id = receipt.event_id

        result = gateway.get_result(receipt.receipt_id)
        assert result is not None
        assert result.status == "ALLOW"

    def test_get_capabilities(self, gateway):
        caps = gateway.get_capabilities()
        assert len(caps) > 0
        assert "filesystem.read" in caps


class TestObservationAPI:
    def test_get_trace_by_id_found(self, gateway, mock_daemon):
        from cognitive_runtime.contracts.execution_trace import ExecutionTrace

        mock_daemon.loop._traces = [
            ExecutionTrace(
                event_id="e1", session_id="s1", sequence_no=1,
                preflight_valid=True, risk_score=0.1,
                p4_verdict="ALLOW", execution_status="SUCCESS",
                total_time=1.0,
            )
        ]
        trace = gateway.get_trace_by_id("e1")
        assert trace is not None
        assert trace.status == "ALLOW"

    def test_get_trace_by_id_not_found(self, gateway):
        trace = gateway.get_trace_by_id("nonexistent")
        assert trace is None

    def test_list_traces_paginated(self, gateway, mock_daemon):
        from cognitive_runtime.contracts.execution_trace import ExecutionTrace

        mock_daemon.loop._traces = [
            ExecutionTrace(
                event_id=f"e{i}", session_id="s1", sequence_no=i,
                preflight_valid=True, risk_score=0.1,
                p4_verdict="ALLOW" if i % 2 == 0 else "BLOCK",
                execution_status="SUCCESS",
                total_time=1.0,
            ) for i in range(10)
        ]
        result = gateway.list_traces("s1", limit=3)
        assert len(result.traces) == 3
        assert result.total == 10

    def test_list_traces_empty(self, gateway):
        result = gateway.list_traces("nonexistent")
        assert result.traces == []
        assert result.total == 0


class TestAgentAPI:
    def test_register_agent(self, gateway):
        dto = RegisterAgentDTO(
            agent_id="a1", name="test-agent",
            capabilities=["filesystem.read", "audit.read"],
        )
        profile = gateway.register_agent(dto)
        assert profile.agent_id == "a1"
        assert profile.name == "test-agent"
        assert profile.active is True
        assert profile.registered_at > 0

    def test_get_agent_found(self, gateway):
        dto = RegisterAgentDTO(agent_id="a1", name="agent")
        gateway.register_agent(dto)
        profile = gateway.get_agent("a1")
        assert profile is not None
        assert profile.agent_id == "a1"

    def test_get_agent_not_found(self, gateway):
        profile = gateway.get_agent("nonexistent")
        assert profile is None

    def test_list_agents(self, gateway):
        gateway.register_agent(RegisterAgentDTO(agent_id="a1", name="agent1"))
        gateway.register_agent(RegisterAgentDTO(agent_id="a2", name="agent2"))
        agents = gateway.list_agents()
        assert len(agents) == 2

    def test_deactivate_agent(self, gateway):
        gateway.register_agent(RegisterAgentDTO(agent_id="a1", name="agent"))
        result = gateway.deactivate_agent("a1")
        assert result is True
        profile = gateway.get_agent("a1")
        assert profile.active is False

    def test_deactivate_nonexistent(self, gateway):
        result = gateway.deactivate_agent("nonexistent")
        assert result is False


class TestCONTRACT_LEAK_001:
    def test_gateway_does_not_expose_daemon(self, gateway):
        assert not hasattr(gateway, "_daemon_public")
        assert not hasattr(gateway, "internal_daemon")

    def test_gateway_does_not_expose_loop(self, gateway):
        assert not hasattr(gateway, "loop")
        assert not hasattr(gateway, "runtime_loop")
        assert not hasattr(gateway, "get_loop")

    def test_dtos_have_no_internal_references(self, gateway):
        daemon_status = gateway.get_daemon_status()
        assert not hasattr(daemon_status, "governance_engine")
        assert not hasattr(daemon_status, "recovery_coordinator")
        assert not hasattr(daemon_status, "p4_authority")

    def test_public_trace_no_internal_fields(self, gateway, mock_daemon):
        from cognitive_runtime.contracts.execution_trace import ExecutionTrace
        mock_daemon.loop._traces = [
            ExecutionTrace(event_id="e1", session_id="s1", sequence_no=1,
                           preflight_valid=True, risk_score=0.1,
                           p4_verdict="ALLOW", execution_status="SUCCESS",
                           total_time=1.0)
        ]
        trace = gateway.get_trace_by_id("e1")
        assert not hasattr(trace, "p4_verdict")
        assert not hasattr(trace, "p4_reason")
        assert not hasattr(trace, "preflight_valid")
        assert not hasattr(trace, "governance_score")

    def test_gateway_property_daemon_returns_daemon(self, gateway, mock_daemon):
        assert gateway.daemon is mock_daemon


class TestGATEWAY_IMMUTABILITY_001:
    def test_pending_map_is_bounded(self, gateway):
        for i in range(1500):
            dto = SubmitEventDTO(session_id=f"s{i}", source="test", payload={})
            gateway.submit_event(dto)
        assert len(gateway._pending) <= 1000

    def test_gateway_has_no_cache(self, gateway):
        assert not hasattr(gateway, "_cache")
        assert not hasattr(gateway, "_session_state")

    def test_gateway_has_no_lifecycle_state(self, gateway):
        assert not hasattr(gateway, "_lifecycle_state")


class TestGatewayStatelessInvariants:
    def test_two_gateways_daemon_same_status(self, mock_daemon):
        g1 = LocalRuntimeGateway(mock_daemon)
        g2 = LocalRuntimeGateway(mock_daemon)
        assert g1.get_daemon_status() == g2.get_daemon_status()

    def test_daemon_status_changes_reflected(self, mock_daemon):
        from dataclasses import replace

        g1 = LocalRuntimeGateway(mock_daemon)
        s1 = g1.get_daemon_status()

        mock_daemon.status = replace(mock_daemon.status, cycle_count=99)

        s2 = g1.get_daemon_status()
        assert s2.cycle_count == 99
