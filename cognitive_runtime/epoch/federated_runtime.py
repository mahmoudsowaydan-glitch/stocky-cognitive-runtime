import random
from typing import Any, Callable, Dict, List, Optional

from ..distributed_consensus import (
    ConsensusEngine,
    ConsensusResult,
    DistributedRealityStore,
    NodeStateProposal,
)
from ..distributed_schema import (
    SchemaHandshake,
    SchemaSyncRegistry,
)
from ..schema_evolution.evolution_graph import EvolutionGraph
from ..schema_evolution.evolution_node import SchemaVersionNode
from ..telemetry.telemetry_snapshot import TelemetrySnapshot
from .benchmark_runtime import BenchmarkRuntime


FEDERATION_VERSION = "1.0.0"


class FederatedRuntime:
    """In-process federation of 2 BenchmarkRuntime nodes with shared consensus.
    
    Each cycle:
        1. Both nodes cycle independently (traces, governance, confidence)
        2. Both build NodeStateProposals from their physiological state
        3. ConsensusEngine votes and determines agreed schema version
        4. DistributedRealityStore records the shared truth
        5. Federation telemetry tracks consensus_strength, inter-node divergence
    
    Exposes node_a as primary for single-runtime interface compatibility
    with LivingEpoch.
    """

    def __init__(
        self,
        runtime_factory: Callable[[], Any],
        seed: int = 42,
        capture_interval: int = 100,
    ):
        self._node_a = runtime_factory()
        self._node_b = runtime_factory()
        self._cycle_count = 0
        self._seed = seed

        # Schema evolution graph: single version for Stage 1
        self._graph = EvolutionGraph()
        self._graph.register_node(SchemaVersionNode(
            version=FEDERATION_VERSION, parent_versions=(), is_frozen=True,
        ))

        self._consensus_engine = ConsensusEngine(
            graph=self._graph, current_version=FEDERATION_VERSION,
        )
        self._reality_store = DistributedRealityStore()
        self._schema_registry = SchemaSyncRegistry()

        self._schema_registry.register_node(SchemaHandshake(
            node_id="node_a", schema_version=FEDERATION_VERSION,
            supported_versions=[FEDERATION_VERSION],
        ))
        self._schema_registry.register_node(SchemaHandshake(
            node_id="node_b", schema_version=FEDERATION_VERSION,
            supported_versions=[FEDERATION_VERSION],
        ))

        self._consensus_history: List[ConsensusResult] = []
        self._reality_snapshots: List[Dict] = []
        self._federation_cycle_count = 0

        self._telemetry = self._node_a._telemetry

    def __setattr__(self, name: str, value: Any) -> None:
        super().__setattr__(name, value)
        if name == "_telemetry" and hasattr(self, "_node_a"):
            self._node_a._telemetry = value
            self._node_b._telemetry = value

    # ── Primary node interface (for LivingEpoch compatibility) ──

    @property
    def governance(self) -> Any:
        return self._node_a.governance

    @property
    def stability(self) -> Any:
        return self._node_a.stability

    @property
    def confidence(self) -> Any:
        return self._node_a.confidence

    @property
    def coherence(self) -> Any:
        return self._node_a.coherence

    @property
    def causal_graph(self) -> Any:
        return self._node_a.causal_graph

    @property
    def compression(self) -> Any:
        return self._node_a.compression

    @property
    def state(self) -> Any:
        return self._node_a.state

    @property
    def liveness(self) -> Any:
        return self._node_a.liveness

    @property
    def traces(self) -> List:
        return self._node_a.traces

    @property
    def cycle_count(self) -> int:
        return self._cycle_count

    @property
    def event_generator(self) -> Any:
        return self._node_a.event_generator

    @property
    def _checkpoint_manager(self) -> Any:
        return self._node_a._checkpoint_manager

    @property
    def consensus_history(self) -> List[ConsensusResult]:
        return list(self._consensus_history)

    @property
    def reality_store(self) -> DistributedRealityStore:
        return self._reality_store

    @property
    def schema_registry(self) -> SchemaSyncRegistry:
        return self._schema_registry

    # ── Core cycle ──

    def cycle(self, rng: Optional[random.Random] = None) -> Optional[TelemetrySnapshot]:
        snap_a = self._node_a.cycle(rng)
        self._node_b.cycle(rng)
        self._cycle_count += 1
        self._federation_cycle_count += 1

        # Consensus cycle
        prop_a = self._build_proposal("node_a")
        prop_b = self._build_proposal("node_b")
        result = self._consensus_engine.propose([prop_a, prop_b])
        self._consensus_history.append(result)

        # Store shared reality
        if result.agreed_version:
            reality = self._reality_store.store_reality(
                global_schema_version=result.agreed_version,
                active_nodes=result.participating_nodes,
                rejected_nodes=result.rejected_nodes,
            )
            self._reality_snapshots.append({
                "cycle": self._cycle_count,
                "strength": result.consensus_strength,
                "conflicts": len(result.conflict_reasons),
                "participants": len(result.participating_nodes),
            })

        return snap_a

    def _build_proposal(self, node_id: str) -> NodeStateProposal:
        node = self._node_a if node_id == "node_a" else self._node_b
        stab = node.stability.score_history[-1] if node.stability.score_history else 0.5
        conf = node.confidence.score_history[-1] if node.confidence.score_history else 0.5
        return NodeStateProposal(
            node_id=node_id,
            schema_version=FEDERATION_VERSION,
            causal_snapshot_hash=hash(str(node.causal_graph.nodes)),
            stability_score=stab,
            confidence_score=conf,
        )

    def stop(self) -> None:
        self._node_a.stop()
        self._node_b.stop()

    @staticmethod
    def factory(
        seed: int = 42,
        capture_interval: int = 100,
    ) -> "FederatedRuntime":
        return FederatedRuntime(
            runtime_factory=lambda: BenchmarkRuntime(
                seed=seed, capture_interval=capture_interval,
            ),
            seed=seed,
            capture_interval=capture_interval,
        )
