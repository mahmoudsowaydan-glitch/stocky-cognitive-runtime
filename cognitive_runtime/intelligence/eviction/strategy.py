from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Protocol


class EvictionStrategy(Protocol):
    """Deterministic eviction strategy — must be reproducible under identical replay."""

    def select_for_eviction(self, store: Dict[str, Any]) -> Optional[str]:
        """Return the key to evict, or None if no eviction needed.

        Deterministic invariant (OBS-MEM-003): must use only deterministic inputs
        (insertion order, cycle_no, causal recurrence, governance relevance).
        Must never use time.time(), random, or non-reproducible metrics.
        """
        ...

    def record_access(self, key: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        """Record an access or update for the given key.

        Called on upsert and lookup to maintain recency/frequency data.
        """
        ...
