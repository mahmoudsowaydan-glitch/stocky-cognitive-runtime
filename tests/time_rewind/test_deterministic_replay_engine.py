"""Tests for cognitive_runtime/time_rewind/deterministic_replay_engine.py."""

import pytest

from cognitive_runtime.contracts.execution_trace import ExecutionTrace
from cognitive_runtime.time_rewind import (
    RewindEvent, DeterministicReplayEngine, SystemState,
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
def timeline():
    return [
        RewindEvent(timestamp=0.0, trace_id="e1", node_id="s1",
                     execution_snapshot={
                         "event_id": "e1", "session_id": "s1",
                         "sequence_no": 1, "correlation_id": "c1",
                         "risk_score": 0.5, "p4_verdict": "ALLOW",
                         "execution_status": "SUCCESS", "final_status": "completed",
                     },
                     causal_hash="a"*64),
        RewindEvent(timestamp=1.0, trace_id="e2", node_id="s1",
                     execution_snapshot={
                         "event_id": "e2", "session_id": "s1",
                         "sequence_no": 2, "correlation_id": "c2",
                         "risk_score": 0.8, "p4_verdict": "DENY",
                         "execution_status": "SKIPPED", "final_status": "blocked",
                     },
                     causal_hash="b"*64),
    ]


@pytest.fixture
def engine(graph):
    return DeterministicReplayEngine(graph, "1.1.0")


# ── replay ──


def test_replay_returns_system_state(engine, timeline):
    state = engine.replay(timeline)
    assert isinstance(state, SystemState)
    assert state.trace_count == 2


def test_replay_traces_reconstructed(engine, timeline):
    state = engine.replay(timeline)
    ids = [t.event_id for t in state.traces]
    assert "e1" in ids
    assert "e2" in ids


def test_replay_from_empty_timeline(engine):
    state = engine.replay([])
    assert state.trace_count == 0
    assert state.traces == []


def test_replay_state_hash_not_empty(engine, timeline):
    state = engine.replay(timeline)
    assert len(state.state_hash) == 64


def test_replay_schema_version_in_state(engine, timeline):
    state = engine.replay(timeline, schema_version="1.0.0")
    assert state.schema_version == "1.1.0"


# ── TIME-001: deterministic replay ──


def test_replay_deterministic_same_input(engine, timeline):
    state_a = engine.replay(timeline)
    state_b = engine.replay(timeline)
    assert state_a.state_hash == state_b.state_hash


def test_replay_deterministic_reversed_timeline(engine, timeline):
    state_a = engine.replay(timeline)
    state_b = engine.replay(list(reversed(timeline)))
    assert state_a.state_hash == state_b.state_hash


# ── TIME-003: no side effects ──


def test_replay_does_not_mutate_timeline(engine, timeline):
    original_hashes = [e.causal_hash for e in timeline]
    engine.replay(timeline)
    assert [e.causal_hash for e in timeline] == original_hashes


# ── TIME-004: pure function ──


def test_replay_pure_no_mutation_between_calls(engine, timeline):
    h1 = engine.replay(timeline).state_hash
    # Call with different data
    other = [
        RewindEvent(timestamp=0.0, trace_id="e3", node_id="s2",
                     execution_snapshot={
                         "event_id": "e3", "session_id": "s2",
                         "sequence_no": 1, "correlation_id": "c3",
                         "risk_score": 0.1, "p4_verdict": "ALLOW",
                         "execution_status": "SUCCESS", "final_status": "completed",
                     },
                     causal_hash="c"*64),
    ]
    h2 = engine.replay(timeline).state_hash
    assert h1 == h2


# ── replay_deterministic ──


def test_replay_deterministic_same_timelines(engine, timeline):
    assert engine.replay_deterministic(timeline, timeline) is True


def test_replay_deterministic_different_timelines(engine, timeline):
    other = [
        RewindEvent(timestamp=0.0, trace_id="e3", node_id="s2",
                     execution_snapshot={"event_id": "e3"},
                     causal_hash="d"*64),
    ]
    assert engine.replay_deterministic(timeline, other) is False


# ── system state ──


def test_system_state_immutable():
    import dataclasses
    assert dataclasses.is_dataclass(SystemState)
