"""doctrine_registry.py — Single source of truth for schema evolution.

Bootstraps the known lineage and provides current/allowed/frozen
version information to the rest of the runtime.
"""

from typing import List

from ..contracts.frozen.schema_version import FROZEN_SCHEMA_VERSION
from .evolution_graph import EvolutionGraph
from .evolution_node import SchemaVersionNode


class DoctrineRegistry:
    def __init__(self) -> None:
        self._graph = EvolutionGraph()
        self._bootstrap_lineage()

    def _bootstrap_lineage(self) -> None:
        v1_0_0 = SchemaVersionNode(
            version="1.0.0",
            parent_versions=(),
            is_frozen=True,
            breaking_changes=(),
            compatibility_hash="",
        )
        v1_1_0 = SchemaVersionNode(
            version="1.1.0",
            parent_versions=("1.0.0",),
            is_frozen=True,
            breaking_changes=(),
            compatibility_hash="",
        )
        self._graph.register_node(v1_0_0)
        self._graph.register_node(v1_1_0)

    @property
    def graph(self) -> EvolutionGraph:
        return self._graph

    @property
    def current_version(self) -> str:
        return str(FROZEN_SCHEMA_VERSION)

    @property
    def allowed_versions(self) -> List[str]:
        ancestors = self._graph.get_ancestors(self.current_version)
        ancestors.insert(0, self.current_version)
        return ancestors[:3]

    @property
    def frozen_versions(self) -> List[str]:
        return [
            v for v in self._graph.versions
            if (node := self._graph.get_node(v)) and node.is_frozen
        ]

    def is_allowed(self, version: str) -> bool:
        return version in self.allowed_versions

    def is_supported(self, version: str) -> bool:
        return self._graph.has_node(version) and self._graph.has_lineage_to_root(version)
