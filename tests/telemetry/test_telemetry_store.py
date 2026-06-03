import json
import os
import tempfile
import unittest
from collections import deque

from cognitive_runtime.telemetry.telemetry_snapshot import TelemetrySnapshot
from cognitive_runtime.telemetry.telemetry_store import TelemetryStore


class TestTelemetrySnapshot(unittest.TestCase):
    def test_snapshot_creation(self):
        snap = TelemetrySnapshot(
            cycle_no=42,
            governance_score=0.85,
            entropy_score=0.12,
            drift_score=0.05,
            stability_score=0.92,
            confidence_score=0.88,
            entropy_velocity=0.01,
            governance_oscillation_count=2,
            confidence_hysteresis=0.03,
            causal_density=1.5,
            await_amplification=0.15,
            checkpoint_size_kb=45.2,
            pending_tasks=3,
            is_stalled=False,
            health_status="healthy",
        )
        self.assertEqual(snap.cycle_no, 42)
        self.assertEqual(snap.governance_score, 0.85)
        self.assertEqual(snap.health_status, "healthy")
        self.assertFalse(snap.is_stalled)


class TestTelemetryStore(unittest.TestCase):
    def setUp(self):
        self.store = TelemetryStore()

    def _snap(self, cycle: int, gov: float = 0.8, stab: float = 0.9,
              conf: float = 0.85, ent: float = 0.1, drift: float = 0.05,
              ev: float = 0.0, aa: float = 0.1, cd: float = 1.0,
              ck: float = 50.0, pending: int = 0, stalled: bool = False,
              health: str = "healthy"):
        return TelemetrySnapshot(
            cycle_no=cycle, governance_score=gov, entropy_score=ent,
            drift_score=drift, stability_score=stab, confidence_score=conf,
            entropy_velocity=ev, governance_oscillation_count=0,
            confidence_hysteresis=0.0, causal_density=cd,
            await_amplification=aa, checkpoint_size_kb=ck,
            pending_tasks=pending, is_stalled=stalled, health_status=health,
        )

    def test_empty_store(self):
        self.assertIsNone(self.store.latest())
        self.assertEqual(0, self.store.capture_count)
        self.assertEqual(0, len(self.store.hot))
        self.assertEqual(0, len(self.store.warm))

    def test_record_single(self):
        snap = self._snap(1)
        self.store.record(snap)
        self.assertEqual(1, self.store.capture_count)
        self.assertEqual(1, len(self.store.hot))
        self.assertEqual(snap, self.store.latest())

    def test_hot_maxlen(self):
        for i in range(1500):
            self.store.record(self._snap(i))
        self.assertLessEqual(len(self.store.hot), 1000)

    def test_warm_compress_at_interval(self):
        for i in range(1000):
            self.store.record(self._snap(i, gov=0.8, ent=0.1, stab=0.9, conf=0.85))
        self.assertEqual(1, len(self.store.warm))
        agg = self.store.warm[0]
        self.assertEqual((0, 999), agg.cycle_range)
        self.assertEqual(1000, agg.count)
        self.assertAlmostEqual(agg.mean_governance, 0.8, places=4)

    def test_warm_compress_twice(self):
        for i in range(2000):
            self.store.record(self._snap(i, gov=0.8, ent=0.1, stab=0.9, conf=0.85))
        self.assertEqual(2, len(self.store.warm))

    def test_stall_free_streak(self):
        for i in range(10):
            self.store.record(self._snap(i, health="healthy"))
        self.assertEqual(10, self.store.stall_free_streak)
        self.store.record(self._snap(11, stalled=True, health="stalled"))
        self.assertEqual(0, self.store.stall_free_streak)

    def test_save_and_load_cold(self):
        for i in range(1000):
            self.store.record(self._snap(i, gov=0.8, ent=0.1))
        with tempfile.TemporaryDirectory() as tmp:
            self.store.save_cold(tmp)
            files = os.listdir(tmp)
            self.assertTrue(any(f.endswith(".json") for f in files))
            store2 = TelemetryStore()
            loaded = store2.load_cold(tmp)
            self.assertEqual(1, loaded)
            self.assertEqual(1, len(store2.warm))

    def test_get_physiology_without_enough_data(self):
        phys = self.store.get_physiology()
        self.assertFalse(phys.memory_plateau)
        self.assertFalse(phys.recovery_cost_stable)

    def test_get_physiology_with_enough_data(self):
        for i in range(3000):
            self.store.record(self._snap(i, gov=0.8, ent=0.1, stab=0.9, conf=0.85, cd=0.5, aa=0.1))
        phys = self.store.get_physiology()
        self.assertAlmostEqual(phys.entropy_slope, 0.0, places=4)
        self.assertTrue(phys.governance_stable)

    def test_empty_compress_does_not_crash(self):
        store = TelemetryStore()
        store.record(self._snap(0))
        store._compress_empty()
        self.assertEqual(1, len(store.warm))

    def test_checkpoint_growth_in_compress(self):
        sizes = [10.0, 20.0, 30.0]
        for i, ck in enumerate(sizes):
            self.store.record(self._snap(i, ck=ck))
        for i in range(3, 1000):
            self.store.record(self._snap(i, ck=30.0))
        self.assertEqual(1, len(self.store.warm))
        self.assertAlmostEqual(self.store.warm[0].total_checkpoint_growth_kb, 20.0, places=4)

    def test_stall_count_in_compress(self):
        for i in range(1000):
            stalled = i % 100 == 0
            self.store.record(self._snap(i, stalled=stalled, health="stalled" if stalled else "healthy"))
        self.assertEqual(1, len(self.store.warm))
        self.assertEqual(self.store.warm[0].total_stalls, 10)

    def test_min_health_in_compress(self):
        for i in range(1000):
            health = "critical" if i == 500 else "healthy"
            self.store.record(self._snap(i, health=health))
        self.assertEqual(self.store.warm[0].min_health, "critical")

    def test_load_cold_nonexistent_dir(self):
        loaded = self.store.load_cold("nonexistent_dir_xyz")
        self.assertEqual(0, loaded)

    def test_compress_empty_window(self):
        store = TelemetryStore()
        agg = store._compress()
        self.assertEqual(0, agg.count)
        self.assertEqual((0, 0), agg.cycle_range)
