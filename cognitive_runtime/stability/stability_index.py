from dataclasses import dataclass
from typing import List


@dataclass
class StabilityWindow:
    window_id: str
    trace_count: int
    failure_rate: float
    drift_rate: float
    avg_cycle_ms: float
    cycle_time_std: float
    new_pattern_ratio: float
    pattern_repeat_rate: float
    recovery_speed: int


@dataclass
class StabilityScore:
    overall: float
    failure_score: float
    drift_score: float
    consistency_score: float
    timing_stability: float
    novelty_score: float
    system_regression_score: float


@dataclass
class StabilityTrend:
    direction: str
    delta: float
    window_count: int
    last_n_scores: List[float]


@dataclass
class StabilityReport:
    current_window: StabilityWindow
    score: StabilityScore
    trend: StabilityTrend
    anomalies: List[str]
