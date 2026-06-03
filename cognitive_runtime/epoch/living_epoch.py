import random
from typing import Any, Callable, Dict, List, Optional, Tuple

from ..telemetry.telemetry_probe import NullTelemetryProbe, TelemetryProbe
from ..telemetry.telemetry_snapshot import TelemetrySnapshot
from ..telemetry.telemetry_store import TelemetryStore
from .benchmark_runtime import BenchmarkRuntime
from .epoch_metrics import VelocityMetrics, VelocityTracker
from .epoch_report import (
    EpochReport,
    PhaseSnapshot,
    Postmortem,
    ReplayIntegrityReport,
)
from .epoch_seed import EpochSeed
from .epoch_state import EpochPhase, PHASE_TRANSITIONS
from .event_generator import EventGenerator
from .panic_detector import PanicConfig, PanicDetector, PanicEvent, PanicType


DEFAULT_RUNTIME_FACTORY: Callable[[], Any] = lambda: BenchmarkRuntime(
    seed=42, capture_interval=100,
)


class LivingEpoch:
    def __init__(
        self,
        seed: int,
        runtime_factory: Callable[[], Any] = DEFAULT_RUNTIME_FACTORY,
        telemetry_store: Optional[TelemetryStore] = None,
        panic_config: Optional[PanicConfig] = None,
        capture_interval: int = 100,
        phase_cycle_limits: Optional[Dict[EpochPhase, int]] = None,
        enable_chaos: bool = True,
        replay_challenge_mode: str = "none",
    ):
        self._seed = EpochSeed(seed)
        self._runtime_factory = runtime_factory
        self._replay_challenge_mode = replay_challenge_mode
        self._store = telemetry_store or TelemetryStore()
        self._probe = TelemetryProbe(store=self._store, capture_interval=capture_interval)
        self._tracker = VelocityTracker()
        self._detector = PanicDetector(panic_config)
        self._limits = phase_cycle_limits or {
            EpochPhase.WARMUP: 500,
            EpochPhase.STABILIZATION: 1000,
            EpochPhase.CHAOS: 2000,
            EpochPhase.RECOVERY: 500,
            EpochPhase.OBSERVATION: 3000,
            EpochPhase.SHUTDOWN: 100,
            EpochPhase.RECOVERY_BOOT: 200,
            EpochPhase.REPLAY_VALIDATION: 200,
        }
        self._enable_chaos = enable_chaos
        self._phase_snapshots: List[PhaseSnapshot] = []
        self._phase_start_cycle: Dict[EpochPhase, int] = {}
        self._cycle_count = 0
        self._aborted = False
        self._replay_divergence_count = 0

    @property
    def seed(self) -> EpochSeed:
        return self._seed

    @property
    def store(self) -> TelemetryStore:
        return self._store

    @property
    def cycle_count(self) -> int:
        return self._cycle_count

    def abort(self) -> None:
        self._aborted = True

    def run(self) -> EpochReport:
        try:
            return self._run_phases()
        except Exception as e:
            return EpochReport(
                seed=self._seed.value,
                passed=False,
                message=f"Epoch crashed: {e}",
            )

    def _run_phases(self) -> EpochReport:
        phases = [
            EpochPhase.WARMUP,
            EpochPhase.STABILIZATION,
        ]
        if self._enable_chaos:
            phases.append(EpochPhase.CHAOS)
            phases.append(EpochPhase.RECOVERY)
        phases.append(EpochPhase.OBSERVATION)
        phases.append(EpochPhase.SHUTDOWN)
        phases.append(EpochPhase.RECOVERY_BOOT)
        phases.append(EpochPhase.REPLAY_VALIDATION)

        runtime = self._runtime_factory()
        self._runtime = runtime
        self._sync_probe(runtime)

        for phase in phases:
            if self._aborted:
                break
            self._phase_start_cycle[phase] = self._cycle_count
            limit = self._limits.get(phase, 500)

            if phase == EpochPhase.RECOVERY_BOOT:
                self._run_recovery_boot(runtime)
            elif phase == EpochPhase.REPLAY_VALIDATION:
                self._run_replay_validation(limit)
            else:
                self._run_phase(runtime, phase, limit)

            snap = self._take_phase_snapshot(runtime, phase)
            self._phase_snapshots.append(snap)

        runtime.stop()
        postmortem = self._build_postmortem()
        passed = self._evaluate_pass_fail(postmortem)
        return EpochReport(
            seed=self._seed.value,
            passed=passed,
            message=self._build_message(passed, postmortem),
            postmortem=postmortem,
        )

    def _sync_probe(self, runtime: Any) -> None:
        if hasattr(runtime, "_telemetry"):
            runtime._telemetry = self._probe

    def _run_phase(self, runtime: Any, phase: EpochPhase, limit: int) -> None:
        phase_cycle = 0
        cycle_delta = 0

        phase_index = list(EpochPhase).index(phase)
        rng = random.Random(self._seed.chaos_seed + phase_index)

        while phase_cycle < limit and not self._aborted:
            self._cycle_count += 1
            phase_cycle += 1
            cycle_delta += 1

            # push mock events for backward compat
            event = self._produce_event(rng, phase)
            if event is not None and hasattr(runtime, "_queue"):
                runtime._queue.push(event)

            if phase == EpochPhase.CHAOS and self._enable_chaos:
                self._inject_chaos(rng, runtime, cycle_delta)

            # advance real runtime state
            if hasattr(runtime, "cycle"):
                runtime.cycle(rng)
            # sync cycle state for probe extraction (mock runtimes)
            runtime._cycle_count = self._cycle_count
            if hasattr(runtime, "state"):
                runtime.state.total_events_processed = self._cycle_count

            if phase_cycle % 100 == 0:
                fc = getattr(runtime, "_finalize_cycle", None)
                if fc is not None:
                    fc(None)

            snap = self._probe.capture(runtime)
            if snap is not None:
                self._tracker.record_snapshot(snap)
                self._check_panics(snap, phase)

    def _run_recovery_boot(self, runtime: Any) -> None:
        limit = self._limits.get(EpochPhase.RECOVERY_BOOT, 200)
        phase_index = list(EpochPhase).index(EpochPhase.RECOVERY_BOOT)
        rng = random.Random(self._seed.chaos_seed + phase_index)

        fresh = self._runtime_factory()
        self._sync_probe(fresh)

        for i in range(min(limit, 50)):
            if self._aborted:
                break
            self._cycle_count += 1
            if hasattr(fresh, "cycle") and isinstance(fresh, BenchmarkRuntime):
                snap = fresh.cycle(rng)
                if isinstance(snap, TelemetrySnapshot):
                    self._tracker.record_snapshot(snap)

        fresh.stop()

    def _run_replay_validation(self, limit: int) -> None:
        phase_index = list(EpochPhase).index(EpochPhase.REPLAY_VALIDATION)
        base_rng = random.Random(self._seed.chaos_seed + phase_index)
        replay_seed = base_rng.randint(0, 2**31)

        ref = self._runtime_factory()
        sub = self._build_replay_challenge_runtime()
        # Use independent probes so each runtime captures at its own cadence
        ref._telemetry = TelemetryProbe(store=self._store, capture_interval=50)
        sub._telemetry = TelemetryProbe(store=self._store, capture_interval=50)

        if not isinstance(ref, BenchmarkRuntime) or not isinstance(sub, BenchmarkRuntime):
            ref.stop()
            sub.stop()
            return

        n = min(limit, 100)
        ref_traces: List[float] = []
        sub_traces: List[float] = []

        for i in range(n):
            if self._aborted:
                break
            rng = random.Random(replay_seed + i)
            self._cycle_count += 1

            rsnap = ref.cycle(rng)
            ssnap = sub.cycle(rng)
            if isinstance(rsnap, TelemetrySnapshot) and isinstance(ssnap, TelemetrySnapshot):
                ref_traces.append(rsnap.entropy_score)
                sub_traces.append(ssnap.entropy_score)
                pair_div = abs(rsnap.entropy_score - ssnap.entropy_score)
                self._tracker.record_replay_divergence(int(pair_div * 1000))

        ref.stop()
        sub.stop()

    def _build_replay_challenge_runtime(self):
        sub = self._runtime_factory()
        if self._replay_challenge_mode == "none":
            return sub
        if self._replay_challenge_mode == "seed_offset":
            offset_seed = self._seed.value + 1
            if hasattr(sub, '_seed'):
                sub._seed = offset_seed
            if hasattr(sub, '_rng'):
                sub._rng = random.Random(offset_seed)
            if hasattr(sub, '_event_generator'):
                sub._event_generator = EventGenerator(seed=offset_seed, rng=sub._rng)
        return sub

    def _produce_event(self, rng: random.Random, phase: EpochPhase) -> Any:
        class _MockEvent:
            def __init__(self, eid: str):
                self.event_id = eid
                self.session_id = "epoch"
        if rng.random() < 0.1:
            return _MockEvent(f"epoch-{self._cycle_count}")
        return None

    def _inject_chaos(self, rng: random.Random, runtime: Any, delta: int) -> None:
        if rng.random() > 0.05:
            return
        cm = getattr(runtime, "_checkpoint_manager", None)
        if cm is None:
            return
        if rng.random() < 0.3:
            pass

    def _check_panics(self, snap: TelemetrySnapshot, phase: EpochPhase) -> None:
        metrics = self._tracker.compute()
        panics = self._detector.check(metrics, snap.cycle_no, phase.name)
        for p in panics:
            if p.panic_type in (PanicType.ENTROPY_RUNAWAY, PanicType.OSCILLATION_EXPLOSION):
                self.abort()

    def _take_phase_snapshot(self, runtime: Any, phase: EpochPhase) -> PhaseSnapshot:
        metrics = self._tracker.compute()
        phys = self._store.get_physiology() if self._store.capture_count > 0 else None
        return PhaseSnapshot(
            phase=phase,
            cycle=self._cycle_count,
            metrics=metrics,
            physiology=phys,
        )

    def _build_postmortem(self) -> Postmortem:
        return Postmortem(
            cycle_count=self._cycle_count,
            telemetry_captures=self._store.capture_count,
            panics=self._detector.events,
            phase_snapshots=self._phase_snapshots,
            final_physiology=self._store.get_physiology() if self._store.capture_count > 0 else None,
            replay_report=ReplayIntegrityReport(
                divergence_velocity=self._tracker.compute().replay_divergence_velocity,
            ),
        )

    def _evaluate_pass_fail(self, pm: Postmortem) -> bool:
        if self._aborted:
            return False
        if len(pm.panics) > 0:
            abort_panics = [p for p in pm.panics
                            if p.panic_type in (PanicType.ENTROPY_RUNAWAY,
                                                PanicType.OSCILLATION_EXPLOSION)]
            if abort_panics:
                return False
        return True

    def _build_message(self, passed: bool, pm: Postmortem) -> str:
        if self._aborted:
            return f"EPOCH_ABORTED: {len(pm.panics)} panics at cycle {self._cycle_count}"
        if not passed:
            return f"EPOCH_FAILED: {len(pm.panics)} panics, replay={pm.replay_report.passed if pm.replay_report else 'N/A'}"
        return (
            f"EPOCH_PASSED: {self._cycle_count} cycles, "
            f"{pm.telemetry_captures} captures, "
            f"{len(pm.panics)} non-critical panics, "
            f"replay={pm.replay_report.passed if pm.replay_report else 'N/A'}"
        )
