import asyncio
from unittest.mock import AsyncMock, MagicMock, PropertyMock

import pytest

from cognitive_runtime.runtime.daemon.runtime_daemon import (
    CrashBoundary,
    CrashCategory,
    DaemonHeartbeatMonitor,
    RuntimeDaemon,
)
from cognitive_runtime.runtime.daemon.runtime_lifecycle import (
    LifecycleState,
    InvalidLifecycleTransition,
)
from cognitive_runtime.runtime.daemon.runtime_status import RuntimeStatus


def make_mock_loop(**overrides):
    loop = MagicMock()

    loop._orchestrator = MagicMock()
    loop._orchestrator.is_running = False
    loop._orchestrator.start = MagicMock()
    loop._orchestrator.state = MagicMock()
    loop._orchestrator.tick_heartbeat = MagicMock()

    loop._queue = MagicMock()
    loop._queue.open = MagicMock()
    loop._queue.close = MagicMock()
    loop._queue.pop = MagicMock(return_value=None)
    loop._queue.queue_depth = 0

    loop._process_event = AsyncMock()

    loop._state = MagicMock()
    loop._state.status = "stopped"
    loop._state.health_status = "healthy"
    loop._state.total_events_processed = 0
    loop._state.consecutive_failures = 0
    loop._state.last_error = None
    loop._state.record_error = MagicMock()

    loop._recovery_coordinator = MagicMock()
    loop._recovery_coordinator.recover = MagicMock()
    loop._recovery_completed = False

    loop._liveness = MagicMock()
    loop._liveness.on_idle = MagicMock()

    loop.stop = MagicMock()
    loop.pause = MagicMock()
    loop.resume = MagicMock()

    loop.state = loop._state

    for k, v in overrides.items():
        setattr(loop, k, v)

    return loop


@pytest.fixture
def mock_loop():
    return make_mock_loop()


@pytest.fixture
def daemon(mock_loop):
    return RuntimeDaemon(mock_loop)


async def boot_daemon(daemon, mock_loop):
    """Helper: boot the daemon with proper mock wiring."""
    def _start():
        mock_loop._orchestrator.is_running = True
    mock_loop._orchestrator.start = MagicMock(side_effect=_start)
    await daemon.boot()
    return daemon


# ── CrashBoundary ──

class TestCrashBoundary:
    def test_recoverable_connection_error(self):
        assert CrashBoundary.classify(ConnectionError("connection refused")) == CrashCategory.RECOVERABLE

    def test_recoverable_timeout(self):
        assert CrashBoundary.classify(TimeoutError("timed out")) == CrashCategory.RECOVERABLE

    def test_recoverable_oserror(self):
        assert CrashBoundary.classify(OSError("temporary failure")) == CrashCategory.RECOVERABLE

    def test_non_recoverable_memory_error(self):
        assert CrashBoundary.classify(MemoryError("oom")) == CrashCategory.NON_RECOVERABLE

    def test_non_recoverable_system_error(self):
        assert CrashBoundary.classify(SystemError("internal")) == CrashCategory.NON_RECOVERABLE

    def test_non_recoverable_keyboard_interrupt(self):
        assert CrashBoundary.classify(KeyboardInterrupt()) == CrashCategory.NON_RECOVERABLE

    def test_non_recoverable_unknown(self):
        assert CrashBoundary.classify(Exception("something unexpected")) == CrashCategory.NON_RECOVERABLE

    def test_configuration_keyword(self):
        assert CrashBoundary.classify(Exception("invalid config")) == CrashCategory.CONFIGURATION
        assert CrashBoundary.classify(Exception("configuration error")) == CrashCategory.CONFIGURATION

    def test_internal_runtime_assertion(self):
        assert CrashBoundary.classify(AssertionError("invariant failed")) == CrashCategory.INTERNAL_RUNTIME

    def test_internal_runtime_runtime_error(self):
        assert CrashBoundary.classify(RuntimeError("contract violation")) == CrashCategory.INTERNAL_RUNTIME


# ── DaemonHeartbeatMonitor ──

class TestDaemonHeartbeatMonitor:
    def test_initial_state(self):
        monitor = DaemonHeartbeatMonitor()
        assert monitor.last_heartbeat_at is None
        assert monitor.last_skew_ms == 0.0
        assert monitor.stall_count == 0

    def test_observe_sets_heartbeat(self):
        monitor = DaemonHeartbeatMonitor()
        loop = make_mock_loop()
        monitor.observe(loop)
        assert monitor.last_heartbeat_at is not None

    def test_observe_no_stall_on_first_call(self):
        monitor = DaemonHeartbeatMonitor()
        loop = make_mock_loop()
        monitor.observe(loop)
        assert monitor.stall_count == 0

    def test_stall_detected(self):
        import time
        monitor = DaemonHeartbeatMonitor()
        loop = make_mock_loop()
        monitor._last_heartbeat = time.time() - 10
        monitor.observe(loop)
        assert monitor.stall_count == 1

    def test_no_stall_within_threshold(self):
        import time
        monitor = DaemonHeartbeatMonitor()
        loop = make_mock_loop()
        monitor._last_heartbeat = time.time() - 1
        monitor.observe(loop)
        assert monitor.stall_count == 0


# ── Initial State ──

class TestRuntimeDaemonInitialState:
    def test_starts_stopped(self, daemon):
        assert daemon.lifecycle == LifecycleState.STOPPED

    def test_status_is_read_only(self, daemon):
        status = daemon.status
        assert isinstance(status, RuntimeStatus)
        assert status.lifecycle_state == LifecycleState.STOPPED

    def test_status_is_frozen(self, daemon):
        status = daemon.status
        with pytest.raises(Exception):
            status.lifecycle_state = LifecycleState.RUNNING


# ── Lifecycle ──

class TestRuntimeDaemonLifecycle:
    @pytest.mark.asyncio
    async def test_boot_transitions_to_running(self, daemon, mock_loop):
        d = await boot_daemon(daemon, mock_loop)
        assert d.lifecycle == LifecycleState.RUNNING
        await d.shutdown()

    @pytest.mark.asyncio
    async def test_boot_calls_recovery_when_needed(self, daemon, mock_loop):
        mock_loop._recovery_completed = False
        d = await boot_daemon(daemon, mock_loop)
        mock_loop._recovery_coordinator.recover.assert_called_once()
        assert d.lifecycle == LifecycleState.RUNNING
        await d.shutdown()

    @pytest.mark.asyncio
    async def test_boot_skips_recovery_when_completed(self, daemon, mock_loop):
        mock_loop._recovery_completed = True
        d = await boot_daemon(daemon, mock_loop)
        mock_loop._recovery_coordinator.recover.assert_not_called()
        assert d.lifecycle == LifecycleState.RUNNING
        await d.shutdown()

    @pytest.mark.asyncio
    async def test_boot_fails_on_timeout(self, daemon, mock_loop):
        mock_loop._orchestrator.is_running = False
        mock_loop._orchestrator.start = MagicMock()
        with pytest.raises(RuntimeError, match="failed to start"):
            await daemon.boot()
        assert daemon.lifecycle == LifecycleState.SHUTDOWN

    @pytest.mark.asyncio
    async def test_shutdown_from_running(self, daemon, mock_loop):
        d = await boot_daemon(daemon, mock_loop)
        assert d.lifecycle == LifecycleState.RUNNING
        await d.shutdown()
        assert d.lifecycle == LifecycleState.SHUTDOWN
        mock_loop.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_pause_and_resume(self, daemon, mock_loop):
        d = await boot_daemon(daemon, mock_loop)
        assert d.lifecycle == LifecycleState.RUNNING

        d.pause()
        assert d.lifecycle == LifecycleState.PAUSED
        mock_loop.pause.assert_called_once()

        d.resume()
        assert d.lifecycle == LifecycleState.RUNNING
        mock_loop.resume.assert_called_once()
        await d.shutdown()

    @pytest.mark.asyncio
    async def test_pause_from_wrong_state_raises(self, daemon):
        with pytest.raises(InvalidLifecycleTransition):
            daemon.pause()

    @pytest.mark.asyncio
    async def test_resume_from_wrong_state_raises(self, daemon):
        with pytest.raises(InvalidLifecycleTransition):
            daemon.resume()

    @pytest.mark.asyncio
    async def test_boot_from_wrong_state_raises(self, daemon, mock_loop):
        d = await boot_daemon(daemon, mock_loop)
        with pytest.raises(InvalidLifecycleTransition):
            await d.boot()
        await d.shutdown()

    @pytest.mark.asyncio
    async def test_shutdown_from_stopped_raises(self, daemon):
        with pytest.raises(InvalidLifecycleTransition):
            await daemon.shutdown()


# ── Crash Handling ──

class TestRuntimeDaemonCrash:
    @pytest.mark.asyncio
    async def test_recoverable_crash_recovery_success(self, daemon, mock_loop):
        d = await boot_daemon(daemon, mock_loop)
        assert d.lifecycle == LifecycleState.RUNNING

        await d._handle_event_crash(ConnectionError("connection lost"))

        assert d.lifecycle == LifecycleState.RUNNING
        assert d._panic_count == 1
        assert d._recovery_count == 1
        mock_loop._recovery_coordinator.recover.assert_called()
        await d.shutdown()

    @pytest.mark.asyncio
    async def test_non_recoverable_crash_shutdown(self, daemon, mock_loop):
        d = await boot_daemon(daemon, mock_loop)
        await d._handle_event_crash(MemoryError("out of memory"))
        assert d.lifecycle == LifecycleState.SHUTDOWN
        assert d._panic_count == 1

    @pytest.mark.asyncio
    async def test_configuration_crash_shutdown(self, daemon, mock_loop):
        d = await boot_daemon(daemon, mock_loop)
        await d._handle_event_crash(Exception("configuration error"))
        assert d.lifecycle == LifecycleState.SHUTDOWN

    @pytest.mark.asyncio
    async def test_recovery_failure_shutdown(self, daemon, mock_loop):
        call_count = 0
        def recover_side_effect(*args):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return MagicMock()
            raise RuntimeError("recovery failed")
        mock_loop._recovery_coordinator.recover = MagicMock(
            side_effect=recover_side_effect
        )
        d = await boot_daemon(daemon, mock_loop)
        await d._handle_event_crash(ConnectionError("transient"))
        assert d.lifecycle == LifecycleState.SHUTDOWN
        assert d._panic_count == 1

    @pytest.mark.asyncio
    async def test_panic_count_tracks_crashes(self, daemon, mock_loop):
        d = await boot_daemon(daemon, mock_loop)
        await d._handle_event_crash(ConnectionError("first"))
        await d._handle_event_crash(TimeoutError("second"))
        await d._handle_event_crash(OSError("third"))
        assert d._panic_count == 3
        assert d._recovery_count == 3
        await d.shutdown()


# ── Status ──

class TestRuntimeDaemonStatus:
    def test_status_default(self, daemon):
        status = daemon.status
        assert status.lifecycle_state == LifecycleState.STOPPED

    @pytest.mark.asyncio
    async def test_status_after_boot(self, daemon, mock_loop):
        d = await boot_daemon(daemon, mock_loop)
        status = d.status
        assert status.lifecycle_state == LifecycleState.RUNNING
        assert status.health_status == "healthy"
        await d.shutdown()

    @pytest.mark.asyncio
    async def test_status_after_crash(self, daemon, mock_loop):
        d = await boot_daemon(daemon, mock_loop)
        await d._handle_event_crash(ConnectionError("lost"))
        status = d.status
        assert status.panic_count == 1
        assert status.recovery_count == 1
        await d.shutdown()

    @pytest.mark.asyncio
    async def test_status_after_shutdown(self, daemon, mock_loop):
        d = await boot_daemon(daemon, mock_loop)
        await d.shutdown()
        status = d.status
        assert status.lifecycle_state == LifecycleState.SHUTDOWN


# ── Supervision ──

class TestRuntimeDaemonSupervision:
    @pytest.mark.asyncio
    async def test_pause_stops_event_processing(self, daemon, mock_loop):
        from cognitive_runtime.contracts.execution_contract import HostEvent
        event = HostEvent(event_id="e1", session_id="s1", timestamp=1000.0, source="test", payload={})
        mock_loop._queue.pop = MagicMock(return_value=event)

        d = await boot_daemon(daemon, mock_loop)

        await asyncio.sleep(0.05)

        d.pause()
        mock_loop._process_event.reset_mock()

        await asyncio.sleep(0.1)

        mock_loop._process_event.assert_not_called()
        await d.shutdown()

    @pytest.mark.asyncio
    async def test_processes_events_when_running(self, daemon, mock_loop):
        from cognitive_runtime.contracts.execution_contract import HostEvent
        event = HostEvent(event_id="e1", session_id="s1", timestamp=1000.0, source="test", payload={})
        mock_loop._queue.pop = MagicMock(side_effect=[event, None])

        d = await boot_daemon(daemon, mock_loop)

        await asyncio.sleep(0.05)

        mock_loop._process_event.assert_called_once()
        assert d.lifecycle == LifecycleState.RUNNING
        await d.shutdown()

    @pytest.mark.asyncio
    async def test_shutdown_cancels_task(self, daemon, mock_loop):
        d = await boot_daemon(daemon, mock_loop)
        assert d._daemon_task is not None
        assert not d._daemon_task.done()
        await d.shutdown()
        assert d._daemon_task.done()


# ── RuntimeStatus Data Class ──

class TestRuntimeStatusDataClass:
    def test_frozen_dataclass(self):
        status = RuntimeStatus()
        with pytest.raises(Exception):
            status.lifecycle_state = LifecycleState.RUNNING

    def test_default_values(self):
        status = RuntimeStatus()
        assert status.lifecycle_state == LifecycleState.STOPPED
        assert status.uptime_seconds == 0.0
        assert status.cycle_count == 0
        assert status.last_heartbeat_at is None
        assert status.last_heartbeat_skew_ms == 0.0
        assert status.panic_count == 0
        assert status.recovery_count == 0
        assert status.health_status == "healthy"
        assert status.consecutive_failures == 0
        assert status.last_error is None

    def test_equality_by_value(self):
        s1 = RuntimeStatus(cycle_count=10)
        s2 = RuntimeStatus(cycle_count=10)
        assert s1 == s2

    def test_inequality(self):
        s1 = RuntimeStatus(panic_count=1)
        s2 = RuntimeStatus(panic_count=2)
        assert s1 != s2
