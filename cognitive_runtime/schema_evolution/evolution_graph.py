"""evolution_graph.py — Directed version lineage graph.

Invariants enforced:
  EVOL-001: No orphan version allowed (all versions have path to root)
  EVOL-002: All versions must have lineage path to root
  EVOL-003: Only graph-approved transitions allowed (direct parent→child)
"""

from typing import Dict, List, Optional

from .evolution_node import SchemaVersionNode


class EvolutionGraph:
    def __init__(self) -> None:
        self._nodes: Dict[str, SchemaVersionNode] = {}

    @property
    def root_version(self) -> Optional[str]:
        for v, node in self._nodes.items():
            if not node.parent_versions:
                return v
        return None

    def register_node(self, node: SchemaVersionNode) -> None:
        if node.version in self._nodes:
            raise ValueError(f"Version already registered: {node.version}")
        for pv in node.parent_versions:
            if pv not in self._nodes:
                raise ValueError(
                    f"Parent version {pv} not registered (register parents first)"
                )
        self._nodes[node.version] = node

    def get_node(self, version: str) -> Optional[SchemaVersionNode]:
        return self._nodes.get(version)

    def has_node(self, version: str) -> bool:
        return version in self._nodes

    @property
    def node_count(self) -> int:
        return len(self._nodes)

    @property
    def versions(self) -> List[str]:
        return list(self._nodes.keys())

    def is_valid_transition(self, from_version: str, to_version: str) -> bool:
        from_node = self._nodes.get(from_version)
        to_node = self._nodes.get(to_version)
        if from_node is None or to_node is None:
            return False
        return bool(to_node.parent_versions) and from_version in to_node.parent_versions

    def has_lineage_to_root(self, version: str) -> bool:
        node = self._nodes.get(version)
        if node is None:
            return False
        visited: set = set()
        current = node
        while current.parent_versions:
            if current.version in visited:
                return False
            visited.add(current.version)
            parent_ver = current.parent_versions[0]
            parent = self._nodes.get(parent_ver)
            if parent is None:
                return False
            current = parent
        return True

    def is_orphan(self, version: str) -> bool:
        if version not in self._nodes:
            return False
        return not self.has_lineage_to_root(version)

    def get_ancestors(self, version: str) -> List[str]:
        node = self._nodes.get(version)
        if node is None:
            return []
        result: List[str] = []
        visited: set = set()
        current = node
        while current.parent_versions:
            if current.version in visited:
                break
            visited.add(current.version)
            parent_ver = current.parent_versions[0]
            parent = self._nodes.get(parent_ver)
            if parent is None:
                break
            result.append(parent_ver)
            current = parent
        return result

    def detect_orphans(self) -> List[str]:
        return [v for v in self._nodes if self.is_orphan(v)]
