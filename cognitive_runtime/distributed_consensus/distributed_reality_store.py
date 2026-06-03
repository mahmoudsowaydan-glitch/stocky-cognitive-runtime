"""distributed_reality_store.py — Stores the agreed-upon system reality snapshot.

The reality is the single shared truth produced by consensus across all nodes.
"""

import hashlib
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass(frozen=True)
class DistributedReality:
    global_schema_version: str
    active_nodes: List[str] = field(default_factory=list)
    rejected_nodes: List[str] = field(default_factory=list)
    consensus_hash: str = ""


class DistributedRealityStore:
    def __init__(self) -> None:
        self._reality: Optional[DistributedReality] = None

    def store_reality(
        self,
        global_schema_version: str,
        active_nodes: List[str],
        rejected_nodes: List[str],
    ) -> DistributedReality:
        raw = f"{global_schema_version}|{sorted(active_nodes)}|{sorted(rejected_nodes)}"
        consensus_hash = hashlib.sha256(raw.encode("utf-8")).hexdigest()

        self._reality = DistributedReality(
            global_schema_version=global_schema_version,
            active_nodes=sorted(active_nodes),
            rejected_nodes=sorted(rejected_nodes),
            consensus_hash=consensus_hash,
        )
        return self._reality

    def get_reality(self) -> Optional[DistributedReality]:
        return self._reality

    def clear(self) -> None:
        self._reality = None

    def verify_integrity(self, reality: DistributedReality) -> bool:
        raw = f"{reality.global_schema_version}|{sorted(reality.active_nodes)}|{sorted(reality.rejected_nodes)}"
        expected_hash = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        return reality.consensus_hash == expected_hash
