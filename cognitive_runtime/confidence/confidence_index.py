from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional


class ExecutionConfidenceGradient(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    CRITICAL = "CRITICAL"


@dataclass
class DecisionCertainty:
    risk_proximity: float
    verdict_clarity: float
    rule_conflict_density: float
    overall: float


@dataclass
class OperationalReadiness:
    queue_health: float
    processing_health: float
    latency_health: float
    backpressure_ratio: float
    overall: float


@dataclass
class RuntimeConfidenceScore:
    decision_confidence: float
    operational_confidence: float
    execution_confidence: float
    overall: float
    gradient: ExecutionConfidenceGradient


@dataclass
class ConfidenceReport:
    score: RuntimeConfidenceScore
    gradient: ExecutionConfidenceGradient
    referenced_stability_snapshot: Optional[float]
    trend_direction: str
    trend_delta: float
    degradation_detected: bool
