import pytest
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from cognitive_runtime.contracts.execution_trace import ExecutionTrace
from cognitive_runtime.contracts.frozen.trace_contract import (
    ExecutionTraceContract,
    TraceContract,
)
from cognitive_runtime.contracts.frozen.schema_version import get_expected_fingerprint


def test_execution_trace_contract_expected_fields():
    contract = ExecutionTraceContract(
        identity={"event_id": "e1", "session_id": "s1", "sequence_no": 1, "correlation_id": "c1"},
        preflight={"valid": True, "reason": "ok", "rules_triggered": [], "risk_score": 0.1},
        p4={"verdict": "ALLOW", "reason": "ok", "risk_level": "low", "rule_triggered": None},
        sandbox={"status": "SUCCESS", "error": None, "capabilities": [], "resource_usage": {}},
        timing={"preflight_time": 0.0, "p4_time": 0.0, "execution_time": 1.0, "total_time": 1.0},
        final_status="P4_ALLOW",
    )
    assert contract.identity["event_id"] == "e1"
    assert contract.p4["verdict"] == "ALLOW"
    assert contract.sandbox["status"] == "SUCCESS"
    assert contract.timing["total_time"] == 1.0
    assert contract.final_status == "P4_ALLOW"


def test_execution_trace_contract_from_instance():
    trace = ExecutionTrace(
        event_id="e1", session_id="s1", sequence_no=1, correlation_id="c1",
        preflight_valid=True, preflight_reason="ok",
        preflight_rules_triggered=["rule_1"],
        risk_score=0.2,
        p4_verdict="ALLOW", p4_reason="ok", p4_risk_level="low", p4_rule_triggered=None,
        execution_status="SUCCESS", execution_error=None,
        capabilities_checked=["read"], resource_usage={"cpu": 0.5},
        preflight_time=0.01, p4_time=0.02, execution_time=0.5, total_time=0.53,
        final_status="P4_ALLOW",
    )
    contract = ExecutionTraceContract.from_instance(trace)
    assert contract.identity["event_id"] == "e1"
    assert contract.preflight["valid"] is True
    assert contract.preflight["rules_triggered"] == ["rule_1"]
    assert contract.preflight["risk_score"] == 0.2
    assert contract.p4["verdict"] == "ALLOW"
    assert contract.p4["risk_level"] == "low"
    assert contract.sandbox["status"] == "SUCCESS"
    assert contract.sandbox["capabilities"] == ["read"]
    assert contract.sandbox["resource_usage"] == {"cpu": 0.5}
    assert contract.timing["preflight_time"] == 0.01
    assert contract.timing["total_time"] == 0.53
    assert contract.final_status == "P4_ALLOW"


def test_execution_trace_contract_is_frozen():
    contract = ExecutionTraceContract({}, {}, {}, {}, {}, "")
    with pytest.raises(Exception):
        contract.final_status = "CHANGED"


def test_execution_trace_contract_validate_valid():
    contract = ExecutionTraceContract(
        identity={"event_id": "e1"}, preflight={},
        p4={"verdict": "ALLOW"}, sandbox={"status": "SUCCESS"},
        timing={}, final_status="P4_ALLOW",
    )
    assert contract.validate() == []


def test_execution_trace_contract_validate_empty_event_id():
    contract = ExecutionTraceContract(
        identity={"event_id": ""}, preflight={},
        p4={"verdict": "ALLOW"}, sandbox={"status": "SUCCESS"},
        timing={}, final_status="",
    )
    violations = contract.validate()
    assert "event_id must be non-empty" in violations


def test_execution_trace_contract_validate_invalid_verdict():
    contract = ExecutionTraceContract(
        identity={"event_id": "e1"}, preflight={},
        p4={"verdict": "INVALID"}, sandbox={"status": "SUCCESS"},
        timing={}, final_status="",
    )
    violations = contract.validate()
    assert any("invalid verdict" in v for v in violations)


def test_execution_trace_contract_validate_valid_verdicts():
    for verdict in ("ALLOW", "BLOCK", "DEFER", "REVIEW", "UNKNOWN", "BLOCKED_BY_PREFLIGHT"):
        contract = ExecutionTraceContract(
            identity={"event_id": "e1"}, preflight={},
            p4={"verdict": verdict}, sandbox={"status": "SUCCESS"},
            timing={}, final_status="",
        )
        assert contract.validate() == []


def test_execution_trace_contract_validate_invalid_execution_status():
    contract = ExecutionTraceContract(
        identity={"event_id": "e1"}, preflight={},
        p4={"verdict": "ALLOW"}, sandbox={"status": "INVALID"},
        timing={}, final_status="",
    )
    violations = contract.validate()
    assert any("invalid execution status" in v for v in violations)


def test_execution_trace_contract_validate_valid_execution_statuses():
    for status in ("SUCCESS", "FAILED", "UNKNOWN", "SKIPPED", "QUEUED"):
        contract = ExecutionTraceContract(
            identity={"event_id": "e1"}, preflight={},
            p4={"verdict": "ALLOW"}, sandbox={"status": status},
            timing={}, final_status="",
        )
        assert contract.validate() == []


def test_trace_contract_expected_fields_21():
    assert len(TraceContract.EXPECTED_FIELDS) == 21


def test_trace_contract_expected_fields_content():
    fields = TraceContract.EXPECTED_FIELDS
    for f in ("event_id", "session_id", "sequence_no", "correlation_id",
              "preflight_valid", "preflight_reason", "preflight_rules_triggered", "risk_score",
              "p4_verdict", "p4_reason", "p4_risk_level", "p4_rule_triggered",
              "execution_status", "execution_error", "capabilities_checked", "resource_usage",
              "preflight_time", "p4_time", "execution_time", "total_time",
              "final_status"):
        assert f in fields


def test_trace_contract_normalizer_method():
    assert "normalize" in TraceContract.EXPECTED_NORMALIZER_METHODS


def test_trace_contract_check_trace_valid():
    trace = ExecutionTrace(
        event_id="e1", session_id="s1", sequence_no=1, correlation_id="c1",
        preflight_valid=True, p4_verdict="ALLOW", execution_status="SUCCESS", final_status="P4_ALLOW",
    )
    assert TraceContract.check_trace(trace) == []


def test_trace_contract_check_trace_missing():
    assert len(TraceContract.check_trace(object())) == 21


def test_trace_contract_check_trace_partial():
    trace = ExecutionTrace(event_id="e1", session_id="s1", sequence_no=1, correlation_id="c1")
    assert TraceContract.check_trace(trace) == []


def test_trace_contract_check_normalizer_missing():
    violations = TraceContract.check_normalizer(object())
    assert "missing method" in violations[0]


def test_trace_contract_check_normalizer_not_callable():
    class Bad:
        normalize = "not_callable"
    violations = TraceContract.check_normalizer(Bad())
    assert "not callable" in violations[0]


def test_trace_contract_check_normalizer_valid():
    from cognitive_runtime.contracts.execution_trace import ExecutionTraceNormalizer
    assert TraceContract.check_normalizer(ExecutionTraceNormalizer()) == []


def test_trace_contract_fingerprint_registered():
    fp = get_expected_fingerprint("ExecutionTrace")
    assert fp is not None
    assert isinstance(fp, str)
