import os
import random
import tempfile
import time
import uuid
from typing import Any, Dict, List, Optional

from ..contracts.causal_graph import CausalGraph, CausalGraphBuilder
from ..contracts.execution_trace import ExecutionTrace
from ..confidence.runtime_confidence import RuntimeConfidenceEngine
from ..governance.governance_engine import GovernanceEngine
from ..intelligence.compression_engine import CompressionEngine
from ..liveness.liveness_monitor import LivenessMonitor
from ..recovery.delta_checkpoint import DeltaCheckpointManager
from ..runtime.coherence_monitor import CoherenceMonitor
from ..runtime.runtime_state import RuntimeState
from ..stability.stability_analyzer import StabilityAnalyzer
from ..telemetry.telemetry_probe import TelemetryProbe
from ..telemetry.telemetry_snapshot import TelemetrySnapshot
from .event_generator import EventGenerator, EventProfile


class BenchmarkRuntime:
    def __init__(
        self,
        seed: int = 42,
        capture_interval: int = 100,
        event_generator: Optional[EventGenerator] = None,
    ):
        self._cycle_count = 0
        self._seed = seed
        self._rng = random.Random(seed)
        self._traces: List[ExecutionTrace] = []
        self._causal_graph = CausalGraph({}, [])
        self._graph_builder = CausalGraphBuilder()

        self._event_generator = event_generator or EventGenerator(seed=seed, rng=self._rng)

        cdir = tempfile.mkdtemp(prefix="epoch_ckpt_")
        self._ckpt_mgr = DeltaCheckpointManager(
            checkpoint_dir=cdir, base_interval=500,
            delta_interval=100, max_bases=3,
        )

        self._compression = CompressionEngine()
        self._stability = StabilityAnalyzer(self._compression.store)
        self._confidence = RuntimeConfidenceEngine()
        self._coherence = CoherenceMonitor()
        self._governance = GovernanceEngine()

        self._state = RuntimeState()
        self._state.status = "running"
        self._state.total_events_processed = 0

        self._liveness = LivenessMonitor()
        for _ in range(100):
            self._liveness.on_cycle_start(time.time())
            self._liveness.on_cycle_end(time.time() + 0.001)

        self._telemetry = TelemetryProbe(
            store=None, capture_interval=capture_interval,
        )

    @property
    def governance(self) -> GovernanceEngine:
        return self._governance

    @property
    def stability(self) -> StabilityAnalyzer:
        return self._stability

    @property
    def confidence(self) -> RuntimeConfidenceEngine:
        return self._confidence

    @property
    def coherence(self) -> CoherenceMonitor:
        return self._coherence

    @property
    def causal_graph(self) -> CausalGraph:
        return self._causal_graph

    @property
    def compression(self) -> CompressionEngine:
        return self._compression

    @property
    def state(self) -> RuntimeState:
        return self._state

    @property
    def liveness(self) -> LivenessMonitor:
        return self._liveness

    @property
    def traces(self) -> List[ExecutionTrace]:
        return list(self._traces)

    @property
    def telemetry(self) -> TelemetryProbe:
        return self._telemetry

    @property
    def cycle_count(self) -> int:
        return self._cycle_count

    @property
    def event_generator(self) -> EventGenerator:
        return self._event_generator

    @property
    def _checkpoint_manager(self) -> DeltaCheckpointManager:
        return self._ckpt_mgr

    def cycle(self, rng: Optional[random.Random] = None) -> Optional[TelemetrySnapshot]:
        r = rng or self._rng
        self._cycle_count += 1
        self._state.total_events_processed = self._cycle_count

        ts = time.time()
        self._liveness.on_cycle_start(ts)

        profiles = self._event_generator.generate(self._cycle_count)
        for profile in profiles:
            trace = self._profile_to_trace(profile)
            self._traces.append(trace)
            self._coherence.check_trace(trace)

        if self._cycle_count % 50 == 0 and self._traces:
            self._build_causal_graph()
            self._process_intelligence()

        if self._cycle_count % 10 == 0:
            self._assess(r)

        if self._cycle_count % 100 == 0:
            self._save_checkpoint()

        self._state.average_cycle_ms = 0.5 + r.random() * 2.0
        self._state.last_cycle_ms = 0.3 + r.random() * 3.0
        self._state.queue_depth = r.randint(0, 5)

        mid = ts + 0.001
        self._liveness.on_cycle_end(mid)

        return self._telemetry.capture(self)

    def stop(self) -> None:
        self._state.status = "stopped"

    def _profile_to_trace(self, profile: EventProfile) -> ExecutionTrace:
        return ExecutionTrace(
            event_id=str(uuid.uuid4()),
            session_id="bench",
            sequence_no=self._cycle_count,
            preflight_valid=profile.preflight_valid,
            preflight_reason=profile.preflight_reason,
            p4_verdict=profile.p4_verdict,
            p4_reason=profile.p4_reason,
            p4_rule_triggered=profile.p4_rule_triggered,
            execution_status=profile.execution_status,
            execution_error=profile.execution_error,
            risk_score=profile.risk_score,
            capabilities_checked=profile.capabilities_checked,
            total_time=round(0.5 + self._rng.random() * 5.0, 2),
            final_status=profile.final_status,
        )

    def _build_causal_graph(self) -> None:
        try:
            window_size = min(50, len(self._traces))
            window = self._traces[-window_size:] if window_size > 0 else []
            self._causal_graph = self._graph_builder.build(window)
        except Exception:
            pass

    def _process_intelligence(self) -> None:
        try:
            window_size = min(50, len(self._traces))
            window = self._traces[-window_size:] if window_size > 0 else []
            self._compression.process(self._causal_graph, window)
        except Exception:
            pass

    def _assess(self, rng: random.Random) -> None:
        window = self._traces[-50:] if self._traces else []
        if self._cycle_count >= 10:
            self._governance.assess(
                traces=window,
                state=self._state,
                graph=self._causal_graph,
                store=self._compression.store,
                coherence=self._coherence,
                stability=self._stability,
                confidence=self._confidence,
            )
            self._stability.analyze(
                traces=window,
                state=self._state,
                graph=self._causal_graph,
            )
        if self._cycle_count % 75 == 0:
            self._confidence.assess(
                traces=window,
                state=self._state,
                queue_snapshot={"depth": self._state.queue_depth},
                stability_snapshot=self._stability.score_history[-1] if self._stability.score_history else None,
            )

    def _save_checkpoint(self) -> None:
        try:
            self._ckpt_mgr.create(
                traces=self._traces[-100:],
                state=self._state,
                causal_graph=self._causal_graph,
                governance=self._governance,
            )
        except Exception:
            pass

    @staticmethod
    def factory(seed: int = 42, capture_interval: int = 100) -> "BenchmarkRuntime":
        return BenchmarkRuntime(seed=seed, capture_interval=capture_interval)
