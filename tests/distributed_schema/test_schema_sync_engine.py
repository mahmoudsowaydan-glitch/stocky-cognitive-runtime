"""Tests for cognitive_runtime/distributed_schema/schema_sync_engine.py."""

import pytest

from cognitive_runtime.distributed_schema import (
    SchemaHandshake, SchemaSyncEngine,
)
from cognitive_runtime.schema_evolution import (
    EvolutionGraph, SchemaVersionNode,
)


@pytest.fixture
def graph():
    g = EvolutionGraph()
    g.register_node(SchemaVersionNode(version="1.0.0", parent_versions=()))
    g.register_node(SchemaVersionNode(version="1.1.0", parent_versions=("1.0.0",)))
    return g


# ── evaluate_node ──


def test_exact_version_match(graph):
    engine = SchemaSyncEngine(graph, "1.1.0")
    handshake = SchemaHandshake(node_id="node_a", schema_version="1.1.0")
    response = engine.evaluate_node(handshake)
    assert response.status == "ACCEPT"
    assert response.migration_required is False
    assert response.reason == "exact_version_match"


def test_backward_compatible_accept(graph):
    engine = SchemaSyncEngine(graph, "1.1.0")
    handshake = SchemaHandshake(node_id="node_b", schema_version="1.0.0")
    response = engine.evaluate_node(handshake)
    assert response.status == "ACCEPT"
    assert response.migration_required is False
    assert response.reason == "backward_compatible"


def test_forward_node_rejected_when_no_reverse_path(graph):
    """Engine at 1.0.0, node at 1.1.0: backward compat fails (0>=1),
    build_path(1.1.0→1.0.0) can't find ancestors of 1.0.0 → REJECT."""
    engine = SchemaSyncEngine(graph, "1.0.0")
    handshake = SchemaHandshake(node_id="node_c", schema_version="1.1.0")
    response = engine.evaluate_node(handshake)
    assert response.status == "REJECT"


def test_migrate_path_with_three_version_graph():
    g = EvolutionGraph()
    g.register_node(SchemaVersionNode(version="1.0.0", parent_versions=()))
    g.register_node(SchemaVersionNode(version="1.1.0", parent_versions=("1.0.0",)))
    g.register_node(SchemaVersionNode(version="1.2.0", parent_versions=("1.1.0",)))

    engine = SchemaSyncEngine(g, "1.2.0")
    # 1.0.0 is NOT backward compatible with 1.2.0 (delta=2 > MAX=1)
    # but IS in ancestors of 1.2.0 → MIGRATE
    handshake = SchemaHandshake(node_id="node_x", schema_version="1.0.0")
    response = engine.evaluate_node(handshake)
    assert response.status == "MIGRATE"
    assert response.migration_required is True
    assert response.reason == "migration_path_available"


def test_incompatible_version_rejected(graph):
    engine = SchemaSyncEngine(graph, "1.1.0")
    handshake = SchemaHandshake(node_id="node_d", schema_version="2.0.0")
    response = engine.evaluate_node(handshake)
    assert response.status == "REJECT"
    assert response.reason == "NO_COMPATIBLE_SCHEMA_PATH"


def test_orphan_version_rejected(graph):
    engine = SchemaSyncEngine(graph, "1.1.0")
    handshake = SchemaHandshake(node_id="node_e", schema_version="99.0.0")
    response = engine.evaluate_node(handshake)
    assert response.status == "REJECT"


# ── evaluate_version ──


def test_version_same(graph):
    engine = SchemaSyncEngine(graph, "1.1.0")
    response = engine.evaluate_version("1.1.0", "1.1.0")
    assert response.status == "ACCEPT"


def test_version_backward_compatible(graph):
    engine = SchemaSyncEngine(graph, "1.1.0")
    response = engine.evaluate_version("1.0.0", "1.1.0")
    assert response.status == "ACCEPT"


def test_version_migrate_reverse_rejected(graph):
    engine = SchemaSyncEngine(graph, "1.0.0")
    response = engine.evaluate_version("1.1.0", "1.0.0")
    assert response.status == "REJECT"


def test_version_migrate_with_three_version_graph():
    g = EvolutionGraph()
    g.register_node(SchemaVersionNode(version="1.0.0", parent_versions=()))
    g.register_node(SchemaVersionNode(version="1.1.0", parent_versions=("1.0.0",)))
    g.register_node(SchemaVersionNode(version="1.2.0", parent_versions=("1.1.0",)))

    engine = SchemaSyncEngine(g, "1.2.0")
    response = engine.evaluate_version("1.0.0", "1.2.0")
    assert response.status == "MIGRATE"
    assert response.migration_required is True


def test_version_reject(graph):
    engine = SchemaSyncEngine(graph, "1.1.0")
    response = engine.evaluate_version("1.0.0", "2.0.0")
    assert response.status == "REJECT"


# ── DSYNC-005: deterministic ──


def test_decisions_are_deterministic(graph):
    engine = SchemaSyncEngine(graph, "1.1.0")
    h = SchemaHandshake(node_id="node_x", schema_version="1.0.0")
    r1 = engine.evaluate_node(h)
    r2 = engine.evaluate_node(h)
    assert r1.status == r2.status
    assert r1.reason == r2.reason


def test_no_hidden_state(graph):
    engine = SchemaSyncEngine(graph, "1.1.0")
    h1 = SchemaHandshake(node_id="n1", schema_version="1.0.0")
    h2 = SchemaHandshake(node_id="n2", schema_version="2.0.0")
    r1 = engine.evaluate_node(h1)
    r2 = engine.evaluate_node(h2)
    r3 = engine.evaluate_node(h1)
    assert r1.status == r3.status
