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
from .observer_runtime import ObserverRuntime


ASYMMETRIC_VERSION = "1.0.0"


class AsymmetricFederatedRuntime:
    """Node A (Executor) + Node B (Observer) — asymmetric federation.
    
    Node A generates events, makes decisions, builds causal graphs.
    Node B receives A's traces, assesses independently, never executes.
    
    Measures Observer Drift: how much the observer's interpretation
    diverges from the executor's self-assessment of shared reality.
    """

    def __init__(
        self,
        runtime_factory: Callable[[], Any],
        seed: int = 42,
        capture_interval: int = 100,
    ):
        self._node_a = runtime_factory()
        self._node_b = ObserverRuntime(
            node_id="observer", capture_interval=capture_interval,
        )
        self._cycle_count = 0
        self._seed = seed

        self._graph = EvolutionGraph()
        self._graph.register_node(SchemaVersionNode(
            version=ASYMMETRIC_VERSION, parent_versions=(), is_frozen=True,
        ))

        self._consensus_engine = ConsensusEngine(
            graph=self._graph, current_version=ASYMMETRIC_VERSION,
        )
        self._reality_store = DistributedRealityStore()
        self._schema_registry = SchemaSyncRegistry()

        self._schema_registry.register_node(SchemaHandshake(
            node_id="executor", schema_version=ASYMMETRIC_VERSION,
            supported_versions=[ASYMMETRIC_VERSION],
        ))
        self._schema_registry.register_node(SchemaHandshake(
            node_id="observer", schema_version=ASYMMETRIC_VERSION,
            supported_versions=[ASYMMETRIC_VERSION],
        ))

        self._consensus_history: List[ConsensusResult] = []
        self._reality_snapshots: List[Dict] = []
        self._observer_drift_history: List[Dict] = []
        self._federation_cycle_count = 0

        self._telemetry = self._node_a._telemetry

    def __setattr__(self, name: str, value: Any) -> None:
        super().__setattr__(name, value)
        if name == "_telemetry" and hasattr(self, "_node_a"):
            self._node_a._telemetry = value
            if hasattr(self, "_node_b"):
                self._node_b._telemetry = value

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
    def observer_drift_history(self) -> List[Dict]:
        return list(self._observer_drift_history)

    @property
    def reality_store(self) -> DistributedRealityStore:
        return self._reality_store

    @property
    def schema_registry(self) -> SchemaSyncRegistry:
        return self._schema_registry

    @property
    def executor(self) -> BenchmarkRuntime:
        return self._node_a

    @property
    def observer(self) -> ObserverRuntime:
        return self._node_b

    def cycle(self, rng: Optional[random.Random] = None) -> Optional[TelemetrySnapshot]:
        r = rng or random.Random(self._seed + self._cycle_count)

        # Step 1: Executor generates events and assesses
        snap_a = self._node_a.cycle(r)

        # Step 2: Observer receives A's traces and assesses independently
        self._node_b.observe(self._node_a.traces, r)

        self._cycle_count += 1
        self._federation_cycle_count += 1

        # Step 3: Build proposals from each node's perspective
        prop_a = self._build_proposal("executor", self._node_a)
        prop_b = self._build_proposal("observer", self._node_b)

        # Step 4: Consensus — do they agree on the same reality?
        result = self._consensus_engine.propose([prop_a, prop_b])
        self._consensus_history.append(result)

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

        # Step 5: Measure Observer Drift
        a_metrics = self._extract_node_metrics(self._node_a)
        b_metrics = self._extract_node_metrics(self._node_b)
        drift = {
            "cycle": self._cycle_count,
            "governance_drift": abs(a_metrics["governance_score"] - b_metrics["governance_score"]),
            "stability_drift": abs(a_metrics["stability_score"] - b_metrics["stability_score"]),
            "confidence_drift": abs(a_metrics["confidence_score"] - b_metrics["confidence_score"]),
            "consensus_strength": result.consensus_strength,
        }
        self._observer_drift_history.append(drift)

        return snap_a

    def _build_proposal(self, node_id: str, node: Any) -> NodeStateProposal:
        stab = node.stability.score_history[-1] if node.stability.score_history else 0.5
        conf = node.confidence.score_history[-1] if node.confidence.score_history else 0.5
        return NodeStateProposal(
            node_id=node_id,
            schema_version=ASYMMETRIC_VERSION,
            causal_snapshot_hash=hash(str(getattr(node, "causal_graph", None))),
            stability_score=stab,
            confidence_score=conf,
        )

    def _extract_node_metrics(self, node: Any) -> Dict:
        gov = getattr(node, "governance", None)
        stab = getattr(node, "stability", None)
        conf = getattr(node, "confidence", None)

        gov_score = 0.0
        if gov and hasattr(gov, "score") and gov.score is not None:
            gov_score = gov.score if isinstance(gov.score, (int, float)) else 0.0
        elif gov and hasattr(gov, "score_history") and gov.score_history:
            gov_score = gov.score_history[-1]

        stab_score = 0.0
        if stab and stab.score_history:
            stab_score = stab.score_history[-1]

        conf_score = 0.0
        if conf and conf.score_history:
            conf_score = conf.score_history[-1]

        return {
            "governance_score": gov_score,
            "stability_score": stab_score,
            "confidence_score": conf_score,
        }

    def stop(self) -> None:
        self._node_a.stop()
        self._node_b.stop()

    @staticmethod
    def factory(
        seed: int = 42,
        capture_interval: int = 100,
    ) -> "AsymmetricFederatedRuntime":
        return AsymmetricFederatedRuntime(
            runtime_factory=lambda: BenchmarkRuntime(
                seed=seed, capture_interval=capture_interval,
            ),
            seed=seed,
            capture_interval=capture_interval,
        )
