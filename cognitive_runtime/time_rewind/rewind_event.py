"""rewind_event.py — Frozen event representation for temporal reconstruction.

Carries the minimum state needed to rebuild system history deterministically.
No runtime state, no HAL dependency.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class RewindEvent:
    timestamp: float
    trace_id: str
    node_id: str
    execution_snapshot: dict
    causal_hash: str
