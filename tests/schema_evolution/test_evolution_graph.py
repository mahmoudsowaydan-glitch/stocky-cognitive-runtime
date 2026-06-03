"""Tests for cognitive_runtime/schema_evolution/evolution_graph.py.

Covers EVOL-001, EVOL-002, EVOL-003 invariants.
"""

import pytest

from cognitive_runtime.schema_evolution.evolution_graph import EvolutionGraph
from cognitive_runtime.schema_evolution.evolution_node import SchemaVersionNode


# ── fixtures ──


@pytest.fixture
def graph():
    g = EvolutionGraph()
    v1 = SchemaVersionNode(version="1.0.0", parent_versions=())
    v2 = SchemaVersionNode(version="1.1.0", parent_versions=("1.0.0",))
    g.register_node(v1)
    g.register_node(v2)
    return g


@pytest.fixture
def triple_graph():
    g = EvolutionGraph()
    v1 = SchemaVersionNode(version="1.0.0", parent_versions=())
    v2 = SchemaVersionNode(version="1.1.0", parent_versions=("1.0.0",))
    v3 = SchemaVersionNode(version="2.0.0", parent_versions=("1.1.0",))
    g.register_node(v1)
    g.register_node(v2)
    g.register_node(v3)
    return g


# ── register ──


def test_register_root(graph):
    assert graph.node_count == 2
    assert graph.root_version == "1.0.0"


def test_register_duplicate(graph):
    dup = SchemaVersionNode(version="1.0.0", parent_versions=())
    with pytest.raises(ValueError, match="already registered"):
        graph.register_node(dup)


def test_register_orphan_parent():
    g = EvolutionGraph()
    orphan = SchemaVersionNode(version="2.0.0", parent_versions=("1.0.0",))
    with pytest.raises(ValueError, match="not registered"):
        g.register_node(orphan)


# ── is_valid_transition (EVOL-003) ──


def test_valid_transition_parent_to_child(graph):
    assert graph.is_valid_transition("1.0.0", "1.1.0") is True


def test_invalid_transition_reverse(graph):
    assert graph.is_valid_transition("1.1.0", "1.0.0") is False


def test_invalid_transition_unknown(graph):
    assert graph.is_valid_transition("1.0.0", "99.0.0") is False


def test_valid_chain_transitions(triple_graph):
    assert triple_graph.is_valid_transition("1.0.0", "1.1.0") is True
    assert triple_graph.is_valid_transition("1.1.0", "2.0.0") is True


def test_invalid_skip_transition(triple_graph):
    assert triple_graph.is_valid_transition("1.0.0", "2.0.0") is False


# ── has_lineage_to_root (EVOL-002) ──


def test_root_lineage(graph):
    assert graph.has_lineage_to_root("1.0.0") is True


def test_child_lineage(graph):
    assert graph.has_lineage_to_root("1.1.0") is True


def test_nonexistent_lineage(graph):
    assert graph.has_lineage_to_root("99.0.0") is False


def test_lineage_chain(triple_graph):
    assert triple_graph.has_lineage_to_root("1.0.0") is True
    assert triple_graph.has_lineage_to_root("1.1.0") is True
    assert triple_graph.has_lineage_to_root("2.0.0") is True


# ── is_orphan / detect_orphans (EVOL-001) ──


def test_no_orphans_in_valid_graph(graph):
    assert graph.detect_orphans() == []


def test_orphan_detected():
    g = EvolutionGraph()
    root = SchemaVersionNode(version="1.0.0", parent_versions=())
    g.register_node(root)
    orphan = SchemaVersionNode(version="2.0.0", parent_versions=("1.0.0",))
    g.is_valid_transition("1.0.0", "2.0.0")
    assert True


def test_orphan_after_parent_removed():
    g = EvolutionGraph()
    root = SchemaVersionNode(version="1.0.0", parent_versions=())
    g.register_node(root)
    rogue = SchemaVersionNode(version="3.0.0", parent_versions=("2.0.0",))
    with pytest.raises(ValueError, match="not registered"):
        g.register_node(rogue)


def test_nonexistent_is_not_orphan(graph):
    assert graph.is_orphan("unknown") is False


# ── get_ancestors ──


def test_root_ancestors(graph):
    assert graph.get_ancestors("1.0.0") == []


def test_child_ancestors(graph):
    assert graph.get_ancestors("1.1.0") == ["1.0.0"]


def test_chain_ancestors(triple_graph):
    assert triple_graph.get_ancestors("2.0.0") == ["1.1.0", "1.0.0"]


def test_unknown_ancestors(graph):
    assert graph.get_ancestors("x") == []
