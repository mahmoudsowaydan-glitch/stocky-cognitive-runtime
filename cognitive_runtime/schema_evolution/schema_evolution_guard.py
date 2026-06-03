"""schema_evolution_guard.py — Runtime integration layer for schema evolution.

Flow:
  Step 1 — compatibility check
  Step 2 — attempt migration
  Step 3 — reject (NO_VALID_MIGRATION_PATH)
"""

import copy
from typing import Any, Dict, List, Optional

from .compatibility_rules import CompatibilityRules
from .evolution_graph import EvolutionGraph
from .migration_engine import MigrationEngine


class SchemaEvolutionGuard:
    def __init__(self, graph: EvolutionGraph):
        self._graph = graph
        self._engine = MigrationEngine(graph)

    def validate_snapshot(self, snapshot: Any,
                          current_version: str) -> Any:
        snap_version = getattr(snapshot, "schema_version", None)
        if snap_version is None:
            raise ValueError("Snapshot has no schema_version")

        if snap_version == current_version:
            return self._clone(snapshot)

        if CompatibilityRules.is_backward_compatible(
            snap_version, current_version, self._graph
        ):
            return self._clone(snapshot)

        plan = self._engine.build_path(snap_version, current_version)
        if plan.is_supported:
            result = self._clone(snapshot)
            if hasattr(result, "traces"):
                migrated = []
                for t in result.traces:
                    migrated.append(
                        self._engine.migrate_trace(t, snap_version, current_version)
                    )
                result.traces = migrated
            result.schema_version = current_version
            return result

        raise ValueError(
            f"NO_VALID_MIGRATION_PATH: {snap_version} -> {current_version}"
        )

    def migrate_snapshot(self, snapshot: Any,
                         from_v: str, to_v: str) -> Any:
        plan = self._engine.build_path(from_v, to_v)
        if not plan.is_supported:
            raise ValueError(
                f"NO_VALID_MIGRATION_PATH: {from_v} -> {to_v}"
            )
        result = self._clone(snapshot)
        if hasattr(result, "traces"):
            migrated = []
            for t in result.traces:
                migrated.append(
                    self._engine.migrate_trace(t, from_v, to_v)
                )
            result.traces = migrated
        result.schema_version = to_v
        return result

    @staticmethod
    def _clone(obj: Any) -> Any:
        return copy.deepcopy(obj)
