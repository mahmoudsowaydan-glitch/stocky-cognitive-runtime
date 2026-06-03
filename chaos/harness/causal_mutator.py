"""
causal_mutator.py — Mutates trace lists before causal graph construction.

Injects:
- Causal cycles (self-referencing event_id chains)
- Orphan nodes (broken parent references)
- Duplicate event_ids
- Invalid influence edges
"""

import copy
import random
from typing import Any, Dict, List, Optional


class CausalMutator:
    """Post-hoc mutation of trace lists before graph building."""

    def __init__(self, seed: Optional[int] = None):
        self._rng = random.Random(seed)

    def inject_cycle(self, traces: List[Any]) -> List[Any]:
        """Create a circular reference by making the last trace reference the first."""
        if len(traces) < 2:
            return traces
        mutated = copy.deepcopy(traces)
        idx = self._rng.randint(0, len(mutated) - 2)
        t = mutated[idx]
        if isinstance(t, dict):
            t["event_id"] = mutated[-1].get("event_id") if isinstance(mutated[-1], dict) else mutated[-1].event_id
        else:
            t.event_id = mutated[-1].event_id if isinstance(mutated[-1], dict) else mutated[-1].event_id
        return mutated

    def create_orphan(self, traces: List[Any]) -> List[Any]:
        """Break correlation_id chain to create an orphan trace."""
        if not traces:
            return traces
        mutated = copy.deepcopy(traces)
        idx = self._rng.randint(0, len(mutated) - 1)
        t = mutated[idx]
        if isinstance(t, dict):
            t["correlation_id"] = f"orphan_{self._rng.randint(1, 99999)}"
        else:
            t.correlation_id = f"orphan_{self._rng.randint(1, 99999)}"
        return mutated

    def duplicate_event_id(self, traces: List[Any]) -> List[Any]:
        """Make two traces share the same event_id."""
        if len(traces) < 2:
            return traces
        mutated = copy.deepcopy(traces)
        src = mutated[0]
        dst_idx = self._rng.randint(1, len(mutated) - 1)
        eid = src.get("event_id") if isinstance(src, dict) else src.event_id
        dst = mutated[dst_idx]
        if isinstance(dst, dict):
            dst["event_id"] = eid
        else:
            dst.event_id = eid
        return mutated

    def corrupt_final_status(self, traces: List[Any], rate: float = 0.3) -> List[Any]:
        """Randomly flip final_status values."""
        mutated = copy.deepcopy(traces)
        for t in mutated:
            if self._rng.random() < rate:
                val = self._rng.choice(["UNKNOWN", "CORRUPTED", None, "P4_ALLOW", "P4_BLOCK"])
                if isinstance(t, dict):
                    t["final_status"] = val
                else:
                    t.final_status = val
        return mutated

    def random_mutation(self, traces: List[Any]) -> List[Any]:
        """Apply a random causal mutation."""
        mutators = [
            self.inject_cycle,
            self.create_orphan,
            self.duplicate_event_id,
            self.corrupt_final_status,
        ]
        return self._rng.choice(mutators)(traces)
