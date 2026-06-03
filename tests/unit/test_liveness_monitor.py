import time
from typing import List

import pytest

from cognitive_runtime.liveness.liveness_monitor import LivenessMonitor, NullLivenessMonitor


class TestNullLivenessMonitor:
    def test_all_methods_are_noops(self):
        m = NullLivenessMonitor()
        m.on_cycle_start(1.0)
        m.on_cycle_end(2.0)
        m.on_idle()
        m.on_event_received()
        m.on_await_start("p3", "e1", 1.0)
        m.on_await_end("p3", "e1", 1.1)
        m.on_heartbeat(1.0)
        assert m.get_report() is None


class TestLivenessMonitorCycleTracking:
    def test_initial_report_is_empty(self):
        m = LivenessMonitor()
        r = m.get_report()
        assert r.cycle_no == 0
        assert r.total_cycles == 0
        assert r.total_idle == 0
        assert r.cycle_durations.count == 0
        assert r.pending_asyncio_tasks == 0
        assert r.is_stalled is False

    def test_cycle_start_end_tracks_duration(self):
        m = LivenessMonitor()
        m.on_cycle_start(1000.0)
        m.on_cycle_end(1000.05)
        r = m.get_report()
        assert r.cycle_no == 1
        assert r.total_cycles == 1
        assert r.cycle_durations.count == 1
        assert r.cycle_durations.p50_ms == 50.0  # 0.05s = 50ms

    def test_multiple_cycles_compute_percentiles(self):
        m = LivenessMonitor(max_history=100)
        for i in range(100):
            m.on_cycle_start(1000.0 + i * 0.1)
            m.on_cycle_end(1000.0 + i * 0.1 + 0.01)  # 10ms each
        r = m.get_report()
        assert r.total_cycles == 100
        assert r.cycle_durations.count == 100
        assert r.cycle_durations.p50_ms == 10.0
        assert r.cycle_durations.p95_ms == 10.0
        assert r.cycle_durations.p99_ms == 10.0

    def test_cycle_count_monotonic(self):
        m = LivenessMonitor()
        for i in range(1, 6):
            m.on_cycle_start(1000.0 + i)
            m.on_cycle_end(1000.0 + i + 0.01)
            assert m.get_report().total_cycles == i

    def test_cycle_end_without_start_does_not_record(self):
        m = LivenessMonitor()
        m.on_cycle_end(100.0)
        assert m.get_report().cycle_durations.count == 0


class TestLivenessMonitorIdleTracking:
    def test_idle_streak_tracks_consecutive_idles(self):
        m = LivenessMonitor()
        for _ in range(5):
            m.on_idle()
        r = m.get_report()
        assert r.queue_starvation_cycles == 5
        assert r.max_starvation_cycles == 5
        assert r.total_idle == 5

    def test_event_received_resets_idle_streak(self):
        m = LivenessMonitor()
        for _ in range(3):
            m.on_idle()
        m.on_event_received()
        for _ in range(2):
            m.on_idle()
        r = m.get_report()
        assert r.queue_starvation_cycles == 2
        assert r.max_starvation_cycles == 3
        assert r.total_idle == 5

    def test_no_idle_events(self):
        m = LivenessMonitor()
        r = m.get_report()
        assert r.queue_starvation_cycles == 0
        assert r.max_starvation_cycles == 0
        assert r.total_idle == 0


class TestLivenessMonitorAwaitTracking:
    def test_records_await_phase(self):
        m = LivenessMonitor()
        m.on_cycle_start(1000.0)
        m.on_await_start("p3", "e1", 1000.0)
        m.on_await_end("p3", "e1", 1000.02)
        m.on_cycle_end(1000.05)
        r = m.get_report()
        assert "p3" in r.phase_await_stats
        stats = r.phase_await_stats["p3"]
        assert stats.count == 1
        assert stats.p50_ms == 20.0
        assert stats.p95_ms == 20.0
        assert stats.max_ms == 20.0

    def test_multiple_phases_separate_stats(self):
        m = LivenessMonitor()
        m.on_cycle_start(1000.0)
        m.on_await_start("p3", "e1", 1000.0)
        m.on_await_end("p3", "e1", 1000.01)
        m.on_await_start("p4", "prop-e1", 1000.02)
        m.on_await_end("p4", "prop-e1", 1000.05)
        m.on_await_start("sandbox", "d1", 1000.06)
        m.on_await_end("sandbox", "d1", 1000.1)
        m.on_cycle_end(1000.12)
        r = m.get_report()
        assert set(r.phase_await_stats.keys()) == {"p3", "p4", "sandbox"}
        assert r.phase_await_stats["p3"].count == 1
        assert r.phase_await_stats["p4"].count == 1
        assert r.phase_await_stats["sandbox"].count == 1

    def test_await_end_without_start_is_noop(self):
        m = LivenessMonitor()
        m.on_cycle_start(1000.0)
        m.on_await_end("p3", "e1", 1000.02)
        m.on_cycle_end(1000.05)
        r = m.get_report()
        assert r.phase_await_stats == {}

    def test_current_await_shows_stalled(self):
        m = LivenessMonitor()
        m.on_cycle_start(1000.0)
        m.on_await_start("p4", "prop-e1", 1000.0)
        r = m.get_report()
        assert r.is_stalled is True

    def test_reports_multiple_awaits_same_phase_percentiles(self):
        m = LivenessMonitor()
        m.on_cycle_start(1000.0)
        durations = [5, 10, 15, 20, 25]  # ms
        for i, d in enumerate(durations):
            m.on_await_start("p3", f"e{i}", 1000.0)
            m.on_await_end("p3", f"e{i}", 1000.0 + d / 1000.0)
        m.on_cycle_end(1001.0)
        r = m.get_report()
        stats = r.phase_await_stats["p3"]
        assert stats.count == 5
        assert stats.p50_ms == 15.0  # median of 5,10,15,20,25
        assert stats.p95_ms == 25.0
        assert stats.max_ms == 25.0


class TestLivenessMonitorStallDetection:
    def test_detects_stall_above_threshold(self):
        m = LivenessMonitor()
        m.STALL_THRESHOLD_MS = 0.001  # any await counts as stall
        m.on_cycle_start(1000.0)
        m.on_await_start("p3", "e1", 1000.0)
        m.on_await_end("p3", "e1", 1000.05)
        m.on_cycle_end(1000.06)
        r = m.get_report()
        assert len(r.stall_events) == 1
        assert r.stall_events[0].phase == "p3"
        assert r.stall_events[0].id == "e1"

    def test_no_stalls_below_threshold(self):
        m = LivenessMonitor()
        m.STALL_THRESHOLD_MS = 1000.0
        m.on_cycle_start(1000.0)
        m.on_await_start("sandbox", "d1", 1000.0)
        m.on_await_end("sandbox", "d1", 1000.01)
        m.on_cycle_end(1000.02)
        r = m.get_report()
        assert len(r.stall_events) == 0


class TestLivenessMonitorHeartbeat:
    def test_single_heartbeat_no_skew(self):
        m = LivenessMonitor()
        m.on_heartbeat(1000.0)
        r = m.get_report()
        assert r.heartbeat_skew_ms == 0.0
        assert r.heartbeat_delta_variance == 0.0

    def test_heartbeat_skew_detected(self):
        m = LivenessMonitor()
        m.on_heartbeat(1000.0)
        m.on_heartbeat(1000.1)  # 100ms interval
        m.on_heartbeat(1000.3)  # 200ms interval — skew = 50ms from mean 150ms
        r = m.get_report()
        assert r.heartbeat_skew_ms > 0.0

    def test_regular_heartbeats_low_variance(self):
        m = LivenessMonitor()
        for i in range(5):
            m.on_heartbeat(1000.0 + i * 0.1)
        r = m.get_report()
        assert r.heartbeat_delta_variance < 1.0  # very low variance


class TestLivenessMonitorMaxHistory:
    def test_max_history_respected_for_cycle_durations(self):
        m = LivenessMonitor(max_history=10)
        for i in range(100):
            m.on_cycle_start(1000.0 + i)
            m.on_cycle_end(1000.0 + i + 0.01)
        r = m.get_report()
        assert r.cycle_durations.count == 10  # only last 10

    def test_max_history_respected_for_await_records(self):
        m = LivenessMonitor(max_history=5)
        for i in range(20):
            m.on_cycle_start(1000.0 + i)
            m.on_await_start("p3", f"e{i}", 1000.0 + i)
            m.on_await_end("p3", f"e{i}", 1000.0 + i + 0.01)
            m.on_cycle_end(1000.0 + i + 0.02)
        r = m.get_report()
        assert r.phase_await_stats["p3"].count == 5  # only last 5


class TestLivenessMonitorFullIntegration:
    def test_full_cycle_with_all_observations(self):
        m = LivenessMonitor()
        m.on_cycle_start(1000.0)
        m.on_event_received()
        m.on_await_start("p3", "e1", 1000.0)
        m.on_await_end("p3", "e1", 1000.005)
        m.on_await_start("p4", "prop-e1", 1000.006)
        m.on_await_end("p4", "prop-e1", 1000.01)
        m.on_await_start("sandbox", "d1", 1000.011)
        m.on_await_end("sandbox", "d1", 1000.05)
        m.on_heartbeat(1000.06)
        m.on_cycle_end(1000.07)

        r = m.get_report()
        assert r.total_cycles == 1
        assert r.cycle_durations.count == 1
        assert r.queue_starvation_cycles == 0
        assert r.max_starvation_cycles == 0
        assert r.phase_await_stats["p3"].count == 1
        assert r.phase_await_stats["p4"].count == 1
        assert r.phase_await_stats["sandbox"].count == 1
        assert r.heartbeat_skew_ms == 0.0

    def test_mixed_idle_and_active_cycles(self):
        m = LivenessMonitor()
        # 3 idle cycles
        for _ in range(3):
            m.on_cycle_start(time.time())
            m.on_idle()
            m.on_cycle_end(time.time())
        # 2 active cycles
        for i in range(2):
            m.on_cycle_start(time.time())
            m.on_event_received()
            m.on_await_start("p3", f"e{i}", time.time())
            m.on_await_end("p3", f"e{i}", time.time())
            m.on_heartbeat(time.time())
            m.on_cycle_end(time.time())

        r = m.get_report()
        assert r.total_cycles == 5
        assert r.total_idle == 3
        assert r.queue_starvation_cycles == 0  # reset by event_received
        assert r.max_starvation_cycles == 3
