from dataclasses import dataclass, field
from enum import Enum
from typing import List

from .epoch_metrics import VelocityMetrics


class PanicType(Enum):
    OSCILLATION_EXPLOSION = "oscillation_explosion"
    ENTROPY_RUNAWAY = "entropy_runaway"
    RECOVERY_AMPLIFICATION = "recovery_amplification"
    REPLAY_DIVERGENCE_CASCADE = "replay_divergence_cascade"
    TELEMETRY_OVERHEAD = "telemetry_overhead"


@dataclass
class PanicEvent:
    panic_type: PanicType
    cycle: int
    value: float
    threshold: float
    phase: str


@dataclass
class PanicConfig:
    oscillation_explosion_threshold: float = 0.1
    entropy_runaway_threshold: float = 0.01
    recovery_amplification_threshold: float = 5.0
    replay_divergence_threshold: float = 0.1
    telemetry_memory_ratio_threshold: float = 0.05


class PanicDetector:
    MAX_EVENTS = 1000

    def __init__(self, config: PanicConfig = None):
        self._config = config or PanicConfig()
        self._events: List[PanicEvent] = []

    @property
    def events(self) -> List[PanicEvent]:
        return list(self._events)

    @property
    def has_panics(self) -> bool:
        return len(self._events) > 0

    def _prune_events(self) -> None:
        while len(self._events) > self.MAX_EVENTS:
            self._events.pop(0)

    def check(self, metrics: VelocityMetrics, cycle: int, phase: str) -> List[PanicEvent]:
        new_events: List[PanicEvent] = []
        if abs(metrics.governance_oscillation_velocity) > self._config.oscillation_explosion_threshold:
            ev = PanicEvent(
                PanicType.OSCILLATION_EXPLOSION, cycle,
                abs(metrics.governance_oscillation_velocity),
                self._config.oscillation_explosion_threshold, phase,
            )
            self._events.append(ev)
            new_events.append(ev)
        if abs(metrics.entropy_velocity) > self._config.entropy_runaway_threshold:
            ev = PanicEvent(
                PanicType.ENTROPY_RUNAWAY, cycle,
                metrics.entropy_velocity,
                self._config.entropy_runaway_threshold, phase,
            )
            self._events.append(ev)
            new_events.append(ev)
        if metrics.recovery_latency_slope > self._config.recovery_amplification_threshold:
            ev = PanicEvent(
                PanicType.RECOVERY_AMPLIFICATION, cycle,
                metrics.recovery_latency_slope,
                self._config.recovery_amplification_threshold, phase,
            )
            self._events.append(ev)
            new_events.append(ev)
        if metrics.replay_divergence_velocity > self._config.replay_divergence_threshold:
            ev = PanicEvent(
                PanicType.REPLAY_DIVERGENCE_CASCADE, cycle,
                metrics.replay_divergence_velocity,
                self._config.replay_divergence_threshold, phase,
            )
            self._events.append(ev)
            new_events.append(ev)
        self._prune_events()
        return new_events
