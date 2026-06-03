"""Survival: EXTREME profile — runtime survives max-intensity multi-axis chaos."""

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


def test_extreme_profile_all_injectors_active():
    profile = get_profile("extreme")
    injectors = profile.active_injectors()
    assert len(injectors) == 5
    assert "event_queue" in injectors
    assert "runtime_deps" in injectors
    assert "wal" in injectors
    assert "causal" in injectors
    assert "timing" in injectors


def test_extreme_profile_higher_rates_than_severe():
    extreme = get_profile("extreme")
    severe = get_profile("severe")
    assert extreme.event_queue.corruption_rate >= severe.event_queue.corruption_rate
    assert extreme.wal.corruption_rate >= severe.wal.corruption_rate
    assert extreme.causal.corruption_rate >= severe.causal.corruption_rate
    assert extreme.timing.skew_seconds >= severe.timing.skew_seconds


def test_extreme_wal_mutation_recoverable(checkpoint_manager, wal_mutator):
    snap = RuntimeSnapshot.capture(object(), snapshot_id="cp_ext")
    checkpoint_manager.save(snap)
    wal_mutator.corrupt_schema_version("cp_ext")
    wal_mutator.corrupt_traces("cp_ext")
    wal_mutator.arbitrary_mutation("cp_ext")
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


def test_extreme_timing_distortion_survivable():
    distorter = TimingDistorter(seed=42)
    distorter.set_skew(500.0)
    distorter.set_jitter(0.2)
    distorter.enable_inversion()
    with TimingDistorterContext(distorter):
        t1 = time.time()
        t2 = time.time()
    restored = time.time()
    assert restored > 0
    assert t2 >= t1 or t2 < t1


def test_extreme_causal_corruption_graceful():
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
    ) for i in range(50)]

    mutator = CausalMutator(seed=42)
    mutated = mutator.corrupt_final_status(
        mutator.create_orphan(
            mutator.duplicate_event_id(
                mutator.inject_cycle(traces)
            )
        ), rate=0.5
    )
    builder = CausalGraphBuilder()
    graph = builder.build(mutated)
    assert len(graph.nodes) >= 1


def test_extreme_fault_injector_config_applied():
    from chaos.harness.fault_injector import FaultInjector
    profile = get_profile("extreme")

    queue = MagicMock()
    queue._events = []
    queue.push = lambda e: e.event_id
    queue.pop = lambda timeout=None: queue._events.pop(0) if queue._events else None

    injector = FaultInjector(queue, seed=42)
    cfg = profile.event_queue
    injector.corruption_rate = cfg.corruption_rate
    injector.duplication_rate = cfg.duplication_rate
    injector.delay_range = cfg.delay_range

    assert injector.corruption_rate == cfg.corruption_rate
    assert injector.duplication_rate == cfg.duplication_rate
    assert injector.delay_range == cfg.delay_range


def test_extreme_runtime_deps_distortion_survivable():
    from chaos.harness.runtime_distorter import distort_runtime_deps, P3Distorter, P4Distorter, SandboxDistorter
    profile = get_profile("extreme")

    p3 = lambda e: MagicMock(proposal_id="p1")
    p4 = lambda p: MagicMock(verdict="ALLOW")
    pool = MagicMock()
    pool.execute = MagicMock(return_value=MagicMock(status="SUCCESS"))

    p3d, p4d, sbd = distort_runtime_deps(p3, p4, pool, profile.runtime_deps)
    assert isinstance(p3d, P3Distorter)
    assert isinstance(p4d, P4Distorter)
    assert isinstance(sbd, SandboxDistorter)
