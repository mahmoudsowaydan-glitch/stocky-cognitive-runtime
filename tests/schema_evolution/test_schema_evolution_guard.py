"""Tests for cognitive_runtime/schema_evolution/schema_evolution_guard.py."""

import pytest

from cognitive_runtime.schema_evolution import (
    EvolutionGraph, SchemaVersionNode, SchemaEvolutionGuard,
)
from cognitive_runtime.recovery.runtime_snapshot import RuntimeSnapshot
from cognitive_runtime.contracts.execution_trace import ExecutionTrace


@pytest.fixture
def graph():
    g = EvolutionGraph()
    g.register_node(SchemaVersionNode(version="1.0.0", parent_versions=()))
    g.register_node(SchemaVersionNode(version="1.1.0", parent_versions=("1.0.0",)))
    return g


def make_trace(event_id, risk=0.0):
    return ExecutionTrace(
        event_id=event_id, session_id="s1", sequence_no=int(event_id[1:]),
        correlation_id="c1", risk_score=risk,
    )


def test_validate_snapshot_current_version(graph):
    snap = RuntimeSnapshot(
        snapshot_id="cp_1", created_at=1.0,
        runtime_state_snapshot={}, trace_count=1,
        traces=[{"event_id": "e1"}],
        schema_version="1.1.0",
    )
    guard = SchemaEvolutionGuard(graph)
    result = guard.validate_snapshot(snap, "1.1.0")
    assert result.schema_version == "1.1.0"


def test_validate_snapshot_compatible_backward(graph):
    snap = RuntimeSnapshot(
        snapshot_id="cp_1", created_at=1.0,
        runtime_state_snapshot={}, trace_count=1,
        traces=[make_trace("e1", risk=50.0).__dict__],
        schema_version="1.0.0",
    )
    guard = SchemaEvolutionGuard(graph)
    result = guard.validate_snapshot(snap, "1.1.0")
    assert result.schema_version == "1.0.0"


def test_validate_snapshot_invalid_path_rejected(graph):
    snap = RuntimeSnapshot(
        snapshot_id="cp_1", created_at=1.0,
        runtime_state_snapshot={}, trace_count=0, traces=[],
        schema_version="1.0.0",
    )
    guard = SchemaEvolutionGuard(graph)
    with pytest.raises(ValueError, match="NO_VALID_MIGRATION_PATH"):
        guard.validate_snapshot(snap, "2.0.0")


def test_snapshot_missing_version_rejected(graph):
    snap = RuntimeSnapshot(
        snapshot_id="cp_1", created_at=1.0,
        runtime_state_snapshot={}, trace_count=0, traces=[],
        schema_version=None,
    )
    guard = SchemaEvolutionGuard(graph)
    with pytest.raises(ValueError, match="no schema_version"):
        guard.validate_snapshot(snap, "1.1.0")


def test_migrate_snapshot_changes_schema_version(graph):
    traces = [make_trace("e1").__dict__]
    snap = RuntimeSnapshot(
        snapshot_id="cp_1", created_at=1.0,
        runtime_state_snapshot={}, trace_count=1, traces=traces,
        schema_version="1.0.0",
    )
    guard = SchemaEvolutionGuard(graph)
    result = guard.migrate_snapshot(snap, "1.0.0", "1.1.0")
    assert result.schema_version == "1.1.0"


def test_migrate_snapshot_invalid_path(graph):
    snap = RuntimeSnapshot(
        snapshot_id="cp_1", created_at=1.0,
        runtime_state_snapshot={}, trace_count=0, traces=[],
        schema_version="1.0.0",
    )
    guard = SchemaEvolutionGuard(graph)
    with pytest.raises(ValueError, match="NO_VALID_MIGRATION_PATH"):
        guard.migrate_snapshot(snap, "1.0.0", "2.0.0")


def test_guard_does_not_mutate_original_snapshot(graph):
    traces = [make_trace("e1", risk=50.0).__dict__]
    snap = RuntimeSnapshot(
        snapshot_id="cp_1", created_at=1.0,
        runtime_state_snapshot={}, trace_count=1, traces=traces,
        schema_version="1.0.0",
    )
    guard = SchemaEvolutionGuard(graph)
    guard.migrate_snapshot(snap, "1.0.0", "1.1.0")
    assert snap.schema_version == "1.0.0"
