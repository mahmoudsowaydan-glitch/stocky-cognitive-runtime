from dataclasses import FrozenInstanceError

import pytest

from cognitive_runtime.contracts.public.dtos import (
    AgentProfileDTO,
    DaemonStatusDTO,
    EventStatusDTO,
    HealthDTO,
    PaginatedTracesDTO,
    PublicTraceDTO,
    ReceiptDTO,
    RegisterAgentDTO,
    SubmitEventDTO,
)
from cognitive_runtime.runtime.gateway.local_runtime_gateway import trace_to_public


class TestPublicTraceDTO:
    def test_defaults(self):
        dto = PublicTraceDTO()
        assert dto.event_id == ""
        assert dto.session_id == ""
        assert dto.status == "UNKNOWN"
        assert dto.risk_score == 0.0
        assert dto.total_time_ms == 0.0
        assert dto.error is None
        assert dto.created_at == 0.0

    def test_frozen(self):
        dto = PublicTraceDTO()
        with pytest.raises(FrozenInstanceError):
            dto.status = "ALLOW"

    def test_no_internal_fields(self):
        fields = set(PublicTraceDTO.__dataclass_fields__)
        internal = {"p4_verdict", "p4_reason", "p4_rule_triggered", "p4_risk_level",
                     "preflight_valid", "preflight_reason", "preflight_rules_triggered",
                     "execution_status", "capabilities_checked", "resource_usage",
                     "preflight_time", "p4_time", "execution_time",
                     "governance_score", "confidence_score", "stability_score",
                     "sequence_no", "correlation_id"}
        assert fields.isdisjoint(internal), f"Internal fields leaked: {fields & internal}"


class TestReceiptDTO:
    def test_defaults(self):
        dto = ReceiptDTO()
        assert dto.receipt_id == ""
        assert dto.event_id == ""
        assert dto.correlation_id == ""
        assert dto.submitted_at == 0.0

    def test_frozen(self):
        with pytest.raises(FrozenInstanceError):
            ReceiptDTO().receipt_id = "new"


class TestEventStatusDTO:
    def test_defaults(self):
        dto = EventStatusDTO()
        assert dto.status == "pending"

    def test_frozen(self):
        with pytest.raises(FrozenInstanceError):
            EventStatusDTO().status = "completed"


class TestDaemonStatusDTO:
    def test_defaults(self):
        dto = DaemonStatusDTO()
        assert dto.lifecycle == "STOPPED"
        assert dto.health == "healthy"

    def test_frozen(self):
        with pytest.raises(FrozenInstanceError):
            DaemonStatusDTO().lifecycle = "RUNNING"


class TestHealthDTO:
    def test_defaults(self):
        dto = HealthDTO()
        assert dto.status == "healthy"
        assert dto.panic_count == 0
        assert dto.recovery_count == 0


class TestAgentProfileDTO:
    def test_defaults(self):
        dto = AgentProfileDTO()
        assert dto.agent_id == ""
        assert dto.active is True
        assert dto.capabilities == []

    def test_frozen(self):
        with pytest.raises(FrozenInstanceError):
            AgentProfileDTO().agent_id = "new"


class TestSubmitEventDTO:
    def test_defaults(self):
        dto = SubmitEventDTO()
        assert dto.session_id == ""
        assert dto.correlation_id == ""


class TestRegisterAgentDTO:
    def test_defaults(self):
        dto = RegisterAgentDTO()
        assert dto.agent_id == ""
        assert dto.capabilities == []


class TestPaginatedTracesDTO:
    def test_defaults(self):
        dto = PaginatedTracesDTO()
        assert dto.traces == []
        assert dto.next_cursor is None
        assert dto.total == 0


class TestTraceToPublic:
    @pytest.fixture
    def allow_trace(self):
        class FakeTrace:
            event_id = "e1"
            session_id = "s1"
            p4_verdict = "ALLOW"
            execution_status = "SUCCESS"
            risk_score = 0.1
            total_time = 1.5
            execution_error = None
            p4_reason = "ok"
        return FakeTrace()

    @pytest.fixture
    def block_trace(self):
        class FakeTrace:
            event_id = "e2"
            session_id = "s1"
            p4_verdict = "BLOCK"
            execution_status = "UNKNOWN"
            risk_score = 0.8
            total_time = 0.5
            execution_error = None
            p4_reason = "policy violation"
        return FakeTrace()

    @pytest.fixture
    def failed_trace(self):
        class FakeTrace:
            event_id = "e3"
            session_id = "s1"
            p4_verdict = "ALLOW"
            execution_status = "FAILED"
            risk_score = 0.5
            total_time = 2.0
            execution_error = "sandbox crashed"
            p4_reason = "ok"
        return FakeTrace()

    def test_allow_trace(self, allow_trace):
        dto = trace_to_public(allow_trace)
        assert dto.status == "ALLOW"
        assert dto.event_id == "e1"
        assert dto.risk_score == 0.1

    def test_block_trace(self, block_trace):
        dto = trace_to_public(block_trace)
        assert dto.status == "BLOCK"
        assert dto.event_id == "e2"

    def test_failed_trace(self, failed_trace):
        dto = trace_to_public(failed_trace)
        assert dto.status == "FAILED"
        assert dto.error == "sandbox crashed"

    def test_no_p4_reason_in_dto(self, allow_trace):
        dto = trace_to_public(allow_trace)
        assert not hasattr(dto, "p4_reason")
        assert not hasattr(dto, "p4_verdict")

    def test_no_preflight_in_dto(self, allow_trace):
        dto = trace_to_public(allow_trace)
        assert not hasattr(dto, "preflight_valid")
        assert not hasattr(dto, "preflight_reason")
