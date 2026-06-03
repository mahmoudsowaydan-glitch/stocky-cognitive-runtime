import pytest

from cognitive_runtime.contracts.execution_trace import (
    ExecutionTrace,
    ExecutionTraceNormalizer,
    ExecutionTraceStore,
    enriched_to_trace_dict,
)
from cognitive_runtime.contracts.enriched_event import EnrichedEvent
from cognitive_runtime.contracts.execution_contract import (
    Capability,
    ExecutionProposal,
    ExecutionResult,
    HostEvent,
    PolicyDecision,
)


def test_execution_trace_defaults():
    t = ExecutionTrace()
    assert t.event_id == ""
    assert t.session_id == ""
    assert t.sequence_no == 0
    assert t.correlation_id == ""
    assert t.preflight_valid is False
    assert t.preflight_reason is None
    assert t.preflight_rules_triggered == []
    assert t.risk_score == 0.0
    assert t.p4_verdict == "UNKNOWN"
    assert t.p4_reason is None
    assert t.p4_risk_level is None
    assert t.p4_rule_triggered is None
    assert t.execution_status == "UNKNOWN"
    assert t.execution_error is None
    assert t.capabilities_checked == []
    assert t.resource_usage == {}
    assert t.preflight_time == 0.0
    assert t.p4_time == 0.0
    assert t.execution_time == 0.0
    assert t.total_time == 0.0
    assert t.final_status == "UNKNOWN"


def test_execution_trace_defaults_independent():
    t1 = ExecutionTrace()
    t2 = ExecutionTrace()
    t1.event_id = "e1"
    assert t2.event_id == ""


def test_normalize_full_raw_dict():
    raw = {
        "event_id": "evt-001",
        "session_id": "s1",
        "sequence_no": 3,
        "correlation_id": "cid-abc",
        "preflight": {
            "valid": True,
            "reason": "all_checks_passed",
            "rules": ["rule_a"],
        },
        "risk_score": 0.15,
        "p4": {
            "verdict": "ALLOW",
            "reason": "safe",
            "risk_level": "low",
            "rule_triggered": None,
        },
        "sandbox": {
            "status": "SUCCESS",
            "error": None,
            "capabilities": ["PROCESS_EXECUTE"],
            "resource_usage": {"cpu_ms": 42},
        },
        "timing": {
            "preflight": 1.0,
            "p4": 0.5,
            "execution": 10.0,
            "total": 11.5,
        },
    }
    norm = ExecutionTraceNormalizer()
    t = norm.normalize(raw)
    assert t.event_id == "evt-001"
    assert t.session_id == "s1"
    assert t.sequence_no == 3
    assert t.correlation_id == "cid-abc"
    assert t.preflight_valid is True
    assert t.preflight_reason == "all_checks_passed"
    assert t.preflight_rules_triggered == ["rule_a"]
    assert t.risk_score == 0.15
    assert t.p4_verdict == "ALLOW"
    assert t.p4_reason == "safe"
    assert t.p4_risk_level == "low"
    assert t.p4_rule_triggered is None
    assert t.execution_status == "SUCCESS"
    assert t.execution_error is None
    assert t.capabilities_checked == ["PROCESS_EXECUTE"]
    assert t.resource_usage == {"cpu_ms": 42}
    assert t.preflight_time == 1.0
    assert t.p4_time == 0.5
    assert t.execution_time == 10.0
    assert t.total_time == 11.5
    assert t.final_status == "P4_ALLOW"


def test_normalize_empty_dict_uses_defaults():
    norm = ExecutionTraceNormalizer()
    t = norm.normalize({})
    assert t.event_id == ""
    assert t.session_id == ""
    assert t.sequence_no == 0
    assert t.correlation_id == ""
    assert t.preflight_valid is False
    assert t.preflight_reason is None
    assert t.preflight_rules_triggered == []
    assert t.risk_score == 0.0
    assert t.p4_verdict == "UNKNOWN"
    assert t.p4_reason is None
    assert t.execution_status == "UNKNOWN"
    assert t.final_status == "UNKNOWN"


def test_normalize_final_status_sandbox_failed():
    raw = {"sandbox": {"status": "FAILED", "error": "crash"}}
    norm = ExecutionTraceNormalizer()
    t = norm.normalize(raw)
    assert t.final_status == "SANDBOX_FAILED"


def test_normalize_final_status_p4_verdict():
    for verdict in ("ALLOW", "BLOCK", "DEFER", "REVIEW"):
        raw = {"p4": {"verdict": verdict}}
        t = ExecutionTraceNormalizer().normalize(raw)
        assert t.final_status == f"P4_{verdict}"


def test_normalize_final_status_preflight_invalid():
    raw = {"preflight": {"valid": False}}
    t = ExecutionTraceNormalizer().normalize(raw)
    assert t.final_status == "BLOCKED_BY_PREFLIGHT"


def test_normalize_sandbox_takes_priority_over_p4():
    raw = {
        "sandbox": {"status": "FAILED"},
        "p4": {"verdict": "ALLOW"},
        "preflight": {"valid": True},
    }
    t = ExecutionTraceNormalizer().normalize(raw)
    assert t.final_status == "SANDBOX_FAILED"


def test_normalize_p4_takes_priority_over_preflight():
    raw = {
        "preflight": {"valid": False},
        "p4": {"verdict": "BLOCK"},
    }
    t = ExecutionTraceNormalizer().normalize(raw)
    assert t.final_status == "P4_BLOCK"


def test_normalize_missing_nested_keys():
    raw = {"preflight": {}, "p4": {}, "sandbox": {}}
    t = ExecutionTraceNormalizer().normalize(raw)
    assert t.preflight_valid is False
    assert t.preflight_reason is None
    assert t.preflight_rules_triggered == []
    assert t.p4_verdict == "UNKNOWN"
    assert t.final_status == "UNKNOWN"


def test_enriched_to_trace_dict_full():
    host = HostEvent(
        event_id="e1", session_id="s1",
        timestamp=100.0, source="test", payload={},
    )
    proposal = ExecutionProposal(
        proposal_id="p1", session_id="s1", event_id="e1",
        action="read", target="/f", params={},
        required_capabilities=[Capability.FILESYSTEM_READ],
        confidence=0.9, risk_score=0.05, metadata={},
    )
    decision = PolicyDecision(
        decision_id="d1", proposal_id="p1", session_id="s1",
        verdict="ALLOW", reason="ok", risk_level="low",
        rule_triggered=None, confidence=0.9,
    )
    result = ExecutionResult(
        execution_id="x1", proposal_id="p1", session_id="s1",
        status="SUCCESS", output={"ok": True}, error=None,
        started_at=100.0, finished_at=101.0,
    )
    enriched = EnrichedEvent(
        event_id="e1", session_id="s1",
        sequence_no=1, correlation_id="cid-1",
        host_event=host, p3_proposal=proposal,
        p4_decision=decision, execution_result=result,
    )
    d = enriched_to_trace_dict(enriched)
    assert d["event_id"] == "e1"
    assert d["session_id"] == "s1"
    assert d["sequence_no"] == 1
    assert d["correlation_id"] == "cid-1"
    assert d["preflight"]["valid"] is True
    assert d["preflight"]["reason"] == "proposal_built"
    assert d["risk_score"] == 0.05
    assert d["p4"]["verdict"] == "ALLOW"
    assert d["p4"]["reason"] == "ok"
    assert d["sandbox"]["status"] == "SUCCESS"
    assert d["sandbox"]["capabilities"] == ["filesystem.read"]
    assert d["timing"]["execution"] == 1.0
    assert d["timing"]["total"] == 1.0


def test_enriched_to_trace_dict_without_execution():
    host = HostEvent(
        event_id="e2", session_id="s1",
        timestamp=100.0, source="test", payload={},
    )
    proposal = ExecutionProposal(
        proposal_id="p2", session_id="s1", event_id="e2",
        action="write", target="/f", params={},
        required_capabilities=[Capability.FILESYSTEM_WRITE],
        confidence=0.8, risk_score=0.9, metadata={},
    )
    decision = PolicyDecision(
        decision_id="d2", proposal_id="p2", session_id="s1",
        verdict="BLOCK", reason="high_risk", risk_level="high",
        rule_triggered="rule_42", confidence=0.95,
    )
    enriched = EnrichedEvent(
        event_id="e2", session_id="s1",
        sequence_no=2, correlation_id="cid-2",
        host_event=host, p3_proposal=proposal,
        p4_decision=decision, execution_result=None,
    )
    d = enriched_to_trace_dict(enriched)
    assert d["sandbox"]["status"] == "SKIPPED"
    assert d["sandbox"]["error"] is None
    assert d["timing"]["execution"] == 0.0
    assert d["timing"]["total"] == 0.0


def test_enriched_to_trace_dict_minimal():
    host = HostEvent(
        event_id="e3", session_id="s1",
        timestamp=100.0, source="test", payload={},
    )
    enriched = EnrichedEvent(
        event_id="e3", session_id="s1",
        sequence_no=3, correlation_id="cid-3",
        host_event=host,
    )
    d = enriched_to_trace_dict(enriched)
    assert d["preflight"]["valid"] is False
    assert d["risk_score"] == 0.0
    assert d["p4"]["verdict"] == "UNKNOWN"
    assert d["sandbox"]["status"] == "SKIPPED"
    assert d["sandbox"]["capabilities"] == []
    assert d["timing"]["total"] == 0.0


def test_store_add_and_len():
    store = ExecutionTraceStore()
    assert len(store) == 0
    store.add(ExecutionTrace(event_id="e1"))
    assert len(store) == 1


def test_store_by_correlation_id():
    store = ExecutionTraceStore()
    t = ExecutionTrace(event_id="e1", correlation_id="c1")
    store.add(t)
    assert store.by_correlation_id("c1") is t
    assert store.by_correlation_id("missing") is None


def test_store_by_event_id():
    store = ExecutionTraceStore()
    t = ExecutionTrace(event_id="e1", correlation_id="c1")
    store.add(t)
    assert store.by_event_id("e1") is t
    assert store.by_event_id("missing") is None


def test_store_by_final_status():
    store = ExecutionTraceStore()
    t1 = ExecutionTrace(event_id="e1", final_status="P4_ALLOW")
    t2 = ExecutionTrace(event_id="e2", final_status="P4_BLOCK")
    t3 = ExecutionTrace(event_id="e3", final_status="P4_ALLOW")
    store.add(t1)
    store.add(t2)
    store.add(t3)
    results = store.by_final_status("P4_ALLOW")
    assert len(results) == 2
    assert t1 in results
    assert t3 in results


def test_store_recent():
    store = ExecutionTraceStore()
    for i in range(10):
        store.add(ExecutionTrace(event_id=f"e{i}"))
    recent = store.recent(3)
    assert len(recent) == 3
    assert [t.event_id for t in recent] == ["e7", "e8", "e9"]


def test_store_recent_less_than_n():
    store = ExecutionTraceStore()
    t = ExecutionTrace(event_id="e1")
    store.add(t)
    assert store.recent(10) == [t]


def test_store_clear():
    store = ExecutionTraceStore()
    store.add(ExecutionTrace(event_id="e1"))
    store.clear()
    assert len(store) == 0


def test_store_all_returns_copy():
    store = ExecutionTraceStore()
    t = ExecutionTrace(event_id="e1")
    store.add(t)
    all_traces = store.all
    assert len(all_traces) == 1
    all_traces.clear()
    assert len(store) == 1


def test_store_all_returns_all():
    store = ExecutionTraceStore()
    for i in range(5):
        store.add(ExecutionTrace(event_id=f"e{i}"))
    assert len(store.all) == 5


def test_store_max_size_drops_oldest():
    store = ExecutionTraceStore(max_size=3)
    for i in range(5):
        store.add(ExecutionTrace(event_id=f"e{i}", correlation_id=f"c{i}"))
    assert len(store) == 3
    assert store.by_event_id("e0") is None
    assert store.by_event_id("e1") is None
    assert store.by_event_id("e2") is not None
    assert store.by_event_id("e3") is not None
    assert store.by_event_id("e4") is not None


def test_store_max_size_default():
    store = ExecutionTraceStore()
    assert store._max_size == 1000


def test_store_preserves_order():
    store = ExecutionTraceStore()
    for i in range(5):
        store.add(ExecutionTrace(event_id=f"e{i}"))
    assert [t.event_id for t in store.all] == ["e0", "e1", "e2", "e3", "e4"]
