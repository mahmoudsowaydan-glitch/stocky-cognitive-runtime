"""Tests for cognitive_runtime/recovery/persistence_guard.py."""

import pytest

from cognitive_runtime.recovery.persistence_guard import PersistenceGuard, PersistenceValidation
from cognitive_runtime.recovery.runtime_snapshot import RuntimeSnapshot
from cognitive_runtime.contracts.frozen.schema_version import FROZEN_SCHEMA_VERSION, FROZEN_SCHEMA_VERSION_STR, fingerprint


# ── Helpers ──


def make_snapshot(schema_version=FROZEN_SCHEMA_VERSION_STR, trace_count=0, traces=None,
                  set_fingerprint=False):
    traces = traces or ([] if trace_count == 0 else
                        [{"event_id": f"e{i}", "final_status": "P4_ALLOW"}
                         for i in range(trace_count)])
    snap = RuntimeSnapshot(
        snapshot_id="cp_test", created_at=1000.0,
        runtime_state_snapshot={"status": "stopped"},
        trace_count=trace_count, traces=traces,
        schema_version=schema_version,
    )
    if set_fingerprint:
        snap.schema_fingerprint = fingerprint("RuntimeSnapshot")
    return snap


# ── PersistenceValidation ──


def test_persistence_validation_required():
    pv = PersistenceValidation(
        valid=True, schema_match=True,
        schema_snapshot=FROZEN_SCHEMA_VERSION_STR, schema_current=FROZEN_SCHEMA_VERSION_STR,
        has_required_fields=True, missing_fields=[],
        contract_violations=[], trace_count_positive=True,
    )
    assert pv.valid is True
    assert pv.schema_match is True
    assert pv.has_required_fields is True
    assert pv.missing_fields == []
    assert pv.contract_violations == []


def test_persistence_validation_details_default():
    pv = PersistenceValidation(
        valid=True, schema_match=True,
        schema_snapshot=FROZEN_SCHEMA_VERSION_STR, schema_current=FROZEN_SCHEMA_VERSION_STR,
        has_required_fields=True, missing_fields=[],
        contract_violations=[], trace_count_positive=True,
    )
    assert pv.details == ""


# ── validate_snapshot — valid ──


def test_validate_valid_snapshot():
    snap = make_snapshot(trace_count=2, set_fingerprint=True)
    result = PersistenceGuard().validate_snapshot(snap)
    assert result.valid is True
    assert result.schema_match is True
    assert result.has_required_fields is True


def test_validate_no_fingerprint_skips_check():
    snap = make_snapshot(trace_count=2)
    snap.schema_fingerprint = ""
    result = PersistenceGuard().validate_snapshot(snap)
    assert result.valid is True


# ── validate_snapshot — schema mismatch ──


def test_validate_schema_mismatch_major():
    snap = make_snapshot(schema_version="2.0.0")
    result = PersistenceGuard().validate_snapshot(snap)
    assert result.valid is False
    assert result.schema_match is False
    assert any("Schema mismatch" in v for v in result.contract_violations)


def test_validate_schema_mismatch_minor():
    snap = make_snapshot(schema_version="1.2.0")
    result = PersistenceGuard().validate_snapshot(snap)
    assert result.valid is False
    assert result.schema_match is False


def test_validate_invalid_schema_format():
    snap = make_snapshot(schema_version="invalid")
    result = PersistenceGuard().validate_snapshot(snap)
    assert result.valid is False
    assert result.schema_match is False


# ── validate_snapshot — missing fields ──


def test_validate_missing_snapshot_id():
    snap = make_snapshot()
    snap.snapshot_id = None
    result = PersistenceGuard().validate_snapshot(snap)
    assert result.valid is False
    assert result.has_required_fields is False
    assert "snapshot_id" in result.missing_fields


def test_validate_missing_traces():
    snap = make_snapshot()
    snap.traces = None
    result = PersistenceGuard().validate_snapshot(snap)
    assert "traces" in result.missing_fields


def test_validate_trace_count_mismatch():
    snap = make_snapshot(trace_count=5, traces=[{"event_id": "e0"}])
    result = PersistenceGuard().validate_snapshot(snap)
    assert result.valid is False
    assert any("Trace count mismatch" in v for v in result.contract_violations)


def test_validate_fingerprint_mismatch():
    snap = make_snapshot(set_fingerprint=True)
    snap.schema_fingerprint = "wrong_fingerprint"
    result = PersistenceGuard().validate_snapshot(snap)
    assert result.valid is False
    assert any("Fingerprint mismatch" in v for v in result.contract_violations)


def test_validate_multiple_missing_fields():
    snap = make_snapshot()
    snap.snapshot_id = None
    snap.created_at = None
    result = PersistenceGuard().validate_snapshot(snap)
    assert result.valid is False
    assert "snapshot_id" in result.missing_fields
    assert "created_at" in result.missing_fields


# ── validate_snapshot — values ──


def test_validate_schema_values():
    snap = make_snapshot()
    result = PersistenceGuard().validate_snapshot(snap)
    expected = str(FROZEN_SCHEMA_VERSION)
    assert result.schema_snapshot == expected
    assert result.schema_current == expected


def test_validate_trace_count_positive():
    snap = make_snapshot(trace_count=0)
    result = PersistenceGuard().validate_snapshot(snap)
    assert result.trace_count_positive is True


# ── validate_runtime ──


def test_validate_runtime_no_contract_guard():
    class NoGuardLoop:
        pass
    result = PersistenceGuard().validate_runtime(NoGuardLoop())
    assert result == []


def test_validate_runtime_passed():
    class MockContractGuard:
        def run_all(self, loop):
            return {"passed": True}
    class Loop:
        _contract_guard = MockContractGuard()
    result = PersistenceGuard().validate_runtime(Loop())
    assert result == []


def test_validate_runtime_violations():
    class MockContractGuard:
        def run_all(self, loop):
            return {"passed": False}
        @property
        def violations(self):
            return [{"component": "trace", "message": "missing field"}]
    class Loop:
        _contract_guard = MockContractGuard()
    result = PersistenceGuard().validate_runtime(Loop())
    assert len(result) == 1
    assert "trace:" in result[0]


# ── SchemaEvolutionGuard integration ──


def _make_evolution_guard():
    from cognitive_runtime.schema_evolution.evolution_graph import EvolutionGraph
    from cognitive_runtime.schema_evolution.evolution_node import SchemaVersionNode
    from cognitive_runtime.schema_evolution.schema_evolution_guard import SchemaEvolutionGuard
    g = EvolutionGraph()
    g.register_node(SchemaVersionNode(version="1.0.0", parent_versions=(), is_frozen=True,
                                       breaking_changes=(), compatibility_hash=""))
    g.register_node(SchemaVersionNode(version="1.1.0", parent_versions=("1.0.0",), is_frozen=True,
                                       breaking_changes=(), compatibility_hash=""))
    return SchemaEvolutionGuard(g)


def test_evolution_guard_exact_version_match():
    guard = PersistenceGuard(schema_evolution_guard=_make_evolution_guard())
    snap = make_snapshot(schema_version="1.1.0", trace_count=2, set_fingerprint=True)
    result = guard.validate_snapshot(snap)
    assert result.valid is True
    assert result.schema_match is True


def test_evolution_guard_backward_compat_accepted():
    guard = PersistenceGuard(schema_evolution_guard=_make_evolution_guard())
    snap = make_snapshot(schema_version="1.0.0", trace_count=1, set_fingerprint=True)
    result = guard.validate_snapshot(snap)
    assert result.valid is True
    assert result.schema_match is True


def test_evolution_guard_major_mismatch_rejected():
    guard = PersistenceGuard(schema_evolution_guard=_make_evolution_guard())
    snap = make_snapshot(schema_version="2.0.0", trace_count=1)
    result = guard.validate_snapshot(snap)
    assert result.valid is False
    assert result.schema_match is False
    assert any("Schema mismatch" in v for v in result.contract_violations)


def test_evolution_guard_unknown_minor_rejected():
    guard = PersistenceGuard(schema_evolution_guard=_make_evolution_guard())
    snap = make_snapshot(schema_version="1.2.0", trace_count=1)
    result = guard.validate_snapshot(snap)
    assert result.valid is False
    assert result.schema_match is False


def test_evolution_guard_invalid_format_rejected():
    guard = PersistenceGuard(schema_evolution_guard=_make_evolution_guard())
    snap = make_snapshot(schema_version="not.a.version", trace_count=1)
    result = guard.validate_snapshot(snap)
    assert result.valid is False
    assert result.schema_match is False


def test_evolution_guard_other_checks_still_run():
    guard = PersistenceGuard(schema_evolution_guard=_make_evolution_guard())
    snap = make_snapshot(schema_version="1.1.0", trace_count=5, traces=[{"event_id": "e0"}])
    result = guard.validate_snapshot(snap)
    assert result.valid is False
    assert any("Trace count mismatch" in v for v in result.contract_violations)


def test_evolution_guard_does_not_migrate_original():
    guard = PersistenceGuard(schema_evolution_guard=_make_evolution_guard())
    snap = make_snapshot(schema_version="1.0.0", trace_count=1, set_fingerprint=True)
    result = guard.validate_snapshot(snap)
    assert result.valid is True
    assert result.schema_match is True
    assert snap.schema_version == "1.0.0"
