"""distributed_migration_orchestrator.py — Coordinates migration across nodes.

Flow:
  For each target node:
    1. Evaluate compatibility via SchemaSyncEngine
    2. If MIGRATE → execute via MigrationEngine
    3. If REJECT → mark node as isolated

Invariants:
  DSYNC-002: All cross-node data must be validated or migrated
  DSYNC-003: No partial synchronization allowed
  DSYNC-004: Failure in migration isolates node (not cascade failure)
  DSYNC-005: Schema decisions are deterministic and graph-based only
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ..schema_evolution.evolution_graph import EvolutionGraph
from ..schema_evolution.migration_engine import MigrationEngine
from .schema_sync_engine import SchemaSyncEngine
from .schema_sync_protocol import SchemaHandshake, SchemaSyncResponse
from .schema_sync_registry import SchemaSyncRegistry


@dataclass
class SyncResult:
    node_id: str
    success: bool
    action: str  # ACCEPT | MIGRATE | REJECT | ISOLATED
    reason: str = ""
    details: str = ""


class DistributedMigrationOrchestrator:
    def __init__(self, graph: EvolutionGraph, current_version: str):
        self._graph = graph
        self._current_version = current_version
        self._engine = SchemaSyncEngine(graph, current_version)
        self._migration_engine = MigrationEngine(graph)
        self._sync_log: List[SyncResult] = []

    @property
    def sync_log(self) -> List[SyncResult]:
        return list(self._sync_log)

    def synchronize_node(self, handshake: SchemaHandshake) -> SyncResult:
        response = self._engine.evaluate_node(handshake)

        if response.status == "ACCEPT":
            result = SyncResult(
                node_id=handshake.node_id, success=True,
                action="ACCEPT", reason=response.reason,
            )
            self._sync_log.append(result)
            return result

        if response.status == "MIGRATE":
            result = SyncResult(
                node_id=handshake.node_id, success=True,
                action="MIGRATE", reason=response.reason,
                details=f"migrate {handshake.schema_version} -> {self._current_version}",
            )
            self._sync_log.append(result)
            return result

        result = SyncResult(
            node_id=handshake.node_id, success=False,
            action="ISOLATED", reason=response.reason,
        )
        self._sync_log.append(result)
        return result

    def synchronize_cluster(self, registry: SchemaSyncRegistry) -> List[SyncResult]:
        results: List[SyncResult] = []
        for node_id in registry.node_ids:
            handshake = registry.get_node_schema(node_id)
            if handshake is None:
                continue
            result = self.synchronize_node(handshake)
            results.append(result)
        return results

    def synchronize_trace_to_node(self, trace: Any,
                                  handshake: SchemaHandshake) -> Any:
        response = self._engine.evaluate_node(handshake)

        if response.status == "ACCEPT":
            return trace

        if response.status == "MIGRATE":
            return self._migration_engine.migrate_trace(
                trace, handshake.schema_version, self._current_version,
            )

        raise ValueError(
            f"Cannot synchronize trace: {response.reason} "
            f"(node={handshake.node_id}, version={handshake.schema_version})"
        )

    def synchronize_traces_to_node(self, traces: List[Any],
                                   handshake: SchemaHandshake) -> List[Any]:
        return [self.synchronize_trace_to_node(t, handshake) for t in traces]
