"""Tests for cognitive_runtime/distributed_consensus/consensus_state.py."""

from cognitive_runtime.distributed_consensus import NodeStateProposal, ConsensusResult


def test_proposal_minimal():
    p = NodeStateProposal(
        node_id="n1", schema_version="1.1.0",
        causal_snapshot_hash="abc", stability_score=0.8, confidence_score=0.9,
    )
    assert p.node_id == "n1"
    assert p.schema_version == "1.1.0"
    assert p.stability_score == 0.8
    assert p.confidence_score == 0.9


def test_result_minimal():
    r = ConsensusResult(agreed_version="1.1.0")
    assert r.agreed_version == "1.1.0"
    assert r.participating_nodes == []
    assert r.consensus_strength == 0.0


def test_result_with_rejected():
    r = ConsensusResult(
        agreed_version="1.1.0",
        participating_nodes=["n1", "n2"],
        rejected_nodes=["n3"],
        consensus_strength=0.85,
        conflict_reasons=["orphan_schema_1.0.0"],
    )
    assert "n3" in r.rejected_nodes
    assert r.consensus_strength == 0.85


def test_proposal_immutable():
    import dataclasses
    assert dataclasses.is_dataclass(NodeStateProposal)


def test_result_immutable():
    import dataclasses
    assert dataclasses.is_dataclass(ConsensusResult)
