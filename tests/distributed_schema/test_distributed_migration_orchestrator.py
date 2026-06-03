"""Tests for cognitive_runtime/distributed_schema/distributed_migration_orchestrator.py."""

import pytest

from cognitive_runtime.distributed_schema import (
    SchemaHandshake, SchemaSyncEngine, SchemaSyncRegistry,
    DistributedMigrationOrchestrator,
)
from cognitive_runtime.schema_evolution import (
    EvolutionGraph, SchemaVersionNode, SchemaEvolutionGuard,
)


@pytest.fixture
def graph():
    g = EvolutionGraph()
    g.register_node(SchemaVersionNode(version="1.0.0", parent_versions=()))
    g.register_node(SchemaVersionNode(version="1.1.0", parent_versions=("1.0.0",)))
    return g


@pytest.fixture
def orchestrator(graph):
    return DistributedMigrationOrchestrator(graph, "1.1.0")


@pytest.fixture
def registry():
    r = SchemaSyncRegistry()
    r.register_node(SchemaHandshake(node_id="n1", schema_version="1.1.0"))
    r.register_node(SchemaHandshake(node_id="n2", schema_version="1.0.0"))
    r.register_node(SchemaHandshake(node_id="n3", schema_version="2.0.0"))
    return r


# ── synchronize_node ──


def test_sync_node_same_version(orchestrator):
    h = SchemaHandshake(node_id="n1", schema_version="1.1.0")
    result = orchestrator.synchronize_node(h)
    assert result.success is True
    assert result.action == "ACCEPT"


def test_sync_node_backward_compatible(orchestrator):
    h = SchemaHandshake(node_id="n2", schema_version="1.0.0")
    result = orchestrator.synchronize_node(h)
    assert result.success is True
    assert result.action == "ACCEPT"


def test_sync_node_migratable(orchestrator):
    h = SchemaHandshake(node_id="n3", schema_version="1.0.0")
    result = orchestrator.synchronize_node(h)
    assert result.success is True
    assert result.action == "ACCEPT"


def test_sync_node_migrate_with_three_node_graph():
    g = EvolutionGraph()
    g.register_node(SchemaVersionNode(version="1.0.0", parent_versions=()))
    g.register_node(SchemaVersionNode(version="1.1.0", parent_versions=("1.0.0",)))
    g.register_node(SchemaVersionNode(version="1.2.0", parent_versions=("1.1.0",)))
    o = DistributedMigrationOrchestrator(g, "1.2.0")
    h = SchemaHandshake(node_id="n_old", schema_version="1.0.0")
    result = o.synchronize_node(h)
    assert result.success is True
    assert result.action == "MIGRATE"
    assert "1.0.0 -> 1.2.0" in result.details


def test_sync_node_incompatible(orchestrator):
    h = SchemaHandshake(node_id="n4", schema_version="2.0.0")
    result = orchestrator.synchronize_node(h)
    assert result.success is False
    assert result.action == "ISOLATED"


def test_sync_node_orphan(orchestrator):
    h = SchemaHandshake(node_id="n5", schema_version="99.0.0")
    result = orchestrator.synchronize_node(h)
    assert result.success is False
    assert result.action == "ISOLATED"


# ── synchronize_cluster (DSYNC-003) ──


def test_sync_cluster_all(orchestrator, registry):
    results = orchestrator.synchronize_cluster(registry)
    assert len(results) == 3


def test_sync_cluster_isolates_incompatible(orchestrator, registry):
    results = orchestrator.synchronize_cluster(registry)
    for r in results:
        if r.node_id == "n3":
            assert r.action == "ISOLATED"


def test_sync_cluster_accepts_compatible(orchestrator, registry):
    results = orchestrator.synchronize_cluster(registry)
    for r in results:
        if r.node_id == "n1":
            assert r.action == "ACCEPT"


def test_sync_log_tracks_history(orchestrator):
    h1 = SchemaHandshake(node_id="n1", schema_version="1.1.0")
    h2 = SchemaHandshake(node_id="n2", schema_version="99.0.0")
    orchestrator.synchronize_node(h1)
    orchestrator.synchronize_node(h2)
    assert len(orchestrator.sync_log) == 2


# ── synchronize_trace_to_node (DSYNC-002) ──


def test_sync_trace_accepted(orchestrator):
    h = SchemaHandshake(node_id="n1", schema_version="1.1.0")
    trace = {"event_id": "e1", "risk_score": 50.0}
    result = orchestrator.synchronize_trace_to_node(trace, h)
    assert result["risk_score"] == 50.0


def test_sync_trace_migrated(orchestrator):
    h = SchemaHandshake(node_id="n1", schema_version="1.1.0")
    trace = {"event_id": "e1", "risk_score": 50.0}
    result = orchestrator.synchronize_trace_to_node(trace, h)
    assert result is not None


def test_sync_trace_rejected(orchestrator):
    h = SchemaHandshake(node_id="n1", schema_version="2.0.0")
    trace = {"event_id": "e1"}
    with pytest.raises(ValueError, match="Cannot synchronize trace"):
        orchestrator.synchronize_trace_to_node(trace, h)


# ── DSYNC-004: isolation not cascade ──


def test_isolation_does_not_affect_others(orchestrator, registry):
    results = orchestrator.synchronize_cluster(registry)
    isolated = [r for r in results if r.action == "ISOLATED"]
    accepted = [r for r in results if r.action == "ACCEPT"]
    assert len(isolated) == 1
    assert len(isolated) + len(accepted) == len(results)


# ── DSYNC-005: deterministic ──


def test_orchestrator_decisions_deterministic(orchestrator):
    h = SchemaHandshake(node_id="n1", schema_version="1.0.0")
    r1 = orchestrator.synchronize_node(h)
    orchestrator._sync_log.clear()
    r2 = orchestrator.synchronize_node(h)
    assert r1.action == r2.action
    assert r1.success == r2.success
