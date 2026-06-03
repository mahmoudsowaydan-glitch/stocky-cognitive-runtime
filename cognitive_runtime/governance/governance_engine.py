from typing import Any, Dict, List, Optional

from ..contracts.causal_graph import CausalGraph
from ..contracts.execution_trace import ExecutionTrace
from ..runtime.coherence_monitor import CoherenceMonitor
from ..runtime.runtime_state import RuntimeState
from ..stability.stability_analyzer import StabilityAnalyzer
from ..confidence.runtime_confidence import RuntimeConfidenceEngine
from ..intelligence.intelligence_store import IntelligenceStore
from .architectural_decay import ArchitecturalDecay
from .doctrine_drift import DoctrineDrift
from .entropy_index import EntropyIndex
from .governance_pressure import GovernancePressure
from .governance_report import DecaySignal, GovernanceReport


class GovernanceEngine:
    def __init__(self):
        self._entropy_index = EntropyIndex()
        self._doctrine_drift = DoctrineDrift()
        self._pressure = GovernancePressure()
        self._decay = ArchitecturalDecay()
        self._score_history: List[float] = []

    def assess(self, traces: List[ExecutionTrace],
               state: RuntimeState,
               graph: CausalGraph,
               store: IntelligenceStore,
               coherence: CoherenceMonitor,
               stability: StabilityAnalyzer,
               confidence: Optional[RuntimeConfidenceEngine] = None
               ) -> GovernanceReport:
        entropy = self._entropy_index.analyze(traces, graph, store)
        drift = self._doctrine_drift.analyze(traces, coherence.history)
        pressure = self._pressure.analyze(traces)
        decay = self._decay.analyze(traces, entropy, stability, confidence)

        raw_score = (
            0.35 * entropy.overall
            + 0.30 * drift.overall
            + 0.25 * pressure.overall
            + 0.10 * min(1.0, sum(d.severity for d in decay) / max(1, len(decay)))
        )
        score = round(min(1.0, raw_score), 4)

        self._score_history.append(score)
        if len(self._score_history) > 20:
            self._score_history.pop(0)

        trend = self._detect_trend()
        status = self._classify_status(entropy.overall, drift.overall,
                                       pressure.overall, decay)

        return GovernanceReport(
            entropy=entropy,
            drift=drift,
            pressure=pressure,
            decay_signals=decay,
            governance_status=status,
            score=score,
            trend_direction=trend["direction"],
            trend_delta=trend["delta"],
        )

    def _classify_status(self, entropy: float, drift: float,
                         pressure: float, decay: List[DecaySignal]) -> str:
        max_decay = max([s.severity for s in decay]) if decay else 0.0
        worst = max(entropy, drift, pressure, max_decay)

        if worst >= 0.7:
            return "CRITICAL"
        elif worst >= 0.5:
            return "ELEVATED"
        elif worst >= 0.3:
            return "MONITORING"
        else:
            return "NOMINAL"

    def _detect_trend(self) -> Dict[str, float]:
        if len(self._score_history) < 2:
            return {"direction": "stable", "delta": 0.0}

        recent = self._score_history[-min(10, len(self._score_history)):]
        mid = len(recent) // 2
        avg_first = sum(recent[:mid]) / mid
        avg_second = sum(recent[mid:]) / (len(recent) - mid)
        delta = avg_second - avg_first

        if abs(delta) < 0.02:
            return {"direction": "stable", "delta": round(delta, 4)}
        elif delta > 0:
            return {"direction": "worsening", "delta": round(delta, 4)}
        else:
            return {"direction": "improving", "delta": round(delta, 4)}

    @property
    def score_history(self) -> List[float]:
        return list(self._score_history)
