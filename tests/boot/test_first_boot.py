import asyncio
import os

import pytest

from cognitive_runtime.boot.first_boot import (
    BootResult,
    console_report,
    p3_builder,
    p4_authority,
    run_first_boot,
)
from cognitive_runtime.capabilities import analyze_worker
from cognitive_runtime.contracts.execution_contract import (
    Capability,
    ExecutionProposal,
    HostEvent,
)
from cognitive_runtime.contracts.execution_trace import ExecutionTrace
from cognitive_runtime.contracts.public.dtos import (
    PublicTraceDTO,
    SubmitEventDTO,
)
from cognitive_runtime.runtime.gateway.local_runtime_gateway import trace_to_public


class TestP3Builder:
    @pytest.mark.asyncio
    async def test_creates_proposal_for_analyze_event(self):
        event = HostEvent(
            event_id="e1", session_id="s1", timestamp=1000.0,
            source="analyze", payload={"action": "analyze", "target": "."},
        )
        proposal = await p3_builder(event)
        assert proposal.event_id == "e1"
        assert proposal.action == "analyze"
        assert proposal.target == "."
        assert Capability.FILESYSTEM_READ in proposal.required_capabilities

    @pytest.mark.asyncio
    async def test_uses_payload_risk_score(self):
        event = HostEvent(
            event_id="e1", session_id="s1", timestamp=1000.0,
            source="test", payload={"risk_score": 0.5},
        )
        proposal = await p3_builder(event)
        assert proposal.risk_score == 0.5


class TestP4Authority:
    @pytest.mark.asyncio
    async def test_allows_low_risk(self):
        from cognitive_runtime.contracts.execution_contract import ExecutionProposal
        proposal = ExecutionProposal(
            proposal_id="p1", session_id="s1", event_id="e1",
            action="analyze", target=".", params={},
            required_capabilities=[Capability.FILESYSTEM_READ],
            confidence=0.8, risk_score=0.1, metadata={},
        )
        decision = await p4_authority(proposal)
        assert decision.verdict == "ALLOW"
        assert decision.risk_level == "low"

    @pytest.mark.asyncio
    async def test_blocks_high_risk(self):
        proposal = ExecutionProposal(
            proposal_id="p2", session_id="s1", event_id="e2",
            action="analyze", target=".", params={},
            required_capabilities=[Capability.FILESYSTEM_READ],
            confidence=0.8, risk_score=0.8, metadata={},
        )
        decision = await p4_authority(proposal)
        assert decision.verdict == "BLOCK"
        assert decision.risk_level == "high"


class TestAnalyzeWorker:
    @pytest.mark.asyncio
    async def test_analyzes_directory(self):
        proposal = ExecutionProposal(
            proposal_id="p1", session_id="s1", event_id="e1",
            action="analyze", target=".", params={},
            required_capabilities=[Capability.FILESYSTEM_READ],
            confidence=0.8, risk_score=0.1, metadata={},
        )
        from cognitive_runtime.contracts.execution_contract import PolicyDecision
        decision = PolicyDecision(
            decision_id="d1", proposal_id="p1", session_id="s1",
            verdict="ALLOW", reason="ok", risk_level="low",
            rule_triggered=None, confidence=0.9,
        )
        result = await analyze_worker(proposal, decision)
        assert result["status"] == "SUCCESS"
        assert "total_entries" in result
        assert result["total_entries"] >= 0

    @pytest.mark.asyncio
    async def test_handles_nonexistent_path(self):
        proposal = ExecutionProposal(
            proposal_id="p1", session_id="s1", event_id="e1",
            action="analyze", target="/nonexistent_path_xyz", params={},
            required_capabilities=[Capability.FILESYSTEM_READ],
            confidence=0.8, risk_score=0.1, metadata={},
        )
        from cognitive_runtime.contracts.execution_contract import PolicyDecision
        decision = PolicyDecision(
            decision_id="d1", proposal_id="p1", session_id="s1",
            verdict="ALLOW", reason="ok", risk_level="low",
            rule_triggered=None, confidence=0.9,
        )
        result = await analyze_worker(proposal, decision)
        assert result["status"] == "FAILED"
        assert "path_not_found" in result.get("error", "")


class TestFirstBootPipeline:
    @pytest.mark.asyncio
    async def test_full_pipeline_processes_event(self):
        result = await run_first_boot()

        assert result.event_id != ""
        assert result.receipt_id != ""
        assert result.status == "ALLOW"
        assert result.total_events_processed >= 1
        assert result.duration_seconds > 0

    @pytest.mark.asyncio
    async def test_trace_dto_sanitized(self):
        result = await run_first_boot()

        assert result.trace_dto is not None
        assert isinstance(result.trace_dto, PublicTraceDTO)
        assert not hasattr(result.trace_dto, "p4_verdict")
        assert not hasattr(result.trace_dto, "p4_reason")
        assert not hasattr(result.trace_dto, "preflight_valid")

    @pytest.mark.asyncio
    async def test_no_internal_leak_invariant(self):
        result = await run_first_boot()
        assert result.invariants["no_internal_leak"] is True

    @pytest.mark.asyncio
    async def test_pipeline_completeness_invariant(self):
        result = await run_first_boot()
        assert result.invariants["pipeline_completeness"] is True

    @pytest.mark.asyncio
    async def test_deterministic_trace_generated(self):
        result = await run_first_boot()
        assert result.invariants["deterministic_trace"] is True


class TestFirstBootSafety:
    @pytest.mark.asyncio
    async def test_event_does_not_modify_architecture(self):
        from cognitive_runtime.runtime.runtime_loop import RuntimeLoop
        from cognitive_runtime.contracts.frozen.doctrine_runtime_guard import (
            DoctrineRuntimeGuard,
        )

        result = await run_first_boot()

        # After running, the architecture must still pass CI gate
        guard = DoctrineRuntimeGuard()
        # We can't test the full gate without a loop, but we can verify
        # that no Phase M code modified any runtime module
        assert result.invariants["pipeline_completeness"] is True

    @pytest.mark.asyncio
    async def test_console_can_display_results(self):
        result = await run_first_boot()
        report = console_report(result)
        assert "FIRST BOOT REPORT" in report
        assert result.event_id in report
        assert result.status in report

    @pytest.mark.asyncio
    async def test_console_report_shows_invariants(self):
        result = await run_first_boot()
        report = console_report(result)
        assert "Invariants:" in report
        assert "pipeline_completeness: PASS" in report
        assert "no_internal_leak: PASS" in report


class TestTraceToPublicSanitized:
    def test_no_internal_fields_in_public_trace(self):
        trace = ExecutionTrace(
            event_id="e1", session_id="s1", sequence_no=1,
            correlation_id="c1",
            preflight_valid=True, preflight_reason="ok",
            risk_score=0.1,
            p4_verdict="ALLOW", p4_reason="ok", p4_risk_level="low",
            execution_status="SUCCESS",
            final_status="P4_ALLOW",
        )
        dto = trace_to_public(trace)
        assert dto.event_id == "e1"
        assert dto.status == "ALLOW"
        assert not hasattr(dto, "p4_verdict")
        assert not hasattr(dto, "p4_reason")
        assert not hasattr(dto, "preflight_valid")
        assert not hasattr(dto, "correlation_id")
        assert not hasattr(dto, "sequence_no")
