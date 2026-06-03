"""governance_guard.py — Final gatekeeper between evaluation and state mutation.

Checks:
  - invariant preservation (no frozen key mutation)
  - delta bounds (change <= 10%)
  - drift constraints
  - historical consistency (Phase F replay validation stub)

GOV-001: Cannot violate frozen invariants
GOV-005: Replayable governance evolution
"""

from typing import Optional

from .governance_state_model import GovernanceState


class GovernanceGuard:
    MAX_DELTA = 0.10

    def approve(self, current: GovernanceState,
                proposed: GovernanceState) -> bool:
        if proposed is None:
            return False

        # GOV-001: frozen keys must not change
        if current.version != proposed.version:
            return False

        # Delta bounds per field
        if abs(proposed.drift_tolerance - current.drift_tolerance) > self.MAX_DELTA:
            return False
        if abs(proposed.confidence_threshold - current.confidence_threshold) > self.MAX_DELTA:
            return False
        if abs(proposed.stability_threshold - current.stability_threshold) > self.MAX_DELTA:
            return False

        # Thresholds must stay in [0, 1]
        for v in [proposed.drift_tolerance, proposed.confidence_threshold,
                  proposed.stability_threshold]:
            if v < 0.0 or v > 1.0:
                return False

        # GV invariant: stability_threshold must never exceed confidence_threshold
        # (system must not require more stability from itself than it has confidence)
        if proposed.stability_threshold > proposed.confidence_threshold:
            return False

        return True
