import random
from typing import Any, List, Optional

from ..confidence.runtime_confidence import RuntimeConfidenceEngine
from ..contracts.causal_graph import CausalGraph
from ..contracts.execution_trace import ExecutionTrace
from ..governance.governance_engine import GovernanceEngine
from ..intelligence.intelligence_store import IntelligenceStore
from ..liveness.liveness_monitor import LivenessMonitor
from ..runtime.coherence_monitor import CoherenceMonitor
from ..runtime.runtime_state import RuntimeState
from ..stability.stability_analyzer import StabilityAnalyzer
from ..telemetry.telemetry_probe import TelemetryProbe
from ..telemetry.telemetry_snapshot import TelemetrySnapshot
from ..telemetry.telemetry_store import TelemetryStore
from .benchmark_runtime import BenchmarkRuntime


class ObserverRuntime:
    """Pure observer node — no event generation, no execution.
    
    Receives traces from an executor node and builds independent
    governance, stability, and confidence assessments from the
    same data. Measures Observer Drift: B's interpretation vs A's.
    """

    def __init__(
        self,
        node_id: str = "observer",
        capture_interval: int = 100,
    ):
        self._node_id = node_id
        self._cycle_count = 0
        self._traces: List[ExecutionTrace] = []

        self._store = IntelligenceStore()
        self._governance = GovernanceEngine()
        self._stability = StabilityAnalyzer(store=self._store)
        self._empty_graph = CausalGraph(nodes={}, edges=[])
        self._confidence = RuntimeConfidenceEngine()
        self._coherence = CoherenceMonitor()
        self._state = RuntimeState()
        self._state.status = "observing"
        self._state.total_events_processed = 0

        self._liveness = LivenessMonitor()
        for _ in range(100):
            self._liveness.on_cycle_start(0.0)
            self._liveness.on_cycle_end(0.001)

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

    @telemetry.setter
    def telemetry(self, value: TelemetryProbe) -> None:
        self._telemetry = value

    @property
    def cycle_count(self) -> int:
        return self._cycle_count

    @property
    def causal_graph(self) -> Any:
        return None

    @property
    def compression(self) -> Any:
        return None

    @property
    def event_generator(self) -> Any:
        return None

    @property
    def _checkpoint_manager(self) -> Any:
        return None

    def observe(self, traces: List[ExecutionTrace], rng: random.Random) -> Optional[TelemetrySnapshot]:
        """Receive and assess traces from executor. Returns capture snapshot."""
        self._cycle_count += 1
        self._traces = list(traces)
        self._state.total_events_processed = len(self._traces)

        ts = 0.0
        self._liveness.on_cycle_start(ts)

        for trace in self._traces:
            self._coherence.check_trace(trace)

        if len(self._traces) >= 10 and self._cycle_count % 5 == 0:
            window = self._traces[-50:] if self._traces else []
            self._governance.assess(
                traces=window,
                state=self._state,
                graph=self._empty_graph,
                store=self._store,
                coherence=self._coherence,
                stability=self._stability,
                confidence=self._confidence,
            )
            self._stability.analyze(
                traces=window, state=self._state, graph=self._empty_graph,
            )
            if self._cycle_count % 15 == 0:
                self._confidence.assess(
                    traces=window,
                    state=self._state,
                    queue_snapshot={"depth": 0},
                    stability_snapshot=(
                        self._stability.score_history[-1]
                        if self._stability.score_history else None
                    ),
                )

        mid = ts + 0.001
        self._liveness.on_cycle_end(mid)
        return self._telemetry.capture(self)

    def stop(self) -> None:
        self._state.status = "stopped"
