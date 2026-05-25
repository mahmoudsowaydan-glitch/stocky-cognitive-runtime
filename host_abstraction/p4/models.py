from dataclasses import dataclass
from enum import Enum


class PolicyVerdict(str, Enum):
    ALLOW = "ALLOW"
    BLOCK = "BLOCK"
    DEFER = "DEFER"
    REVIEW = "REVIEW"


class PolicyRiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


@dataclass
class PolicyResult:
    final_verdict: PolicyVerdict
    risk_score: float
    rule_triggered: str
    reason: str
    override_bridge: bool
