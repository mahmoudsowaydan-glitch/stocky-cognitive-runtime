from dataclasses import dataclass, field
from typing import List, Optional

from ..telemetry.telemetry_snapshot import TelemetrySnapshot


@dataclass
class VelocityMetrics:
    entropy_velocity: float = 0.0
    governance_oscillation_velocity: float = 0.0
    confidence_drift_velocity: float = 0.0
    replay_divergence_velocity: float = 0.0
    recovery_latency_slope: float = 0.0

    def all_stable(self, epsilon: float = 0.001) -> bool:
        return (
            abs(self.entropy_velocity) < epsilon
            and abs(self.governance_oscillation_velocity) < epsilon
            and abs(self.confidence_drift_velocity) < epsilon
            and abs(self.replay_divergence_velocity) < epsilon
            and abs(self.recovery_latency_slope) < epsilon
        )


class VelocityTracker:
    def __init__(self, window_size: int = 20):
        self._snapshots: List[TelemetrySnapshot] = []
        self._window_size = window_size
        self._replay_diverge_history: List[int] = []
        self._recovery_latency_history: List[float] = []

    def record_snapshot(self, snap: TelemetrySnapshot) -> None:
        self._snapshots.append(snap)
        if len(self._snapshots) > self._window_size:
            self._snapshots.pop(0)

    def record_replay_divergence(self, count: int) -> None:
        self._replay_diverge_history.append(count)
        if len(self._replay_diverge_history) > self._window_size:
            self._replay_diverge_history.pop(0)

    def record_recovery_latency(self, ms: float) -> None:
        self._recovery_latency_history.append(ms)
        if len(self._recovery_latency_history) > self._window_size:
            self._recovery_latency_history.pop(0)

    def compute(self) -> VelocityMetrics:
        metrics = VelocityMetrics()
        if len(self._snapshots) >= 2:
            first = self._snapshots[0]
            last = self._snapshots[-1]
            d_cycle = last.cycle_no - first.cycle_no
            if d_cycle > 0:
                metrics.entropy_velocity = (
                    last.entropy_score - first.entropy_score
                ) / d_cycle
                metrics.governance_oscillation_velocity = (
                    last.governance_oscillation_count
                    - first.governance_oscillation_count
                ) / d_cycle
                metrics.confidence_drift_velocity = (
                    last.confidence_score - first.confidence_score
                ) / d_cycle
        if len(self._replay_diverge_history) >= 2:
            d = (self._replay_diverge_history[-1] - self._replay_diverge_history[0])
            metrics.replay_divergence_velocity = d / max(1, len(self._replay_diverge_history))
        if len(self._recovery_latency_history) >= 2:
            slope = (self._recovery_latency_history[-1] - self._recovery_latency_history[0])
            metrics.recovery_latency_slope = slope / max(1, len(self._recovery_latency_history))
        return metrics
