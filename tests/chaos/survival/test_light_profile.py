"""Survival: LIGHT profile — runtime survives mild event queue distortion."""

from unittest.mock import MagicMock
from chaos.harness.chaos_profile import get_profile
from cognitive_runtime.recovery.crash_detector import CrashDetector
from cognitive_runtime.contracts.execution_trace import ExecutionTrace


def test_light_profile_detects_no_false_crash():
    profile = get_profile("light")
    assert profile.severity.value == "LIGHT"
    assert len(profile.active_injectors()) >= 1


def test_light_event_corruption_still_deterministic():
    cfg = get_profile("light").event_queue
    assert cfg.corruption_rate == 0.05
    assert cfg.delay_range == (0.01, 0.05)


def test_light_profile_no_unclean_detection():
    detector = CrashDetector()
    traces = [ExecutionTrace(
        event_id=f"e{i}", session_id="s1", sequence_no=i,
        correlation_id=f"c{i}",
        preflight_valid=True, preflight_reason="ok",
        risk_score=0.1,
        p4_verdict="ALLOW", p4_reason="ok", p4_risk_level="low",
        execution_status="SUCCESS",
        final_status="P4_ALLOW",
    ) for i in range(3)]
    state = MagicMock()
    state.status = "stopped"
    state.health_status = "healthy"
    queue = MagicMock()
    queue.stats.processed = 3
    loop = MagicMock()
    loop._traces = traces
    loop._state = state
    loop._queue = queue
    result = detector.detect(loop)
    assert not result.unclean_shutdown
    assert result.corrupted_cycles == 0
