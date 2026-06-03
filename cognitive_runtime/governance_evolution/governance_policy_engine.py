"""governance_policy_engine.py — Evaluates system behavior vs governance goals.

Inputs from:
  - Stability (Phase 6A)
  - Confidence (Phase 6B)
  - Consensus (Phase E)
  - Replay (Phase F)

No runtime state, no HAL dependency.
"""

from typing import Dict


class GovernancePolicyEngine:
    def evaluate(self, system_metrics: Dict[str, float]) -> Dict[str, float]:
        stability = system_metrics.get("stability", 1.0)
        confidence = system_metrics.get("confidence", 1.0)
        consensus_strength = system_metrics.get("consensus_strength", 1.0)
        replay_accuracy = system_metrics.get("replay_accuracy", 1.0)

        drift_pressure = max(0.0, 1.0 - min(stability, confidence))
        stability_gap = max(0.0, 0.7 - stability)
        confidence_gap = max(0.0, 0.7 - confidence)
        consensus_fragmentation = max(0.0, 1.0 - consensus_strength)

        return {
            "drift_pressure": round(drift_pressure, 4),
            "stability_gap": round(stability_gap, 4),
            "confidence_gap": round(confidence_gap, 4),
            "consensus_fragmentation": round(consensus_fragmentation, 4),
            "replay_accuracy": replay_accuracy,
            "stability": stability,
            "confidence": confidence,
            "consensus_strength": consensus_strength,
        }
