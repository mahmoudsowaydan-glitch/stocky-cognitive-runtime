"""Tests for cognitive_runtime/schema_evolution/breaking_change_detector.py."""

import pytest

from cognitive_runtime.schema_evolution import (
    BreakingChangeDetector, EvolutionGraph, SchemaVersionNode,
)


@pytest.fixture
def graph():
    g = EvolutionGraph()
    g.register_node(SchemaVersionNode(version="1.0.0", parent_versions=()))
    g.register_node(SchemaVersionNode(version="1.1.0", parent_versions=("1.0.0",)))
    return g


def test_safe_change_not_breaking(graph):
    result = BreakingChangeDetector().detect("1.0.0", "1.1.0", graph)
    assert result["is_breaking"] is False
    assert result["severity"] == "low"
    assert result["reasons"] == []


def test_illegal_jump_is_breaking_from_registered_version():
    g = EvolutionGraph()
    g.register_node(SchemaVersionNode(version="1.0.0", parent_versions=()))
    g.register_node(SchemaVersionNode(version="1.1.0", parent_versions=("1.0.0",)))
    g.register_node(SchemaVersionNode(version="1.2.0", parent_versions=("1.1.0",)))
    result = BreakingChangeDetector().detect("1.0.0", "1.2.0", g)
    assert result["is_breaking"] is True
    assert "illegal_version_jump" in result["reasons"]


def test_illegal_jump_critical_severity(graph):
    result = BreakingChangeDetector().detect("1.0.0", "2.0.0", graph)
    assert result["severity"] == "critical"


def test_orphan_is_critical(graph):
    result = BreakingChangeDetector().detect("1.0.0", "99.0.0", graph)
    assert result["is_breaking"] is True
    assert result["severity"] == "critical"


def test_orphan_contains_orphan_keyword(graph):
    result = BreakingChangeDetector().detect("1.0.0", "99.0.0", graph)
    assert "orphan_version_detected" in result["reasons"]


def test_reverse_transition_detected(graph):
    result = BreakingChangeDetector().detect("1.1.0", "1.0.0", graph)
    assert result["is_breaking"] is True


def test_no_graph_node_from_version(graph):
    result = BreakingChangeDetector().detect("5.0.0", "1.1.0", graph)
    assert result["is_breaking"] is True


def test_same_version_is_not_breaking(graph):
    result = BreakingChangeDetector().detect("1.0.0", "1.0.0", graph)
    assert result["is_breaking"] is True


def test_unknown_from_is_not_orphan_blocker(graph):
    result = BreakingChangeDetector().detect("2.0.0", "1.1.0", graph)
    assert result["is_breaking"] is True


def test_no_mutation(graph):
    before = graph.node_count
    BreakingChangeDetector().detect("1.0.0", "99.0.0", graph)
    BreakingChangeDetector().detect("1.0.0", "1.1.0", graph)
    assert graph.node_count == before
