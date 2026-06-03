import pytest
from cognitive_runtime.contracts.execution_contract import (
    Capability,
    HostEvent,
    ExecutionProposal,
    PolicyDecision,
    ExecutionResult,
    DeadLetterEvent,
)

class TestCapability:
    def test_enum_values(self):
        assert Capability.FILESYSTEM_READ.value == "filesystem.read"
        assert Capability.FILESYSTEM_WRITE.value == "filesystem.write"
        assert Capability.PROCESS_EXECUTE.value == "process.execute"
        assert Capability.NETWORK_HTTP.value == "network.http"
        assert Capability.RUNTIME_SPAWN.value == "runtime.spawn"
        assert Capability.AUDIT_READ.value == "audit.read"
        assert Capability.REPLAY_READ.value == "replay.read"
        assert Capability.COUNTERFACTUAL_ANALYZE.value == "counterfactual.analyze"

    def test_from_legacy_read_file(self):
        assert Capability.from_legacy("READ_FILE") == Capability.FILESYSTEM_READ

    def test_from_legacy_write_file(self):
        assert Capability.from_legacy("WRITE_FILE") == Capability.FILESYSTEM_WRITE

    def test_from_legacy_execute(self):
        assert Capability.from_legacy("EXECUTE") == Capability.PROCESS_EXECUTE

    def test_from_legacy_network(self):
        assert Capability.from_legacy("NETWORK") == Capability.NETWORK_HTTP

    def test_from_legacy_audit(self):
        assert Capability.from_legacy("AUDIT") == Capability.AUDIT_READ

    def test_from_legacy_replay(self):
        assert Capability.from_legacy("REPLAY") == Capability.REPLAY_READ

    def test_from_legacy_counterfactual(self):
        assert Capability.from_legacy("COUNTERFACTUAL") == Capability.COUNTERFACTUAL_ANALYZE

    def test_from_legacy_unknown_fallback(self):
        assert Capability.from_legacy("UNKNOWN_LEGACY") == Capability.FILESYSTEM_READ
        assert Capability.from_legacy("") == Capability.FILESYSTEM_READ
        assert Capability.from_legacy("NOT_A_REAL_NAME") == Capability.FILESYSTEM_READ


class TestHostEvent:
    def test_create(self):
        ev = HostEvent(
            event_id="e1", session_id="s1", timestamp=100.0,
            source="cli", payload={"cmd": "ls"},
        )
        assert ev.event_id == "e1"
        assert ev.session_id == "s1"
        assert ev.timestamp == 100.0
        assert ev.source == "cli"
        assert ev.payload == {"cmd": "ls"}

    def test_frozen(self):
        ev = HostEvent(event_id="e", session_id="s", timestamp=0.0, source="t", payload={})
        with pytest.raises(AttributeError):
            ev.event_id = "other"

    def test_all_fields(self):
        ev = HostEvent(
            event_id="e99", session_id="s99", timestamp=999.0,
            source="agent", payload={"key": "val"},
        )
        assert ev.event_id == "e99"
        assert ev.session_id == "s99"
        assert ev.timestamp == 999.0
        assert ev.source == "agent"
        assert ev.payload == {"key": "val"}


class TestExecutionProposal:
    def test_create(self):
        prop = ExecutionProposal(
            proposal_id="p1", session_id="s1", event_id="e1",
            action="read", target="/tmp/x",
            params={"path": "/tmp/x"},
            required_capabilities=[Capability.FILESYSTEM_READ],
            confidence=0.9, risk_score=0.1,
            metadata={"src": "test"},
        )
        assert prop.proposal_id == "p1"
        assert prop.session_id == "s1"
        assert prop.event_id == "e1"
        assert prop.action == "read"
        assert prop.target == "/tmp/x"
        assert prop.params == {"path": "/tmp/x"}
        assert prop.required_capabilities == [Capability.FILESYSTEM_READ]
        assert prop.confidence == 0.9
        assert prop.risk_score == 0.1
        assert prop.metadata == {"src": "test"}

    def test_frozen(self):
        prop = ExecutionProposal(
            proposal_id="p", session_id="s", event_id="e", action="a",
            target=None, params={}, required_capabilities=[], confidence=0.0,
            risk_score=0.0, metadata={},
        )
        with pytest.raises(AttributeError):
            prop.proposal_id = "other"

    def test_correlation_id_default(self):
        prop = ExecutionProposal(
            proposal_id="p", session_id="s", event_id="e", action="a",
            target=None, params={}, required_capabilities=[], confidence=0.0,
            risk_score=0.0, metadata={},
        )
        assert prop.correlation_id == ""

    def test_correlation_id_custom(self):
        prop = ExecutionProposal(
            proposal_id="p", session_id="s", event_id="e", action="a",
            target=None, params={}, required_capabilities=[], confidence=0.0,
            risk_score=0.0, metadata={}, correlation_id="c1",
        )
        assert prop.correlation_id == "c1"


class TestPolicyDecision:
    def test_create(self):
        dec = PolicyDecision(
            decision_id="d1", proposal_id="p1", session_id="s1",
            verdict="ALLOW", reason="ok", risk_level="low",
            rule_triggered=None, confidence=0.95,
        )
        assert dec.decision_id == "d1"
        assert dec.proposal_id == "p1"
        assert dec.session_id == "s1"
        assert dec.verdict == "ALLOW"
        assert dec.reason == "ok"
        assert dec.risk_level == "low"
        assert dec.rule_triggered is None
        assert dec.confidence == 0.95

    def test_frozen(self):
        dec = PolicyDecision(
            decision_id="d", proposal_id="p", session_id="s",
            verdict="ALLOW", reason="r", risk_level="low",
            rule_triggered=None, confidence=0.0,
        )
        with pytest.raises(AttributeError):
            dec.decision_id = "other"

    def test_verdict_literal_values(self):
        for v in ("ALLOW", "BLOCK", "DEFER", "REVIEW"):
            dec = PolicyDecision(
                decision_id="d", proposal_id="p", session_id="s",
                verdict=v, reason="r", risk_level="low",
                rule_triggered=None, confidence=0.0,
            )
            assert dec.verdict == v

    def test_correlation_id_default(self):
        dec = PolicyDecision(
            decision_id="d", proposal_id="p", session_id="s",
            verdict="ALLOW", reason="r", risk_level="low",
            rule_triggered=None, confidence=0.0,
        )
        assert dec.correlation_id == ""

    def test_correlation_id_custom(self):
        dec = PolicyDecision(
            decision_id="d", proposal_id="p", session_id="s",
            verdict="BLOCK", reason="no", risk_level="high",
            rule_triggered="rule_1", confidence=0.9,
            correlation_id="c2",
        )
        assert dec.correlation_id == "c2"


class TestExecutionResult:
    def test_create(self):
        res = ExecutionResult(
            execution_id="ex1", proposal_id="p1", session_id="s1",
            status="SUCCESS", output={"data": "ok"}, error=None,
            started_at=100.0, finished_at=101.0,
        )
        assert res.execution_id == "ex1"
        assert res.proposal_id == "p1"
        assert res.session_id == "s1"
        assert res.status == "SUCCESS"
        assert res.output == {"data": "ok"}
        assert res.error is None
        assert res.started_at == 100.0
        assert res.finished_at == 101.0

    def test_frozen(self):
        res = ExecutionResult(
            execution_id="e", proposal_id="p", session_id="s",
            status="SUCCESS", output=None, error=None,
            started_at=0.0, finished_at=1.0,
        )
        with pytest.raises(AttributeError):
            res.execution_id = "other"

    def test_all_status_literals(self):
        for s in ("SUCCESS", "FAILED", "SKIPPED", "QUEUED"):
            res = ExecutionResult(
                execution_id="e", proposal_id="p", session_id="s",
                status=s, output=None, error=None,
                started_at=0.0, finished_at=1.0,
            )
            assert res.status == s

    def test_correlation_id_default(self):
        res = ExecutionResult(
            execution_id="e", proposal_id="p", session_id="s",
            status="SUCCESS", output=None, error=None,
            started_at=0.0, finished_at=1.0,
        )
        assert res.correlation_id == ""

    def test_correlation_id_custom(self):
        res = ExecutionResult(
            execution_id="e", proposal_id="p", session_id="s",
            status="FAILED", output=None, error="err",
            started_at=0.0, finished_at=1.0,
            correlation_id="c3",
        )
        assert res.correlation_id == "c3"


class TestDeadLetterEvent:
    def test_create(self):
        dle = DeadLetterEvent(
            event_id="dle1", original_event={"event_id": "e1"},
            failure_reason="timeout", retry_count=3,
        )
        assert dle.event_id == "dle1"
        assert dle.original_event == {"event_id": "e1"}
        assert dle.failure_reason == "timeout"
        assert dle.retry_count == 3

    def test_frozen(self):
        dle = DeadLetterEvent(
            event_id="d", original_event={}, failure_reason="r", retry_count=0,
        )
        with pytest.raises(AttributeError):
            dle.event_id = "other"
