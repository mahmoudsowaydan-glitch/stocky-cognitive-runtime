"""governance_state_model.py — Frozen representation of system governance.

Captures the active thresholds, weights, and tolerances that define
how the system interprets its own behavior.
"""

from dataclasses import dataclass, field
from typing import Dict


@dataclass(frozen=True)
class GovernanceState:
    version: str
    policy_weights: Dict[str, float] = field(default_factory=dict)
    threshold_map: Dict[str, float] = field(default_factory=dict)
    drift_tolerance: float = 0.1
    confidence_threshold: float = 0.7
    stability_threshold: float = 0.7
