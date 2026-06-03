import asyncio
import time
from typing import Optional

from ..runtime_loop import RuntimeLoop
from .runtime_lifecycle import LifecycleState, LifecycleTransition, InvalidLifecycleTransition
from .runtime_status import RuntimeStatus


class CrashCategory:
    RECOVERABLE = "RECOVERABLE"
    NON_RECOVERABLE = "NON_RECOVERABLE"
    CONFIGURATION = "CONFIGURATION"
    INTERNAL_RUNTIME = "INTERNAL_RUNTIME"


class CrashBoundary:
    RECOVERABLE_KEYWORDS = ["temporary", "transient", "retry", "timeout", "connection"]
    CONFIG_KEYWORDS = ["configuration", "config", "startup", "invalid config"]

    @staticmethod
    def classify(exc: Exception) -> str:
        exc_name = type(exc).__name__
        exc_msg = str(exc).lower()

        if isinstance(exc, (MemoryError, SystemError, KeyboardInterrupt)):
            return CrashCategory.NON_RECOVERABLE

        if any(k in exc_msg for k in CrashBoundary.CONFIG_KEYWORDS):
            return CrashCategory.CONFIGURATION

        if isinstance(exc, (ConnectionError, TimeoutError, OSError)):
            return CrashCategory.RECOVERABLE

        if isinstance(exc, (AssertionError, RuntimeError)):
            return CrashCategory.INTERNAL_RUNTIME

        if any(k in exc_msg for k in CrashBoundary.RECOVERABLE_KEYWORDS):
            return CrashCategory.RECOVERABLE

        return CrashCategory.NON_RECOVERABLE


class DaemonHeartbeatMonitor:
    STALL_THRESHOLD_MS = 5000.0

    def __init__(self):
        self._last_heartbeat: Optional[float] = None
        self._last_skew_ms: float = 0.0
        self._stall_count: int = 0

    def observe(self, loop: RuntimeLoop) -> None:
        ts = time.time()
        if self._last_heartbeat is not None:
            delta_ms = (ts - self._last_heartbeat) * 1000
            if delta_ms > self.STALL_THRESHOLD_MS:
                self._stall_count += 1
            self._last_skew_ms = delta_ms
        self._last_heartbeat = ts

    @property
    def last_heartbeat_at(self) -> Optional[float]:
        return self._last_heartbeat

    @property
    def last_skew_ms(self) -> float:
        return self._last_skew_ms

    @property
    def stall_count(self) -> int:
        return self._stall_count


class RuntimeDaemon:
    def __init__(self, loop: RuntimeLoop):
        self._loop = loop
        self._lifecycle = LifecycleState.STOPPED
        self._heartbeat = DaemonHeartbeatMonitor()
        self._daemon_task: Optional[asyncio.Task] = None
        self._panic_count: int = 0
        self._recovery_count: int = 0
        self._started_at: Optional[float] = None
        self._crash_event: Optional[Exception] = None

    async def boot(self) -> None:
        self._assert_current(LifecycleState.STOPPED)
        self._transition(LifecycleState.BOOTING)

        self._started_at = time.time()

        if not self._loop._recovery_completed:
            report = self._loop._recovery_coordinator.recover(self._loop)
            self._loop._recovery_completed = True

        self._daemon_task = asyncio.create_task(self._run_forever())

        for _ in range(200):
            if self._loop._orchestrator.is_running:
                break
            await asyncio.sleep(0.005)
        else:
            if self._daemon_task and not self._daemon_task.done():
                self._daemon_task.cancel()
                try:
                    await self._daemon_task
                except (asyncio.CancelledError, Exception):
                    pass
            self._lifecycle = LifecycleState.SHUTDOWN
            raise RuntimeError("RuntimeLoop failed to start within timeout")

        self._transition(LifecycleState.RUNNING)

    async def shutdown(self) -> None:
        LifecycleTransition.assert_transition(self._lifecycle, LifecycleState.SHUTDOWN)
        self._loop.stop()
        if self._daemon_task and not self._daemon_task.done():
            self._daemon_task.cancel()
            try:
                await self._daemon_task
            except (asyncio.CancelledError, Exception):
                pass
        self._lifecycle = LifecycleState.SHUTDOWN

    def pause(self) -> None:
        self._assert_current(LifecycleState.RUNNING)
        self._loop.pause()
        self._transition(LifecycleState.PAUSED)

    def resume(self) -> None:
        self._assert_current(LifecycleState.PAUSED)
        self._loop.resume()
        self._transition(LifecycleState.RUNNING)

    async def _run_forever(self) -> None:
        self._loop._orchestrator.start()
        self._loop._queue.open()

        try:
            while self._lifecycle not in (LifecycleState.SHUTDOWN,):
                try:
                    self._heartbeat.observe(self._loop)

                    if self._lifecycle == LifecycleState.PAUSED:
                        await asyncio.sleep(0.1)
                        continue

                    if self._lifecycle == LifecycleState.RECOVERING:
                        await asyncio.sleep(0.1)
                        continue

                    event = self._loop._queue.pop()
                    if event is None:
                        await asyncio.sleep(0.1)
                        continue

                    start_time = time.time()
                    await self._loop._process_event(event)
                    duration_ms = (time.time() - start_time) * 1000
                    self._loop._state.record_cycle(duration_ms, True, self._loop._queue.queue_depth)
                    await asyncio.sleep(0)

                except asyncio.CancelledError:
                    break
                except Exception as exc:
                    duration_ms = (time.time() - start_time) * 1000
                    self._loop._state.record_cycle(duration_ms, False, self._loop._queue.queue_depth)
                    await self._handle_event_crash(exc)
        finally:
            self._loop._queue.close()

    async def _handle_event_crash(self, exc: Exception) -> None:
        self._panic_count += 1
        category = CrashBoundary.classify(exc)
        self._loop._state.record_error(f"daemon.crash.{category}: {exc}")

        if category in (CrashCategory.RECOVERABLE, CrashCategory.INTERNAL_RUNTIME):
            self._transition(LifecycleState.RECOVERING)
            self._recovery_count += 1
            try:
                self._loop._recovery_coordinator.recover(self._loop)
                self._transition(LifecycleState.RUNNING)
            except Exception as recovery_exc:
                self._loop._state.record_error(f"daemon.recovery_failed: {recovery_exc}")
                self._transition(LifecycleState.SHUTDOWN)
        else:
            self._transition(LifecycleState.SHUTDOWN)

    def _transition(self, to: LifecycleState) -> None:
        LifecycleTransition.assert_transition(self._lifecycle, to)
        self._lifecycle = to

    def _assert_current(self, expected: LifecycleState) -> None:
        if self._lifecycle != expected:
            raise InvalidLifecycleTransition(self._lifecycle, expected)

    @property
    def status(self) -> RuntimeStatus:
        s = self._loop.state
        return RuntimeStatus(
            lifecycle_state=self._lifecycle,
            uptime_seconds=time.time() - (self._started_at or time.time()),
            cycle_count=s.total_events_processed,
            last_heartbeat_at=self._heartbeat.last_heartbeat_at,
            last_heartbeat_skew_ms=self._heartbeat.last_skew_ms,
            panic_count=self._panic_count,
            recovery_count=self._recovery_count,
            health_status=s.health_status,
            consecutive_failures=s.consecutive_failures,
            last_error=s.last_error,
        )

    @property
    def lifecycle(self) -> LifecycleState:
        return self._lifecycle

    @property
    def loop(self) -> RuntimeLoop:
        return self._loop
