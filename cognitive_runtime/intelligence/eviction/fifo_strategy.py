from collections import OrderedDict
from typing import Any, Dict, Optional

from .strategy import EvictionStrategy


class FIFOEviction:
    """First-in-first-out eviction — deterministic, uses dict insertion order.

    OBS-MEM-003 compliant: uses only deterministic insertion order.
    No time-based or random inputs.
    """

    def __init__(self):
        self._insertion_order: OrderedDict[str, None] = OrderedDict()

    def select_for_eviction(self, store: Dict[str, Any]) -> Optional[str]:
        if not store:
            return None
        if not self._insertion_order:
            self._rebuild(store)
        oldest = next(iter(self._insertion_order))
        if oldest in store:
            return oldest
        self._rebuild(store)
        oldest = next(iter(self._insertion_order))
        return oldest if oldest in store else None

    def record_access(self, key: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        if key not in self._insertion_order:
            self._insertion_order[key] = None

    def _rebuild(self, store: Dict[str, Any]) -> None:
        self._insertion_order.clear()
        for k in store:
            self._insertion_order[k] = None
