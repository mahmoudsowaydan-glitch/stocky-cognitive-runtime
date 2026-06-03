"""governance_evolution_engine.py — Proposes new governance state safely.

Rules:
  1. NO BREAKING EVOLUTION — frozen invariant violation → reject
  2. GRADUAL ADAPTATION ONLY — change_rate <= 10% per cycle
  3. STABILITY-AWARE — stability < 0.7 → freeze evolution
  4. CONSENSUS SAFETY GATE — fragmentation > threshold → no evolution

GOV-001: Cannot violate frozen invariants
GOV-002: No evolution under instability
GOV-003: All changes deterministic
GOV-004: No randomness, no ML
GOV-005: Replayable (all inputs provided, pure function)
"""

import copy
from typing import Dict, List, Optional

from .governance_state_model import GovernanceState


class GovernanceEvolutionEngine:
    MAX_CHANGE_RATE = 0.10
    STABILITY_FREEZE_THRESHOLD = 0.7
    FROZEN_KEYS = {"version"}

    def evolve(self, state: GovernanceState,
               metrics: Dict[str, float]) -> GovernanceState:
        # Rule 3: stability freeze
        stability = metrics.get("stability", 1.0)
        if stability < self.STABILITY_FREEZE_THRESHOLD:
            return state

        # Rule 4: consensus safety gate
        fragmentation = metrics.get("consensus_fragmentation", 0.0)
        if fragmentation > state.drift_tolerance:
            return state

        # Rule 2: gradual adaptation (only when drift exceeds tolerance)
        drift = metrics.get("drift_pressure", 0.0)
        if drift <= state.drift_tolerance:
            return state

        new_weights = self._adapt_weights(state.policy_weights, drift)
        new_thresholds = self._adapt_thresholds(state.threshold_map, drift)
        new_drift = self._clamp_change(state.drift_tolerance, drift)
        new_confidence = self._clamp_change(state.confidence_threshold, drift)
        new_stability = self._clamp_change(state.stability_threshold, drift)

        return GovernanceState(
            version=state.version,
            policy_weights=new_weights,
            threshold_map=new_thresholds,
            drift_tolerance=new_drift,
            confidence_threshold=new_confidence,
            stability_threshold=new_stability,
        )

    def _adapt_weights(self, weights: Dict[str, float],
                       drift: float) -> Dict[str, float]:
        if not weights:
            return weights
        result = dict(weights)
        for key in result:
            delta = result[key] * min(drift, self.MAX_CHANGE_RATE)
            if drift > 0.5:
                result[key] = round(min(1.0, result[key] + delta), 4)
            else:
                result[key] = round(max(0.0, result[key] - delta), 4)
        total = sum(result.values())
        if total > 0:
            result = {k: round(v / total, 4) for k, v in result.items()}
        return result

    def _adapt_thresholds(self, thresholds: Dict[str, float],
                          drift: float) -> Dict[str, float]:
        if not thresholds:
            return thresholds
        result = dict(thresholds)
        for key in result:
            result[key] = self._clamp_change(result[key], drift)
        return result

    def _clamp_change(self, value: float, drift: float) -> float:
        max_delta = value * self.MAX_CHANGE_RATE
        if drift > 0.5:
            return round(min(1.0, value + max_delta), 4)
        else:
            return round(max(0.0, value - max_delta), 4)
