from typing import List, Optional

from ..contracts.execution_trace import ExecutionTrace
from ..stability.stability_analyzer import StabilityAnalyzer
from ..confidence.runtime_confidence import RuntimeConfidenceEngine
from .governance_report import DecaySignal, EntropyMetrics


class ArchitecturalDecay:
    def analyze(self, traces: List[ExecutionTrace],
                entropy: EntropyMetrics,
                stability_analyzer: StabilityAnalyzer,
                confidence_engine: Optional[RuntimeConfidenceEngine] = None
                ) -> List[DecaySignal]:
        signals: List[DecaySignal] = []

        if len(traces) < 10:
            return signals

        # 1. Cyclic causal chains
        cyclic = self._detect_cyclic_chains(traces)
        if cyclic > 0:
            signals.append(DecaySignal(
                signal_type="cyclic_causal_chains",
                severity=min(1.0, cyclic / 10.0),
                description=f"{cyclic} repeated causal chain patterns detected",
            ))

        # 2. Entropy acceleration
        if hasattr(stability_analyzer, '_score_history'):
            history = stability_analyzer._score_history
            if len(history) >= 4:
                accel = self._detect_entropy_acceleration(entropy, history)
                if accel > 0:
                    signals.append(DecaySignal(
                        signal_type="entropy_acceleration",
                        severity=min(1.0, accel),
                        description="Entropy increasing while stability declining",
                    ))

        # 3. Confidence degradation correlation
        if confidence_engine is not None:
            conf_history = confidence_engine._score_history
            if len(conf_history) >= 6:
                corr = self._detect_confidence_correlation(entropy, conf_history)
                if corr > 0:
                    signals.append(DecaySignal(
                        signal_type="confidence_entropy_divergence",
                        severity=min(1.0, corr),
                        description="Confidence declining as entropy rises",
                    ))

        # 4. Unstable pattern emergence
        unstable = self._detect_unstable_patterns(traces, entropy)
        if unstable > 0:
            signals.append(DecaySignal(
                signal_type="unstable_pattern_emergence",
                severity=min(1.0, unstable),
                description="High pattern novelty combined with entropy growth",
            ))

        return signals

    def _detect_cyclic_chains(self, traces: List[ExecutionTrace]) -> float:
        final_statuses = [t.final_status for t in traces]
        freq: dict = {}
        for s in final_statuses:
            freq[s] = freq.get(s, 0) + 1
        repeats = sum(1 for v in freq.values() if v > 2)
        return min(1.0, repeats / max(1, len(freq)))

    def _detect_entropy_acceleration(self, entropy: EntropyMetrics,
                                     stability_history: List[float]) -> float:
        recent_stab = stability_history[-min(4, len(stability_history)):]
        if len(recent_stab) < 2:
            return 0.0
        stability_delta = recent_stab[-1] - recent_stab[0]
        if stability_delta < -0.05 and entropy.overall > 0.3:
            return abs(stability_delta) * entropy.overall
        return 0.0

    def _detect_confidence_correlation(self, entropy: EntropyMetrics,
                                       conf_history: List[float]) -> float:
        recent_conf = conf_history[-min(6, len(conf_history)):]
        if len(recent_conf) < 2:
            return 0.0
        conf_delta = recent_conf[-1] - recent_conf[0]
        if conf_delta < -0.05 and entropy.overall > 0.3:
            return abs(conf_delta) * entropy.overall
        return 0.0

    def _detect_unstable_patterns(self, traces: List[ExecutionTrace],
                                  entropy: EntropyMetrics) -> float:
        if entropy.pattern_explosion > 0.5 and entropy.trace_inflation > 0.2:
            return entropy.pattern_explosion * entropy.trace_inflation
        return 0.0
