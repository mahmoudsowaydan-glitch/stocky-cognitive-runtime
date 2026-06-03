import unittest
from unittest.mock import MagicMock, PropertyMock

from cognitive_runtime.telemetry.telemetry_probe import (
    NullTelemetryProbe,
    TelemetryProbe,
)
from cognitive_runtime.telemetry.telemetry_store import TelemetryStore


class _MockLoop:
    def __init__(self):
        self.state = MagicMock()
        self.state.total_events_processed = 100
        self.state.health_status = "healthy"
        self.state.queue_depth = 3
        self.governance = MagicMock()
        self.governance.score_history = [0.8, 0.82, 0.85]
        self.governance.assess = MagicMock()
        report = MagicMock()
        report.entropy.overall = 0.12
        report.drift.overall = 0.05
        self.governance.assess.return_value = report
        self.stability = MagicMock()
        self.stability.score_history = [0.9, 0.91, 0.92]
        self.confidence = MagicMock()
        self.confidence.score_history = [0.85, 0.86, 0.88]
        self.causal_graph = MagicMock()
        self.causal_graph.nodes = ["a", "b", "c"]
        self.causal_graph.edges = [("a", "b"), ("b", "c")]
        self.liveness = MagicMock()
        liveness_report = MagicMock()
        liveness_report.cycle_durations = MagicMock()
        liveness_report.cycle_durations.p95_ms = 100.0
        liveness_report.phase_await_stats = {
            "p3": MagicMock(max_ms=5.0),
            "p4": MagicMock(max_ms=10.0),
        }
        liveness_report.is_stalled = False
        self.liveness.get_report.return_value = liveness_report
        self._checkpoint_manager = MagicMock()
        meta = MagicMock()
        meta.size_bytes = 51200
        self._checkpoint_manager.latest = meta
        self.compression = MagicMock()
        self.compression.store = MagicMock()
        self.coherence = MagicMock()
        self.traces = []


class TestTelemetryProbe(unittest.TestCase):
    def setUp(self):
        self.store = TelemetryStore()
        self.probe = TelemetryProbe(store=self.store, capture_interval=1)
        self.loop = _MockLoop()

    def test_probe_enabled(self):
        self.assertTrue(self.probe.enabled)

    def test_probe_store(self):
        self.assertIs(self.store, self.probe.store)

    def test_capture_returns_snapshot(self):
        snap = self.probe.capture(self.loop)
        self.assertIsNotNone(snap)
        self.assertEqual(snap.cycle_no, 100)
        self.assertAlmostEqual(snap.governance_score, 0.85)
        self.assertAlmostEqual(snap.stability_score, 0.92)
        self.assertAlmostEqual(snap.confidence_score, 0.88)
        self.assertAlmostEqual(snap.entropy_score, 0.12)
        self.assertAlmostEqual(snap.drift_score, 0.05)

    def test_capture_stores_in_telemetry(self):
        self.probe.capture(self.loop)
        self.assertEqual(1, self.store.capture_count)
        self.assertEqual(1, len(self.store.hot))

    def test_capture_interval_skips(self):
        probe = TelemetryProbe(store=self.store, capture_interval=5)
        for _ in range(4):
            snap = probe.capture(self.loop)
            self.assertIsNone(snap)
        snap = probe.capture(self.loop)
        self.assertIsNotNone(snap)
        self.assertEqual(1, self.store.capture_count)

    def test_entropy_velocity(self):
        self.probe.capture(self.loop)
        snap2 = self.probe.capture(self.loop)
        self.assertIsNotNone(snap2)

    def test_causal_density(self):
        snap = self.probe.capture(self.loop)
        self.assertAlmostEqual(snap.causal_density, 2.0 / 3.0)

    def test_await_amplification(self):
        snap = self.probe.capture(self.loop)
        self.assertGreater(snap.await_amplification, 0.0)

    def test_checkpoint_size(self):
        snap = self.probe.capture(self.loop)
        self.assertAlmostEqual(snap.checkpoint_size_kb, 50.0, places=1)

    def test_pending_tasks(self):
        snap = self.probe.capture(self.loop)
        self.assertEqual(snap.pending_tasks, 3)

    def test_is_stalled(self):
        snap = self.probe.capture(self.loop)
        self.assertFalse(snap.is_stalled)

    def test_health_status(self):
        snap = self.probe.capture(self.loop)
        self.assertEqual(snap.health_status, "healthy")

    def test_governance_oscillation_tracking(self):
        probe = TelemetryProbe(store=self.store, capture_interval=1)
        loop = _MockLoop()
        loop.governance.score_history = [0.5]
        probe.capture(loop)
        loop.governance.score_history = [0.8]
        probe.capture(loop)
        loop.governance.score_history = [0.6]
        probe.capture(loop)
        self.assertGreater(probe._oscillation_count, 0)

    def test_confidence_hysteresis(self):
        probe = TelemetryProbe(store=self.store, capture_interval=1)
        loop = _MockLoop()
        for i in range(10):
            loop.governance.score_history = [0.5 + i * 0.02]
            probe.capture(loop)
        self.assertGreater(probe._compute_hysteresis(0.7), 0.0)

    def test_no_traces_fallback(self):
        loop = _MockLoop()
        loop.state.total_events_processed = 0
        snap = self.probe.capture(loop)
        self.assertEqual(snap.cycle_no, 0)

    def test_no_governance_fallback(self):
        loop = _MockLoop()
        loop.governance = None
        snap = self.probe.capture(loop)
        self.assertAlmostEqual(snap.governance_score, 0.0)

    def test_no_causal_graph(self):
        loop = _MockLoop()
        loop.causal_graph = None
        snap = self.probe.capture(loop)
        self.assertAlmostEqual(snap.causal_density, 0.0)

    def test_no_liveness(self):
        loop = _MockLoop()
        loop.liveness = None
        snap = self.probe.capture(loop)
        self.assertAlmostEqual(snap.await_amplification, 0.0)
        self.assertFalse(snap.is_stalled)

    def test_no_checkpoint_manager(self):
        loop = _MockLoop()
        del loop._checkpoint_manager
        snap = self.probe.capture(loop)
        self.assertAlmostEqual(snap.checkpoint_size_kb, 0.0)


class TestNullTelemetryProbe(unittest.TestCase):
    def setUp(self):
        self.probe = NullTelemetryProbe()

    def test_not_enabled(self):
        self.assertFalse(self.probe.enabled)

    def test_capture_returns_none(self):
        result = self.probe.capture("anything")
        self.assertIsNone(result)

    def test_store_is_empty(self):
        store = self.probe.store
        self.assertEqual(0, store.capture_count)

    def test_noop_on_loop(self):
        loop = _MockLoop()
        self.probe.capture(loop)
        self.assertEqual(0, self.probe.store.capture_count)
