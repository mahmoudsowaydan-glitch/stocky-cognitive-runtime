from dataclasses import dataclass, field
from typing import Dict, List, Optional

import random

from .epoch_seed import EpochSeed


@dataclass
class EventProfile:
    event_type: str
    preflight_valid: bool = True
    p4_verdict: str = "ALLOW"
    execution_status: str = "SUCCESS"
    risk_score: float = 0.0
    p4_rule_triggered: Optional[str] = None
    capabilities_checked: List[str] = field(default_factory=list)
    execution_error: Optional[str] = None
    preflight_reason: Optional[str] = None
    p4_reason: Optional[str] = None
    final_status: str = ""


BASE_WEIGHTS: Dict[str, int] = {
    "NORMAL": 40,
    "HIGH_RISK": 10,
    "CONFLICT": 10,
    "RECOVERY": 8,
    "MIGRATION": 8,
    "ANOMALY": 8,
    "CHAOS": 8,
    "RESOURCE_PRESSURE": 8,
}


# Distribution schedules that shift as cycle_count progresses.
# Each entry: (max_cycle, weights_override)
# When cycle_count < max_cycle, that regime's weights apply.
# Schedules designed for mid-phase regime shifts so entropy velocity
# becomes measurable within a single epoch phase.
DISTRIBUTION_SCHEDULE: List[tuple] = [
    # WARMUP (0-500) — mostly normal, moderate anomaly
    (500, {
        "NORMAL": 55, "HIGH_RISK": 5, "CONFLICT": 5,
        "RECOVERY": 5, "MIGRATION": 5, "ANOMALY": 8,
        "CHAOS": 10, "RESOURCE_PRESSURE": 7,
    }),
    # STABILIZATION early (500-1000) — HIGH_RISK + MIGRATION spike
    (1000, {
        "NORMAL": 35, "HIGH_RISK": 15, "CONFLICT": 5,
        "RECOVERY": 5, "MIGRATION": 15, "ANOMALY": 5,
        "CHAOS": 10, "RESOURCE_PRESSURE": 10,
    }),
    # STABILIZATION late (1000-1500) — CONFLICT + RESOURCE_PRESSURE spike
    (1500, {
        "NORMAL": 35, "HIGH_RISK": 10, "CONFLICT": 15,
        "RECOVERY": 5, "MIGRATION": 5, "ANOMALY": 5,
        "CHAOS": 10, "RESOURCE_PRESSURE": 15,
    }),
    # CHAOS early (1500-2500) — CHAOS + ANOMALY spike
    (2500, {
        "NORMAL": 25, "HIGH_RISK": 10, "CONFLICT": 5,
        "RECOVERY": 5, "MIGRATION": 5, "ANOMALY": 15,
        "CHAOS": 25, "RESOURCE_PRESSURE": 10,
    }),
    # CHAOS late (2500-3500) — RESOURCE_PRESSURE + CONFLICT spike
    (3500, {
        "NORMAL": 30, "HIGH_RISK": 10, "CONFLICT": 15,
        "RECOVERY": 5, "MIGRATION": 5, "ANOMALY": 5,
        "CHAOS": 15, "RESOURCE_PRESSURE": 15,
    }),
    # RECOVERY (3500-4000) — RECOVERY heavy
    (4000, {
        "NORMAL": 30, "HIGH_RISK": 5, "CONFLICT": 5,
        "RECOVERY": 30, "MIGRATION": 5, "ANOMALY": 5,
        "CHAOS": 10, "RESOURCE_PRESSURE": 10,
    }),
    # OBSERVATION early (4000-6500) — mixed with CHAOS pressure
    (6500, {
        "NORMAL": 30, "HIGH_RISK": 10, "CONFLICT": 10,
        "RECOVERY": 10, "MIGRATION": 10, "ANOMALY": 8,
        "CHAOS": 12, "RESOURCE_PRESSURE": 10,
    }),
    # OBSERVATION late (6500+) — balanced, default weights
    (100000, {
        "NORMAL": 40, "HIGH_RISK": 10, "CONFLICT": 10,
        "RECOVERY": 8, "MIGRATION": 8, "ANOMALY": 8,
        "CHAOS": 8, "RESOURCE_PRESSURE": 8,
    }),
]


class EventGenerator:
    def __init__(
        self,
        seed: int,
        rng: Optional[random.Random] = None,
        weights: Optional[Dict[str, int]] = None,
        schedule: Optional[List[tuple]] = None,
    ):
        self._rng = rng or random.Random(seed)
        self._schedule = schedule or DISTRIBUTION_SCHEDULE
        self._base_weights = weights or BASE_WEIGHTS

        self._epoch_seed = EpochSeed(seed)
        self._event_rng = random.Random(self._epoch_seed.chaos_seed)
        self._consecutive_failures = 0

    def generate(self, cycle_count: int) -> List[EventProfile]:
        n_events = self._rng.randint(1, 3)
        profiles: List[EventProfile] = []

        weights = self._resolve_weights(cycle_count)
        type_list = list(weights.keys())
        weight_list = [weights[t] for t in type_list]

        for _ in range(n_events):
            etype = self._pick_type(type_list, weight_list)
            profile = self._build_profile(etype)
            profiles.append(profile)

            if etype == "CHAOS" or (etype == "HIGH_RISK" and profile.execution_status == "FAILED"):
                self._consecutive_failures += 1
            elif etype == "RECOVERY":
                self._consecutive_failures = 0

        return profiles

    def reset_consecutive_failures(self) -> None:
        self._consecutive_failures = 0

    def _resolve_weights(self, cycle_count: int) -> Dict[str, int]:
        for max_cycle, regime_weights in self._schedule:
            if cycle_count < max_cycle:
                return regime_weights
        return self._base_weights

    def _pick_type(self, type_list: List[str], weight_list: List[int]) -> str:
        if self._consecutive_failures >= 3 and self._rng.random() < 0.6:
            return "RECOVERY"
        return self._rng.choices(type_list, weights=weight_list, k=1)[0]

    def _build_profile(self, etype: str) -> EventProfile:
        r = self._event_rng

        if etype == "NORMAL":
            return EventProfile(
                event_type="NORMAL",
                preflight_valid=r.random() > 0.05,
                p4_verdict="ALLOW" if r.random() > 0.1 else "DENY",
                execution_status="SUCCESS" if r.random() > 0.03 else "FAILURE",
                risk_score=round(r.random() * 0.5, 4),
                p4_reason=None if r.random() > 0.1 else "standard_deny",
                execution_error=None,
                final_status="",
            )

        if etype == "HIGH_RISK":
            rs = round(0.70 + r.random() * 0.25, 4)
            return EventProfile(
                event_type="HIGH_RISK",
                preflight_valid=True,
                p4_verdict="ALLOW",
                execution_status="SUCCESS" if r.random() > 0.2 else "FAILED",
                risk_score=min(rs, 0.99),
                p4_reason="high_risk_approved",
                execution_error="sandbox_timeout" if r.random() < 0.2 else None,
                final_status="",
            )

        if etype == "CONFLICT":
            rs = round(0.85 + r.random() * 0.14, 4)
            return EventProfile(
                event_type="CONFLICT",
                preflight_valid=True,
                p4_verdict="ALLOW",
                execution_status="SUCCESS",
                risk_score=min(rs, 0.99),
                p4_reason="approved_despite_risk",
                final_status="",
            )

        if etype == "RECOVERY":
            return EventProfile(
                event_type="RECOVERY",
                preflight_valid=True,
                p4_verdict="ALLOW",
                execution_status="SUCCESS",
                risk_score=round(r.random() * 0.15, 4),
                p4_reason="recovery_approved",
                final_status="",
            )

        if etype == "MIGRATION":
            return EventProfile(
                event_type="MIGRATION",
                preflight_valid=True,
                p4_verdict="ALLOW" if r.random() > 0.15 else "REVIEW",
                execution_status="SUCCESS",
                risk_score=round(0.30 + r.random() * 0.30, 4),
                capabilities_checked=["SCHEMA_WRITE", "MIGRATION_EXECUTE"],
                p4_reason="migration_approved" if r.random() > 0.15 else "migration_needs_review",
                p4_rule_triggered=None if r.random() > 0.15 else "SCHEMA_CHANGE_REVIEW",
                final_status="",
            )

        if etype == "ANOMALY":
            return EventProfile(
                event_type="ANOMALY",
                preflight_valid=False,
                p4_verdict="UNKNOWN",
                execution_status="UNKNOWN",
                risk_score=round(r.random() * 0.3, 4),
                preflight_reason="unexpected_payload",
                p4_reason="preflight_failed",
                final_status="BLOCKED_BY_PREFLIGHT",
            )

        if etype == "CHAOS":
            if r.random() < 0.5:
                return EventProfile(
                    event_type="CHAOS",
                    preflight_valid=True,
                    p4_verdict="BLOCK",
                    execution_status="UNKNOWN",
                    risk_score=round(0.70 + r.random() * 0.25, 4),
                    p4_rule_triggered="CAPABILITY_ESCALATION",
                    p4_reason="capability_escalation_blocked",
                    final_status="P4_BLOCK",
                )
            else:
                rs = round(0.50 + r.random() * 0.40, 4)
                return EventProfile(
                    event_type="CHAOS",
                    preflight_valid=True,
                    p4_verdict="ALLOW",
                    execution_status="FAILED",
                    risk_score=min(rs, 0.95),
                    execution_error="chaotic_failure",
                    p4_reason="allowed_but_failed",
                    final_status="",
                )

        if etype == "RESOURCE_PRESSURE":
            verdicts = ["REVIEW", "DEFER", "BLOCK"]
            v = verdicts[r.randint(0, 2)]
            rules = ["RATE_LIMIT_EXCEEDED", "RESOURCE_EXHAUSTED", "QUOTA_EXCEEDED"]
            rule = rules[r.randint(0, 2)]
            return EventProfile(
                event_type="RESOURCE_PRESSURE",
                preflight_valid=True,
                p4_verdict=v,
                execution_status="UNKNOWN",
                risk_score=round(0.60 + r.random() * 0.25, 4),
                p4_rule_triggered=rule,
                p4_reason=f"resource_pressure_{v.lower()}",
                final_status=f"P4_{v}",
            )

        return EventProfile(event_type="NORMAL")
