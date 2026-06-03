import pytest

from cognitive_runtime.sandbox.preflight_analyzer import PreflightAnalyzer, PreflightResult
from cognitive_runtime.contracts.execution_contract import Capability, ExecutionProposal


@pytest.fixture
def analyzer():
    return PreflightAnalyzer()


@pytest.fixture
def valid_proposal():
    return ExecutionProposal(
        proposal_id="p1",
        session_id="s1",
        event_id="e1",
        action="read",
        target="/tmp/file",
        params={},
        required_capabilities=[Capability.FILESYSTEM_READ],
        confidence=0.8,
        risk_score=0.1,
        metadata={},
    )


class TestPreflightResult:
    def test_defaults(self):
        result = PreflightResult(valid=True)
        assert result.valid is True
        assert result.reason == ""
        assert result.risk_score == 0.0
        assert result.flags == []
        assert result.triggered_rules == []

    def test_defaults_not_valid(self):
        result = PreflightResult(valid=False)
        assert result.valid is False


class TestPreflightAnalyzer:
    def test_valid_proposal_returns_valid(self, analyzer, valid_proposal):
        result = analyzer.analyze(valid_proposal)
        assert result.valid is True
        assert result.reason == "preflight_passed"

    def test_missing_action_returns_blocked(self, analyzer):
        proposal = ExecutionProposal(
            proposal_id="p1", session_id="s1", event_id="e1",
            action="", target=None, params={},
            required_capabilities=[Capability.FILESYSTEM_READ],
            confidence=0.8, risk_score=0.1, metadata={},
        )
        result = analyzer.analyze(proposal)
        assert result.valid is False
        assert "BLOCKED_BY_PREFLIGHT" in result.reason
        assert "proposal_has_action" in result.reason

    def test_missing_action_triggered_rules(self, analyzer):
        proposal = ExecutionProposal(
            proposal_id="p1", session_id="s1", event_id="e1",
            action="", target=None, params={},
            required_capabilities=[Capability.FILESYSTEM_READ],
            confidence=0.8, risk_score=0.1, metadata={},
        )
        result = analyzer.analyze(proposal)
        assert "proposal_has_action" in result.triggered_rules

    def test_missing_capabilities_returns_blocked(self, analyzer):
        proposal = ExecutionProposal(
            proposal_id="p1", session_id="s1", event_id="e1",
            action="read", target=None, params={},
            required_capabilities=[],
            confidence=0.8, risk_score=0.1, metadata={},
        )
        result = analyzer.analyze(proposal)
        assert result.valid is False
        assert "capabilities_not_empty" in result.reason

    def test_missing_event_id(self, analyzer):
        proposal = ExecutionProposal(
            proposal_id="p1", session_id="s1", event_id="",
            action="read", target=None, params={},
            required_capabilities=[Capability.FILESYSTEM_READ],
            confidence=0.8, risk_score=0.1, metadata={},
        )
        result = analyzer.analyze(proposal)
        assert result.valid is False
        assert "proposal_has_event_id" in result.reason

    def test_missing_session_id(self, analyzer):
        proposal = ExecutionProposal(
            proposal_id="p1", session_id="", event_id="e1",
            action="read", target=None, params={},
            required_capabilities=[Capability.FILESYSTEM_READ],
            confidence=0.8, risk_score=0.1, metadata={},
        )
        result = analyzer.analyze(proposal)
        assert result.valid is False
        assert "proposal_has_session_id" in result.reason

    def test_confidence_out_of_range(self, analyzer):
        proposal = ExecutionProposal(
            proposal_id="p1", session_id="s1", event_id="e1",
            action="read", target=None, params={},
            required_capabilities=[Capability.FILESYSTEM_READ],
            confidence=-0.1, risk_score=0.1, metadata={},
        )
        result = analyzer.analyze(proposal)
        assert result.valid is False
        assert "confidence_in_range" in result.reason

    def test_risk_score_out_of_range(self, analyzer):
        proposal = ExecutionProposal(
            proposal_id="p1", session_id="s1", event_id="e1",
            action="read", target=None, params={},
            required_capabilities=[Capability.FILESYSTEM_READ],
            confidence=0.8, risk_score=1.5, metadata={},
        )
        result = analyzer.analyze(proposal)
        assert result.valid is False
        assert "risk_score_in_range" in result.reason

    def test_unknown_capability(self, analyzer):
        proposal = ExecutionProposal(
            proposal_id="p1", session_id="s1", event_id="e1",
            action="read", target=None, params={},
            required_capabilities=["bogus.cap"],
            confidence=0.8, risk_score=0.1, metadata={},
        )
        result = analyzer.analyze(proposal)
        assert result.valid is False
        assert "capabilities_are_known" in result.reason

    def test_write_without_target(self, analyzer):
        proposal = ExecutionProposal(
            proposal_id="p1", session_id="s1", event_id="e1",
            action="write", target=None, params={},
            required_capabilities=[Capability.FILESYSTEM_WRITE],
            confidence=0.8, risk_score=0.1, metadata={},
        )
        result = analyzer.analyze(proposal)
        assert result.valid is False
        assert "target_present_for_write" in result.reason

    def test_high_risk_network_write_triggers_flag(self, analyzer):
        proposal = ExecutionProposal(
            proposal_id="p1", session_id="s1", event_id="e1",
            action="http_write", target="http://example.com", params={},
            required_capabilities=[Capability.NETWORK_HTTP, Capability.FILESYSTEM_WRITE],
            confidence=0.8, risk_score=0.9, metadata={},
        )
        result = analyzer.analyze(proposal)
        assert result.valid is True
        assert len(result.flags) > 0
        assert any("no_network_write_high_risk" in f for f in result.flags)
        assert "no_network_write_high_risk" in result.triggered_rules

    def test_risk_score_propagated(self, analyzer):
        proposal = ExecutionProposal(
            proposal_id="p1", session_id="s1", event_id="e1",
            action="read", target="/tmp/file", params={},
            required_capabilities=[Capability.FILESYSTEM_READ],
            confidence=0.8, risk_score=0.42, metadata={},
        )
        result = analyzer.analyze(proposal)
        assert result.risk_score == 0.42

    def test_first_block_rule_short_circuits(self, analyzer):
        proposal = ExecutionProposal(
            proposal_id="p1", session_id="s1", event_id="",
            action="", target=None, params={},
            required_capabilities=[Capability.FILESYSTEM_READ],
            confidence=0.8, risk_score=0.1, metadata={},
        )
        result = analyzer.analyze(proposal)
        assert result.valid is False
        assert "proposal_has_action" in result.triggered_rules
        assert len(result.triggered_rules) == 1

    def test_capability_enum_to_value_conversion(self, analyzer):
        props = [
            ExecutionProposal(
                proposal_id="p1", session_id="s1", event_id="e1",
                action="read", target="/tmp/file", params={},
                required_capabilities=caps,
                confidence=0.8, risk_score=0.1, metadata={},
            )
            for caps in [[Capability.FILESYSTEM_READ],
                         [Capability.AUDIT_READ],
                         [Capability.PROCESS_EXECUTE]]
        ]
        for p in props:
            result = analyzer.analyze(p)
            assert result.valid is True, f"failed for {p.required_capabilities}"
