"""Tests for cognitive_runtime/time_rewind/rewind_event.py."""

from cognitive_runtime.time_rewind import RewindEvent


def test_minimal():
    e = RewindEvent(
        timestamp=1.0, trace_id="t1", node_id="n1",
        execution_snapshot={"key": "val"}, causal_hash="abc123",
    )
    assert e.timestamp == 1.0
    assert e.trace_id == "t1"
    assert e.node_id == "n1"
    assert e.execution_snapshot == {"key": "val"}
    assert e.causal_hash == "abc123"


def test_immutable():
    import dataclasses
    assert dataclasses.is_dataclass(RewindEvent)
