"""schema_sync_registry.py — Tracks all nodes and their schema states.

Responsible for:
  - Registering nodes with their schema handshake
  - Updating node schema versions
  - Detecting cluster-wide incompatibilities

Invariants:
  DSYNC-001: No node assumes schema compatibility
  DSYNC-003: No partial synchronization allowed
  DSYNC-004: Failure in migration isolates node (not cascade failure)
"""

from typing import Dict, List, Optional

from .schema_sync_protocol import SchemaHandshake


class SchemaSyncRegistry:
    def __init__(self) -> None:
        self._nodes: Dict[str, SchemaHandshake] = {}

    def register_node(self, handshake: SchemaHandshake) -> None:
        self._nodes[handshake.node_id] = handshake

    def update_node_schema(self, node_id: str,
                           new_version: str,
                           supported: Optional[List[str]] = None) -> bool:
        existing = self._nodes.get(node_id)
        if existing is None:
            return False
        self._nodes[node_id] = SchemaHandshake(
            node_id=node_id,
            schema_version=new_version,
            supported_versions=supported or existing.supported_versions,
        )
        return True

    def get_node_schema(self, node_id: str) -> Optional[SchemaHandshake]:
        return self._nodes.get(node_id)

    @property
    def node_count(self) -> int:
        return len(self._nodes)

    @property
    def node_ids(self) -> List[str]:
        return list(self._nodes.keys())

    def detect_cluster_incompatibility(self, target_version: str) -> List[str]:
        incompatible: List[str] = []
        for node_id, handshake in self._nodes.items():
            if handshake.schema_version != target_version:
                if target_version not in handshake.supported_versions:
                    incompatible.append(node_id)
        return incompatible

    def get_versions_in_cluster(self) -> Dict[str, List[str]]:
        versions: Dict[str, List[str]] = {}
        for node_id, handshake in self._nodes.items():
            ver = handshake.schema_version
            versions.setdefault(ver, []).append(node_id)
        return versions
