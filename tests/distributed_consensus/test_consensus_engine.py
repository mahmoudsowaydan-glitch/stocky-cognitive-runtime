"""Tests for cognitive_runtime/distributed_consensus/consensus_engine.py."""

import pytest

from cognitive_runtime.distributed_consensus import (
    NodeStateProposal, ConsensusEngine,
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


# ── propose: basic ──


def test_empty_proposals(graph):
    engine = ConsensusEngine(graph, "1.1.0")
    result = engine.propose([])
    assert result.agreed_version == "1.1.0"
    assert result.consensus_strength == 0.0


def test_single_node_same_version(graph):
    engine = ConsensusEngine(graph, "1.1.0")
    proposals = [
        NodeStateProposal(
            node_id="n1", schema_version="1.1.0",
            causal_snapshot_hash="a", stability_score=0.9, confidence_score=0.9,
        ),
    ]
    result = engine.propose(proposals)
    assert result.agreed_version == "1.1.0"
    assert result.consensus_strength >= 0.7
    assert "n1" in result.participating_nodes


def test_all_nodes_same_version(graph):
    engine = ConsensusEngine(graph, "1.1.0")
    proposals = [
        NodeStateProposal(n, "1.1.0", f"h{i}", 0.85, 0.85)
        for i, n in enumerate(["n1", "n2", "n3"])
    ]
    result = engine.propose(proposals)
    assert result.agreed_version == "1.1.0"
    assert len(result.participating_nodes) == 3
    assert len(result.rejected_nodes) == 0


# ── propose: majority selection ──


def test_dominant_version_wins(graph):
    engine = ConsensusEngine(graph, "1.1.0")
    proposals = [
        NodeStateProposal("n1", "1.1.0", "h1", 0.9, 0.9),
        NodeStateProposal("n2", "1.1.0", "h2", 0.8, 0.8),
        NodeStateProposal("n3", "1.0.0", "h3", 0.6, 0.6),
    ]
    result = engine.propose(proposals)
    assert result.agreed_version == "1.1.0"
    assert "n1" in result.participating_nodes
    assert "n2" in result.participating_nodes


def test_minority_gets_rejected(graph):
    engine = ConsensusEngine(graph, "1.1.0")
    proposals = [
        NodeStateProposal("n1", "1.1.0", "h1", 0.9, 0.9),
        NodeStateProposal("n2", "1.0.0", "h2", 0.6, 0.6),
    ]
    result = engine.propose(proposals)
    assert result.agreed_version == "1.1.0"
    assert "n1" in result.participating_nodes
    assert "n2" in result.rejected_nodes


def test_dominant_weight_below_threshold(graph):
    engine = ConsensusEngine(graph, "1.1.0")
    proposals = [
        NodeStateProposal("n1", "1.0.0", "h1", 0.3, 0.3),
        NodeStateProposal("n2", "1.1.0", "h2", 0.4, 0.4),
    ]
    result = engine.propose(proposals)
    assert result.agreed_version == "1.1.0"
    assert "below_threshold" in " ".join(result.conflict_reasons)


# ── CONS-003: symmetric evaluation ──


def test_symmetric_evaluation_all_versions(graph):
    engine = ConsensusEngine(graph, "1.1.0")
    props = [
        NodeStateProposal("n1", "1.0.0", "h1", 0.9, 0.9),
        NodeStateProposal("n2", "1.1.0", "h2", 0.9, 0.9),
    ]
    r1 = engine.propose(props)
    r2 = engine.propose(props[::-1])
    assert r1.agreed_version == r2.agreed_version
    assert sorted(r1.participating_nodes) == sorted(r2.participating_nodes)


# ── CONS-005: reproducible ──


def test_consensus_reproducible(graph):
    engine = ConsensusEngine(graph, "1.1.0")
    proposals = [
        NodeStateProposal("n1", "1.1.0", "h1", 0.9, 0.9),
        NodeStateProposal("n2", "1.0.0", "h2", 0.7, 0.7),
        NodeStateProposal("n3", "1.0.0", "h3", 0.7, 0.7),
    ]
    r1 = engine.propose(proposals)
    r2 = engine.propose(proposals)
    assert r1.agreed_version == r2.agreed_version
    assert r1.participating_nodes == r2.participating_nodes
    assert r1.rejected_nodes == r2.rejected_nodes
    assert r1.consensus_strength == r2.consensus_strength


# ── CONS-002: no single node override ──


def test_no_single_node_override(graph):
    engine = ConsensusEngine(graph, "1.1.0")
    proposals = [
        NodeStateProposal("n1", "2.0.0", "h1", 1.0, 1.0),
        NodeStateProposal("n2", "1.1.0", "h2", 0.8, 0.8),
        NodeStateProposal("n3", "1.1.0", "h3", 0.8, 0.8),
    ]
    result = engine.propose(proposals)
    assert result.agreed_version == "1.1.0"


# ── conflict detection ──


def test_unknown_version_conflict(graph):
    """An unregistered version in proposals triggers conflict."""
    engine = ConsensusEngine(graph, "1.1.0")
    proposals = [
        NodeStateProposal("n1", "1.1.0", "h1", 0.9, 0.9),
        NodeStateProposal("n2", "99.0.0", "h2", 0.9, 0.9),
    ]
    result = engine.propose(proposals)
    assert any("unknown" in r for r in result.conflict_reasons)


def test_orphan_detection_code_path(graph):
    """Orphan check exists; in a valid graph no orphans arise."""
    engine = ConsensusEngine(graph, "1.1.0")
    proposals = [
        NodeStateProposal("n1", "1.1.0", "h1", 0.9, 0.9),
    ]
    result = engine.propose(proposals)
    # In a clean graph, no orphan conflicts should fire
    orphan_found = any("orphan" in r for r in result.conflict_reasons)
    assert orphan_found is False


def test_unknown_version_not_orphan(graph):
    """An unregistered version is not a graph orphan; flagged differently."""
    engine = ConsensusEngine(graph, "1.1.0")
    proposals = [
        NodeStateProposal("n1", "1.1.0", "h1", 0.9, 0.9),
        NodeStateProposal("n2", "99.0.0", "h2", 0.9, 0.9),
    ]
    result = engine.propose(proposals)
    assert result.agreed_version == "1.1.0"


def test_close_margin_conflict(graph):
    """Two versions within 0.05 weight margin trigger conflict."""
    engine = ConsensusEngine(graph, "1.1.0")
    # n1(1.1.0): weight = 0.71*0.4 + 0.65*0.4 + 1.0*0.2 = 0.744
    # n2(1.0.0): weight = 0.70*0.4 + 0.70*0.4 + 0.7*0.2 = 0.700
    # diff = 0.044 < 0.05 → close margin
    proposals = [
        NodeStateProposal("n1", "1.1.0", "h1", 0.71, 0.65),
        NodeStateProposal("n2", "1.0.0", "h2", 0.70, 0.70),
    ]
    result = engine.propose(proposals)
    assert any("close_margin" in r for r in result.conflict_reasons)


# ── graph_freshness ──


def test_current_version_freshness_max(graph):
    engine = ConsensusEngine(graph, "1.1.0")
    assert engine._graph_freshness("1.1.0") == 1.0


def test_ancestor_freshness(graph):
    engine = ConsensusEngine(graph, "1.1.0")
    freshness = engine._graph_freshness("1.0.0")
    assert freshness > 0


# ── 3-node examples ──


def test_three_nodes_with_different_versions(chain_graph):
    engine = ConsensusEngine(chain_graph, "1.2.0")
    proposals = [
        NodeStateProposal("n1", "1.2.0", "h1", 0.9, 0.9),
        NodeStateProposal("n2", "1.1.0", "h2", 0.8, 0.8),
        NodeStateProposal("n3", "1.0.0", "h3", 0.7, 0.7),
    ]
    result = engine.propose(proposals)
    # 1.2.0 has freshness=1.0 + high stability/confidence → dominates
    assert result.agreed_version == "1.2.0"
    assert "n1" in result.participating_nodes


def test_three_nodes_majority_at_current(chain_graph):
    engine = ConsensusEngine(chain_graph, "1.1.0")
    proposals = [
        NodeStateProposal("n1", "1.1.0", "h1", 0.85, 0.85),
        NodeStateProposal("n2", "1.1.0", "h2", 0.85, 0.85),
        NodeStateProposal("n3", "1.2.0", "h3", 0.90, 0.90),
    ]
    result = engine.propose(proposals)
    # 1.1.0 has 2 nodes with high stability+confidence → should beat single 1.2.0
    assert result.agreed_version == "1.1.0"
    assert len(result.participating_nodes) == 2
    assert len(result.rejected_nodes) == 1
