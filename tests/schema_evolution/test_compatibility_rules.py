"""Tests for cognitive_runtime/schema_evolution/compatibility_rules.py."""

import pytest

from cognitive_runtime.schema_evolution import CompatibilityRules, EvolutionGraph, SchemaVersionNode


@pytest.fixture
def graph():
    g = EvolutionGraph()
    g.register_node(SchemaVersionNode(version="1.0.0", parent_versions=()))
    g.register_node(SchemaVersionNode(version="1.1.0", parent_versions=("1.0.0",)))
    return g


@pytest.fixture
def triple_graph():
    g = EvolutionGraph()
    g.register_node(SchemaVersionNode(version="1.0.0", parent_versions=()))
    g.register_node(SchemaVersionNode(version="1.1.0", parent_versions=("1.0.0",)))
    g.register_node(SchemaVersionNode(version="1.2.0", parent_versions=("1.1.0",)))
    return g


# ── is_backward_compatible (EVOL-COMP-001) ──


def test_backward_same_version(graph):
    assert CompatibilityRules.is_backward_compatible("1.0.0", "1.0.0", graph) is True


def test_backward_minor_bump(graph):
    assert CompatibilityRules.is_backward_compatible("1.0.0", "1.1.0", graph) is True


def test_backward_major_bump_rejected(graph):
    assert CompatibilityRules.is_backward_compatible("1.0.0", "2.0.0", graph) is False


def test_backward_two_step_rejected(graph):
    assert CompatibilityRules.is_backward_compatible("1.0.0", "1.2.0", graph) is False


def test_backward_downgrade_rejected(graph):
    assert CompatibilityRules.is_backward_compatible("1.1.0", "1.0.0", graph) is False


def test_backward_rejects_non_version(graph):
    with pytest.raises((ValueError, IndexError)):
        CompatibilityRules.is_backward_compatible("1.0.0", "invalid", graph)


# ── is_forward_compatible (EVOL-COMP-002) ──


def test_forward_same_version(graph):
    assert CompatibilityRules.is_forward_compatible("1.0.0", "1.0.0", graph) is True


def test_forward_older_can_read_newer_same_minor(graph):
    assert CompatibilityRules.is_forward_compatible("1.0.0", "1.0.1", graph) is True


def test_forward_older_cannot_read_newer_minor(graph):
    assert CompatibilityRules.is_forward_compatible("1.0.0", "1.1.0", graph) is False


def test_forward_major_bump_rejected(graph):
    assert CompatibilityRules.is_forward_compatible("1.0.0", "2.0.0", graph) is False


def test_forward_newer_to_older(graph):
    assert CompatibilityRules.is_forward_compatible("1.1.0", "1.0.0", graph) is True


# ── is_allowed_transition (EVOL-COMP-003 + EVOL-COMP-004) ──


def test_allowed_transition_valid(graph):
    assert CompatibilityRules.is_allowed_transition("1.0.0", "1.1.0", graph) is True


def test_allowed_transition_same_version(graph):
    assert CompatibilityRules.is_allowed_transition("1.0.0", "1.0.0", graph) is False


def test_allowed_transition_invalid_jump(graph):
    assert CompatibilityRules.is_allowed_transition("1.0.0", "2.0.0", graph) is False


def test_allowed_transition_no_graph_edge(graph):
    assert CompatibilityRules.is_allowed_transition("1.1.0", "1.0.0", graph) is False


def test_allowed_transition_requires_lineage(triple_graph):
    assert CompatibilityRules.is_allowed_transition("1.1.0", "1.2.0", triple_graph) is True
    assert CompatibilityRules.is_allowed_transition("1.0.0", "1.2.0", triple_graph) is False


# ── EVOL-SEM-001: read-only ──


def test_rules_do_not_mutate_graph(graph):
    before_count = graph.node_count
    CompatibilityRules.is_allowed_transition("1.0.0", "1.1.0", graph)
    assert graph.node_count == before_count
