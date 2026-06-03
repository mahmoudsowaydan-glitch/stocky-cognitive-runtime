"""Tests for cognitive_runtime/recovery/replay_validator.py."""

import pytest

from cognitive_runtime.recovery.replay_validator import ReplayValidator, ReplayValidation
from cognitive_runtime.recovery.runtime_snapshot import RuntimeSnapshot
from cognitive_runtime.contracts.execution_trace import ExecutionTrace
from cognitive_runtime.contracts.frozen.schema_version import fingerprint


# ── Helpers ──


def make_trace(event_id, final_status="P4_ALLOW", session_id="s1",
               sequence_no=0, correlation_id="", exec_status="SUCCESS"):
    return ExecutionTrace(
        event_id=event_id, session_id=session_id,
        sequence_no=sequence_no,
        correlation_id=correlation_id or f"c{event_id[1:]}",
        preflight_valid=True, preflight_reason="preflight_passed",
        risk_score=0.1,
        p4_verdict="ALLOW" if final_status == "P4_ALLOW" else "BLOCK",
        p4_reason="ok", p4_risk_level="low",
        execution_status=exec_status,
        final_status=final_status,
    )


def make_trace_dict(event_id, final_status="P4_ALLOW"):
    return {
        "event_id": event_id, "session_id": "s1",
        "sequence_no": int(event_id[1:]),
        "correlation_id": f"c{event_id[1:]}",
        "preflight_valid": True, "preflight_reason": "preflight_passed",
        "preflight_rules_triggered": [], "risk_score": 0.1,
        "p4_verdict": "ALLOW", "p4_reason": "ok",
        "p4_risk_level": "low", "p4_rule_triggered": None,
        "execution_status": "SUCCESS", "execution_error": None,
        "capabilities_checked": [], "resource_usage": {},
        "preflight_time": 0.0, "p4_time": 0.0,
        "execution_time": 0.0, "total_time": 0.0,
        "final_status": final_status,
    }


def make_snapshot(traces_dicts):
    return RuntimeSnapshot(
        snapshot_id="cp_replay", created_at=1000.0,
        runtime_state_snapshot={"status": "stopped"},
        trace_count=len(traces_dicts),
        traces=traces_dicts,
    )


# ── ReplayValidation ──


def test_replay_validation_required():
    rv = ReplayValidation(
        valid=True, total_original=5, total_replayed=5,
        divergence_count=0, divergences=[],
        causal_integrity=True, trace_fingerprint_match=True,
        original_fingerprint="abc", replayed_fingerprint="abc",
        details="valid",
    )
    assert rv.valid is True
    assert rv.total_original == 5
    assert rv.divergence_count == 0
    assert rv.causal_integrity is True


def test_replay_validation_divergence():
    rv = ReplayValidation(
        valid=False, total_original=3, total_replayed=4,
        divergence_count=1,
        divergences=[{"type": "count_mismatch", "detail": "3 vs 4"}],
        causal_integrity=True, trace_fingerprint_match=False,
        original_fingerprint="abc", replayed_fingerprint="xyz",
        details="1 divergence(s) found",
    )
    assert rv.valid is False
    assert rv.divergence_count == 1
    assert rv.trace_fingerprint_match is False


# ── Identical traces ──


def test_identical_traces_valid():
    traces_dict = [make_trace_dict("e0"), make_trace_dict("e1")]
    snap = make_snapshot(traces_dict)
    replayed = [make_trace("e0"), make_trace("e1")]
    result = ReplayValidator().validate(snap, replayed)
    assert result.valid is True
    assert result.divergence_count == 0


def test_identical_traces_fingerprint_match():
    traces_dict = [make_trace_dict(f"e{i}") for i in range(3)]
    snap = make_snapshot(traces_dict)
    replayed = [make_trace(f"e{i}") for i in range(3)]
    result = ReplayValidator().validate(snap, replayed)
    assert result.trace_fingerprint_match is True
    assert result.original_fingerprint == result.replayed_fingerprint


def test_identical_traces_causal_integrity():
    traces_dict = [make_trace_dict(f"e{i}") for i in range(5)]
    snap = make_snapshot(traces_dict)
    replayed = [make_trace(f"e{i}") for i in range(5)]
    result = ReplayValidator().validate(snap, replayed)
    assert result.causal_integrity is True


def test_identical_ten_traces(sample_traces_10):
    traces_dict = [
        {"event_id": t.event_id, "session_id": t.session_id,
         "sequence_no": t.sequence_no,
         "correlation_id": t.correlation_id,
         "preflight_valid": t.preflight_valid,
         "preflight_reason": t.preflight_reason,
         "preflight_rules_triggered": t.preflight_rules_triggered,
         "risk_score": t.risk_score,
         "p4_verdict": t.p4_verdict, "p4_reason": t.p4_reason,
         "p4_risk_level": t.p4_risk_level,
         "p4_rule_triggered": t.p4_rule_triggered,
         "execution_status": t.execution_status,
         "execution_error": t.execution_error,
         "capabilities_checked": t.capabilities_checked,
         "resource_usage": t.resource_usage,
         "preflight_time": t.preflight_time, "p4_time": t.p4_time,
         "execution_time": t.execution_time, "total_time": t.total_time,
         "final_status": t.final_status}
        for t in sample_traces_10
    ]
    snap = make_snapshot(traces_dict)
    result = ReplayValidator().validate(snap, sample_traces_10)
    assert result.valid is True
    assert result.total_original == 10
    assert result.total_replayed == 10


# ── Divergences ──


def test_event_id_mismatch():
    traces_dict = [make_trace_dict("e0"), make_trace_dict("e1")]
    snap = make_snapshot(traces_dict)
    replayed = [make_trace("e0"), make_trace("e2")]
    result = ReplayValidator().validate(snap, replayed)
    assert result.valid is False
    types = [d["type"] for d in result.divergences]
    assert "event_id_mismatch" in types


def test_final_status_mismatch():
    traces_dict = [make_trace_dict("e0", "P4_ALLOW")]
    snap = make_snapshot(traces_dict)
    replayed = [make_trace("e0", "P4_BLOCK")]
    result = ReplayValidator().validate(snap, replayed)
    assert result.valid is False
    types = [d["type"] for d in result.divergences]
    assert "final_status_mismatch" in types


def test_count_mismatch():
    traces_dict = [make_trace_dict(f"e{i}") for i in range(3)]
    snap = make_snapshot(traces_dict)
    replayed = [make_trace(f"e{i}") for i in range(2)]
    result = ReplayValidator().validate(snap, replayed)
    assert result.valid is False
    types = [d["type"] for d in result.divergences]
    assert "count_mismatch" in types


def test_different_order_detected():
    traces_dict = [make_trace_dict("e0"), make_trace_dict("e1")]
    snap = make_snapshot(traces_dict)
    replayed = [make_trace("e1"), make_trace("e0")]
    result = ReplayValidator().validate(snap, replayed)
    assert result.valid is False


def test_extra_replayed_trace():
    traces_dict = [make_trace_dict("e0")]
    snap = make_snapshot(traces_dict)
    replayed = [make_trace("e0"), make_trace("e1")]
    result = ReplayValidator().validate(snap, replayed)
    assert result.valid is False
    assert result.total_original == 1
    assert result.total_replayed == 2


# ── _dict_to_trace ──


def test_dict_to_trace_conversion():
    d = {"event_id": "e42", "session_id": "s2", "sequence_no": 42,
         "final_status": "P4_ALLOW"}
    trace = ReplayValidator()._dict_to_trace(d)
    assert isinstance(trace, ExecutionTrace)
    assert trace.event_id == "e42"
    assert trace.session_id == "s2"


def test_dict_to_trace_defaults():
    trace = ReplayValidator()._dict_to_trace({})
    assert trace.event_id == ""
    assert trace.final_status == "UNKNOWN"


def test_dict_to_trace_passthrough():
    t = make_trace("e1")
    result = ReplayValidator()._dict_to_trace(t)
    assert result is t


def test_dict_to_trace_unknown_type():
    trace = ReplayValidator()._dict_to_trace(42)
    assert isinstance(trace, ExecutionTrace)
    assert trace.event_id == ""


def test_build_trace_list():
    dicts = [{"event_id": "e1"}, {"event_id": "e2"}]
    traces = ReplayValidator()._build_trace_list(dicts)
    assert len(traces) == 2
    assert all(isinstance(t, ExecutionTrace) for t in traces)


# ── Fingerprint ──


def test_same_traces_same_fingerprint():
    traces = [make_trace_dict("e0", "P4_ALLOW"),
              make_trace_dict("e1", "P4_BLOCK")]
    snap = make_snapshot(traces)
    replayed = [make_trace("e0", "P4_ALLOW"), make_trace("e1", "P4_BLOCK")]
    result = ReplayValidator().validate(snap, replayed)
    assert result.original_fingerprint == result.replayed_fingerprint


def test_different_traces_different_fingerprint():
    traces = [make_trace_dict("e0", "P4_ALLOW")]
    snap = make_snapshot(traces)
    replayed = [make_trace("e0", "P4_BLOCK")]
    result = ReplayValidator().validate(snap, replayed)
    assert result.original_fingerprint != result.replayed_fingerprint


def test_fingerprint_deterministic():
    d1 = [make_trace_dict("e0"), make_trace_dict("e1")]
    d2 = [make_trace_dict("e0"), make_trace_dict("e1")]
    replayed = [make_trace("e0"), make_trace("e1")]
    v = ReplayValidator()
    r1 = v.validate(make_snapshot(d1), replayed)
    r2 = v.validate(make_snapshot(d2), replayed)
    assert r1.original_fingerprint == r2.original_fingerprint


# ── Causal graph ──


def test_causal_integrity_identical():
    traces = [make_trace_dict(f"e{i}") for i in range(3)]
    snap = make_snapshot(traces)
    replayed = [make_trace(f"e{i}") for i in range(3)]
    result = ReplayValidator().validate(snap, replayed)
    assert result.causal_integrity is True


def test_causal_integrity_single_trace():
    traces = [make_trace_dict("e0")]
    snap = make_snapshot(traces)
    replayed = [make_trace("e0")]
    result = ReplayValidator().validate(snap, replayed)
    assert result.causal_integrity is True


def test_causal_graph_with_empty_traces():
    snap = make_snapshot([])
    result = ReplayValidator().validate(snap, [])
    assert result.valid is True
    assert result.causal_integrity is True


# ── Details ──


def test_valid_details():
    traces = [make_trace_dict("e0")]
    snap = make_snapshot(traces)
    result = ReplayValidator().validate(snap, [make_trace("e0")])
    assert result.details == "valid"


def test_invalid_details():
    traces = [make_trace_dict("e0")]
    snap = make_snapshot(traces)
    result = ReplayValidator().validate(snap, [make_trace("e1")])
    assert "divergence(s)" in result.details
