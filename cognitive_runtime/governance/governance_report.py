from dataclasses import dataclass, field
from typing import List


@dataclass
class EntropyMetrics:
    causal_density: float
    pattern_explosion: float
    trace_inflation: float
    graph_branching: float
    overall: float


@dataclass
class DriftMetrics:
    preflight_overreach: float
    p4_avoidance: float
    risk_influence: float
    coherence_drift_rate: float
    overall: float


@dataclass
class PressureMetrics:
    rule_conflict_rate: float
    p4_overload_rate: float
    ambiguity_rate: float
    escalation_rate: float
    overall: float


@dataclass
class DecaySignal:
    signal_type: str
    severity: float
    description: str


@dataclass
class GovernanceReport:
    entropy: EntropyMetrics
    drift: DriftMetrics
    pressure: PressureMetrics
    decay_signals: List[DecaySignal]
    governance_status: str
    score: float
    trend_direction: str
    trend_delta: float
