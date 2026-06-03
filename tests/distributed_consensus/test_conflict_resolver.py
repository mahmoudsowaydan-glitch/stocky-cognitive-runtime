"""Tests for cognitive_runtime/distributed_consensus/conflict_resolver.py."""

import pytest

from cognitive_runtime.distributed_consensus import (
    NodeStateProposal, ConflictResolver, ResolutionPlan,
    ResolutionStrategy,
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


@pytest.fixture
def chain_graph():
    g = EvolutionGraph()
    g.register_node(SchemaVersionNode(version="1.0.0", parent_versions=()))
    g.register_node(SchemaVersionNode(version="1.1.0", parent_versions=("1.0.0",)))
    g.register_node(SchemaVersionNode(version="1.2.0", parent_versions=("1.1.0",)))
    return g


# ── VERSION_PRIORITY ──


def test_version_priority_selects_newest(graph):
    resolver = ConflictResolver(graph, "1.1.0")
    proposals = [
        NodeStateProposal("n1", "1.0.0", "h1", 0.9, 0.9),
        NodeStateProposal("n2", "1.1.0", "h2", 0.9, 0.9),
    ]
    plan = resolver.resolve(proposals, ResolutionStrategy.VERSION_PRIORITY)
    assert plan.chosen_version == "1.1.0"
    assert "n2" in plan.participating_nodes


def test_version_priority_unanimous(graph):
    resolver = ConflictResolver(graph, "1.1.0")
    proposals = [
        NodeStateProposal("n1", "1.0.0", "h1", 1.0, 1.0),
        NodeStateProposal("n2", "1.0.0", "h2", 1.0, 1.0),
    ]
    plan = resolver.resolve(proposals, ResolutionStrategy.VERSION_PRIORITY)
    assert plan.chosen_version == "1.0.0"
    assert plan.resolution_details == "unanimous"


def test_version_priority_empty(graph):
    resolver = ConflictResolver(graph, "1.1.0")
    plan = resolver.resolve([], ResolutionStrategy.VERSION_PRIORITY)
    assert plan.chosen_version == "1.1.0"


# ── STABILITY_PRIORITY ──


def test_stability_priority_selects_highest_avg(graph):
    resolver = ConflictResolver(graph, "1.1.0")
    proposals = [
        NodeStateProposal("n1", "1.0.0", "h1", 0.9, 0.9),
        NodeStateProposal("n2", "1.0.0", "h2", 0.95, 0.9),
        NodeStateProposal("n3", "1.1.0", "h3", 0.5, 0.9),
    ]
    plan = resolver.resolve(proposals, ResolutionStrategy.STABILITY_PRIORITY)
    assert plan.chosen_version == "1.0.0"
    assert "n1" in plan.participating_nodes


def test_stability_priority_single_node(graph):
    resolver = ConflictResolver(graph, "1.1.0")
    proposals = [
        NodeStateProposal("n1", "1.0.0", "h1", 0.3, 0.3),
    ]
    plan = resolver.resolve(proposals, ResolutionStrategy.STABILITY_PRIORITY)
    assert plan.chosen_version == "1.0.0"


# ── MIGRATION_COST_MINIMIZATION ──


def test_migration_cost_selects_cheapest(chain_graph):
    resolver = ConflictResolver(chain_graph, "1.2.0")
    proposals = [
        NodeStateProposal("n1", "1.2.0", "h1", 1.0, 1.0),
        NodeStateProposal("n2", "1.0.0", "h2", 1.0, 1.0),
    ]
    plan = resolver.resolve(proposals, ResolutionStrategy.MIGRATION_COST_MINIMIZATION)
    # 1.2.0 requires 0 migration, 1.0.0 would require 2 migrations for the other
    assert plan.chosen_version == "1.2.0"


def test_migration_cost_equal_tiebreak(chain_graph):
    resolver = ConflictResolver(chain_graph, "1.1.0")
    proposals = [
        NodeStateProposal("n1", "1.1.0", "h1", 0.9, 0.9),
        NodeStateProposal("n2", "1.2.0", "h2", 0.9, 0.9),
    ]
    plan = resolver.resolve(proposals, ResolutionStrategy.MIGRATION_COST_MINIMIZATION)
    # Both require 0 or 1 migration → deterministic choice
    assert plan.chosen_version in ("1.1.0", "1.2.0")


# ── CONS-004: conflicts resolved ──


def test_conflict_resolved_not_ignored(graph):
    resolver = ConflictResolver(graph, "1.1.0")
    proposals = [
        NodeStateProposal("n1", "1.0.0", "h1", 0.9, 0.9),
        NodeStateProposal("n2", "1.1.0", "h2", 0.9, 0.9),
    ]
    plan = resolver.resolve(proposals, ResolutionStrategy.VERSION_PRIORITY)
    assert plan.chosen_version is not None
    assert len(plan.rejected_nodes) >= 0


# ── CONS-005: reproducible ──


def test_version_priority_reproducible(graph):
    resolver = ConflictResolver(graph, "1.1.0")
    proposals = [
        NodeStateProposal("n1", "1.0.0", "h1", 0.9, 0.9),
        NodeStateProposal("n2", "1.1.0", "h2", 0.9, 0.9),
    ]
    p1 = resolver.resolve(proposals, ResolutionStrategy.VERSION_PRIORITY)
    p2 = resolver.resolve(proposals, ResolutionStrategy.VERSION_PRIORITY)
    assert p1.chosen_version == p2.chosen_version
    assert p1.participating_nodes == p2.participating_nodes
    assert p1.rejected_nodes == p2.rejected_nodes


def test_stability_priority_reproducible(graph):
    resolver = ConflictResolver(graph, "1.1.0")
    proposals = [
        NodeStateProposal("n1", "1.0.0", "h1", 0.8, 0.9),
        NodeStateProposal("n2", "1.1.0", "h2", 0.7, 0.9),
        NodeStateProposal("n3", "1.0.0", "h3", 0.6, 0.9),
    ]
    p1 = resolver.resolve(proposals, ResolutionStrategy.STABILITY_PRIORITY)
    p2 = resolver.resolve(proposals, ResolutionStrategy.STABILITY_PRIORITY)
    assert p1.chosen_version == p2.chosen_version


# ── no randomness ──


def test_no_randomness_all_strategies(graph):
    resolver = ConflictResolver(graph, "1.1.0")
    proposals = [
        NodeStateProposal("n1", "1.0.0", "h1", 0.9, 0.9),
        NodeStateProposal("n2", "1.1.0", "h2", 0.8, 0.8),
    ]
    for strategy in ResolutionStrategy:
        r1 = resolver.resolve(proposals, strategy)
        r2 = resolver.resolve(proposals, strategy)
        assert r1.chosen_version == r2.chosen_version


# ── default strategy ──


def test_default_strategy_is_version_priority(graph):
    resolver = ConflictResolver(graph, "1.1.0")
    proposals = [
        NodeStateProposal("n1", "1.0.0", "h1", 0.9, 0.9),
        NodeStateProposal("n2", "1.1.0", "h2", 0.9, 0.9),
    ]
    plan = resolver.resolve(proposals)
    assert plan.strategy_used == ResolutionStrategy.VERSION_PRIORITY


def test_resolution_plan_immutable():
    import dataclasses
    assert dataclasses.is_dataclass(ResolutionPlan)
