"""Tests for cognitive_runtime/schema_evolution/migration_engine.py."""

import copy

import pytest

from cognitive_runtime.schema_evolution import (
    EvolutionGraph, SchemaVersionNode, MigrationEngine, MigrationPlan,
)
from cognitive_runtime.contracts.execution_trace import ExecutionTrace


@pytest.fixture
def graph():
    g = EvolutionGraph()
    g.register_node(SchemaVersionNode(version="1.0.0", parent_versions=()))
    g.register_node(SchemaVersionNode(version="1.1.0", parent_versions=("1.0.0",)))
    return g


@pytest.fixture
def chain_graph():
    g = EvolutionGraph()
    g.register_node(SchemaVersionNode(version="1.0.0", parent_versions=()))
    g.register_node(SchemaVersionNode(version="1.1.0", parent_versions=("1.0.0",)))
    g.register_node(SchemaVersionNode(version="1.2.0", parent_versions=("1.1.0",)))
    return g


# ── build_path ──


def test_build_path_valid_minor_bump(graph):
    engine = MigrationEngine(graph)
    plan = engine.build_path("1.0.0", "1.1.0")
    assert plan.is_supported is True
    assert "1.0.0->1.1.0" in plan.steps


def test_build_path_same_version_unsupported(graph):
    engine = MigrationEngine(graph)
    plan = engine.build_path("1.0.0", "1.0.0")
    assert plan.is_supported is False


def test_build_path_major_jump_rejected(graph):
    engine = MigrationEngine(graph)
    plan = engine.build_path("1.0.0", "2.0.0")
    assert plan.is_supported is False


def test_build_path_reverse_rejected(graph):
    engine = MigrationEngine(graph)
    plan = engine.build_path("1.1.0", "1.0.0")
    assert plan.is_supported is False


def test_build_path_unknown_version(graph):
    engine = MigrationEngine(graph)
    plan = engine.build_path("1.0.0", "99.0.0")
    assert plan.is_supported is False


def test_build_path_chain_upgrade(chain_graph):
    engine = MigrationEngine(chain_graph)
    plan = engine.build_path("1.0.0", "1.2.0")
    assert plan.is_supported is True
    assert "1.0.0->1.1.0" in plan.steps
    assert "1.1.0->1.2.0" in plan.steps


def test_build_path_single_step_chain(chain_graph):
    engine = MigrationEngine(chain_graph)
    plan = engine.build_path("1.1.0", "1.2.0")
    assert plan.is_supported is True
    assert "1.1.0->1.2.0" in plan.steps


# ── migrate_trace ──


def test_migrate_trace_normalizes_risk_score(graph):
    trace = ExecutionTrace(
        event_id="e1", session_id="s1", sequence_no=1,
        correlation_id="c1", risk_score=75.0,
    )
    engine = MigrationEngine(graph)
    result = engine.migrate_trace(trace, "1.0.0", "1.1.0")
    assert result.risk_score == 0.75


def test_migrate_trace_adds_confidence_field_for_dict(graph):
    trace = {
        "event_id": "e1", "session_id": "s1", "sequence_no": 1,
        "correlation_id": "c1",
    }
    engine = MigrationEngine(graph)
    result = engine.migrate_trace(trace, "1.0.0", "1.1.0")
    assert result["execution_confidence"] == 1.0


def test_migrate_trace_does_not_mutate_original(graph):
    trace = ExecutionTrace(
        event_id="e1", session_id="s1", sequence_no=1,
        correlation_id="c1", risk_score=50.0,
    )
    original_score = trace.risk_score
    engine = MigrationEngine(graph)
    engine.migrate_trace(trace, "1.0.0", "1.1.0")
    assert trace.risk_score == original_score


def test_migrate_trace_invalid_path_rejected(graph):
    trace = ExecutionTrace(
        event_id="e1", session_id="s1", sequence_no=1,
        correlation_id="c1",
    )
    engine = MigrationEngine(graph)
    with pytest.raises(ValueError, match="No supported migration path"):
        engine.migrate_trace(trace, "1.0.0", "2.0.0")


def test_migrate_trace_deterministic(graph):
    trace = {
        "event_id": "e1", "session_id": "s1", "sequence_no": 1,
        "correlation_id": "c1", "risk_score": 30.0,
    }
    engine = MigrationEngine(graph)
    r1 = engine.migrate_trace(trace, "1.0.0", "1.1.0")
    r2 = engine.migrate_trace(trace, "1.0.0", "1.1.0")
    assert r1["risk_score"] == r2["risk_score"]
    assert r1["execution_confidence"] == r2["execution_confidence"]


def test_migrate_trace_dict_input(graph):
    trace = {
        "event_id": "e1", "session_id": "s1", "sequence_no": 1,
        "correlation_id": "c1", "risk_score": 90.0,
    }
    engine = MigrationEngine(graph)
    result = engine.migrate_trace(trace, "1.0.0", "1.1.0")
    assert result["risk_score"] == 0.9
    assert result["execution_confidence"] == 1.0


# ── EVOL invariants ──


def test_migration_plan_fields():
    plan = MigrationPlan(from_version="1.0.0", to_version="1.1.0")
    import dataclasses
    assert dataclasses.is_dataclass(plan)
    assert plan.from_version == "1.0.0"
    assert plan.to_version == "1.1.0"
    assert plan.steps == []


def test_engine_does_not_mutate_graph(graph):
    before_count = graph.node_count
    engine = MigrationEngine(graph)
    engine.build_path("1.0.0", "1.1.0")
    assert graph.node_count == before_count
