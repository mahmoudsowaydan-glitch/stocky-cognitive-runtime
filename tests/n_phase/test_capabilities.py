"""
test_capabilities.py — Phase N Step 2: Unit tests for all 4 capability providers.
Validates determinism, dict-only output, and no runtime object leakage.
"""

import asyncio
import os

import pytest

from cognitive_runtime.capabilities import CapabilityRegistry
from cognitive_runtime.capabilities.report import execute as report_execute
from cognitive_runtime.capabilities.repository import execute as repository_execute
from cognitive_runtime.capabilities.search import execute as search_execute
from cognitive_runtime.capabilities.discovery import execute as discovery_execute
from cognitive_runtime.contracts.execution_contract import Capability, ExecutionProposal, PolicyDecision

_MARKER = object()


def _make_proposal(action: str = "analyze", target: str = None, **params) -> ExecutionProposal:
    return ExecutionProposal(
        proposal_id="test-prop",
        session_id="test",
        event_id="test-evt",
        action=action,
        target=target or ".",
        params=params or {},
        required_capabilities=[Capability.FILESYSTEM_READ],
        confidence=0.8,
        risk_score=0.1,
        metadata={},
    )


def _make_decision(verdict: str = "ALLOW") -> PolicyDecision:
    return PolicyDecision(
        decision_id="test-dec",
        proposal_id="test-prop",
        session_id="test",
        verdict=verdict,
        reason="test",
        risk_level="low",
        rule_triggered=None,
        confidence=0.9,
    )


class TestRepositoryCapability:
    @pytest.mark.asyncio
    async def test_returns_dict(self):
        result = await repository_execute(_make_proposal(target="."), _make_decision())
        assert isinstance(result, dict), f"Expected dict, got {type(result)}"

    @pytest.mark.asyncio
    async def test_has_expected_fields(self):
        result = await repository_execute(_make_proposal(target="."), _make_decision())
        assert "path" in result
        assert "files" in result
        assert "directories" in result
        assert "total_entries" in result
        assert result["status"] == "SUCCESS"

    @pytest.mark.asyncio
    async def test_deterministic_output(self):
        r1 = await repository_execute(_make_proposal(target="."), _make_decision())
        r2 = await repository_execute(_make_proposal(target="."), _make_decision())
        assert r1["files"] == r2["files"]
        assert r1["directories"] == r2["directories"]

    @pytest.mark.asyncio
    async def test_no_runtime_objects(self):
        result = await repository_execute(_make_proposal(target="."), _make_decision())
        for v in result.values():
            assert not hasattr(v, "__class__") or v.__class__ in (str, int, float, bool, list, dict, tuple, type(None)), \
                f"Contains runtime object: {type(v)}"

    @pytest.mark.asyncio
    async def test_handles_nonexistent_path(self):
        result = await repository_execute(_make_proposal(target="/nonexistent_path_xyz"), _make_decision())
        assert result["status"] == "FAILED"


class TestSearchCapability:
    @pytest.mark.asyncio
    async def test_returns_dict(self):
        result = await search_execute(_make_proposal(target="."), _make_decision())
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_search_py_files(self):
        result = await search_execute(
            _make_proposal(action="search", pattern="*.py", max_results=50),
            _make_decision(),
        )
        assert result["status"] == "SUCCESS"
        assert "matches" in result
        assert result["total_matches"] >= 0

    @pytest.mark.asyncio
    async def test_deterministic_output(self):
        params = {"pattern": "*.py", "max_results": 50}
        r1 = await search_execute(_make_proposal(**params), _make_decision())
        r2 = await search_execute(_make_proposal(**params), _make_decision())
        assert r1["total_matches"] == r2["total_matches"]
        assert r1["matches"] == r2["matches"]

    @pytest.mark.asyncio
    async def test_no_runtime_objects(self):
        result = await search_execute(
            _make_proposal(action="search", pattern="*.py", max_results=10),
            _make_decision(),
        )
        for v in result.values():
            assert not hasattr(v, "__class__") or v.__class__ in (str, int, float, bool, list, dict, tuple, type(None))


class TestDiscoveryCapability:
    @pytest.mark.asyncio
    async def test_returns_dict(self):
        result = await discovery_execute(_make_proposal(target="."), _make_decision())
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_discovers_test_files(self):
        result = await discovery_execute(_make_proposal(target="."), _make_decision())
        assert result["status"] == "SUCCESS"
        assert "total_test_files" in result
        assert "total_test_functions" in result

    @pytest.mark.asyncio
    async def test_deterministic_output(self):
        r1 = await discovery_execute(_make_proposal(target="."), _make_decision())
        r2 = await discovery_execute(_make_proposal(target="."), _make_decision())
        assert r1["total_test_files"] == r2["total_test_files"]
        assert r1["total_test_functions"] == r2["total_test_functions"]

    @pytest.mark.asyncio
    async def test_no_runtime_objects(self):
        result = await discovery_execute(_make_proposal(target="tests"), _make_decision())
        for v in result.values():
            assert not hasattr(v, "__class__") or v.__class__ in (str, int, float, bool, list, dict, tuple, type(None))

    @pytest.mark.asyncio
    async def test_handles_nonexistent_path(self):
        result = await discovery_execute(_make_proposal(target="/nonexistent_path_xyz"), _make_decision())
        assert result["status"] == "FAILED"


class TestArchitectureReportCapability:
    @pytest.mark.asyncio
    async def test_returns_dict(self):
        result = await report_execute(_make_proposal(target="."), _make_decision())
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_has_expected_fields(self):
        result = await report_execute(_make_proposal(target="."), _make_decision())
        assert "layout" in result
        assert "total_python_modules" in result
        assert "total_directories" in result
        assert result["status"] == "SUCCESS"

    @pytest.mark.asyncio
    async def test_deterministic_output(self):
        r1 = await report_execute(_make_proposal(target="."), _make_decision())
        r2 = await report_execute(_make_proposal(target="."), _make_decision())
        assert r1["total_python_modules"] == r2["total_python_modules"]

    @pytest.mark.asyncio
    async def test_no_runtime_objects(self):
        result = await report_execute(_make_proposal(target="cognitive_runtime"), _make_decision())
        for v in result.values():
            assert not hasattr(v, "__class__") or v.__class__ in (str, int, float, bool, list, dict, tuple, type(None))

    @pytest.mark.asyncio
    async def test_depth_bounded(self):
        result = await report_execute(
            _make_proposal(target=".", max_depth=1),
            _make_decision(),
        )
        assert result["status"] == "SUCCESS"
        assert len(result["layout"]) >= 0


class TestCapabilityRegistry:
    def test_registry_contains_all_actions(self):
        reg = CapabilityRegistry()
        actions = reg.list_actions()
        assert "analyze" in actions
        assert "search" in actions
        assert "count" in actions
        assert "discover_tests" in actions
        assert "generate_report" in actions

    def test_registry_len(self):
        reg = CapabilityRegistry()
        assert len(reg) == 5

    def test_registry_resolve_known(self):
        reg = CapabilityRegistry()
        for action in reg.list_actions():
            assert reg.resolve(action) is not None, f"Failed to resolve {action}"

    def test_registry_resolve_unknown(self):
        reg = CapabilityRegistry()
        assert reg.resolve("nonexistent_action") is None

    def test_registry_contains(self):
        reg = CapabilityRegistry()
        assert "analyze" in reg
        assert "nonexistent" not in reg
