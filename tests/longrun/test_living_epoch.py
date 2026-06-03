import os
import tempfile
import time
import unittest
from unittest.mock import MagicMock

from cognitive_runtime.epoch import (
    BenchmarkRuntime,
    EpochPhase,
    EpochReport,
    EpochSeed,
    LivingEpoch,
    PanicConfig,
    PanicDetector,
    PanicType,
    Postmortem,
    VelocityMetrics,
    VelocityTracker,
)
from cognitive_runtime.telemetry.telemetry_snapshot import TelemetrySnapshot
from cognitive_runtime.telemetry.telemetry_store import TelemetryStore


class TestEpochSeed(unittest.TestCase):
    def test_seed_derives_sub_seeds(self):
        s = EpochSeed(42)
        self.assertEqual(s.value, 42)
        self.assertNotEqual(s.chaos_seed, s.jitter_seed)
        self.assertNotEqual(s.migration_seed, s.replay_seed)

    def test_same_seed_same_derivation(self):
        self.assertEqual(EpochSeed(42).chaos_seed, EpochSeed(42).chaos_seed)

    def test_different_seeds_different_derivation(self):
        self.assertNotEqual(EpochSeed(42).chaos_seed, EpochSeed(99).chaos_seed)

    def test_all_derived_seeds_unique(self):
        s = EpochSeed(42)
        ids = {s.chaos_seed, s.jitter_seed, s.migration_seed, s.replay_seed, s.perturbation_seed}
        self.assertEqual(len(ids), 5)


class TestVelocityMetrics(unittest.TestCase):
    def test_all_stable_by_default(self):
        vm = VelocityMetrics()
        self.assertTrue(vm.all_stable())

    def test_all_stable_with_small_values(self):
        vm = VelocityMetrics(entropy_velocity=0.0005)
        self.assertTrue(vm.all_stable())

    def test_not_stable_with_large_velocity(self):
        vm = VelocityMetrics(entropy_velocity=0.1)
        self.assertFalse(vm.all_stable(epsilon=0.01))

    def test_not_stable_with_oscillation(self):
        vm = VelocityMetrics(governance_oscillation_velocity=0.5)
        self.assertFalse(vm.all_stable(epsilon=0.1))


class TestVelocityTracker(unittest.TestCase):
    def setUp(self):
        self.tracker = VelocityTracker(window_size=10)

    def _snap(self, cycle, ent=0.1, gov_osc=0, conf=0.85):
        return TelemetrySnapshot(
            cycle_no=cycle, governance_score=0.8, entropy_score=ent,
            drift_score=0.05, stability_score=0.9, confidence_score=conf,
            entropy_velocity=0.0, governance_oscillation_count=gov_osc,
            confidence_hysteresis=0.0, causal_density=1.0,
            await_amplification=0.1, checkpoint_size_kb=50.0,
            pending_tasks=0, is_stalled=False, health_status="healthy",
        )

    def test_empty_tracker_returns_defaults(self):
        m = self.tracker.compute()
        self.assertAlmostEqual(m.entropy_velocity, 0.0)

    def test_single_snapshot_no_velocity(self):
        self.tracker.record_snapshot(self._snap(1))
        m = self.tracker.compute()
        self.assertAlmostEqual(m.entropy_velocity, 0.0)

    def test_entropy_velocity_computed(self):
        self.tracker.record_snapshot(self._snap(1, ent=0.1))
        self.tracker.record_snapshot(self._snap(101, ent=0.2))
        m = self.tracker.compute()
        self.assertAlmostEqual(m.entropy_velocity, 0.001)

    def test_oscillation_velocity(self):
        self.tracker.record_snapshot(self._snap(1, gov_osc=0))
        self.tracker.record_snapshot(self._snap(101, gov_osc=5))
        m = self.tracker.compute()
        self.assertAlmostEqual(m.governance_oscillation_velocity, 0.05)

    def test_confidence_drift(self):
        self.tracker.record_snapshot(self._snap(1, conf=0.9))
        self.tracker.record_snapshot(self._snap(101, conf=0.8))
        m = self.tracker.compute()
        self.assertAlmostEqual(m.confidence_drift_velocity, -0.001)

    def test_window_limits_history(self):
        for i in range(30):
            self.tracker.record_snapshot(self._snap(i))
        self.assertEqual(len(self.tracker._snapshots), 10)

    def test_replay_divergence_history(self):
        self.tracker.record_replay_divergence(0)
        self.tracker.record_replay_divergence(3)
        m = self.tracker.compute()
        self.assertAlmostEqual(m.replay_divergence_velocity, 1.5)

    def test_recovery_latency_slope(self):
        self.tracker.record_recovery_latency(10.0)
        self.tracker.record_recovery_latency(50.0)
        m = self.tracker.compute()
        self.assertEqual(m.recovery_latency_slope, 20.0)


class _SnapBuilder:
    def __init__(self):
        self.cycle = 0

    def next(self, ent=0.1, gov_osc=0, conf=0.85, cd=1.0):
        self.cycle += 1
        return TelemetrySnapshot(
            cycle_no=self.cycle, governance_score=0.8, entropy_score=ent,
            drift_score=0.05, stability_score=0.9, confidence_score=conf,
            entropy_velocity=0.0, governance_oscillation_count=gov_osc,
            confidence_hysteresis=0.0, causal_density=cd,
            await_amplification=0.1, checkpoint_size_kb=50.0,
            pending_tasks=0, is_stalled=False, health_status="healthy",
        )


class TestPanicDetector(unittest.TestCase):
    def setUp(self):
        self.detector = PanicDetector()
        self.tracker = VelocityTracker()

    def test_no_panics_with_stable_metrics(self):
        for i in range(10):
            self.tracker.record_snapshot(_SnapBuilder().next())
        m = self.tracker.compute()
        panics = self.detector.check(m, 100, "OBSERVATION")
        self.assertEqual(len(panics), 0)

    def test_oscillation_explosion_detected(self):
        builder = _SnapBuilder()
        self.tracker.record_snapshot(builder.next(gov_osc=0))
        for _ in range(5):
            self.tracker.record_snapshot(builder.next(gov_osc=20))
        m = self.tracker.compute()
        panics = self.detector.check(m, 100, "CHAOS")
        self.assertTrue(any(p.panic_type == PanicType.OSCILLATION_EXPLOSION for p in panics))

    def test_entropy_runaway_detected(self):
        builder = _SnapBuilder()
        self.tracker.record_snapshot(builder.next(ent=0.1))
        for _ in range(5):
            self.tracker.record_snapshot(builder.next(ent=0.5))
        m = self.tracker.compute()
        panics = self.detector.check(m, 200, "OBSERVATION")
        self.assertTrue(any(p.panic_type == PanicType.ENTROPY_RUNAWAY for p in panics))

    def test_recovery_amplification(self):
        self.tracker.record_recovery_latency(10.0)
        for _ in range(5):
            self.tracker.record_recovery_latency(200.0)
        m = self.tracker.compute()
        panics = self.detector.check(m, 100, "RECOVERY")
        self.assertTrue(any(p.panic_type == PanicType.RECOVERY_AMPLIFICATION for p in panics))

    def test_replay_divergence_cascade(self):
        self.tracker.record_replay_divergence(0)
        for _ in range(5):
            self.tracker.record_replay_divergence(10)
        m = self.tracker.compute()
        panics = self.detector.check(m, 100, "OBSERVATION")
        self.assertTrue(any(p.panic_type == PanicType.REPLAY_DIVERGENCE_CASCADE for p in panics))

    def test_config_overrides(self):
        config = PanicConfig(oscillation_explosion_threshold=10.0)
        detector = PanicDetector(config)
        builder = _SnapBuilder()
        self.tracker.record_snapshot(builder.next(gov_osc=0))
        self.tracker.record_snapshot(builder.next(gov_osc=5))
        m = self.tracker.compute()
        panics = detector.check(m, 100, "OBSERVATION")
        self.assertEqual(len(panics), 0)

    def test_panics_accumulate(self):
        config = PanicConfig(entropy_runaway_threshold=0.0001)
        detector = PanicDetector(config)
        builder = _SnapBuilder()
        for i in range(5):
            self.tracker.record_snapshot(builder.next(ent=0.2 + i * 0.1))
            if i > 1:
                m = self.tracker.compute()
                detector.check(m, 100, "OBS")
        self.assertGreater(len(detector.events), 0)


class TestLivingEpoch(unittest.TestCase):
    def _make_runtime(self):
        runtime = MagicMock()
        runtime._queue = MagicMock()
        runtime._queue.push = MagicMock()
        runtime._telemetry = None
        runtime.stop = MagicMock()
        runtime._finalize_cycle = MagicMock()
        runtime._checkpoint_manager = MagicMock()
        runtime.state = MagicMock()
        runtime.state.total_events_processed = 0
        runtime.state.health_status = "healthy"
        runtime.state.queue_depth = 0
        runtime.governance = MagicMock()
        runtime.governance.score_history = [0.8, 0.82, 0.85]
        runtime.stability = MagicMock()
        runtime.stability.score_history = [0.9, 0.91, 0.92]
        runtime.confidence = MagicMock()
        runtime.confidence.score_history = [0.85, 0.86, 0.88]
        runtime.causal_graph = MagicMock()
        runtime.causal_graph.nodes = ["a", "b", "c"]
        runtime.causal_graph.edges = [("a", "b")]
        runtime.liveness = MagicMock()
        lr = MagicMock()
        lr.cycle_durations = MagicMock()
        lr.cycle_durations.p95_ms = 100.0
        lr.phase_await_stats = {}
        lr.is_stalled = False
        runtime.liveness.get_report.return_value = lr
        runtime._checkpoint_manager.latest = MagicMock()
        runtime._checkpoint_manager.latest.size_bytes = 51200
        runtime.compression = MagicMock()
        runtime.compression.store = MagicMock()
        runtime.coherence = MagicMock()
        runtime.traces = []
        return runtime

    def test_epoch_seed_property(self):
        epoch = LivingEpoch(seed=42, runtime_factory=self._make_runtime)
        self.assertEqual(epoch.seed.value, 42)

    def test_epoch_store_property(self):
        epoch = LivingEpoch(seed=42, runtime_factory=self._make_runtime)
        self.assertIsInstance(epoch.store, TelemetryStore)

    def test_epoch_abort(self):
        epoch = LivingEpoch(seed=42, runtime_factory=self._make_runtime)
        report = epoch.run()
        self.assertIsInstance(report, EpochReport)
        self.assertIn("EPOCH", report.message)

    def test_epoch_returns_report_with_seed(self):
        epoch = LivingEpoch(seed=99, runtime_factory=self._make_runtime)
        report = epoch.run()
        self.assertEqual(report.seed, 99)

    def test_epoch_postmortem_has_phases(self):
        epoch = LivingEpoch(seed=42, runtime_factory=self._make_runtime,
                            phase_cycle_limits={
                                EpochPhase.WARMUP: 50,
                                EpochPhase.STABILIZATION: 50,
                                EpochPhase.OBSERVATION: 100,
                                EpochPhase.SHUTDOWN: 10,
                            })
        report = epoch.run()
        self.assertIsNotNone(report.postmortem)
        self.assertGreater(len(report.postmortem.phase_snapshots), 0)

    def test_epoch_telemetry_captures(self):
        epoch = LivingEpoch(seed=42, runtime_factory=self._make_runtime,
                            capture_interval=10,
                            phase_cycle_limits={
                                EpochPhase.WARMUP: 50,
                                EpochPhase.STABILIZATION: 50,
                                EpochPhase.OBSERVATION: 100,
                                EpochPhase.SHUTDOWN: 10,
                            })
        report = epoch.run()
        self.assertIsNotNone(report.postmortem)
        self.assertGreater(report.postmortem.telemetry_captures, 0)

    def test_epoch_chaos_disabled(self):
        epoch = LivingEpoch(seed=42, runtime_factory=self._make_runtime,
                            enable_chaos=False,
                            phase_cycle_limits={
                                EpochPhase.WARMUP: 20,
                                EpochPhase.STABILIZATION: 20,
                                EpochPhase.OBSERVATION: 50,
                                EpochPhase.SHUTDOWN: 10,
                            })
        report = epoch.run()
        self.assertTrue(report.passed)

    def test_epoch_panic_detection(self):
        config = PanicConfig(entropy_runaway_threshold=0.0001)
        epoch = LivingEpoch(seed=42, runtime_factory=self._make_runtime,
                            panic_config=config,
                            capture_interval=1,
                            enable_chaos=False,
                            phase_cycle_limits={
                                EpochPhase.WARMUP: 10,
                                EpochPhase.STABILIZATION: 10,
                                EpochPhase.OBSERVATION: 10,
                                EpochPhase.SHUTDOWN: 5,
                            })
        epoch._tracker.record_snapshot(TelemetrySnapshot(
            cycle_no=0, governance_score=0.8, entropy_score=0.1,
            drift_score=0.05, stability_score=0.9, confidence_score=0.85,
            entropy_velocity=0.0, governance_oscillation_count=0,
            confidence_hysteresis=0.0, causal_density=1.0,
            await_amplification=0.1, checkpoint_size_kb=50.0,
            pending_tasks=0, is_stalled=False, health_status="healthy",
        ))
        epoch._tracker.record_snapshot(TelemetrySnapshot(
            cycle_no=1, governance_score=0.8, entropy_score=0.5,
            drift_score=0.05, stability_score=0.9, confidence_score=0.85,
            entropy_velocity=0.0, governance_oscillation_count=0,
            confidence_hysteresis=0.0, causal_density=1.0,
            await_amplification=0.1, checkpoint_size_kb=50.0,
            pending_tasks=0, is_stalled=False, health_status="healthy",
        ))
        report = epoch.run()
        self.assertFalse(report.passed)
        self.assertIn("ABORTED", report.message)

    def test_epoch_crash_handling(self):
        def bad_factory():
            raise RuntimeError("factory boom")
        epoch = LivingEpoch(seed=42, runtime_factory=bad_factory)
        report = epoch.run()
        self.assertFalse(report.passed)
        self.assertIn("crashed", report.message)


class TestReplayChallenge:
    _PANIC_CONFIG = PanicConfig(
        oscillation_explosion_threshold=0.5,
        entropy_runaway_threshold=5.0,
        recovery_amplification_threshold=3.0,
        replay_divergence_threshold=5.0,
    )

    def test_no_challenge_passes(self):
        epoch = LivingEpoch(
            seed=42,
            runtime_factory=lambda: BenchmarkRuntime(seed=42, capture_interval=5),
            capture_interval=5,
            panic_config=self._PANIC_CONFIG,
            phase_cycle_limits={
                EpochPhase.WARMUP: 200,
                EpochPhase.STABILIZATION: 200,
                EpochPhase.CHAOS: 200,
                EpochPhase.RECOVERY: 200,
                EpochPhase.OBSERVATION: 200,
                EpochPhase.SHUTDOWN: 10,
                EpochPhase.RECOVERY_BOOT: 10,
                EpochPhase.REPLAY_VALIDATION: 50,
            },
            enable_chaos=True,
            replay_challenge_mode="none",
        )
        report = epoch.run()
        assert report.passed, f"No-challenge epoch failed: {report.message}"

    def test_seed_offset_challenge_passes(self):
        epoch = LivingEpoch(
            seed=42,
            runtime_factory=lambda: BenchmarkRuntime(seed=42, capture_interval=5),
            capture_interval=5,
            panic_config=self._PANIC_CONFIG,
            phase_cycle_limits={
                EpochPhase.WARMUP: 200,
                EpochPhase.STABILIZATION: 200,
                EpochPhase.CHAOS: 200,
                EpochPhase.RECOVERY: 200,
                EpochPhase.OBSERVATION: 200,
                EpochPhase.SHUTDOWN: 10,
                EpochPhase.RECOVERY_BOOT: 10,
                EpochPhase.REPLAY_VALIDATION: 50,
            },
            enable_chaos=True,
            replay_challenge_mode="seed_offset",
        )
        report = epoch.run()
        assert report.passed, f"Seed-offset epoch failed: {report.message}"

    def test_seed_offset_produces_divergence(self):
        epoch = LivingEpoch(
            seed=42,
            runtime_factory=lambda: BenchmarkRuntime(seed=42, capture_interval=5),
            capture_interval=5,
            panic_config=self._PANIC_CONFIG,
            phase_cycle_limits={
                EpochPhase.WARMUP: 200,
                EpochPhase.STABILIZATION: 200,
                EpochPhase.CHAOS: 200,
                EpochPhase.RECOVERY: 200,
                EpochPhase.OBSERVATION: 200,
                EpochPhase.SHUTDOWN: 10,
                EpochPhase.RECOVERY_BOOT: 10,
                EpochPhase.REPLAY_VALIDATION: 150,
            },
            enable_chaos=True,
            replay_challenge_mode="seed_offset",
        )
        report = epoch.run()
        assert report.postmortem is not None
        rr = report.postmortem.replay_report
        assert rr is not None, "No replay report"
        assert rr.divergence_velocity != 0, (
            f"Expected non-zero divergence_velocity with seed_offset challenge, "
            f"got {rr.divergence_velocity}"
        )

    def test_no_challenge_no_divergence(self):
        epoch = LivingEpoch(
            seed=42,
            runtime_factory=lambda: BenchmarkRuntime(seed=42, capture_interval=5),
            capture_interval=5,
            panic_config=self._PANIC_CONFIG,
            phase_cycle_limits={
                EpochPhase.WARMUP: 200,
                EpochPhase.STABILIZATION: 200,
                EpochPhase.CHAOS: 200,
                EpochPhase.RECOVERY: 200,
                EpochPhase.OBSERVATION: 200,
                EpochPhase.SHUTDOWN: 10,
                EpochPhase.RECOVERY_BOOT: 10,
                EpochPhase.REPLAY_VALIDATION: 150,
            },
            enable_chaos=True,
            replay_challenge_mode="none",
        )
        report = epoch.run()
        assert report.postmortem is not None
        rr = report.postmortem.replay_report
        assert rr is not None, "No replay report"
        assert rr.divergence_velocity == 0, (
            f"Expected no divergence without challenge, "
            f"got {rr.divergence_velocity}"
        )


class TestEpochReport(unittest.TestCase):
    def test_report_defaults(self):
        r = EpochReport(seed=42, passed=True, message="test")
        self.assertEqual(r.seed, 42)
        self.assertTrue(r.passed)

    def test_postmortem_to_dict(self):
        pm = Postmortem(
            cycle_count=1000,
            telemetry_captures=100,
            panics=[],
            phase_snapshots=[],
            final_physiology=None,
            replay_report=None,
        )
        d = pm.to_dict()
        self.assertEqual(d["cycle_count"], 1000)
        self.assertEqual(d["telemetry_captures"], 100)
