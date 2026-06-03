from typing import Any, Dict, Optional

from .metrics import CausalWeight, EvictionMetrics
from .strategy import EvictionStrategy


class FAAEviction:
    """Frequency-Aware Aging eviction.

    score = frequency × recency × causal relevance
    Evicts lowest-scoring entry.

    OBS-MEM-003 compliant: uses only deterministic cycle_no-based metrics
    (frequency, last_seen_cycle, causal_recurrence, replay_participation,
     governance_relevance).
    No wall-clock, no randomness, no non-deterministic inputs.
    """

    def __init__(self, current_cycle: int = 0):
        self._metrics = EvictionMetrics()
        self._current_cycle = current_cycle

    def advance_cycle(self) -> None:
        self._current_cycle += 1

    def select_for_eviction(self, store: Dict[str, Any]) -> Optional[str]:
        if not store:
            return None
        best_key = None
        best_score = float("inf")
        for key in store:
            w = self._metrics.weights.get(key)
            if w is None:
                w = CausalWeight()
            s = w.score(self._current_cycle)
            if s < best_score:
                best_score = s
                best_key = key
        return best_key

    def record_access(self, key: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        w = self._metrics.weights.get(key)
        if w is None:
            w = CausalWeight(frequency=1, last_seen_cycle=self._current_cycle)
        else:
            w = CausalWeight(
                frequency=w.frequency + 1,
                last_seen_cycle=self._current_cycle,
                causal_recurrence=w.causal_recurrence,
                replay_participation=w.replay_participation,
                governance_relevance=w.governance_relevance,
            )
        if metadata:
            w = CausalWeight(
                frequency=w.frequency,
                last_seen_cycle=w.last_seen_cycle,
                causal_recurrence=metadata.get("causal_recurrence", w.causal_recurrence),
                replay_participation=metadata.get("replay_participation", w.replay_participation),
                governance_relevance=metadata.get("governance_relevance", w.governance_relevance),
            )
        self._metrics.weights[key] = w

    @property
    def metrics(self) -> EvictionMetrics:
        return self._metrics
