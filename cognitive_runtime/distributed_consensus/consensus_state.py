"""consensus_state.py — Core dataclasses for distributed consensus negotiation.

Defines the proposal and result types that flow between nodes.
No runtime state, no HAL dependency.
"""

from dataclasses import dataclass, field
from typing import List


@dataclass(frozen=True)
class NodeStateProposal:
    node_id: str
    schema_version: str
    causal_snapshot_hash: str
    stability_score: float
    confidence_score: float


@dataclass(frozen=True)
class ConsensusResult:
    agreed_version: str
    participating_nodes: List[str] = field(default_factory=list)
    rejected_nodes: List[str] = field(default_factory=list)
    consensus_strength: float = 0.0
    conflict_reasons: List[str] = field(default_factory=list)
