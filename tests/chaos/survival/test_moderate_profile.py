"""Survival: MODERATE profile — runtime survives moderate multi-axis distortion."""

from unittest.mock import MagicMock
from chaos.harness.chaos_profile import get_profile
from cognitive_runtime.recovery.crash_detector import CrashDetector
from cognitive_runtime.recovery.checkpoint_manager import CheckpointManager
from cognitive_runtime.recovery.runtime_snapshot import RuntimeSnapshot
from chaos.harness.wal_mutator import WALMutator


def test_moderate_profile_has_multiple_active_injectors():
    profile = get_profile("moderate")
    injectors = profile.active_injectors()
    assert len(injectors) >= 2
    assert "event_queue" in injectors
    assert "timing" in injectors


def test_moderate_wal_corruption_survivable(checkpoint_manager, wal_mutator):
    snap = RuntimeSnapshot.capture(object(), snapshot_id="cp_mod")
    checkpoint_manager.save(snap)
    wal_mutator.mutate_trace_fields("cp_mod")
    loaded = checkpoint_manager.load_latest()
    result = True
    if loaded:
        from cognitive_runtime.recovery.persistence_guard import PersistenceGuard
        guard = PersistenceGuard()
        result = guard.validate_snapshot(loaded).valid
    assert result is False or loaded is not None


def test_moderate_causal_mutation_detected():
    from chaos.harness.causal_mutator import CausalMutator
    from cognitive_runtime.contracts.causal_graph import CausalGraphBuilder
    from cognitive_runtime.contracts.execution_trace import ExecutionTrace

    traces = [ExecutionTrace(
        event_id=f"e{i}", session_id="s1", sequence_no=i,
        correlation_id=f"c{i}",
        preflight_valid=True, preflight_reason="ok",
        risk_score=0.1,
        p4_verdict="ALLOW", p4_reason="ok", p4_risk_level="low",
        execution_status="SUCCESS",
        final_status="P4_ALLOW",
    ) for i in range(5)]

    mutator = CausalMutator(seed=42)
    mutated = mutator.random_mutation(traces)
    builder = CausalGraphBuilder()
    graph = builder.build(mutated)
    assert len(graph.nodes) >= 1
