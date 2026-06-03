"""Tests for cognitive_runtime/time_rewind/time_rewind_engine.py."""

import pytest

from cognitive_runtime.contracts.execution_trace import ExecutionTrace
from cognitive_runtime.time_rewind import TimeRewindEngine


@pytest.fixture
def traces():
    return [
        ExecutionTrace(event_id="e1", session_id="s1", sequence_no=2,
                       final_status="completed", risk_score=0.5),
        ExecutionTrace(event_id="e2", session_id="s1", sequence_no=1,
                       final_status="completed", risk_score=0.3),
        ExecutionTrace(event_id="e3", session_id="s2", sequence_no=1,
                       final_status="blocked", risk_score=0.9),
    ]


@pytest.fixture
def engine():
    return TimeRewindEngine()


# ── build_timeline ──


def test_build_timeline_sorted_by_session_then_seq(engine, traces):
    timeline = engine.build_timeline(traces)
    assert len(timeline) == 3
    # Order: s1/1, s1/2, s2/1
    assert timeline[0].trace_id == "e2"
    assert timeline[1].trace_id == "e1"
    assert timeline[2].trace_id == "e3"


def test_build_timeline_synthetic_timestamps(engine, traces):
    timeline = engine.build_timeline(traces)
    assert timeline[0].timestamp == 0.0
    assert timeline[1].timestamp == 1.0
    assert timeline[2].timestamp == 2.0


def test_build_timeline_has_causal_hash(engine, traces):
    timeline = engine.build_timeline(traces)
    for event in timeline:
        assert len(event.causal_hash) == 64  # SHA256


def test_build_timeline_snapshot_fields(engine, traces):
    timeline = engine.build_timeline(traces)
    snap = timeline[0].execution_snapshot
    assert "event_id" in snap
    assert "session_id" in snap
    assert "sequence_no" in snap


# ── TIME-001: deterministic ──


def test_build_timeline_deterministic(engine, traces):
    t1 = engine.build_timeline(traces)
    t2 = engine.build_timeline(traces)
    for a, b in zip(t1, t2):
        assert a.timestamp == b.timestamp
        assert a.trace_id == b.trace_id
        assert a.causal_hash == b.causal_hash


def test_build_timeline_reverse_input(engine, traces):
    t1 = engine.build_timeline(traces)
    t2 = engine.build_timeline(list(reversed(traces)))
    for a, b in zip(t1, t2):
        assert a.trace_id == b.trace_id


# ── rewind ──


def test_rewind_empty(engine):
    result = engine.rewind(0.0, [])
    assert result == []


def test_rewind_all_events(engine, traces):
    result = engine.rewind(999.0, traces)
    assert len(result) == 3


def test_rewind_partial(engine, traces):
    # Only first event (timestamp 0.0) included
    result = engine.rewind(0.0, traces)
    assert len(result) == 1
    assert result[0].event_id == "e2"  # first in sorted order


def test_rewind_two_events(engine, traces):
    result = engine.rewind(1.0, traces)
    assert len(result) == 2


# ── TIME-003: no side effects ──


def test_rewind_does_not_mutate_input(engine, traces):
    original_ids = [t.event_id for t in traces]
    engine.rewind(1.0, traces)
    assert [t.event_id for t in traces] == original_ids


# ── validate_replay ──


def test_validate_replay_identical(engine, traces):
    assert engine.validate_replay(traces, list(traces)) is True


def test_validate_replay_different_order(engine, traces):
    reordered = list(reversed(traces))
    assert engine.validate_replay(traces, reordered) is True


def test_validate_replay_different_traces(engine, traces):
    different = [
        ExecutionTrace(event_id="e99", session_id="s99", sequence_no=1),
    ]
    assert engine.validate_replay(traces, different) is False


def test_validate_replay_empty(engine):
    assert engine.validate_replay([], []) is True
    assert engine.validate_replay([], [ExecutionTrace()]) is False


# ── TIME-002: time from order, not system clock ──


def test_time_is_synthetic_not_system_clock(engine, traces):
    timeline = engine.build_timeline(traces)
    for event in timeline:
        assert event.timestamp >= 0.0
        assert event.timestamp == int(event.timestamp)  # whole numbers
