"""schema_sync_engine.py — Core decision engine for distributed schema compatibility.

Flow:
  Step 1 — direct backward compatibility check → ACCEPT
  Step 2 — attempt migration path → MIGRATE
  Step 3 — reject → REJECT

Invariants:
  DSYNC-001: No node assumes schema compatibility
  DSYNC-005: Schema decisions are deterministic and graph-based only
"""

from ..schema_evolution.compatibility_rules import CompatibilityRules
from ..schema_evolution.evolution_graph import EvolutionGraph
from ..schema_evolution.migration_engine import MigrationEngine
from .schema_sync_protocol import SchemaHandshake, SchemaSyncResponse


class SchemaSyncEngine:
    def __init__(self, graph: EvolutionGraph, current_version: str):
        self._graph = graph
        self._current_version = current_version
        self._migration_engine = MigrationEngine(graph)

    @property
    def current_version(self) -> str:
        return self._current_version

    def evaluate_node(self, handshake: SchemaHandshake) -> SchemaSyncResponse:
        node_ver = handshake.schema_version

        if node_ver == self._current_version:
            return SchemaSyncResponse(
                status="ACCEPT", target_version=self._current_version,
                migration_required=False, reason="exact_version_match",
            )

        if CompatibilityRules.is_backward_compatible(
            node_ver, self._current_version, self._graph
        ):
            return SchemaSyncResponse(
                status="ACCEPT", target_version=self._current_version,
                migration_required=False, reason="backward_compatible",
            )

        plan = self._migration_engine.build_path(node_ver, self._current_version)
        if plan.is_supported:
            return SchemaSyncResponse(
                status="MIGRATE", target_version=self._current_version,
                migration_required=True, reason="migration_path_available",
            )

        return SchemaSyncResponse(
            status="REJECT", target_version=None,
            migration_required=False, reason="NO_COMPATIBLE_SCHEMA_PATH",
        )

    def evaluate_version(self, from_v: str, to_v: str) -> SchemaSyncResponse:
        if from_v == to_v:
            return SchemaSyncResponse(
                status="ACCEPT", target_version=to_v,
                migration_required=False, reason="exact_version_match",
            )

        if CompatibilityRules.is_backward_compatible(from_v, to_v, self._graph):
            return SchemaSyncResponse(
                status="ACCEPT", target_version=to_v,
                migration_required=False, reason="backward_compatible",
            )

        plan = self._migration_engine.build_path(from_v, to_v)
        if plan.is_supported:
            return SchemaSyncResponse(
                status="MIGRATE", target_version=to_v,
                migration_required=True, reason="migration_path_available",
            )

        return SchemaSyncResponse(
            status="REJECT", target_version=None,
            migration_required=False, reason="NO_COMPATIBLE_SCHEMA_PATH",
        )
