"""Tests for cognitive_runtime/time_rewind/temporal_consensus_engine.py."""

import pytest

from cognitive_runtime.contracts.execution_trace import ExecutionTrace
from cognitive_runtime.time_rewind import TemporalConsensusEngine
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
def traces():
    return [
        ExecutionTrace(event_id="e1", session_id="s1", sequence_no=1,
                       final_status="completed", risk_score=0.5),
        ExecutionTrace(event_id="e2", session_id="s1", sequence_no=2,
                       final_status="completed", risk_score=0.8),
        ExecutionTrace(event_id="e3", session_id="s2", sequence_no=1,
                       final_status="blocked", risk_score=0.3),
    ]


@pytest.fixture
def engine(graph):
    return TemporalConsensusEngine(graph, "1.1.0")


# ── consensus_at_time ──


def test_consensus_at_time_no_traces(engine):
    result = engine.consensus_at_time(0.0, [])
    assert result.agreed_version == "1.1.0"


def test_consensus_at_time_returns_consensus(engine, traces):
    result = engine.consensus_at_time(999.0, traces)
    assert result.agreed_version is not None
    assert isinstance(result.consensus_strength, float)


def test_consensus_at_time_partial_history(engine, traces):
    # Only first event (sorted: e1 at t=0)
    result = engine.consensus_at_time(0.0, traces)
    assert result.agreed_version == "1.1.0"


def test_consensus_at_time_two_events(engine, traces):
    # Events e1 and e2 at t=1
    result = engine.consensus_at_time(1.0, traces)
    assert result.agreed_version is not None


# ── TIME-005: match original decisions ──


def test_consensus_at_time_deterministic(engine, traces):
    r1 = engine.consensus_at_time(2.0, traces)
    r2 = engine.consensus_at_time(2.0, traces)
    assert r1.agreed_version == r2.agreed_version
    assert r1.consensus_strength == r2.consensus_strength
    assert r1.participating_nodes == r2.participating_nodes


def test_consensus_at_time_deterministic_different_orders(engine, traces):
    r1 = engine.consensus_at_time(2.0, traces)
    r2 = engine.consensus_at_time(2.0, list(reversed(traces)))
    assert r1.agreed_version == r2.agreed_version


# ── TIME-003: no side effects ──


def test_consensus_does_not_mutate_traces(engine, traces):
    original_ids = [t.event_id for t in traces]
    engine.consensus_at_time(2.0, traces)
    assert [t.event_id for t in traces] == original_ids
