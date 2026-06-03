"""Drift injection tests -- verify CompatibilityGuard and PersistenceGuard detect intentional schema, bridge, causal, fingerprint, and version drift."""

from cognitive_runtime.contracts.execution_trace import ExecutionTrace
from cognitive_runtime.contracts.causal_graph import CausalNode
from cognitive_runtime.contracts.frozen.compatibility_guard import CompatibilityGuard
from cognitive_runtime.contracts.frozen.schema_version import (
    FROZEN_SCHEMA_VERSION, SchemaVersion, fingerprint,
)
from cognitive_runtime.contracts.frozen.trace_contract import TraceContract
from cognitive_runtime.contracts.frozen.graph_contract import (
    GraphContract, CausalNodeContract, CausalEdgeContract,
)
from cognitive_runtime.contracts.frozen.bridge_contract import BridgeContract
from cognitive_runtime.recovery.persistence_guard import PersistenceGuard
from cognitive_runtime.recovery.runtime_snapshot import RuntimeSnapshot


# ─── a) Schema Drift ─────────────────────────


def test_missing_field_detected():
    guard = CompatibilityGuard()

    class BadTrace:
        pass

    assert not guard.check_trace(BadTrace())
    assert guard.violation_count > 0
    assert any("missing field" in v["message"] for v in guard.violations)


def test_trace_with_extra_fields_passes():
    guard = CompatibilityGuard()
    assert guard.check_trace(ExecutionTrace(event_id="e1", session_id="s1"))


def test_normalizer_drift_detected():
    guard = CompatibilityGuard()

    class BadNormalizer:
        pass

    assert not guard.check_normalizer(BadNormalizer())
    assert any("missing method" in v["message"] for v in guard.violations)


def test_trace_with_all_fields_passes():
    trace = ExecutionTrace(
        event_id="e1", session_id="s1", sequence_no=1, correlation_id="c1",
        preflight_valid=True, preflight_reason="ok", preflight_rules_triggered=[], risk_score=0.1,
        p4_verdict="ALLOW", p4_reason="ok", p4_risk_level="low", p4_rule_triggered=None,
        execution_status="SUCCESS", execution_error=None,
        capabilities_checked=["filesystem.read"], resource_usage={},
        preflight_time=0.0, p4_time=0.0, execution_time=1.0, total_time=1.0,
        final_status="P4_ALLOW",
    )
    assert TraceContract.check_trace(trace) == []


def test_empty_object_fails_trace_contract():
    assert len(TraceContract.check_trace(object())) == len(TraceContract.EXPECTED_FIELDS)


# ─── b) Bridge Mismatch ──────────────────────


def test_missing_tap_methods_detected():
    guard = CompatibilityGuard()

    class BadTap:
        pass

    assert not guard.check_observation_tap(BadTap())
    assert guard.violation_count > 0


def test_tap_missing_all_methods():
    violations = BridgeContract.check_observation_tap(object())
    assert len(violations) == len(BridgeContract.TAP_EXPECTED_METHODS) + len(BridgeContract.TAP_EXPECTED_PROPERTIES)


def test_feedback_bridge_missing_detected():
    guard = CompatibilityGuard()

    class BadBridge:
        pass

    assert not guard.check_feedback_bridge(BadBridge())


def test_feedback_bridge_passes():
    from cognitive_runtime.runtime.feedback_bridge import FeedbackBridge
    assert BridgeContract.check_feedback_bridge(FeedbackBridge()) == []


def test_enriched_event_missing_fields():
    assert not CompatibilityGuard().check_enriched_event(object())


# ─── c) Causal Corruption ────────────────────


def test_missing_node_attributes_detected():

    class BadNode:
        def __init__(self):
            self.node_id = "n1"

    violations = GraphContract.check_node_instance(BadNode())
    assert len(violations) > 0
    assert any("missing attribute" in v for v in violations)


def test_corrupt_graph_detected():
    guard = CompatibilityGuard()

    class BadGraph:
        pass

    assert not guard.check_graph("corrupt", BadGraph())


def test_invalid_node_type():

    n = CausalNode(
        node_id="n1", event_id="e1", correlation_id="c1",
        node_type="bad_type", data={}, timestamp=0.0,
    )
    contract = CausalNodeContract.from_instance(n)
    violations = contract.validate()
    assert any("invalid node_type" in v for v in violations)


def test_node_empty_id_fails():

    contract = CausalNodeContract(
        node_id="", event_id="e1", correlation_id="c1",
        node_type="host_event", data={}, timestamp=0.0,
        parent_id=None, children=[],
    )
    assert any("node_id must be non-empty" in v for v in contract.validate())


def test_invalid_edge_type():
    contract = CausalEdgeContract(
        edge_id="e1", source_id="n1", target_id="n2",
        edge_type="invalid", meta={},
    )
    assert any("invalid edge_type" in v for v in contract.validate())


def test_missing_edge_attributes_detected():
    assert len(GraphContract.check_edge_instance(object())) > 0


# ─── d) Fingerprint Inconsistency ────────────


def test_fingerprint_changes_when_trace_modified():
    trace = ExecutionTrace(event_id="e1", session_id="s1", final_status="P4_ALLOW")
    fp1 = fingerprint(trace)
    trace.event_id = "e2"
    assert fp1 != fingerprint(trace)


def test_fingerprint_stable_for_unchanged():
    trace = ExecutionTrace(event_id="e1", session_id="s1")
    assert fingerprint(trace) == fingerprint(trace)


def test_persistence_guard_detects_fingerprint_mismatch():
    guard = PersistenceGuard()
    snap = RuntimeSnapshot(
        snapshot_id="cp_test", created_at=100.0,
        runtime_state_snapshot={"status": "running"},
        trace_count=1, traces=[{"event_id": "e1"}],
        schema_version=str(FROZEN_SCHEMA_VERSION), schema_fingerprint="wrong_fingerprint",
    )
    v = guard.validate_snapshot(snap)
    assert not v.valid
    assert any("Fingerprint mismatch" in err for err in v.contract_violations)


def test_fingerprint_differs_empty_vs_nonempty():
    assert fingerprint(object()) != fingerprint(ExecutionTrace(event_id="e1"))


def test_contract_fingerprints_registered():
    from cognitive_runtime.contracts.frozen.schema_version import ContractFingerprints
    assert "ExecutionTrace" in ContractFingerprints
    assert "CausalNode" in ContractFingerprints
    assert "CausalEdge" in ContractFingerprints


# ─── e) Version Mismatch ─────────────────────


def test_major_version_mismatch_rejected():
    snap = RuntimeSnapshot(snapshot_id="cp_bad", created_at=100.0, runtime_state_snapshot={},
                           trace_count=0, traces=[], schema_version="2.0.0")
    v = PersistenceGuard().validate_snapshot(snap)
    assert not v.valid and not v.schema_match
    assert any("Schema mismatch" in err for err in v.contract_violations)


def test_minor_version_mismatch_rejected():
    snap = RuntimeSnapshot(snapshot_id="cp_badm", created_at=100.0, runtime_state_snapshot={},
                           trace_count=0, traces=[], schema_version="1.2.0")
    v = PersistenceGuard().validate_snapshot(snap)
    assert not v.valid and not v.schema_match


def test_current_version_accepted():
    snap = RuntimeSnapshot(snapshot_id="cp_good", created_at=100.0, runtime_state_snapshot={},
                           trace_count=0, traces=[], schema_version=str(FROZEN_SCHEMA_VERSION))
    v = PersistenceGuard().validate_snapshot(snap)
    assert v.valid and v.schema_match


def test_invalid_version_string_caught():
    snap = RuntimeSnapshot(snapshot_id="cp_inv", created_at=100.0, runtime_state_snapshot={},
                           trace_count=0, traces=[], schema_version="not.a.version")
    v = PersistenceGuard().validate_snapshot(snap)
    assert not v.valid and not v.schema_match
    assert any("Invalid schema version" in err for err in v.contract_violations)


def test_compatibility_guard_stores_version():
    guard = CompatibilityGuard(schema_version=SchemaVersion(major=2, minor=0, patch=0))
    assert guard.schema_version.major == 2


def test_schema_version_compatible():
    assert SchemaVersion(1, 0, 0).is_compatible_with(SchemaVersion(1, 0, 5))


def test_schema_version_not_compatible():
    assert not SchemaVersion(1, 0, 0).is_compatible_with(SchemaVersion(2, 0, 0))


def test_snapshot_schema_version_string():
    expected = str(FROZEN_SCHEMA_VERSION)
    snap = RuntimeSnapshot(snapshot_id="cp_t", created_at=100.0, runtime_state_snapshot={},
                           trace_count=0, traces=[], schema_version=expected)
    assert snap.schema_version == expected
