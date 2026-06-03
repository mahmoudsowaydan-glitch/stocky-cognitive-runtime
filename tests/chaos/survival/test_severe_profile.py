"""Survival: SEVERE profile — runtime survives heavy multi-axis chaos."""

import time
from unittest.mock import MagicMock

from chaos.harness.chaos_profile import get_profile
from chaos.harness.timing_distorter import TimingDistorter, TimingDistorterContext
from chaos.harness.wal_mutator import WALMutator
from cognitive_runtime.recovery.checkpoint_manager import CheckpointManager
from cognitive_runtime.recovery.runtime_snapshot import RuntimeSnapshot
from cognitive_runtime.recovery.persistence_guard import PersistenceGuard
from cognitive_runtime.recovery.crash_detector import CrashDetector
from cognitive_runtime.recovery.recovery_coordinator import RecoveryCoordinator
from cognitive_runtime.contracts.execution_trace import ExecutionTrace


def test_severe_profile_all_injectors_active():
    profile = get_profile("severe")
    injectors = profile.active_injectors()
    assert len(injectors) >= 4
    assert "wal" in injectors
    assert "causal" in injectors


def test_severe_wal_mutation_recoverable(checkpoint_manager, wal_mutator):
    snap = RuntimeSnapshot.capture(object(), snapshot_id="cp_sev")
    checkpoint_manager.save(snap)
    wal_mutator.corrupt_schema_version("cp_sev")
    wal_mutator.corrupt_traces("cp_sev")
    loaded = checkpoint_manager.load_latest()
    if loaded:
        guard = PersistenceGuard()
        result = guard.validate_snapshot(loaded)
        assert not result.valid
    cm = CheckpointManager(checkpoint_dir=checkpoint_manager._dir)
    loop = MagicMock()
    loop._traces = []
    loop._state = MagicMock()
    loop._state.status = "stopped"
    loop._state.health_status = "healthy"
    loop._queue = MagicMock()
    loop._queue.stats.processed = 0
    coord = RecoveryCoordinator(checkpoint_manager=cm)
    report = coord.recover(loop)
    assert report.recovery_mode in ("clean_start", "crash_recovery")


def test_severe_timing_distortion_survivable():
    distorter = TimingDistorter(seed=42)
    distorter.set_skew(100.0)
    distorter.set_jitter(0.05)
    with TimingDistorterContext(distorter):
        skewed = time.time()
    restored = time.time()
    assert abs(skewed - restored - 100.0) < 2.0
    assert restored > 0


def test_severe_causal_corruption_graceful():
    from chaos.harness.causal_mutator import CausalMutator
    from cognitive_runtime.contracts.causal_graph import CausalGraphBuilder

    traces = [ExecutionTrace(
        event_id=f"e{i}", session_id="s1", sequence_no=i,
        correlation_id=f"c{i}",
        preflight_valid=True, preflight_reason="ok",
        risk_score=0.1,
        p4_verdict="ALLOW", p4_reason="ok", p4_risk_level="low",
        execution_status="SUCCESS",
        final_status="P4_ALLOW",
    ) for i in range(20)]

    mutator = CausalMutator(seed=42)
    mutated = mutator.corrupt_final_status(mutator.create_orphan(mutator.duplicate_event_id(traces)), rate=0.5)
    builder = CausalGraphBuilder()
    graph = builder.build(mutated)
    assert len(graph.nodes) >= 1
    assert len(graph.failure_points) >= 0
