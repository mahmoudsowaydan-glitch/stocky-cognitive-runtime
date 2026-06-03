from dataclasses import dataclass, field
from typing import Dict


@dataclass
class CausalWeight:
    frequency: int = 0
    last_seen_cycle: int = 0
    causal_recurrence: int = 0
    replay_participation: int = 0
    governance_relevance: float = 0.0

    def score(self, current_cycle: int) -> float:
        """FAA score = frequency × recency × causal relevance.

        recency = 1/(1 + cycles_since_seen) — recently seen = higher score
        Uses only deterministic cycle_no-based metrics.
        OBS-MEM-003 compliant — no wall-clock or randomness.
        """
        cycles_since = max(0, current_cycle - self.last_seen_cycle)
        recency = 1.0 / (1.0 + cycles_since)
        return float(self.frequency) * max(0.1, recency) * max(0.1, self._relevance_factor())

    def _relevance_factor(self) -> float:
        base = 1.0 + self.causal_recurrence + self.replay_participation + self.governance_relevance
        return min(base, 10.0)


@dataclass
class EvictionMetrics:
    weights: Dict[str, CausalWeight] = field(default_factory=dict)
