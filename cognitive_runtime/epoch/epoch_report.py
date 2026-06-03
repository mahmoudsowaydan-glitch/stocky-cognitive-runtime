from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ..telemetry.telemetry_snapshot import PhysiologySummary, TelemetrySnapshot
from .epoch_metrics import VelocityMetrics
from .epoch_state import EpochPhase
from .panic_detector import PanicEvent


@dataclass
class ReplayIntegrityReport:
    divergence_velocity: float = 0.0
    hash_stability: float = 1.0
    deterministic_reconstruction_rate: float = 1.0
    causal_alignment_score: float = 1.0

    @property
    def passed(self) -> bool:
        return (
            abs(self.divergence_velocity) < 0.01
            and self.hash_stability > 0.95
            and self.deterministic_reconstruction_rate > 0.95
            and self.causal_alignment_score > 0.9
        )


@dataclass
class PhaseSnapshot:
    phase: EpochPhase
    cycle: int
    metrics: VelocityMetrics
    physiology: Optional[PhysiologySummary] = None


@dataclass
class Postmortem:
    cycle_count: int
    telemetry_captures: int
    panics: List[PanicEvent]
    phase_snapshots: List[PhaseSnapshot]
    final_physiology: Optional[PhysiologySummary]
    replay_report: Optional[ReplayIntegrityReport]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cycle_count": self.cycle_count,
            "telemetry_captures": self.telemetry_captures,
            "panics": [
                {"type": p.panic_type.value, "cycle": p.cycle,
                 "value": p.value, "threshold": p.threshold, "phase": p.phase}
                for p in self.panics
            ],
            "phases": [
                {"phase": ps.phase.value, "cycle": ps.cycle,
                 "entropy_velocity": ps.metrics.entropy_velocity}
                for ps in self.phase_snapshots
            ],
            "final_physiology": {
                "entropy_slope": self.final_physiology.entropy_slope if self.final_physiology else None,
                "memory_plateau": self.final_physiology.memory_plateau if self.final_physiology else None,
                "recovery_cost_stable": self.final_physiology.recovery_cost_stable if self.final_physiology else None,
                "stall_free_streak": self.final_physiology.stall_free_streak if self.final_physiology else 0,
            } if self.final_physiology else {},
            "replay": {
                "divergence_velocity": self.replay_report.divergence_velocity if self.replay_report else None,
                "hash_stability": self.replay_report.hash_stability if self.replay_report else None,
                "passed": self.replay_report.passed if self.replay_report else False,
            } if self.replay_report else {},
        }


@dataclass
class EpochReport:
    seed: int
    passed: bool
    message: str
    postmortem: Optional[Postmortem] = None
