"""adaptive_governance_loop.py — Runs governance evolution cycle.

Flow:
  1. Collect metrics
  2. Evaluate drift pressure
  3. Propose new governance state
  4. Validate via guard
  5. Commit or reject

GOV-003: All changes deterministic
GOV-004: Derived, not learned
GOV-005: Replayable
"""

from typing import Dict, Optional

from .governance_state_model import GovernanceState
from .governance_policy_engine import GovernancePolicyEngine
from .governance_evolution_engine import GovernanceEvolutionEngine
from .governance_guard import GovernanceGuard


class AdaptiveGovernanceLoop:
    def __init__(self, initial_state: GovernanceState):
        self._state = initial_state
        self._policy_engine = GovernancePolicyEngine()
        self._evolution_engine = GovernanceEvolutionEngine()
        self._guard = GovernanceGuard()
        self._cycle_count: int = 0
        self._last_rejection_reason: Optional[str] = None

    @property
    def state(self) -> GovernanceState:
        return self._state

    @property
    def cycle_count(self) -> int:
        return self._cycle_count

    @property
    def last_rejection_reason(self) -> Optional[str]:
        return self._last_rejection_reason

    def tick(self, system_metrics: Dict[str, float]) -> GovernanceState:
        self._cycle_count += 1
        self._last_rejection_reason = None

        # Step 1-2: Evaluate
        metrics = self._policy_engine.evaluate(system_metrics)

        # Step 3: Propose
        proposed = self._evolution_engine.evolve(self._state, metrics)

        # Step 4: Validate
        if not self._guard.approve(self._state, proposed):
            self._last_rejection_reason = "guard_rejected"
            return self._state

        # Step 5: Commit
        if proposed != self._state:
            self._state = proposed

        return self._state
