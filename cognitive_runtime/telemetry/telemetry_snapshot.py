from dataclasses import dataclass, field
from typing import List


@dataclass
class TelemetrySnapshot:
    cycle_no: int
    governance_score: float
    entropy_score: float
    drift_score: float
    stability_score: float
    confidence_score: float
    entropy_velocity: float
    governance_oscillation_count: int
    confidence_hysteresis: float
    causal_density: float
    await_amplification: float
    checkpoint_size_kb: float
    pending_tasks: int
    is_stalled: bool
    health_status: str


@dataclass
class WarmAggregate:
    cycle_range: tuple
    count: int
    mean_governance: float
    mean_stability: float
    mean_confidence: float
    mean_entropy: float
    mean_drift: float
    mean_entropy_velocity: float
    mean_await_amplification: float
    mean_causal_density: float
    std_entropy: float
    std_stability: float
    trend_governance: float
    trend_stability: float
    trend_confidence: float
    min_health: str
    max_pending: int
    total_checkpoint_growth_kb: float
    total_stalls: int


@dataclass
class PhysiologySummary:
    entropy_slope: float
    memory_plateau: bool
    recovery_cost_stable: bool
    governance_stable: bool
    confidence_stable: bool
    stability_stable: bool
    stall_free_streak: int
    cycle_count: int
